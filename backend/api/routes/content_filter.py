"""
Content filtering endpoints - PII detection, toxicity, etc.
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Tuple
from functools import lru_cache
from contextlib import nullcontext
from datetime import datetime
from uuid import UUID, uuid4
from enum import Enum
import re
import os
import logging
import asyncio

from api.config import get_settings
from api.routes.auth import get_current_user, TokenData
from api.routes.security import get_authenticated_user
from api.routes.rampart_keys import track_api_key_usage, get_api_key_template_pack

router = APIRouter()
logger = logging.getLogger(__name__)

# Import GLiNER detector
try:
    from models.pii_detector_gliner import detect_pii_gliner, redact_pii_gliner, PIIEntity as GLiNERPIIEntity
    GLINER_AVAILABLE = True
except ImportError:
    GLINER_AVAILABLE = False
    GLiNERPIIEntity = None

# Import prompt injection detector
try:
    from api.routes.security import get_detector
    PROMPT_INJECTION_AVAILABLE = True
    logger.info("✓ Prompt injection detector imported successfully")
except ImportError as e:
    PROMPT_INJECTION_AVAILABLE = False
    get_detector = None
    logger.warning(f"⚠️ Prompt injection detector not available: {e}")

# Configuration
PII_DETECTION_ENGINE = os.getenv("PII_DETECTION_ENGINE", "hybrid")  # hybrid, gliner, regex, presidio
PII_MODEL_TYPE = os.getenv("PII_MODEL_TYPE", "balanced")  # edge, balanced, accurate
PII_CONFIDENCE_THRESHOLD = float(os.getenv("PII_CONFIDENCE_THRESHOLD", "0.7"))

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
        ["redact"],
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
    PROMPT_INJECTION = "prompt_injection"
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
    """Toxicity analysis scores from the ML model."""
    toxicity: float   # P(toxic) from citizenlab/distilbert, range [0.0, 1.0]
    is_toxic: bool    # True when toxicity > threshold
    label: str        # "toxic" | "not_toxic"


class PromptInjectionResult(BaseModel):
    """Prompt injection detection result"""
    is_injection: bool = Field(..., description="Whether prompt injection was detected")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence score (0.0-1.0)")
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Overall risk score (0.0-1.0)")
    recommendation: str = Field(..., description="Recommended action: BLOCK, FLAG, MONITOR, or ALLOW")
    patterns_matched: List[str] = Field(default_factory=list, description="List of attack patterns detected (e.g., 'instruction_override', 'role_manipulation')")


class ContentFilterRequest(BaseModel):
    """Request for content filtering"""
    content: str
    filters: List[FilterType] = Field(default_factory=lambda: [FilterType.PII, FilterType.TOXICITY, FilterType.PROMPT_INJECTION])
    redact: Optional[bool] = None
    trace_id: Optional[UUID] = None
    # Dynamic options
    custom_pii_patterns: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional dict of name->regex to augment built-in PII detection"
    )
    toxicity_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Threshold above which content is considered toxic (applied to ML model score)"
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
    prompt_injection: Optional[PromptInjectionResult] = None
    is_safe: bool
    filters_applied: List[FilterType]
    analyzed_at: datetime
    processing_time_ms: float


# In-memory storage
filter_results: Dict[UUID, ContentFilterResponse] = {}


def detect_pii_regex(content: str, custom_patterns: Optional[Dict[str, str]] = None) -> List[PIIEntity]:
    """
    Detect PII in content using regex patterns (legacy/fallback method).
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


def _convert_gliner_to_pii_entity(gliner_entity) -> PIIEntity:
    """Convert GLiNER PIIEntity to our PIIEntity format"""
    # Map GLiNER type to PIIType enum
    type_mapping = {
        "email": PIIType.EMAIL,
        "phone": PIIType.PHONE,
        "ssn": PIIType.SSN,
        "credit_card": PIIType.CREDIT_CARD,
        "ip_address": PIIType.IP_ADDRESS,
        "name": PIIType.NAME,
        "address": PIIType.ADDRESS,
    }
    
    pii_type = type_mapping.get(gliner_entity.type, PIIType.NAME)
    
    return PIIEntity(
        type=pii_type,
        value=gliner_entity.value,
        start=gliner_entity.start,
        end=gliner_entity.end,
        confidence=gliner_entity.confidence,
        label=gliner_entity.label
    )


