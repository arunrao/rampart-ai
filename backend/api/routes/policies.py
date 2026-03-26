"""
Policy management endpoints - compliance templates, rule evaluation, template packs
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, date
from uuid import UUID, uuid4
from enum import Enum
import json
import re
import logging

from api.routes.auth import get_current_user, TokenData

router = APIRouter()
logger = logging.getLogger(__name__)

# Pre-declare every conditionally-imported name as `Any = None`.
# Type is `Any` so call sites like `get_default(...)` and `text("SELECT ...")`
# stay valid to the checker.  At runtime, all call sites are guarded by
# `if not _DB_AVAILABLE: raise HTTPException(503, ...)` so these stubs are
# never actually invoked.
get_default: Any = None
set_default: Any = None
get_conn: Any = None
insert_audit_log: Any = None
DATABASE_URL: str = ""
text: Any = None
detect_pii_gliner: Any = None

# Optional DB availability
try:
    from api.db import get_default, set_default, get_conn, insert_audit_log, DATABASE_URL
    from sqlalchemy import text
    _DB_AVAILABLE = True
except Exception:  # pragma: no cover
    _DB_AVAILABLE = False

# Optional GLiNER PII detector for rule evaluation
try:
    from models.pii_detector_gliner import detect_pii_gliner
    _GLINER_AVAILABLE = True
except Exception:
    _GLINER_AVAILABLE = False

# Optional prompt injection detector for rule evaluation
try:
    from api.routes.security import get_detector as _get_pi_detector
    _PI_AVAILABLE = True
except Exception:
    _PI_AVAILABLE = False


# ---------------------------------------------------------------------------
# Org-wide content filter defaults
# ---------------------------------------------------------------------------

class ContentFilterDefaults(BaseModel):
    """Org-wide defaults for content filtering"""
    redact: Optional[bool] = None
    custom_pii_patterns: Optional[Dict[str, str]] = None
    toxicity_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    use_presidio_pii: Optional[bool] = None
    enable_violence: Optional[bool] = None
    enable_sexual: Optional[bool] = None
    enable_self_harm: Optional[bool] = None
    enable_hate: Optional[bool] = None


@router.get("/policies/defaults/content-filter", response_model=ContentFilterDefaults)
async def get_content_filter_defaults(current_user: TokenData = Depends(get_current_user)):
    """Get default settings for content filter enforcement"""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Defaults store unavailable")
    data = get_default("content_filter_defaults") or {}
    return ContentFilterDefaults(**data)


@router.put("/policies/defaults/content-filter", response_model=ContentFilterDefaults)
async def set_content_filter_defaults(
    payload: ContentFilterDefaults,
    current_user: TokenData = Depends(get_current_user)
):
    """Set default settings for content filter enforcement"""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Defaults store unavailable")
    current = get_default("content_filter_defaults") or {}
    updated = {**current, **{k: v for k, v in payload.dict().items() if v is not None}}
    set_default("content_filter_defaults", updated)
    _emit_audit_log(current_user, "/policies/defaults/content-filter", "PUT", "config_change")
    return ContentFilterDefaults(**updated)


# ---------------------------------------------------------------------------
# Policy models
# ---------------------------------------------------------------------------

class PolicyType(str, Enum):
    CONTENT_FILTER = "content_filter"
    RATE_LIMIT = "rate_limit"
    ACCESS_CONTROL = "access_control"
    DATA_GOVERNANCE = "data_governance"
    COMPLIANCE = "compliance"


class PolicyAction(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    REDACT = "redact"
    FLAG = "flag"
    ALERT = "alert"


class PolicyRule(BaseModel):
    condition: str = Field(..., description="Rule condition expression")
    action: PolicyAction
    priority: int = Field(default=0, description="Higher priority rules evaluated first")
    metadata: Optional[Dict[str, Any]] = None


class PolicyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    policy_type: PolicyType
    rules: List[PolicyRule]
    enabled: bool = True
    tags: Optional[List[str]] = None


class Policy(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    description: Optional[str]
    policy_type: PolicyType
    rules: List[PolicyRule]
    enabled: bool
    tags: Optional[List[str]]
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    version: int = 1


class PolicyEvaluationRequest(BaseModel):
    content: str
    context: Dict[str, Any] = Field(default_factory=dict)
    policy_ids: Optional[List[UUID]] = None


class PolicyViolation(BaseModel):
    policy_id: UUID
    policy_name: str
    rule_index: int
    action: PolicyAction
    reason: str


class PolicyEvaluationResponse(BaseModel):
    allowed: bool
    violations: List[PolicyViolation]
    actions_taken: List[str]
    modified_content: Optional[str] = None


# ---------------------------------------------------------------------------
# Compliance templates
# ---------------------------------------------------------------------------

class ComplianceTemplate(str, Enum):
    GDPR = "gdpr"
    HIPAA = "hipaa"
    SOC2 = "soc2"
    PCI_DSS = "pci_dss"
    CCPA = "ccpa"


_TEMPLATE_DESCRIPTIONS = {
    ComplianceTemplate.GDPR: "EU General Data Protection Regulation — requires PII redaction and data retention controls",
    ComplianceTemplate.HIPAA: "Healthcare data protection — requires PHI redaction and access controls",
    ComplianceTemplate.SOC2: "Service Organization Controls Type II — requires audit logging and encryption enforcement",
    ComplianceTemplate.PCI_DSS: "Payment Card Industry Data Security Standard — blocks unredacted card data and enforces audit logging",
    ComplianceTemplate.CCPA: "California Consumer Privacy Act — enforces PII redaction and consumer rights (opt-out, deletion)",
}


def create_compliance_template(template: ComplianceTemplate) -> Optional[PolicyCreate]:
    """Return a PolicyCreate populated from the given compliance template."""
    templates: Dict[ComplianceTemplate, PolicyCreate] = {
        ComplianceTemplate.GDPR: PolicyCreate(
            name="GDPR Compliance",
            description="European data protection regulations — PII redaction + retention controls",
            policy_type=PolicyType.DATA_GOVERNANCE,
            rules=[
                PolicyRule(condition="contains_pii", action=PolicyAction.REDACT, priority=10),
                PolicyRule(condition="data_retention_exceeded", action=PolicyAction.BLOCK, priority=9),
            ],
            tags=["gdpr", "compliance", "eu"],
        ),
        ComplianceTemplate.HIPAA: PolicyCreate(
            name="HIPAA Compliance",
            description="Healthcare data protection — PHI redaction + unauthorized access blocking",
            policy_type=PolicyType.DATA_GOVERNANCE,
            rules=[
                PolicyRule(condition="contains_phi", action=PolicyAction.REDACT, priority=10),
                PolicyRule(condition="unauthorized_access", action=PolicyAction.BLOCK, priority=10),
            ],
            tags=["hipaa", "compliance", "healthcare"],
        ),
        ComplianceTemplate.SOC2: PolicyCreate(
            name="SOC 2 Type II Compliance",
            description="Service organization controls — audit logging enforcement + encryption checks",
            policy_type=PolicyType.COMPLIANCE,
            rules=[
                PolicyRule(condition="audit_log_required", action=PolicyAction.FLAG, priority=5),
                PolicyRule(condition="encryption_required", action=PolicyAction.BLOCK, priority=8),
            ],
            tags=["soc2", "compliance", "security"],
        ),
        ComplianceTemplate.PCI_DSS: PolicyCreate(
            name="PCI-DSS Compliance",
            description="Payment card data security — blocks unredacted card numbers, CVVs, and PANs",
            policy_type=PolicyType.COMPLIANCE,
            rules=[
                PolicyRule(condition="contains_cvv", action=PolicyAction.BLOCK, priority=10),
                PolicyRule(condition="unencrypted_pan", action=PolicyAction.BLOCK, priority=9),
                PolicyRule(condition="contains_card_data", action=PolicyAction.REDACT, priority=8),
                PolicyRule(condition="audit_log_required", action=PolicyAction.FLAG, priority=5),
            ],
            tags=["pci-dss", "compliance", "payments", "financial"],
        ),
        ComplianceTemplate.CCPA: PolicyCreate(
            name="CCPA Compliance",
            description="California Consumer Privacy Act — PII redaction, opt-out and deletion request handling",
            policy_type=PolicyType.DATA_GOVERNANCE,
            rules=[
                PolicyRule(condition="contains_pii", action=PolicyAction.REDACT, priority=10),
                PolicyRule(condition="data_sale_opt_out", action=PolicyAction.FLAG, priority=8),
                PolicyRule(condition="data_retention_exceeded", action=PolicyAction.BLOCK, priority=7),
                PolicyRule(condition="right_to_delete", action=PolicyAction.FLAG, priority=6),
            ],
            tags=["ccpa", "compliance", "california", "privacy"],
        ),
    }
    return templates.get(template)


# ---------------------------------------------------------------------------
# Template packs
# ---------------------------------------------------------------------------

class TemplatePack(str, Enum):
    DEFAULT = "default"
    CUSTOMER_SUPPORT = "customer_support"
    CODE_ASSISTANT = "code_assistant"
    RAG = "rag"
    HEALTHCARE = "healthcare"
    FINANCIAL = "financial"
    CREATIVE_WRITING = "creative_writing"


@dataclass
class TemplatePackConfig:
    """Runtime configuration applied when a Rampart API key has this pack attached."""
    name: str
    description: str
    use_cases: List[str]
    # ContentFilterRequest fields
    filters: List[str]            # FilterType values
    redact: bool
    toxicity_threshold: float
    use_presidio_pii: bool
    custom_pii_patterns: Optional[Dict[str, str]] = None
    # Linked compliance template (informational; creating it is opt-in)
    compliance_template: Optional[str] = None  # ComplianceTemplate value


_TEMPLATE_PACKS: Dict[TemplatePack, TemplatePackConfig] = {
    TemplatePack.DEFAULT: TemplatePackConfig(
        name="Default",
        description="Balanced protection suitable for general-purpose LLM applications.",
        use_cases=["General API use", "Internal tools", "Prototypes"],
        filters=["pii", "toxicity", "prompt_injection"],
        redact=False,
        toxicity_threshold=0.7,
        use_presidio_pii=False,
    ),
    TemplatePack.CUSTOMER_SUPPORT: TemplatePackConfig(
        name="Customer Support",
        description=(
            "Strict protection for customer-facing chatbots. Redacts PII automatically, "
            "applies tighter toxicity thresholds, and blocks prompt injection attempts."
        ),
        use_cases=["Help desk bots", "Live chat assistants", "Ticket classification"],
        filters=["pii", "toxicity", "prompt_injection"],
        redact=True,
        toxicity_threshold=0.6,
        use_presidio_pii=False,
    ),
    TemplatePack.CODE_ASSISTANT: TemplatePackConfig(
        name="Code Assistant",
        description=(
            "Designed for IDE copilots and code-generation tools. Prioritises prompt injection "
            "and credential scanning; relaxes toxicity checks that trigger on code snippets."
        ),
        use_cases=["IDE plugins", "Code review bots", "CI/CD security gates"],
        filters=["pii", "prompt_injection"],
        redact=False,
        toxicity_threshold=0.85,
        use_presidio_pii=False,
        custom_pii_patterns={
            "api_key_pattern": r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*['\"]?[A-Za-z0-9\-_]{16,}",
            "private_key_header": r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----",
            "aws_access_key": r"AKIA[0-9A-Z]{16}",
            "generic_secret": r"(?i)(password|passwd|secret)\s*[:=]\s*['\"]?[^\s'\"]{8,}",
        },
    ),
    TemplatePack.RAG: TemplatePackConfig(
        name="RAG / Document QA",
        description=(
            "Tailored for retrieval-augmented generation pipelines. Applies stricter injection "
            "thresholds to catch indirect injection via retrieved documents."
        ),
        use_cases=["Document Q&A", "Knowledge base search", "Enterprise RAG pipelines"],
        filters=["pii", "prompt_injection"],
        redact=True,
        toxicity_threshold=0.75,
        use_presidio_pii=False,
    ),
    TemplatePack.HEALTHCARE: TemplatePackConfig(
        name="Healthcare",
        description=(
            "HIPAA-aligned pack for medical applications. Redacts PII/PHI using Presidio "
            "and blocks prompt injection. Links to the HIPAA compliance template."
        ),
        use_cases=["Clinical decision support", "Medical record summarisation", "Patient-facing chatbots"],
        filters=["pii", "prompt_injection"],
        redact=True,
        toxicity_threshold=0.75,
        use_presidio_pii=True,
        compliance_template="hipaa",
    ),
    TemplatePack.FINANCIAL: TemplatePackConfig(
        name="Financial Services",
        description=(
            "PCI-DSS-aligned pack for fintech and banking. Redacts PII and card data, "
            "applies stricter toxicity and injection controls."
        ),
        use_cases=["Banking assistants", "Payment processing", "Fraud detection pipelines"],
        filters=["pii", "toxicity", "prompt_injection"],
        redact=True,
        toxicity_threshold=0.6,
        use_presidio_pii=False,
        compliance_template="pci_dss",
        custom_pii_patterns={
            "iban": r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b",
            "swift_bic": r"\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?\b",
            "routing_number": r"\b0[0-9]{8}\b",
        },
    ),
    TemplatePack.CREATIVE_WRITING: TemplatePackConfig(
        name="Creative Writing",
        description=(
            "Relaxed content thresholds for creative content generation. Maintains injection "
            "detection but allows a wider range of fictional content."
        ),
        use_cases=["Story generation", "Game dialogue", "Marketing copy"],
        filters=["toxicity", "prompt_injection"],
        redact=False,
        toxicity_threshold=0.85,
        use_presidio_pii=False,
    ),
}


def get_template_pack_config(pack: TemplatePack) -> TemplatePackConfig:
    return _TEMPLATE_PACKS[pack]


# ---------------------------------------------------------------------------
# DB-backed policy CRUD helpers
# ---------------------------------------------------------------------------

def _policy_from_row(row) -> Policy:
    is_sqlite = "sqlite" in DATABASE_URL.lower() if _DB_AVAILABLE else True
    rules_raw = row[5]
    tags_raw = row[7]
    if is_sqlite:
        rules = [PolicyRule(**r) for r in json.loads(rules_raw or "[]")]
        tags = json.loads(tags_raw or "[]")
    else:
        rules = [PolicyRule(**r) for r in (rules_raw or [])]
        tags = list(tags_raw or [])
    return Policy(
        id=row[0],
        user_id=row[1],
        name=row[2],
        description=row[3],
        policy_type=PolicyType(row[4]),
        rules=rules,
        enabled=bool(row[6]),
        tags=tags,
        created_at=row[8],
        updated_at=row[9],
        created_by=row[10],
        version=row[11],
    )


def _db_create_policy(policy_create: PolicyCreate, user_id: str) -> Policy:
    is_sqlite = "sqlite" in DATABASE_URL.lower()
    rules_json = json.dumps([r.dict() for r in policy_create.rules])
    tags_json = json.dumps(policy_create.tags or [])
    now = datetime.utcnow()
    with get_conn() as conn:
        if is_sqlite:
            result = conn.execute(
                text(
                    """
                    INSERT INTO policies
                      (user_id, name, description, policy_type, rules, enabled, tags,
                       created_at, updated_at, version)
                    VALUES
                      (:user_id, :name, :description, :policy_type, :rules, :enabled, :tags,
                       :created_at, :updated_at, 1)
                    """
                ),
                {
                    "user_id": user_id,
                    "name": policy_create.name,
                    "description": policy_create.description,
                    "policy_type": policy_create.policy_type.value,
                    "rules": rules_json,
                    "enabled": 1 if policy_create.enabled else 0,
                    "tags": tags_json,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            conn.commit()
            row = conn.execute(
                text("SELECT * FROM policies WHERE rowid = last_insert_rowid()")
            ).fetchone()
        else:
            row = conn.execute(
                text(
                    """
                    INSERT INTO policies
                      (user_id, name, description, policy_type, rules, enabled, tags,
                       created_at, updated_at, version)
                    VALUES
                      (:user_id, :name, :description, :policy_type, :rules::jsonb, :enabled, :tags,
                       :created_at, :updated_at, 1)
                    RETURNING *
                    """
                ),
                {
                    "user_id": user_id,
                    "name": policy_create.name,
                    "description": policy_create.description,
                    "policy_type": policy_create.policy_type.value,
                    "rules": rules_json,
                    "enabled": policy_create.enabled,
                    "tags": policy_create.tags or [],
                    "created_at": now,
                    "updated_at": now,
                },
            ).fetchone()
            conn.commit()
    return _policy_from_row(row)


def _db_get_policy(policy_id: str, user_id: str) -> Optional[Policy]:
    with get_conn() as conn:
        row = conn.execute(
            text("SELECT * FROM policies WHERE id = :id AND user_id = :user_id"),
            {"id": policy_id, "user_id": user_id},
        ).fetchone()
    if not row:
        return None
    return _policy_from_row(row)


def _db_list_policies(
    user_id: str,
    policy_type: Optional[str] = None,
    enabled: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Policy]:
    filters = ["user_id = :user_id"]
    params: Dict[str, Any] = {"user_id": user_id}
    if policy_type:
        filters.append("policy_type = :policy_type")
        params["policy_type"] = policy_type
    if enabled is not None:
        filters.append("enabled = :enabled")
        params["enabled"] = enabled
    where = " AND ".join(filters)
    params["limit"] = limit
    params["offset"] = offset
    with get_conn() as conn:
        rows = conn.execute(
            text(f"SELECT * FROM policies WHERE {where} ORDER BY created_at DESC LIMIT :limit OFFSET :offset"),
            params,
        ).fetchall()
    return [_policy_from_row(r) for r in rows]


def _db_update_policy(policy_id: str, user_id: str, update: PolicyCreate) -> Optional[Policy]:
    is_sqlite = "sqlite" in DATABASE_URL.lower()
    rules_json = json.dumps([r.dict() for r in update.rules])
    tags_json = json.dumps(update.tags or [])
    now = datetime.utcnow()
    with get_conn() as conn:
        if is_sqlite:
            affected = conn.execute(
                text(
                    """
                    UPDATE policies SET
                      name = :name, description = :description, policy_type = :policy_type,
                      rules = :rules, enabled = :enabled, tags = :tags,
                      updated_at = :updated_at, version = version + 1
                    WHERE id = :id AND user_id = :user_id
                    """
                ),
                {
                    "name": update.name,
                    "description": update.description,
                    "policy_type": update.policy_type.value,
                    "rules": rules_json,
                    "enabled": 1 if update.enabled else 0,
                    "tags": tags_json,
                    "updated_at": now,
                    "id": policy_id,
                    "user_id": user_id,
                },
            ).rowcount
        else:
            affected = conn.execute(
                text(
                    """
                    UPDATE policies SET
                      name = :name, description = :description, policy_type = :policy_type,
                      rules = :rules::jsonb, enabled = :enabled, tags = :tags,
                      updated_at = :updated_at, version = version + 1
                    WHERE id = :id AND user_id = :user_id
                    """
                ),
                {
                    "name": update.name,
                    "description": update.description,
                    "policy_type": update.policy_type.value,
                    "rules": rules_json,
                    "enabled": update.enabled,
                    "tags": update.tags or [],
                    "updated_at": now,
                    "id": policy_id,
                    "user_id": user_id,
                },
            ).rowcount
        conn.commit()
    if not affected:
        return None
    return _db_get_policy(policy_id, user_id)


def _db_delete_policy(policy_id: str, user_id: str) -> bool:
    with get_conn() as conn:
        affected = conn.execute(
            text("DELETE FROM policies WHERE id = :id AND user_id = :user_id"),
            {"id": policy_id, "user_id": user_id},
        ).rowcount
        conn.commit()
    return bool(affected)


def _db_toggle_policy(policy_id: str, user_id: str) -> Optional[bool]:
    is_sqlite = "sqlite" in DATABASE_URL.lower()
    with get_conn() as conn:
        if is_sqlite:
            affected = conn.execute(
                text(
                    """
                    UPDATE policies
                    SET enabled = CASE WHEN enabled = 1 THEN 0 ELSE 1 END,
                        updated_at = :now
                    WHERE id = :id AND user_id = :user_id
                    """
                ),
                {"now": datetime.utcnow(), "id": policy_id, "user_id": user_id},
            ).rowcount
        else:
            affected = conn.execute(
                text(
                    """
                    UPDATE policies
                    SET enabled = NOT enabled, updated_at = :now
                    WHERE id = :id AND user_id = :user_id
                    """
                ),
                {"now": datetime.utcnow(), "id": policy_id, "user_id": user_id},
            ).rowcount
        conn.commit()
    if not affected:
        return None
    policy = _db_get_policy(policy_id, user_id)
    return policy.enabled if policy else None


# ---------------------------------------------------------------------------
# Rule condition evaluator
# ---------------------------------------------------------------------------

# Credit card number pattern (basic 13-19 digit groups)
_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
# CVV pattern (3 or 4 digit standalone, often near "cvv", "cvc", "security code")
_CVV_RE = re.compile(r"(?i)(?:cvv|cvc|csc|security\s+code)[:\s]+\d{3,4}")
# PAN pattern (common formats: XXXX-XXXX-XXXX-XXXX)
_PAN_RE = re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b")
# Unmasked SSN
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# PHI keywords
_PHI_KEYWORDS = [
    "patient", "diagnosis", "medical record", "prescription", "treatment",
    "dob", "date of birth", "health insurance", "medicare", "medicaid",
    "icd-", "procedure code", "clinical note", "discharge summary",
]
# PII keywords (fallback when GLiNER unavailable)
_PII_KEYWORDS = [
    "ssn", "social security", "credit card", "passport", "driver license",
    "bank account", "routing number",
]
# Data sale / opt-out keywords (CCPA)
_OPT_OUT_KEYWORDS = [
    "do not sell", "opt out", "opt-out", "withdraw consent",
    "stop sharing", "do not share my data", "privacy rights",
]
# Right-to-delete keywords (CCPA / GDPR)
_DELETE_KEYWORDS = [
    "right to delete", "delete my data", "erase my data", "forget me",
    "right to be forgotten", "data deletion request", "remove my information",
    "right to erasure",
]
# Profanity list (representative; not exhaustive)
_PROFANITY = {
    "fuck", "shit", "asshole", "bastard", "bitch", "cunt", "dick",
    "piss", "prick", "twat", "wanker", "bullshit",
}


def _evaluate_condition(condition: str, content: str, context: Dict[str, Any]) -> bool:
    """Return True if the given rule condition is triggered for content+context."""
    text_lower = content.lower()

    if condition == "contains_pii":
        if _GLINER_AVAILABLE:
            try:
                entities = detect_pii_gliner(content)
                return len(entities) > 0
            except Exception:
                pass
        return (
            bool(_SSN_RE.search(content))
            or bool(_CARD_RE.search(content))
            or any(kw in text_lower for kw in _PII_KEYWORDS)
        )

    if condition == "contains_phi":
        if _GLINER_AVAILABLE:
            try:
                entities = detect_pii_gliner(content)
                phi_types = {"date_of_birth", "age", "medical", "diagnosis", "health", "patient"}
                if any(getattr(e, "type", "").lower() in phi_types for e in entities):
                    return True
            except Exception:
                pass
        return any(kw in text_lower for kw in _PHI_KEYWORDS)

    if condition == "contains_card_data":
        return bool(_CARD_RE.search(content)) or bool(_PAN_RE.search(content))

    if condition == "contains_cvv":
        return bool(_CVV_RE.search(content))

    if condition == "unencrypted_pan":
        # Flag PANs that are not masked (e.g., not "****1234")
        for m in _PAN_RE.finditer(content):
            digits = re.sub(r"\D", "", m.group())
            # Masked PANs have at most 4 exposed digits in typical display formats
            if digits.count("*") == 0 and len(digits) >= 13:
                return True
        return False

    if condition == "audit_log_required":
        # Always True when this rule is active — triggers FLAG so it appears in audit
        return True

    if condition == "encryption_required":
        # Flag if content contains what looks like cleartext credentials/secrets
        secret_re = re.compile(
            r"(?i)(password|passwd|secret|api[_-]?key|access[_-]?token)\s*[:=]\s*['\"]?\S{6,}"
        )
        return bool(secret_re.search(content))

    if condition == "data_retention_exceeded":
        return bool(context.get("data_retention_exceeded", False))

    if condition == "unauthorized_access":
        return bool(context.get("unauthorized_access", False))

    if condition == "data_sale_opt_out":
        return any(kw in text_lower for kw in _OPT_OUT_KEYWORDS)

    if condition == "right_to_delete":
        return any(kw in text_lower for kw in _DELETE_KEYWORDS)

    if condition == "profanity":
        words = set(re.findall(r"[a-z]+", text_lower))
        return bool(words & _PROFANITY)

    # Unknown condition — do not trip
    return False


# ---------------------------------------------------------------------------
# Internal audit log helper
# ---------------------------------------------------------------------------

def _emit_audit_log(
    user: Optional[TokenData],
    endpoint: str,
    method: str,
    event_type: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    if not _DB_AVAILABLE:
        return
    try:
        from api.config import get_settings as _get_settings
        if not _get_settings().audit_log_enabled:
            return
    except Exception:
        pass
    try:
        insert_audit_log(
            endpoint=endpoint,
            http_method=method,
            ip_address="internal",
            event_type=event_type,
            user_id=str(user.user_id) if user else None,
            metadata=metadata,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Policy CRUD endpoints
# ---------------------------------------------------------------------------

@router.post("/policies", response_model=Policy, status_code=201)
async def create_policy(
    policy: PolicyCreate,
    current_user: TokenData = Depends(get_current_user),
):
    """Create a new policy (persisted to DB)."""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database unavailable")
    result = _db_create_policy(policy, str(current_user.user_id))
    _emit_audit_log(current_user, "/policies", "POST", "config_change", {"policy_name": policy.name})
    return result


@router.get("/policies", response_model=List[Policy])
async def list_policies(
    current_user: TokenData = Depends(get_current_user),
    policy_type: Optional[PolicyType] = None,
    enabled: Optional[bool] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List all policies for the current user."""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return _db_list_policies(
        str(current_user.user_id),
        policy_type=policy_type.value if policy_type else None,
        enabled=enabled,
        limit=limit,
        offset=offset,
    )


