"""
Security analysis endpoints - prompt injection, data exfiltration, etc.

Features:
- Hybrid prompt injection detection (regex + DeBERTa)
- Data exfiltration monitoring
- Jailbreak attempt detection
- Real-time threat analysis
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4
from enum import Enum
import os
import logging
import threading

from api.routes.auth import get_current_user, TokenData, extract_token
from api.routes.rampart_keys import get_current_user_from_api_key, track_api_key_usage
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models.prompt_injection_detector import (
    PromptInjectionDetectorLike,
    get_prompt_injection_detector,
)
from security.data_exfiltration_monitor import DataExfiltrationMonitor
from api.memstore import BoundedDict

router = APIRouter()
security = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)

# Initialize hybrid detector (lazy loaded)
_detector: Optional[PromptInjectionDetectorLike] = None
_detector_lock = threading.Lock()
_exfiltration_monitor = None


def _build_arbiter():
    """LLM arbiter for the FLAG/BLOCK band; None unless explicitly enabled in settings."""
    from api.config import get_settings

    s = get_settings()
    if not s.prompt_injection_arbiter_enabled:
        return None
    from models.injection_arbiter import InjectionArbiter

    # Fail loudly here rather than letting every arbiter call degrade into a swallowed
    # warning: an operator who enabled the arbiter should learn at startup that it can't run.
    provider = s.prompt_injection_arbiter_provider
    if provider not in ("openai", "anthropic"):
        raise RuntimeError(f"PROMPT_INJECTION_ARBITER_PROVIDER must be openai or anthropic, got {provider!r}")
    api_key = s.anthropic_api_key if provider == "anthropic" else s.openai_api_key
    if not api_key:
        raise RuntimeError(
            f"PROMPT_INJECTION_ARBITER_ENABLED=true but {provider.upper()}_API_KEY is not set"
        )
    try:
        __import__(provider)
    except ImportError as e:
        raise RuntimeError(f"PROMPT_INJECTION_ARBITER_ENABLED=true but the '{provider}' SDK is not installed") from e

    return InjectionArbiter(
        provider=s.prompt_injection_arbiter_provider,
        model=s.prompt_injection_arbiter_model,
        min_confidence=s.prompt_injection_arbiter_min_confidence,
    )


def get_detector() -> PromptInjectionDetectorLike:
    """Get or create detector instance"""
    global _detector
    if _detector is None:
        with _detector_lock:
            if _detector is None:
                detector_type = os.getenv("PROMPT_INJECTION_DETECTOR", "hybrid")
                use_onnx = os.getenv("PROMPT_INJECTION_USE_ONNX", "true").lower() == "true"
                kwargs = {"arbiter": _build_arbiter()} if detector_type == "hybrid" else {}
                _detector = get_prompt_injection_detector(
                    detector_type=detector_type,
                    use_onnx=use_onnx,
                    **kwargs,
                )
                logger.info(f"✓ Security detector initialized: {detector_type}")
    return _detector


def get_exfiltration_monitor():
    """Get or create data exfiltration monitor instance"""
    global _exfiltration_monitor
    if _exfiltration_monitor is None:
        _exfiltration_monitor = DataExfiltrationMonitor()
        logger.info("✓ DataExfiltrationMonitor initialized")
    return _exfiltration_monitor


# Dual authentication dependency - supports both JWT and API key
def require_auth(*api_key_permissions: str):
    """
    Build a dependency authenticating via either JWT token (dashboard) or API key (application).
    API keys must hold at least one of ``api_key_permissions``; JWT (dashboard) users have full access.
    The dependency returns (user_data, api_key_id) - api_key_id is None for JWT auth.
    """
    async def _authenticate(
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    ) -> tuple[TokenData, Optional[UUID]]:
        # Bearer header (API key or JWT) or the dashboard's HttpOnly session cookie (JWT)
        token, from_cookie = extract_token(request, credentials)

        # Try API key authentication first (starts with 'rmp_')
        if token.startswith('rmp_') and not from_cookie:
            user_data, api_key_id = await get_current_user_from_api_key(
                token, required_any=api_key_permissions
            )
        else:
            # Fall back to JWT authentication
            from api.routes.auth import decode_access_token
            user_data, api_key_id = decode_access_token(token), None

        # Picked up by AuditLogMiddleware so audit rows carry the acting user
        request.state.user_id = str(user_data.user_id)
        return user_data, api_key_id

    return _authenticate


get_authenticated_user = require_auth()


class ThreatType(str, Enum):
    """Types of security threats"""
    PROMPT_INJECTION = "prompt_injection"
    DATA_EXFILTRATION = "data_exfiltration"
    JAILBREAK = "jailbreak"
    SCOPE_VIOLATION = "scope_violation"
    ZERO_CLICK = "zero_click"
    CONTEXT_CONFUSION = "context_confusion"


class SeverityLevel(str, Enum):
    """Severity levels for threats"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityAnalysisRequest(BaseModel):
    """Request for security analysis"""
    content: str = Field(..., description="Content to analyze")
    context_type: str = Field(..., description="input, output, system_prompt")
    trace_id: Optional[UUID] = None
    metadata: Optional[Dict[str, Any]] = None