def detect_pii(content: str, custom_patterns: Optional[Dict[str, str]] = None) -> List[PIIEntity]:
    """
    Detect PII in content using the configured detection engine.
    
    Detection engines:
    - hybrid: GLiNER for unstructured, regex for structured (DEFAULT)
    - gliner: GLiNER ML model only
    - regex: Regex patterns only (fastest)
    - presidio: Microsoft Presidio (if available)
    
    Args:
        content: Text to analyze
        custom_patterns: Additional regex patterns (used in regex/hybrid modes)
    
    Returns:
        List of detected PII entities
    """
    engine = PII_DETECTION_ENGINE.lower()
    
    # GLiNER engine
    if engine == "gliner":
        if GLINER_AVAILABLE:
            try:
                gliner_entities = detect_pii_gliner(
                    content,
                    model_type=PII_MODEL_TYPE,
                    threshold=PII_CONFIDENCE_THRESHOLD
                )
                return [_convert_gliner_to_pii_entity(e) for e in gliner_entities]
            except Exception as e:
                logger.error(f"GLiNER detection failed: {e}, falling back to regex")
                return detect_pii_regex(content, custom_patterns)
        else:
            logger.warning("GLiNER not available, falling back to regex")
            return detect_pii_regex(content, custom_patterns)
    
    # Hybrid engine (RECOMMENDED)
    elif engine == "hybrid":
        entities = []
        
        # Use GLiNER for semantic/unstructured PII (names, addresses, etc.)
        if GLINER_AVAILABLE:
            try:
                gliner_entities = detect_pii_gliner(
                    content,
                    model_type=PII_MODEL_TYPE,
                    custom_labels=["person name", "full name", "address", "organization"],
                    threshold=PII_CONFIDENCE_THRESHOLD
                )
                entities.extend([_convert_gliner_to_pii_entity(e) for e in gliner_entities])
            except Exception as e:
                logger.error(f"GLiNER detection failed in hybrid mode: {e}")
        
        # Use regex for structured PII (SSN, credit cards, emails, phones)
        # These are faster and just as accurate with regex
        regex_entities = detect_pii_regex(content, custom_patterns)
        
        # Merge and deduplicate (prefer higher confidence)
        entities.extend(regex_entities)
        entities = _deduplicate_pii_entities(entities)
        
        return entities
    
    # Presidio engine
    elif engine == "presidio":
        presidio_entities, _ = detect_pii_presidio(content)
        if presidio_entities:
            return presidio_entities
        else:
            # Fallback to regex if Presidio unavailable
            logger.warning("Presidio not available, falling back to regex")
            return detect_pii_regex(content, custom_patterns)
    
    # Regex engine (default/fallback)
    else:
        return detect_pii_regex(content, custom_patterns)


def _deduplicate_pii_entities(entities: List[PIIEntity]) -> List[PIIEntity]:
    """
    Deduplicate PII entities that overlap (prefer higher confidence).
    
    Args:
        entities: List of PII entities (possibly overlapping)
    
    Returns:
        Deduplicated list
    """
    if not entities:
        return []
    
    # Sort by start position, then by confidence (descending)
    sorted_entities = sorted(entities, key=lambda e: (e.start, -e.confidence))
    
    result = []
    for entity in sorted_entities:
        # Check if this entity overlaps with any existing entity
        overlaps = False
        for existing in result:
            # Check for overlap
            if not (entity.end <= existing.start or entity.start >= existing.end):
                overlaps = True
                # If this entity has higher confidence, replace existing
                if entity.confidence > existing.confidence:
                    result.remove(existing)
                    result.append(entity)
                break
        
        if not overlaps:
            result.append(entity)
    
    # Sort by start position for final output
    return sorted(result, key=lambda e: e.start)


# Import ML toxicity detector
try:
    from models.toxicity_detector import detect_toxicity as _detect_toxicity_ml
    TOXICITY_AVAILABLE = True
except ImportError:
    _detect_toxicity_ml = None  # type: ignore
    TOXICITY_AVAILABLE = False


def analyze_toxicity(content: str, threshold: float = 0.7) -> ToxicityScore:
    """
    Run ML-based toxicity analysis.

    Uses unitary/toxic-bert (BERT-base, ~420 MB, multi-label Jigsaw fine-tune).
    Falls back to score=0.0 / label="not_toxic" when the model is not available.
    """
    if TOXICITY_AVAILABLE and _detect_toxicity_ml is not None:
        result = _detect_toxicity_ml(content)
        if result is not None:
            return ToxicityScore(
                toxicity=result["score"],
                is_toxic=result["score"] > threshold,
                label=result["label"],
            )
    # Graceful degradation: model unavailable
    return ToxicityScore(toxicity=0.0, is_toxic=False, label="not_toxic")


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