# NOTE: /policies/templates and /policies/evaluate are static paths that MUST
# be declared before /policies/{policy_id} so FastAPI does not try to coerce
# the literal segment into a UUID and return 422.

@router.get("/policies/templates")
async def list_templates(current_user: TokenData = Depends(get_current_user)):
    """List available compliance templates with descriptions."""
    return {
        "templates": [
            {
                "id": t.value,
                "name": t.value.upper().replace("_", " "),
                "description": _TEMPLATE_DESCRIPTIONS.get(t, f"{t.value.upper()} compliance template"),
            }
            for t in ComplianceTemplate
        ]
    }


@router.get("/policies/{policy_id}", response_model=Policy)
async def get_policy(
    policy_id: UUID,
    current_user: TokenData = Depends(get_current_user),
):
    """Get a specific policy (only if owned by the current user)."""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database unavailable")
    policy = _db_get_policy(str(policy_id), str(current_user.user_id))
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@router.put("/policies/{policy_id}", response_model=Policy)
async def update_policy(
    policy_id: UUID,
    policy_update: PolicyCreate,
    current_user: TokenData = Depends(get_current_user),
):
    """Update an existing policy."""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database unavailable")
    updated = _db_update_policy(str(policy_id), str(current_user.user_id), policy_update)
    if not updated:
        raise HTTPException(status_code=404, detail="Policy not found")
    _emit_audit_log(current_user, f"/policies/{policy_id}", "PUT", "config_change")
    return updated