class ThreatDetection(BaseModel):
    """Detected threat information"""
    threat_type: ThreatType
    severity: SeverityLevel
    confidence: float = Field(..., ge=0.0, le=1.0)
    description: str
    indicators: List[str]
    recommended_action: str


class SecurityAnalysisResponse(BaseModel):
    """Response from security analysis"""
    id: UUID
    content_hash: str
    threats_detected: List[ThreatDetection]
    is_safe: bool
    risk_score: float = Field(..., ge=0.0, le=1.0)
    analyzed_at: datetime
    processing_time_ms: float
    trace_id: Optional[UUID]


class SecurityIncident(BaseModel):
    """Security incident record"""
    id: UUID
    threat_type: ThreatType
    severity: SeverityLevel
    content_preview: str
    trace_id: Optional[UUID]
    user_id: Optional[str]
    detected_at: datetime
    status: str = Field(..., description="open, investigating, resolved, false_positive")
    metadata: Optional[Dict[str, Any]]


# In-memory storage (bounded). Analyses are stored as (owner_user_id, response).
security_analyses: "BoundedDict[UUID, tuple[str, SecurityAnalysisResponse]]" = BoundedDict(10_000)
security_incidents: "BoundedDict[UUID, SecurityIncident]" = BoundedDict(10_000)


def _user_incidents(user_id: UUID) -> List[SecurityIncident]:
    uid = str(user_id)
    return [i for i in list(security_incidents.values()) if i.user_id == uid]


def _get_owned_incident(incident_id: UUID, user_id: UUID) -> SecurityIncident:
    incident = security_incidents.get(incident_id)
    # 404 (not 403) for other users' incidents to avoid enumeration
    if not incident or incident.user_id != str(user_id):
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


def analyze_prompt_injection(content: str, fast_mode: bool = False) -> Optional[ThreatDetection]:
    """
    Analyze content for prompt injection attacks using hybrid detection
    
    Uses DeBERTa + regex for 95% accuracy with <10ms average latency.
    
    Args:
        content: Content to analyze
        fast_mode: Skip DeBERTa for ultra-fast detection (regex only)
    
    Returns:
        ThreatDetection if injection detected, None otherwise
    """
    detector = get_detector()
    
    try:
        # Use hybrid detector (regex + DeBERTa)
        result = detector.detect(content, fast_mode=fast_mode)
        
        confidence = float(result.get("score", result.get("confidence", 0.0)))
        verdict = result.get("verdict")
        degraded = bool(result.get("degraded", False))

        if verdict == "unavailable":
            # Fail closed: the scanner could not fully run, so report that rather than "safe".
            return ThreatDetection(
                threat_type=ThreatType.PROMPT_INJECTION,
                severity=SeverityLevel.MEDIUM,
                confidence=0.5,
                description=f"Prompt injection scan unavailable ({result.get('degraded_reason') or 'degraded'})",
                indicators=["scan_unavailable"],
                recommended_action="flag",
            )

        if verdict in ("flag", "block"):
            severity = SeverityLevel.CRITICAL if verdict == "block" else SeverityLevel.HIGH
            indicators = sorted({r["code"] for r in result.get("reasons", [])})
            detector_used = result.get("detector", "unknown")
            latency = result.get("latency_ms", 0.0)
            description = (
                f"Prompt injection {verdict} ({detector_used}, score {confidence:.2f}, {latency:.1f}ms"
                f"{', degraded' if degraded else ''})"
            )
            return ThreatDetection(
                threat_type=ThreatType.PROMPT_INJECTION,
                severity=severity,
                confidence=max(confidence, 0.75 if verdict == "flag" else 0.9),
                description=description,
                indicators=indicators or ["deberta_injection"],
                recommended_action=verdict,
            )
    
    except Exception as e:
        logger.error(f"Prompt injection detection failed: {e}")
        # Fall back to simple detection on error
        pass
    
    return None