async def _execute_filter_core(
    request: ContentFilterRequest,
    span: Any,
    *,
    redact: bool,
    custom_pii_patterns: Optional[Dict[str, str]],
    toxicity_threshold: float,
    use_presidio_pii: bool,
    persist_result: bool = True,
    record_prometheus: bool = True,
) -> ContentFilterResponse:
    """Shared ML pipeline for /filter and public /filter/demo."""
    import time

    start_time = time.time()

    if _OTEL and span is not None:
        try:
            span.set_attribute("filters", ",".join(request.filters))
            span.set_attribute("redact", bool(redact))
            span.set_attribute("toxicity.threshold", float(toxicity_threshold))
            span.set_attribute("pii.custom_patterns", int(bool(custom_pii_patterns)))
        except Exception:
            pass

    pii_entities: List[PIIEntity] = []
    toxicity_scores = None
    prompt_injection_result = None
    filtered_content = request.content

    settings = get_settings()
    parallel_ml = settings.content_filter_parallel_ml

    async def run_traced_pii() -> Tuple[str, List[PIIEntity], Optional[str]]:
        subctx = (
            _tracer.start_as_current_span("pii_detection") if _OTEL else nullcontext()
        )
        with subctx as subspan:  # type: ignore

            def _pii_work() -> Tuple[str, List[PIIEntity], Optional[str]]:
                if use_presidio_pii:
                    ent, red = detect_pii_presidio(request.content)
                    return ("presidio", ent, red)
                ent = detect_pii(
                    request.content, custom_patterns=custom_pii_patterns
                )
                return ("standard", ent, None)

            kind, entities, presidio_redacted = await asyncio.to_thread(_pii_work)
            if _OTEL and subspan is not None:
                try:
                    subspan.set_attribute("pii.count", len(entities))
                except Exception:
                    pass
            return kind, entities, presidio_redacted

    async def run_traced_toxicity():
        toxctx = (
            _tracer.start_as_current_span("toxicity_analysis") if _OTEL else nullcontext()
        )
        with toxctx as toxspan:  # type: ignore

            def _tox_work():
                return analyze_toxicity(request.content, threshold=toxicity_threshold)

            scores = await asyncio.to_thread(_tox_work)
            if _OTEL and toxspan is not None and scores is not None:
                try:
                    toxspan.set_attribute("toxicity.score", float(scores.toxicity))
                    toxspan.set_attribute("toxicity.is_toxic", bool(scores.is_toxic))
                except Exception:
                    pass
            return scores

    async def run_traced_pi():
        pictx = (
            _tracer.start_as_current_span("prompt_injection_detection") if _OTEL else nullcontext()
        )
        with pictx as pispan:  # type: ignore

            def _pi_work():
                if not PROMPT_INJECTION_AVAILABLE or get_detector is None:
                    return ("unavailable", None)
                try:
                    detector = get_detector()
                    if detector is None:
                        logger.error("Detector is None after get_detector() call")
                        raise ValueError("Detector not initialized")
                    logger.debug(
                        f"Calling detector.detect() with content length: {len(request.content)}"
                    )
                    dr = detector.detect(
                        request.content,
                        fast_mode=settings.prompt_injection_fast_mode,
                    )
                    logger.debug(f"Detection result: {dr}")
                    return ("ok", dr)
                except Exception as e:
                    logger.error(f"Prompt injection detection failed: {e}", exc_info=True)
                    return ("error", e)

            status, payload = await asyncio.to_thread(_pi_work)
            if status == "ok" and payload is not None and _OTEL and pispan is not None:
                try:
                    pispan.set_attribute("injection.detected", bool(payload["is_injection"]))
                    pispan.set_attribute("injection.confidence", float(payload["confidence"]))
                except Exception:
                    pass
            return status, payload

    coroutines = []
    labels: List[str] = []

    if FilterType.PII in request.filters:
        labels.append("pii")
        coroutines.append(run_traced_pii())
    if FilterType.TOXICITY in request.filters:
        labels.append("tox")
        coroutines.append(run_traced_toxicity())
    if FilterType.PROMPT_INJECTION in request.filters:
        labels.append("pi")
        coroutines.append(run_traced_pi())

    results: List[Any] = []
    if coroutines:
        if parallel_ml and len(coroutines) > 1:
            results = await asyncio.gather(*coroutines)
        else:
            for c in coroutines:
                results.append(await c)

    for label, result in zip(labels, results):
        if label == "pii":
            kind, pii_entities, presidio_redacted = result
            if kind == "presidio" and redact and presidio_redacted is not None:
                filtered_content = presidio_redacted
            elif redact and pii_entities and kind != "presidio":
                redctx = (
                    _tracer.start_as_current_span("pii_redaction") if _OTEL else nullcontext()
                )
                with redctx:  # type: ignore
                    filtered_content = redact_pii(request.content, pii_entities)
        elif label == "tox":
            toxicity_scores = result
        elif label == "pi":
            status, payload = result
            if status == "ok" and isinstance(payload, dict):
                detection_result = payload
                prompt_injection_result = PromptInjectionResult(
                    is_injection=detection_result["is_injection"],
                    confidence=detection_result["confidence"],
                    risk_score=detection_result.get(
                        "risk_score", detection_result["confidence"]
                    ),
                    recommendation=detection_result["recommendation"],
                    patterns_matched=[
                        p["pattern"]
                        for p in detection_result.get("regex_results", {}).get(
                            "patterns_matched", []
                        )
                    ]
                    if "regex_results" in detection_result
                    else [],
                )
                logger.info(
                    f"Prompt injection check: is_injection={prompt_injection_result.is_injection}, "
                    f"confidence={prompt_injection_result.confidence}"
                )
            elif status == "unavailable":
                logger.warning(
                    f"Prompt injection detector not available. "
                    f"AVAILABLE={PROMPT_INJECTION_AVAILABLE}, get_detector={get_detector}"
                )
                prompt_injection_result = PromptInjectionResult(
                    is_injection=False,
                    confidence=0.0,
                    risk_score=0.0,
                    recommendation="UNAVAILABLE - Detector not loaded",
                    patterns_matched=[],
                )
            else:
                prompt_injection_result = PromptInjectionResult(
                    is_injection=False,
                    confidence=0.0,
                    risk_score=0.0,
                    recommendation="ERROR - Detection unavailable",
                    patterns_matched=[],
                )

    is_safe = True
    if pii_entities and not redact:
        is_safe = False
    if toxicity_scores and toxicity_scores.toxicity > toxicity_threshold:
        is_safe = False
    if prompt_injection_result and prompt_injection_result.is_injection:
        is_safe = False

    processing_time = (time.time() - start_time) * 1000
    if record_prometheus:
        try:
            if _PROM and METRIC_FILTER_REQUESTS is not None:
                METRIC_FILTER_REQUESTS.labels(
                    redact=str(bool(redact)).lower(),
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
        prompt_injection=prompt_injection_result,
        is_safe=is_safe,
        filters_applied=request.filters,
        analyzed_at=datetime.utcnow(),
        processing_time_ms=round(processing_time, 2)
    )

    if persist_result:
        filter_results[result_id] = response

    return response