@router.delete("/policies/{policy_id}")
async def delete_policy(
    policy_id: UUID,
    current_user: TokenData = Depends(get_current_user),
):
    """Delete a policy."""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database unavailable")
    deleted = _db_delete_policy(str(policy_id), str(current_user.user_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Policy not found")
    _emit_audit_log(current_user, f"/policies/{policy_id}", "DELETE", "config_change")
    return {"message": "Policy deleted", "policy_id": policy_id}


@router.patch("/policies/{policy_id}/toggle")
async def toggle_policy(
    policy_id: UUID,
    current_user: TokenData = Depends(get_current_user),
):
    """Enable or disable a policy."""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database unavailable")
    new_state = _db_toggle_policy(str(policy_id), str(current_user.user_id))
    if new_state is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    return {"message": "Policy toggled", "policy_id": policy_id, "enabled": new_state}


# ---------------------------------------------------------------------------
# Policy evaluation
# ---------------------------------------------------------------------------

@router.post("/policies/evaluate", response_model=PolicyEvaluationResponse)
async def evaluate_policies(
    request: PolicyEvaluationRequest,
    current_user: TokenData = Depends(get_current_user),
):
    """Evaluate content against the caller's enabled policies."""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database unavailable")

    if request.policy_ids:
        policies_to_eval = [
            p for pid in request.policy_ids
            if (p := _db_get_policy(str(pid), str(current_user.user_id))) and p.enabled
        ]
    else:
        policies_to_eval = _db_list_policies(str(current_user.user_id), enabled=True, limit=200)

    violations: List[PolicyViolation] = []
    actions_taken: List[str] = []
    modified_content: Optional[str] = request.content

    for policy in policies_to_eval:
        sorted_rules = sorted(policy.rules, key=lambda r: r.priority, reverse=True)
        for idx, rule in enumerate(sorted_rules):
            if _evaluate_condition(rule.condition, request.content, request.context):
                violation = PolicyViolation(
                    policy_id=policy.id,
                    policy_name=policy.name,
                    rule_index=idx,
                    action=rule.action,
                    reason=f"Rule condition '{rule.condition}' triggered",
                )
                violations.append(violation)
                actions_taken.append(f"{policy.name}: {rule.action.value}")
                if rule.action == PolicyAction.REDACT:
                    modified_content = "[REDACTED]"
                elif rule.action == PolicyAction.BLOCK:
                    modified_content = None

    allowed = not any(v.action == PolicyAction.BLOCK for v in violations)
    return PolicyEvaluationResponse(
        allowed=allowed,
        violations=violations,
        actions_taken=actions_taken,
        modified_content=modified_content if modified_content != request.content else None,
    )


# ---------------------------------------------------------------------------
# Compliance template endpoints
# ---------------------------------------------------------------------------

@router.post("/policies/templates/{template}", response_model=Policy, status_code=201)
async def create_from_template(
    template: ComplianceTemplate,
    current_user: TokenData = Depends(get_current_user),
):
    """Instantiate a compliance template as a new policy."""
    policy_template = create_compliance_template(template)
    if not policy_template:
        raise HTTPException(status_code=404, detail="Template not found")
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database unavailable")
    result = _db_create_policy(policy_template, str(current_user.user_id))
    _emit_audit_log(
        current_user, f"/policies/templates/{template.value}", "POST", "config_change",
        {"template": template.value}
    )
    return result


# ---------------------------------------------------------------------------
# Template pack endpoints
# ---------------------------------------------------------------------------

@router.get("/template-packs")
async def list_template_packs(current_user: TokenData = Depends(get_current_user)):
    """List all available use-case template packs."""
    return {
        "template_packs": [
            {
                "id": pack.value,
                "name": cfg.name,
                "description": cfg.description,
                "use_cases": cfg.use_cases,
                "filters": cfg.filters,
                "redact": cfg.redact,
                "toxicity_threshold": cfg.toxicity_threshold,
                "compliance_template": cfg.compliance_template,
            }
            for pack, cfg in _TEMPLATE_PACKS.items()
        ]
    }


@router.get("/template-packs/{pack}")
async def get_template_pack(
    pack: TemplatePack,
    current_user: TokenData = Depends(get_current_user),
):
    """Get full configuration for a specific template pack."""
    cfg = _TEMPLATE_PACKS.get(pack)
    if not cfg:
        raise HTTPException(status_code=404, detail="Template pack not found")
    return {
        "id": pack.value,
        "name": cfg.name,
        "description": cfg.description,
        "use_cases": cfg.use_cases,
        "filters": cfg.filters,
        "redact": cfg.redact,
        "toxicity_threshold": cfg.toxicity_threshold,
        "use_presidio_pii": cfg.use_presidio_pii,
        "custom_pii_patterns": cfg.custom_pii_patterns,
        "compliance_template": cfg.compliance_template,
    }


# ---------------------------------------------------------------------------
# Audit log endpoint (SOC2 Type II)
# ---------------------------------------------------------------------------

class AuditLogEntry(BaseModel):
    id: str
    timestamp: datetime
    user_id: Optional[str]
    api_key_preview: Optional[str]
    endpoint: str
    http_method: str
    ip_address: str
    status_code: Optional[int]
    processing_time_ms: Optional[float]
    event_type: str
    metadata: Dict[str, Any] = {}


@router.get("/audit-logs", response_model=List[AuditLogEntry])
async def get_audit_logs(
    current_user: TokenData = Depends(get_current_user),
    event_type: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    """
    Retrieve audit logs for SOC2 Type II compliance evidence.
    Returns logs scoped to the current user's activity.
    """
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database unavailable")

    is_sqlite = "sqlite" in DATABASE_URL.lower()
    filters = ["user_id = :user_id"]
    params: Dict[str, Any] = {"user_id": str(current_user.user_id), "limit": limit, "offset": offset}

    if event_type:
        filters.append("event_type = :event_type")
        params["event_type"] = event_type
    if start_date:
        filters.append("timestamp >= :start_date")
        params["start_date"] = datetime.combine(start_date, datetime.min.time())
    if end_date:
        filters.append("timestamp <= :end_date")
        params["end_date"] = datetime.combine(end_date, datetime.max.time())

    where = " AND ".join(filters)

    with get_conn() as conn:
        rows = conn.execute(
            text(
                f"SELECT id, timestamp, user_id, api_key_preview, endpoint, http_method, "
                f"ip_address, status_code, processing_time_ms, event_type, metadata "
                f"FROM audit_logs WHERE {where} "
                f"ORDER BY timestamp DESC LIMIT :limit OFFSET :offset"
            ),
            params,
        ).fetchall()

    entries = []
    for row in rows:
        meta_raw = row[10]
        if isinstance(meta_raw, str):
            try:
                meta = json.loads(meta_raw)
            except Exception:
                meta = {}
        else:
            meta = dict(meta_raw) if meta_raw else {}
        entries.append(
            AuditLogEntry(
                id=str(row[0]),
                timestamp=row[1],
                user_id=row[2],
                api_key_preview=row[3],
                endpoint=row[4],
                http_method=row[5],
                ip_address=row[6],
                status_code=row[7],
                processing_time_ms=row[8],
                event_type=row[9],
                metadata=meta,
            )
        )
    return entries
