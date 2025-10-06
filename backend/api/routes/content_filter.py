"""
Content filtering endpoints - PII detection, toxicity, etc.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Tuple
from functools import lru_cache
from contextlib import nullcontext
from datetime import datetime
from uuid import UUID, uuid4
from enum import Enum
import re

from api.routes.auth import get_current_user, TokenData
from api.routes.security import get_authenticated_user
from api.routes.rampart_keys import track_api_key_usage

router = APIRouter()

# Optional DB-backed defaults availability
try:
    from api.db import get_default
    _DB_OK = True
except Exception:  # pragma: no cover
    _DB_OK = False

# Optional OpenTelemetry tracing
try:
    from opentelemetry import trace as otel_trace  # type: ignore
    _OTEL = True
    _tracer = otel_trace.get_tracer(__name__)
except Exception:  # pragma: no cover
    _OTEL = False
    _tracer = None

# Optional Prometheus metrics
try:
    from prometheus_client import Counter, Histogram  # type: ignore
    _PROM = True
    METRIC_FILTER_REQUESTS = Counter(
        "content_filter_requests_total",
        "Total content filter requests",
        ["redact", "use_model_toxicity"],
    )
    METRIC_FILTER_UNSAFE = Counter(
        "content_filter_unsafe_total",
        "Total content flagged unsafe",
        [],
    )
    METRIC_FILTER_LATENCY_MS = Histogram(
        "content_filter_latency_ms",
        "Content filter processing time (ms)",
        buckets=(1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000),
    )
    METRIC_PII_COUNT = Histogram(
        "content_filter_pii_count",
        "Number of PII entities detected per request",
        buckets=(0, 1, 2, 3, 5, 8, 13),
    )
except Exception:  # pragma: no cover
    _PROM = False
    METRIC_FILTER_REQUESTS = None
    METRIC_FILTER_UNSAFE = None
    METRIC_FILTER_LATENCY_MS = None
    METRIC_PII_COUNT = None


class FilterType(str, Enum):
    """Types of content filters"""
    PII = "pii"
    TOXICITY = "toxicity"
    PROFANITY = "profanity"
    BIAS = "bias"
    SENSITIVE_TOPICS = "sensitive_topics"


class PIIType(str, Enum):
    """Types of PII"""
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    NAME = "name"
    ADDRESS = "address"


class PIIEntity(BaseModel):
    """Detected PII entity"""
    type: PIIType
    value: str
    start: int
    end: int
    confidence: float
    label: Optional[str] = None  # typed label for custom patterns or analyzer-provided type


class ToxicityScore(BaseModel):
    """Toxicity analysis scores"""
    toxicity: float
    severe_toxicity: float
    obscene: float
    threat: float
    insult: float
    identity_attack: float


class ContentFilterRequest(BaseModel):
    """Request for content filtering"""
    content: str
    filters: List[FilterType] = Field(default_factory=lambda: [FilterType.PII, FilterType.TOXICITY])
    redact: bool = False
    trace_id: Optional[UUID] = None
    # Dynamic options
    custom_pii_patterns: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional dict of name->regex to augment built-in PII detection"
    )
    custom_toxic_words: Optional[List[str]] = Field(
        default=None,
        description="Optional list of additional toxic words"
    )
    custom_severe_words: Optional[List[str]] = Field(
        default=None,
        description="Optional list of additional severe toxic words"
    )
    toxicity_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Threshold above which content is considered unsafe based on toxicity"
    )
    use_model_toxicity: bool = Field(
        default=False,
        description="If true, use Detoxify model for toxicity instead of heuristics"
    )
    use_presidio_pii: bool = Field(
        default=False,
        description="If true, use Presidio analyzer/anonymizer for PII instead of regex"
    )


class ContentFilterResponse(BaseModel):
    """Response from content filtering"""
    id: UUID
    original_content: str
    filtered_content: Optional[str] = None
    pii_detected: List[PIIEntity] = []
    toxicity_scores: Optional[ToxicityScore] = None
    is_safe: bool
    filters_applied: List[FilterType]
    analyzed_at: datetime
    processing_time_ms: float


# In-memory storage
filter_results: Dict[UUID, ContentFilterResponse] = {}


def detect_pii(content: str, custom_patterns: Optional[Dict[str, str]] = None) -> List[PIIEntity]:
    """Detect PII in content using regex patterns.
    You can augment defaults with custom named regex patterns.
    """
    entities = []
    
    # Email pattern
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    for match in re.finditer(email_pattern, content):
        entities.append(PIIEntity(
            type=PIIType.EMAIL,
            value=match.group(),
            start=match.start(),
            end=match.end(),
            confidence=0.95
        ))
    
    # Phone pattern (US format)
    phone_pattern = r'\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b'
    for match in re.finditer(phone_pattern, content):
        entities.append(PIIEntity(
            type=PIIType.PHONE,
            value=match.group(),
            start=match.start(),
            end=match.end(),
            confidence=0.90
        ))
    
    # SSN pattern
    ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'
    for match in re.finditer(ssn_pattern, content):
        entities.append(PIIEntity(
            type=PIIType.SSN,
            value=match.group(),
            start=match.start(),
            end=match.end(),
            confidence=0.98
        ))
    
    # Credit card pattern (simplified)
    cc_pattern = r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'
    for match in re.finditer(cc_pattern, content):
        entities.append(PIIEntity(
            type=PIIType.CREDIT_CARD,
            value=match.group(),
            start=match.start(),
            end=match.end(),
            confidence=0.85
        ))
    
    # IP Address pattern
    ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
    for match in re.finditer(ip_pattern, content):
        entities.append(PIIEntity(
            type=PIIType.IP_ADDRESS,
            value=match.group(),
            start=match.start(),
            end=match.end(),
            confidence=0.80
        ))

    # Custom patterns (optional). Any name provided will be returned with that label and generic NAME type.
    if custom_patterns:
        for name, pattern in custom_patterns.items():
            try:
                for match in re.finditer(pattern, content):
                    entities.append(PIIEntity(
                        type=PIIType.NAME,  # keep generic type; use label for specificity
                        value=match.group(),
                        start=match.start(),
                        end=match.end(),
                        confidence=0.75,
                        label=name
                    ))
            except re.error:
                # Skip invalid regex silently; in real systems, collect metrics/logs
                continue

    return entities


def analyze_toxicity(
    content: str,
    custom_toxic_words: Optional[List[str]] = None,
    custom_severe_words: Optional[List[str]] = None,
) -> ToxicityScore:
    """
    Analyze content for toxicity
    In production, use a model like Detoxify or Perspective API
    """
    # Simple heuristic-based scoring (replace with ML model)
    toxic_words = ["hate", "kill", "stupid", "idiot", "dumb"]
    severe_words = ["die", "murder", "attack"]

    if custom_toxic_words:
        toxic_words = list({w.lower() for w in (toxic_words + custom_toxic_words)})
    if custom_severe_words:
        severe_words = list({w.lower() for w in (severe_words + custom_severe_words)})
    
    content_lower = content.lower()
    
    toxic_count = sum(1 for word in toxic_words if word in content_lower)
    severe_count = sum(1 for word in severe_words if word in content_lower)
    
    toxicity = min(toxic_count * 0.2, 1.0)
    severe_toxicity = min(severe_count * 0.3, 1.0)
    
    return ToxicityScore(
        toxicity=toxicity,
        severe_toxicity=severe_toxicity,
        obscene=toxicity * 0.7,
        threat=severe_toxicity * 0.8,
        insult=toxicity * 0.6,
        identity_attack=toxicity * 0.4
    )


# Optional: Detoxify model-backed toxicity
@lru_cache(maxsize=1)
def _get_detoxify_model():
    try:
        from detoxify import Detoxify  # type: ignore
        # Use multilingual small model to keep load time lower
        return Detoxify('original')
    except Exception:
        return None


def analyze_toxicity_model(content: str) -> Optional[ToxicityScore]:
    model = _get_detoxify_model()
    if model is None:
        return None
    try:
        scores = model.predict(content)
        # Detoxify returns keys like: toxicity, severe_toxicity, obscene, threat, insult, identity_attack
        return ToxicityScore(
            toxicity=float(scores.get('toxicity', 0.0)),
            severe_toxicity=float(scores.get('severe_toxicity', 0.0)),
            obscene=float(scores.get('obscene', 0.0)),
            threat=float(scores.get('threat', 0.0)),
            insult=float(scores.get('insult', 0.0)),
            identity_attack=float(scores.get('identity_attack', 0.0)),
        )
    except Exception:
        # Fallback handled by caller
        return None


def redact_pii(content: str, entities: List[PIIEntity]) -> str:
    """Redact PII from content"""
    # Sort entities by start position in reverse order
    sorted_entities = sorted(entities, key=lambda e: e.start, reverse=True)
    
    redacted = content
    for entity in sorted_entities:
        token = (entity.label or entity.type.value).upper()
        redaction = f"[{token}_REDACTED]"
        redacted = redacted[:entity.start] + redaction + redacted[entity.end:]
    
    return redacted


# Presidio integration (optional)
_PRESIDIO_READY = False
try:  # Lazy import names
    from presidio_analyzer import AnalyzerEngine  # type: ignore
    from presidio_anonymizer import AnonymizerEngine  # type: ignore
    _PRESIDIO_READY = True
except Exception:
    _PRESIDIO_READY = False

_analyzer = None
_anonymizer = None


def _get_presidio_engines() -> Tuple[Optional["AnalyzerEngine"], Optional["AnonymizerEngine"]]:  # type: ignore
    global _analyzer, _anonymizer
    if not _PRESIDIO_READY:
        return None, None
    if _analyzer is None:
        try:
            _analyzer = AnalyzerEngine()
        except Exception:
            return None, None
    if _anonymizer is None:
        try:
            _anonymizer = AnonymizerEngine()
        except Exception:
            return None, None
    return _analyzer, _anonymizer


def detect_pii_presidio(content: str) -> Tuple[List[PIIEntity], Optional[str]]:
    analyzer, anonymizer = _get_presidio_engines()
    if not analyzer or not anonymizer:
        return [], None
    try:
        results = analyzer.analyze(text=content, entities=None, language="en")
        entities: List[PIIEntity] = []
        for r in results:
            label = (r.entity_type or "name").lower()
            # Map common labels; default to NAME
            mapping = {
                "email": PIIType.EMAIL,
                "phone_number": PIIType.PHONE,
                "us_ssn": PIIType.SSN,
                "credit_card": PIIType.CREDIT_CARD,
                "ip_address": PIIType.IP_ADDRESS,
                "person": PIIType.NAME,
                "name": PIIType.NAME,
                "location": PIIType.ADDRESS,
            }
            pii_type = mapping.get(label, PIIType.NAME)
            entities.append(
                PIIEntity(
                    type=pii_type,
                    value=content[r.start : r.end],
                    start=int(r.start),
                    end=int(r.end),
                    confidence=float(getattr(r, "score", 0.85) or 0.85),
                    label=r.entity_type.lower() if getattr(r, "entity_type", None) else None,
                )
            )
        # Prepare an anonymized string as well (to use if redact=True)
        operators = {"DEFAULT": {"type": "replace", "new_value": "[REDACTED]"}}
        anonymized = anonymizer.anonymize(text=content, analyzer_results=results, operators=operators)
        return entities, anonymized.text
    except Exception:
        return [], None


@router.post("/filter", response_model=ContentFilterResponse)
async def filter_content(
    request: ContentFilterRequest,
    auth_data: tuple[TokenData, Optional[UUID]] = Depends(get_authenticated_user)
):
    """Filter content for PII, toxicity, and other issues"""
    import time
    # Top-level span for filter operation (nested under FastAPI request span)
    ctx = (
        _tracer.start_as_current_span("content_filter") if _OTEL else nullcontext()
    )
    with ctx as span:  # type: ignore
        start_time = time.time()
        if _OTEL and span is not None:
            try:
                span.set_attribute("filters", ",".join(request.filters))
                span.set_attribute("redact", bool(request.redact))
                span.set_attribute("toxicity.threshold", float(request.toxicity_threshold))
                span.set_attribute("toxicity.use_model", bool(request.use_model_toxicity))
                span.set_attribute("pii.custom_patterns", int(bool(request.custom_pii_patterns)))
            except Exception:
                pass

        # Load defaults from DB (if any) and merge with request
        defaults = get_default("content_filter_defaults") if _DB_OK else None
        redact = request.redact if request.redact is not None else bool(defaults.get("redact", False)) if defaults else request.redact
        custom_pii_patterns = request.custom_pii_patterns or (defaults.get("custom_pii_patterns") if defaults else None)
        custom_toxic_words = request.custom_toxic_words or (defaults.get("custom_toxic_words") if defaults else None)
        custom_severe_words = request.custom_severe_words or (defaults.get("custom_severe_words") if defaults else None)
        toxicity_threshold = request.toxicity_threshold if request.toxicity_threshold is not None else (defaults.get("toxicity_threshold", 0.7) if defaults else 0.7)
        use_model_toxicity = request.use_model_toxicity or (defaults.get("use_model_toxicity") if defaults else False)
        use_presidio_pii = request.use_presidio_pii or (defaults.get("use_presidio_pii") if defaults else False)

        pii_entities: List[PIIEntity] = []
        toxicity_scores = None
        filtered_content = request.content

        # Apply PII
        if FilterType.PII in request.filters:
            subctx = (
                _tracer.start_as_current_span("pii_detection") if _OTEL else nullcontext()
            )
            with subctx as subspan:  # type: ignore
                if use_presidio_pii:
                    pii_entities, presidio_redacted = detect_pii_presidio(request.content)
                    if redact and presidio_redacted is not None:
                        filtered_content = presidio_redacted
                else:
                    pii_entities = detect_pii(
                        request.content, custom_patterns=custom_pii_patterns
                    )
                if _OTEL and subspan is not None:
                    try:
                        subspan.set_attribute("pii.count", len(pii_entities))
                    except Exception:
                        pass
                if redact and pii_entities and not use_presidio_pii:
                    redctx = (
                        _tracer.start_as_current_span("pii_redaction") if _OTEL else nullcontext()
                    )
                    with redctx:  # type: ignore
                        filtered_content = redact_pii(request.content, pii_entities)

        # Apply Toxicity
        if FilterType.TOXICITY in request.filters:
            toxctx = (
                _tracer.start_as_current_span("toxicity_analysis") if _OTEL else nullcontext()
            )
            with toxctx as toxspan:  # type: ignore
                if use_model_toxicity:
                    toxicity_scores = analyze_toxicity_model(request.content)
                if toxicity_scores is None:
                    toxicity_scores = analyze_toxicity(
                        request.content,
                        custom_toxic_words=custom_toxic_words,
                        custom_severe_words=custom_severe_words,
                    )
                if _OTEL and toxspan is not None and toxicity_scores is not None:
                    try:
                        toxspan.set_attribute("toxicity.score", float(toxicity_scores.toxicity))
                        toxspan.set_attribute("toxicity.severe", float(toxicity_scores.severe_toxicity))
                    except Exception:
                        pass

        # Determine if content is safe
        is_safe = True
        if pii_entities and not redact:
            is_safe = False
        if toxicity_scores and toxicity_scores.toxicity > toxicity_threshold:
            is_safe = False

        processing_time = (time.time() - start_time) * 1000
        # Metrics
        try:
            if _PROM and METRIC_FILTER_REQUESTS is not None:
                METRIC_FILTER_REQUESTS.labels(
                    redact=str(bool(request.redact)).lower(),
                    use_model_toxicity=str(bool(getattr(request, "use_model_toxicity", False))).lower(),
                ).inc()
            if _PROM and METRIC_FILTER_LATENCY_MS is not None:
                METRIC_FILTER_LATENCY_MS.observe(processing_time)
            if _PROM and METRIC_PII_COUNT is not None:
                METRIC_PII_COUNT.observe(len(pii_entities))
            if _PROM and METRIC_FILTER_UNSAFE is not None and not is_safe:
                METRIC_FILTER_UNSAFE.inc()
        except Exception:
            pass
        if _OTEL and span is not None:
            try:
                span.set_attribute("processing.ms", round(processing_time, 2))
                span.set_attribute("safe", bool(is_safe))
                span.set_attribute("pii.count", len(pii_entities))
            except Exception:
                pass

        result_id = uuid4()
        response = ContentFilterResponse(
            id=result_id,
            original_content=request.content,
            filtered_content=filtered_content if filtered_content != request.content else None,
            pii_detected=pii_entities,
            toxicity_scores=toxicity_scores,
            is_safe=is_safe,
            filters_applied=request.filters,
            analyzed_at=datetime.utcnow(),
            processing_time_ms=round(processing_time, 2)
        )

        filter_results[result_id] = response
        
        # Track API key usage if authenticated via API key
        current_user, api_key_id = auth_data
        if api_key_id:
            track_api_key_usage(api_key_id, "/filter", tokens_used=0, cost_usd=0.0)
        
        return response


@router.post("/pii/detect", response_model=List[PIIEntity])
async def detect_pii_only(
    content: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Detect PII in content"""
    return detect_pii(content)