def analyze_data_exfiltration(content: str) -> Optional[ThreatDetection]:
    """
    Analyze content for data exfiltration attempts using comprehensive DataExfiltrationMonitor
    
    This now detects:
    - Credentials (API keys, passwords, JWT, AWS keys, private keys)
    - Exfiltration commands (email, send, curl, wget, etc.) with granular severity
    - Database connection strings
    - Internal IP addresses
    - URLs with suspicious parameters
    - Trusted domain whitelisting
    """
    try:
        monitor = get_exfiltration_monitor()
        result = monitor.scan_output(content)
        
        if result["has_exfiltration_risk"]:
            # Map recommendation to severity
            severity_map = {
                "BLOCK": SeverityLevel.CRITICAL,
                "REDACT": SeverityLevel.HIGH,
                "FLAG": SeverityLevel.MEDIUM,
                "ALLOW": SeverityLevel.LOW
            }
            
            # Collect all indicators for detailed reporting
            indicators = []
            
            # Add sensitive data found
            for item in result["sensitive_data_found"]:
                indicators.append(f"{item['type']}: {item['matched_text']}")
            
            # Add exfiltration indicators
            for item in result["exfiltration_indicators"]:
                indicators.append(f"{item['name']} ({item['method']})")
            
            # Add URL analysis
            for url in result.get("urls_found", []):
                if url.get("has_suspicious_params") or not url.get("is_trusted"):
                    indicators.append(f"suspicious_url: {url['domain']}")
            
            return ThreatDetection(
                threat_type=ThreatType.DATA_EXFILTRATION,
                severity=severity_map.get(result["recommendation"], SeverityLevel.MEDIUM),
                confidence=result["risk_score"],
                description="Potential data exfiltration attempt detected",
                indicators=indicators or ["data_exfiltration_risk"],
                recommended_action=result["recommendation"].lower()
            )
    
    except Exception as e:
        logger.error(f"Data exfiltration detection failed: {e}")
        # Fall back to simple detection on error
        pass
    
    return None


def analyze_jailbreak(content: str) -> Optional[ThreatDetection]:
    """Analyze content for jailbreak attempts"""
    jailbreak_patterns = [
        "dan mode",
        "developer mode",
        "jailbreak",
        "unrestricted mode",
        "bypass restrictions",
        "without limitations",
        "ignore safety",
        "ignore ethics"
    ]
    
    content_lower = content.lower()
    detected_patterns = [p for p in jailbreak_patterns if p in content_lower]
    
    if detected_patterns:
        # Higher confidence - each pattern adds 0.5
        confidence = min(len(detected_patterns) * 0.5, 1.0)
        severity = SeverityLevel.HIGH
        
        return ThreatDetection(
            threat_type=ThreatType.JAILBREAK,
            severity=severity,
            confidence=confidence,
            description="Potential jailbreak attempt detected",
            indicators=detected_patterns,
            recommended_action="block"
        )
    return None


@router.post("/analyze", response_model=SecurityAnalysisResponse)
async def analyze_security(
    request: SecurityAnalysisRequest,
    background_tasks: BackgroundTasks,
    auth_data = Depends(require_auth("security:analyze"))
):
    """Analyze content for security threats"""
    import asyncio
    import time
    import hashlib
    
    start_time = time.time()
    
    # Generate content hash
    content_hash = hashlib.sha256(request.content.encode()).hexdigest()[:16]
    
    # Run security analyses — each detector is a blocking sync function so we
    # offload to the thread pool and gather concurrently (mirrors content_filter).
    threats = []
    
    if request.context_type in ["input", "system_prompt"]:
        # Injection (DeBERTa ~50ms) and jailbreak (regex <1ms) run in parallel.
        injection_result, jailbreak_result = await asyncio.gather(
            asyncio.to_thread(analyze_prompt_injection, request.content),
            asyncio.to_thread(analyze_jailbreak, request.content),
        )
        if injection_result:
            threats.append(injection_result)
        if jailbreak_result:
            threats.append(jailbreak_result)
    
    if request.context_type == "output":
        # Exfiltration monitor now includes a GLiNER call (~10–150ms) so must
        # run off the event loop.
        exfil_result = await asyncio.to_thread(analyze_data_exfiltration, request.content)
        if exfil_result:
            threats.append(exfil_result)
    
    # Calculate risk score
    risk_score = 0.0
    if threats:
        risk_score = max(t.confidence for t in threats)
    
    is_safe = risk_score < 0.5
    should_block = risk_score >= 0.5  # Block if risk score is 0.5 or higher
    
    processing_time = (time.time() - start_time) * 1000
    
    analysis_id = uuid4()
    response = SecurityAnalysisResponse(
        id=analysis_id,
        content_hash=content_hash,
        threats_detected=threats,
        is_safe=is_safe,
        risk_score=risk_score,
        analyzed_at=datetime.utcnow(),
        processing_time_ms=round(processing_time, 2),
        trace_id=request.trace_id
    )
    
    current_user, api_key_id = auth_data
    security_analyses[analysis_id] = (str(current_user.user_id), response)
    
    # Track API key usage in background (non-blocking)
    if api_key_id:
        background_tasks.add_task(track_api_key_usage, api_key_id, "/security/analyze", 0, 0.0)
    
    # Create incident if high risk
    if risk_score >= 0.7 and threats:
        incident_id = uuid4()
        incident = SecurityIncident(
            id=incident_id,
            threat_type=threats[0].threat_type,
            severity=threats[0].severity,
            content_preview=request.content[:200],
            trace_id=request.trace_id,
            user_id=str(current_user.user_id),
            detected_at=datetime.utcnow(),
            status="open",
            metadata=request.metadata
        )
        security_incidents[incident_id] = incident
    
    return response