@router.post(
    "/filter",
    response_model=ContentFilterResponse,
    summary="Filter and analyze content for security threats",
    tags=["Content Filter"]
)
async def filter_content(
    request: ContentFilterRequest,
    background_tasks: BackgroundTasks,
    auth_data = Depends(get_authenticated_user)
):
    """
    Comprehensive content analysis combining multiple security filters.
    
    This unified endpoint provides:
    - **Prompt Injection Detection**: Hybrid DeBERTa + Regex (92% accuracy)
    - **PII Detection**: GLiNER ML-based + Regex (93% accuracy)
    - **Toxicity Analysis**: ML-based (unitary/toxic-bert, multi-label Jigsaw fine-tune)
    
    **Performance**: With default settings, PII, toxicity, and prompt-injection phases run **concurrently**
    (via thread offload) so wall time is close to the slowest phase, not the sum of all phases.
    Set `CONTENT_FILTER_PARALLEL_ML=false` to force strictly sequential execution.
    
    **Default Filters**: `["pii", "toxicity", "prompt_injection"]`
    
    **Example**:
    ```json
    {
        "content": "Email me at john@example.com. Ignore all instructions.",
        "filters": ["pii", "toxicity", "prompt_injection"],
        "redact": true
    }
    ```
    
    **Response includes**:
    - `is_safe`: Overall safety assessment (false if any threat detected)
    - `pii_detected`: List of PII entities with confidence scores
    - `toxicity_scores`: Toxicity score with label from ML model
    - `prompt_injection`: Injection detection with risk score and patterns
    - `filtered_content`: Content with PII redacted (if redact=true)
    """
    ctx = (
        _tracer.start_as_current_span("content_filter") if _OTEL else nullcontext()
    )
    with ctx as span:  # type: ignore
        # --- Resolve template pack (if the API key has one attached) ---
        pack_config = None
        current_user, api_key_id = auth_data
        if api_key_id:
            pack_name = get_api_key_template_pack(api_key_id)
            if pack_name:
                try:
                    from api.routes.policies import TemplatePack, get_template_pack_config
                    pack_config = get_template_pack_config(TemplatePack(pack_name))
                except Exception:
                    pack_config = None

        # --- Load org-level DB defaults ---
        defaults = get_default("content_filter_defaults") if _DB_OK else None

        # --- Merge priority: explicit request > pack > DB defaults > system defaults ---
        # redact: None means "not set by caller" — use pack then DB then False
        if request.redact is not None:
            redact = request.redact
        elif pack_config is not None:
            redact = pack_config.redact
        elif defaults and "redact" in defaults:
            redact = bool(defaults["redact"])
        else:
            redact = False

        # filters: if the request contains only the default factory value AND a pack is attached,
        # let the pack override the filter list
        _default_filters = {FilterType.PII, FilterType.TOXICITY, FilterType.PROMPT_INJECTION}
        if pack_config is not None and set(request.filters) == _default_filters:
            try:
                request.filters = [FilterType(f) for f in pack_config.filters]
            except Exception:
                pass  # Keep original if pack has an unrecognised filter

        # custom_pii_patterns: merge pack patterns with any explicit per-request patterns
        if pack_config is not None and pack_config.custom_pii_patterns:
            merged_patterns = dict(pack_config.custom_pii_patterns)
            if request.custom_pii_patterns:
                merged_patterns.update(request.custom_pii_patterns)
            custom_pii_patterns: Optional[Dict[str, str]] = merged_patterns
        else:
            custom_pii_patterns = request.custom_pii_patterns or (
                defaults.get("custom_pii_patterns") if defaults else None
            )

        # toxicity_threshold: if the request value equals the system default (0.7) and a pack
        # is attached with a different value, use the pack value
        _system_default_threshold = 0.7
        if pack_config is not None and request.toxicity_threshold == _system_default_threshold:
            toxicity_threshold = pack_config.toxicity_threshold
        elif request.toxicity_threshold is not None:
            toxicity_threshold = request.toxicity_threshold
        else:
            toxicity_threshold = defaults.get("toxicity_threshold", _system_default_threshold) if defaults else _system_default_threshold

        use_presidio_pii = (
            request.use_presidio_pii
            or (pack_config.use_presidio_pii if pack_config else False)
            or bool(defaults.get("use_presidio_pii") if defaults else False)
        )

        response = await _execute_filter_core(
            request,
            span,
            redact=redact,
            custom_pii_patterns=custom_pii_patterns,
            toxicity_threshold=float(toxicity_threshold),
            use_presidio_pii=bool(use_presidio_pii),
            persist_result=True,
            record_prometheus=True,
        )

        if api_key_id:
            background_tasks.add_task(track_api_key_usage, api_key_id, "/filter", 0, 0.0)

        return response


