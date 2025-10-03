from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4
from enum import Enum

from api.routes.auth import get_current_user, TokenData

router = APIRouter()

# Optional DB-backed defaults
try:
    from api.db import get_default, set_default
    _DB_DEFAULTS = True
except Exception:  # pragma: no cover
    _DB_DEFAULTS = False


class ContentFilterDefaults(BaseModel):
    """Org-wide defaults for content filtering"""
    redact: Optional[bool] = None
    custom_pii_patterns: Optional[Dict[str, str]] = None
    custom_toxic_words: Optional[List[str]] = None
    custom_severe_words: Optional[List[str]] = None
    toxicity_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    use_model_toxicity: Optional[bool] = None
    use_presidio_pii: Optional[bool] = None
    # Future category toggles (placeholders for upcoming classifiers)
    enable_violence: Optional[bool] = None
    enable_sexual: Optional[bool] = None
    enable_self_harm: Optional[bool] = None
    enable_hate: Optional[bool] = None


@router.get("/policies/defaults/content-filter", response_model=ContentFilterDefaults)
async def get_content_filter_defaults(current_user: TokenData = Depends(get_current_user)):
    """Get default settings for content filter enforcement"""
    if not _DB_DEFAULTS:
        raise HTTPException(status_code=503, detail="Defaults store unavailable")
    data = get_default("content_filter_defaults") or {}
    return ContentFilterDefaults(**data)


@router.put("/policies/defaults/content-filter", response_model=ContentFilterDefaults)
async def set_content_filter_defaults(
    payload: ContentFilterDefaults,
    current_user: TokenData = Depends(get_current_user)
):
    """Set default settings for content filter enforcement"""
    if not _DB_DEFAULTS:
        raise HTTPException(status_code=503, detail="Defaults store unavailable")
    # persist only provided fields (partial update semantics)
    current = get_default("content_filter_defaults") or {}
    updated = {**current, **{k: v for k, v in payload.dict().items() if v is not None}}
    set_default("content_filter_defaults", updated)
    return ContentFilterDefaults(**updated)
"""
Policy management endpoints
"""


class PolicyType(str, Enum):
    """Types of policies"""
    CONTENT_FILTER = "content_filter"
    RATE_LIMIT = "rate_limit"
    ACCESS_CONTROL = "access_control"
    DATA_GOVERNANCE = "data_governance"
    COMPLIANCE = "compliance"


class PolicyAction(str, Enum):
    """Actions to take when policy is violated"""
    ALLOW = "allow"
    BLOCK = "block"
    REDACT = "redact"
    FLAG = "flag"
    ALERT = "alert"


class PolicyRule(BaseModel):
    """Individual policy rule"""
    condition: str = Field(..., description="Rule condition expression")
    action: PolicyAction
    priority: int = Field(default=0, description="Higher priority rules evaluated first")
    metadata: Optional[Dict[str, Any]] = None


class PolicyCreate(BaseModel):
    """Create a new policy"""
    name: str
    description: Optional[str] = None
    policy_type: PolicyType
    rules: List[PolicyRule]
    enabled: bool = True
    tags: Optional[List[str]] = None


class Policy(BaseModel):
    """Policy model"""
    id: UUID
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
    """Request to evaluate policies"""
    content: str
    context: Dict[str, Any] = Field(default_factory=dict)
    policy_ids: Optional[List[UUID]] = None


class PolicyViolation(BaseModel):
    """Policy violation details"""
    policy_id: UUID
    policy_name: str
    rule_index: int
    action: PolicyAction
    reason: str


class PolicyEvaluationResponse(BaseModel):
    """Response from policy evaluation"""
    allowed: bool
    violations: List[PolicyViolation]
    actions_taken: List[str]
    modified_content: Optional[str] = None


class ComplianceTemplate(str, Enum):
    """Pre-built compliance templates"""
    GDPR = "gdpr"
    HIPAA = "hipaa"
    SOC2 = "soc2"
    PCI_DSS = "pci_dss"
    CCPA = "ccpa"