@router.post("/pii/redact")
async def redact_pii_only(
    content: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Redact PII from content"""
    entities = detect_pii(content)
    redacted = redact_pii(content, entities)
    return {
        "original": content,
        "redacted": redacted,
        "entities_found": len(entities)
    }


@router.post("/toxicity/analyze", response_model=ToxicityScore)
async def analyze_toxicity_only(
    content: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Analyze content toxicity"""
    return analyze_toxicity(content)


@router.get("/filter/results/{result_id}", response_model=ContentFilterResponse)
async def get_filter_result(
    result_id: UUID,
    current_user: TokenData = Depends(get_current_user)
):
    """Get a specific filter result"""
    if result_id not in filter_results:
        raise HTTPException(status_code=404, detail="Filter result not found")
    return filter_results[result_id]


@router.get("/filter/stats")
async def get_filter_stats(current_user: TokenData = Depends(get_current_user)):
    """Get content filtering statistics including both JWT traces and API key usage"""
    from api.db import get_conn
    from sqlalchemy import text
    
    # JWT trace data (in-memory)
    jwt_filtered = len(filter_results)
    
    total_pii = sum(len(r.pii_detected) for r in filter_results.values())
    unsafe_count = sum(1 for r in filter_results.values() if not r.is_safe)
    
    pii_type_counts = {}
    for result in filter_results.values():
        for entity in result.pii_detected:
            pii_type = entity.type.value
            pii_type_counts[pii_type] = pii_type_counts.get(pii_type, 0) + 1
    
    avg_toxicity = 0.0
    toxicity_results = [r for r in filter_results.values() if r.toxicity_scores]
    if toxicity_results:
        avg_toxicity = sum(r.toxicity_scores.toxicity for r in toxicity_results) / len(toxicity_results)
    
    # API key usage data (from database)
    api_key_filtered = 0
    api_key_breakdown = []
    
    try:
        with get_conn() as conn:
            # Get total API key filter requests
            result = conn.execute(
                text("""
                    SELECT 
                        COALESCE(SUM(u.requests_count), 0) as total_requests
                    FROM rampart_api_keys k
                    LEFT JOIN rampart_api_key_usage u ON k.id = u.api_key_id
                    WHERE k.user_id = :user_id 
                    AND k.is_active = true
                    AND u.endpoint = '/filter'
                """),
                {"user_id": current_user.user_id}
            ).fetchone()
            
            api_key_filtered = result[0] if result else 0
            
            # Get breakdown by API key
            breakdown_result = conn.execute(
                text("""
                    SELECT 
                        k.key_name,
                        k.key_preview,
                        COALESCE(SUM(u.requests_count), 0) as requests
                    FROM rampart_api_keys k
                    LEFT JOIN rampart_api_key_usage u ON k.id = u.api_key_id AND u.endpoint = '/filter'
                    WHERE k.user_id = :user_id AND k.is_active = true
                    GROUP BY k.id, k.key_name, k.key_preview
                    HAVING COALESCE(SUM(u.requests_count), 0) > 0
                    ORDER BY requests DESC
                """),
                {"user_id": current_user.user_id}
            ).fetchall()
            
            api_key_breakdown = [
                {"key_name": row[0], "key_preview": row[1], "requests": row[2]}
                for row in breakdown_result
            ]
    except Exception as e:
        print(f"Error fetching API key filter stats: {e}")
        pass
    
    total_filtered = jwt_filtered + api_key_filtered
    
    return {
        "total_filtered": total_filtered,
        "jwt_filtered": jwt_filtered,
        "api_key_filtered": api_key_filtered,
        "api_key_breakdown": api_key_breakdown,
        "total_pii_detected": total_pii,
        "unsafe_content_count": unsafe_count,
        "pii_type_distribution": pii_type_counts,
        "average_toxicity_score": round(avg_toxicity, 3)
    }