@router.get("/incidents", response_model=List[SecurityIncident])
async def list_incidents(
    current_user: TokenData = Depends(get_current_user),
    status: Optional[str] = None,
    severity: Optional[SeverityLevel] = None,
    limit: int = 50
):
    """List security incidents"""
    incidents = _user_incidents(current_user.user_id)
    
    if status:
        incidents = [i for i in incidents if i.status == status]
    if severity:
        incidents = [i for i in incidents if i.severity == severity]
    
    incidents.sort(key=lambda x: x.detected_at, reverse=True)
    return incidents[:limit]


@router.get("/incidents/{incident_id}", response_model=SecurityIncident)
async def get_incident(
    incident_id: UUID,
    current_user: TokenData = Depends(get_current_user)
):
    """Get a specific security incident (only if it belongs to the current user)"""
    return _get_owned_incident(incident_id, current_user.user_id)


@router.patch("/incidents/{incident_id}/status")
async def update_incident_status(
    incident_id: UUID,
    status: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Update incident status"""
    incident = _get_owned_incident(incident_id, current_user.user_id)
    
    valid_statuses = ["open", "investigating", "resolved", "false_positive"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    incident.status = status
    return {"message": "Status updated", "incident_id": incident_id, "status": status}


@router.get("/stats")
async def get_security_stats(current_user: TokenData = Depends(get_current_user)):
    """Get security statistics including both JWT traces and API key usage"""
    from api.db import get_conn
    from sqlalchemy import text
    
    # JWT trace data (in-memory, scoped to the current user)
    uid = str(current_user.user_id)
    user_analyses = [a for owner, a in list(security_analyses.values()) if owner == uid]
    user_incidents = _user_incidents(current_user.user_id)
    jwt_analyses = len(user_analyses)
    total_incidents = len(user_incidents)
    
    threat_counts = {}
    for incident in user_incidents:
        threat_type = incident.threat_type.value
        threat_counts[threat_type] = threat_counts.get(threat_type, 0) + 1
    
    open_incidents = len([i for i in user_incidents if i.status == "open"])
    
    jwt_risk_score = round(
        sum(a.risk_score for a in user_analyses) / max(jwt_analyses, 1),
        3
    ) if jwt_analyses > 0 else 0
    
    # API key usage data (from database)
    api_key_analyses = 0
    api_key_breakdown = []
    
    try:
        with get_conn() as conn:
            # Get total API key security analyses
            result = conn.execute(
                text("""
                    SELECT 
                        COALESCE(SUM(u.requests_count), 0) as total_requests
                    FROM rampart_api_keys k
                    LEFT JOIN rampart_api_key_usage u ON k.id = u.api_key_id
                    WHERE k.user_id = :user_id 
                    AND k.is_active = true
                    AND u.endpoint = '/security/analyze'
                """),
                {"user_id": current_user.user_id}
            ).fetchone()
            
            api_key_analyses = result[0] if result else 0
            
            # Get breakdown by API key
            breakdown_result = conn.execute(
                text("""
                    SELECT 
                        k.key_name,
                        k.key_preview,
                        COALESCE(SUM(u.requests_count), 0) as requests
                    FROM rampart_api_keys k
                    LEFT JOIN rampart_api_key_usage u ON k.id = u.api_key_id AND u.endpoint = '/security/analyze'
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
        print(f"Error fetching API key security stats: {e}")
        pass
    
    total_analyses = jwt_analyses + api_key_analyses
    
    return {
        "total_analyses": total_analyses,
        "jwt_analyses": jwt_analyses,
        "api_key_analyses": api_key_analyses,
        "api_key_breakdown": api_key_breakdown,
        "total_incidents": total_incidents,
        "open_incidents": open_incidents,
        "threat_distribution": threat_counts,
        "average_risk_score": jwt_risk_score
    }