# In-memory storage
policies_db: Dict[UUID, Policy] = {}


def create_compliance_template(template: ComplianceTemplate) -> PolicyCreate:
    """Create a policy from a compliance template"""
    templates = {
        ComplianceTemplate.GDPR: PolicyCreate(
            name="GDPR Compliance",
            description="European data protection regulations",
            policy_type=PolicyType.DATA_GOVERNANCE,
            rules=[
                PolicyRule(
                    condition="contains_pii",
                    action=PolicyAction.REDACT,
                    priority=10
                ),
                PolicyRule(
                    condition="data_retention_exceeded",
                    action=PolicyAction.BLOCK,
                    priority=9
                )
            ],
            tags=["gdpr", "compliance", "eu"]
        ),
        ComplianceTemplate.HIPAA: PolicyCreate(
            name="HIPAA Compliance",
            description="Healthcare data protection",
            policy_type=PolicyType.DATA_GOVERNANCE,
            rules=[
                PolicyRule(
                    condition="contains_phi",
                    action=PolicyAction.REDACT,
                    priority=10
                ),
                PolicyRule(
                    condition="unauthorized_access",
                    action=PolicyAction.BLOCK,
                    priority=10
                )
            ],
            tags=["hipaa", "compliance", "healthcare"]
        ),
        ComplianceTemplate.SOC2: PolicyCreate(
            name="SOC 2 Compliance",
            description="Service organization controls",
            policy_type=PolicyType.COMPLIANCE,
            rules=[
                PolicyRule(
                    condition="audit_log_required",
                    action=PolicyAction.FLAG,
                    priority=5
                ),
                PolicyRule(
                    condition="encryption_required",
                    action=PolicyAction.BLOCK,
                    priority=8
                )
            ],
            tags=["soc2", "compliance", "security"]
        )
    }
    return templates.get(template)