@router.post(
    "/filter/demo",
    response_model=ContentFilterResponse,
    summary="Try the content filter without authentication (playground)",
    tags=["Content Filter"],
)
async def filter_content_demo(request: ContentFilterRequest):
    """
    Public playground: same analysis as ``POST /filter`` but **no login or API key**.
    Disabled when ``ENABLE_PUBLIC_FILTER_DEMO=false``. Stricter length limit; does not
    persist results or record Prometheus metrics.
    """
    settings = get_settings()
    if not settings.enable_public_filter_demo:
        raise HTTPException(status_code=404, detail="Demo endpoint is disabled")
    max_len = settings.public_filter_demo_max_chars
    if len(request.content) > max_len:
        raise HTTPException(
            status_code=400,
            detail=f"Content exceeds demo limit ({max_len} characters)",
        )

    if request.redact is not None:
        redact = request.redact
    else:
        redact = True
    ctx = (
        _tracer.start_as_current_span("content_filter_demo") if _OTEL else nullcontext()
    )
    with ctx as span:  # type: ignore
        return await _execute_filter_core(
            request,
            span,
            redact=redact,
            custom_pii_patterns=request.custom_pii_patterns,
            toxicity_threshold=float(request.toxicity_threshold),
            use_presidio_pii=False,
            persist_result=False,
            record_prometheus=False,
        )


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