@router.post("/policies", response_model=Policy, status_code=201)
async def create_policy(
    policy: PolicyCreate,
    current_user: TokenData = Depends(get_current_user)
):
    """Create a new policy"""
    policy_id = uuid4()
    new_policy = Policy(
        id=policy_id,
        name=policy.name,
        description=policy.description,
        policy_type=policy.policy_type,
        rules=policy.rules,
        enabled=policy.enabled,
        tags=policy.tags,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    policies_db[policy_id] = new_policy
    return new_policy


@router.get("/policies", response_model=List[Policy])
async def list_policies(
    current_user: TokenData = Depends(get_current_user),
    policy_type: Optional[PolicyType] = None,
    enabled: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0
):
    """List all policies with optional filtering"""
    filtered_policies = list(policies_db.values())
    
    if policy_type:
        filtered_policies = [p for p in filtered_policies if p.policy_type == policy_type]
    if enabled is not None:
        filtered_policies = [p for p in filtered_policies if p.enabled == enabled]
    
    filtered_policies.sort(key=lambda x: x.created_at, reverse=True)
    return filtered_policies[offset:offset + limit]


@router.get("/policies/{policy_id}", response_model=Policy)
async def get_policy(
    policy_id: UUID,
    current_user: TokenData = Depends(get_current_user)
):
    """Get a specific policy"""
    if policy_id not in policies_db:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policies_db[policy_id]


@router.put("/policies/{policy_id}", response_model=Policy)
async def update_policy(
    policy_id: UUID,
    policy_update: PolicyCreate,
    current_user: TokenData = Depends(get_current_user)
):
    """Update an existing policy"""
    if policy_id not in policies_db:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    existing_policy = policies_db[policy_id]
    
    updated_policy = Policy(
        id=policy_id,
        name=policy_update.name,
        description=policy_update.description,
        policy_type=policy_update.policy_type,
        rules=policy_update.rules,
        enabled=policy_update.enabled,
        tags=policy_update.tags,
        created_at=existing_policy.created_at,
        updated_at=datetime.utcnow(),
        created_by=existing_policy.created_by,
        version=existing_policy.version + 1
    )
    
    policies_db[policy_id] = updated_policy
    return updated_policy


@router.delete("/policies/{policy_id}")
async def delete_policy(
    policy_id: UUID,
    current_user: TokenData = Depends(get_current_user)
):
    """Delete a policy"""
    if policy_id not in policies_db:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    del policies_db[policy_id]
    return {"message": "Policy deleted", "policy_id": policy_id}


@router.patch("/policies/{policy_id}/toggle")
async def toggle_policy(
    policy_id: UUID,
    current_user: TokenData = Depends(get_current_user)
):
    """Enable or disable a policy"""
    if policy_id not in policies_db:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    policy = policies_db[policy_id]
    policy.enabled = not policy.enabled
    policy.updated_at = datetime.utcnow()
    
    return {
        "message": "Policy toggled",
        "policy_id": policy_id,
        "enabled": policy.enabled
    }


@router.post("/policies/evaluate", response_model=PolicyEvaluationResponse)
async def evaluate_policies(
    request: PolicyEvaluationRequest,
    current_user: TokenData = Depends(get_current_user)
):
    """Evaluate content against policies"""
    violations = []
    actions_taken = []
    modified_content = request.content
    
    # Get policies to evaluate
    if request.policy_ids:
        policies_to_eval = [
            policies_db[pid] for pid in request.policy_ids 
            if pid in policies_db and policies_db[pid].enabled
        ]
    else:
        policies_to_eval = [p for p in policies_db.values() if p.enabled]
    
    # Sort by rule priority
    for policy in policies_to_eval:
        sorted_rules = sorted(policy.rules, key=lambda r: r.priority, reverse=True)
        
        for idx, rule in enumerate(sorted_rules):
            # Simple rule evaluation (replace with proper rule engine)
            violated = False
            
            # Example rule evaluations
            if rule.condition == "contains_pii" and any(
                keyword in request.content.lower() 
                for keyword in ["ssn", "social security", "credit card"]
            ):
                violated = True
            elif rule.condition == "contains_phi" and any(
                keyword in request.content.lower()
                for keyword in ["patient", "diagnosis", "medical record"]
            ):
                violated = True
            elif rule.condition == "profanity" and any(
                word in request.content.lower()
                for word in ["badword1", "badword2"]  # Replace with actual list
            ):
                violated = True
            
            if violated:
                violation = PolicyViolation(
                    policy_id=policy.id,
                    policy_name=policy.name,
                    rule_index=idx,
                    action=rule.action,
                    reason=f"Rule condition '{rule.condition}' triggered"
                )
                violations.append(violation)
                actions_taken.append(f"{policy.name}: {rule.action.value}")
                
                # Apply action
                if rule.action == PolicyAction.REDACT:
                    modified_content = "[REDACTED]"
                elif rule.action == PolicyAction.BLOCK:
                    modified_content = None
    
    allowed = not any(v.action == PolicyAction.BLOCK for v in violations)
    
    return PolicyEvaluationResponse(
        allowed=allowed,
        violations=violations,
        actions_taken=actions_taken,
        modified_content=modified_content if modified_content != request.content else None
    )


@router.post("/policies/templates/{template}", response_model=Policy, status_code=201)
async def create_from_template(
    template: ComplianceTemplate,
    current_user: TokenData = Depends(get_current_user)
):
    """Create a policy from a compliance template"""
    policy_template = create_compliance_template(template)
    if not policy_template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return await create_policy(policy_template)


@router.get("/policies/templates")
async def list_templates(current_user: TokenData = Depends(get_current_user)):
    """List available compliance templates"""
    return {
        "templates": [
            {
                "id": template.value,
                "name": template.value.upper(),
                "description": f"{template.value.upper()} compliance template"
            }
            for template in ComplianceTemplate
        ]
    }
