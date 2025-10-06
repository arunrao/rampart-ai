"""
Security analysis endpoints - prompt injection, data exfiltration, etc.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4
from enum import Enum

from api.routes.auth import get_current_user, TokenData
from api.routes.rampart_keys import get_current_user_from_api_key, track_api_key_usage
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

router = APIRouter()
security = HTTPBearer()


# Dual authentication dependency - supports both JWT and API key
async def get_authenticated_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> tuple[TokenData, Optional[UUID]]:
    """
    Authenticate user via either JWT token (dashboard) or API key (application).
    Returns (user_data, api_key_id) - api_key_id is None for JWT auth.
    """
    token = credentials.credentials
    
    # Try API key authentication first (starts with 'rmp_')
    if token.startswith('rmp_'):
        user_data, api_key_id = await get_current_user_from_api_key(token)
        return user_data, api_key_id
    
    # Fall back to JWT authentication
    from api.routes.auth import decode_access_token
    user_data = decode_access_token(token)
    return user_data, None


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


# In-memory storage
security_analyses: Dict[UUID, SecurityAnalysisResponse] = {}
security_incidents: Dict[UUID, SecurityIncident] = {}


def analyze_prompt_injection(content: str) -> Optional[ThreatDetection]:
    """Analyze content for prompt injection attacks"""
    # Simple heuristic-based detection (replace with ML model in production)
    injection_patterns = [
        "ignore previous instructions",
        "ignore all previous",
        "disregard previous",
        "new instructions:",
        "system:",
        "override",
        "forget everything",
        "you are now",
        "act as if",
        "system prompt",
        "original instructions",
        "admin mode",
        "developer mode"
    ]
    
    content_lower = content.lower()
    detected_patterns = [p for p in injection_patterns if p in content_lower]
    
    if detected_patterns:
        # Higher confidence scoring - each pattern adds 0.5
        confidence = min(len(detected_patterns) * 0.5, 1.0)
        severity = SeverityLevel.HIGH if confidence >= 0.5 else SeverityLevel.MEDIUM
        
        return ThreatDetection(
            threat_type=ThreatType.PROMPT_INJECTION,
            severity=severity,
            confidence=confidence,
            description="Potential prompt injection attack detected",
            indicators=detected_patterns,
            recommended_action="block" if severity == SeverityLevel.HIGH else "flag"
        )
    return None


def analyze_data_exfiltration(content: str) -> Optional[ThreatDetection]:
    """Analyze content for data exfiltration attempts"""
    # Check for suspicious patterns
    exfiltration_patterns = [
        "send to",
        "send this",
        "email this",
        "email to",
        "post to",
        "upload to",
        "save to url",
        "webhook",
        "http://",
        "https://",
        "curl",
        "wget"
    ]
    
    content_lower = content.lower()
    detected_patterns = [p for p in exfiltration_patterns if p in content_lower]
    
    if detected_patterns:
        # Each pattern adds 0.5 - single strong pattern is enough to block
        confidence = min(len(detected_patterns) * 0.5, 1.0)
        severity = SeverityLevel.CRITICAL if confidence >= 0.7 else SeverityLevel.HIGH
        
        return ThreatDetection(
            threat_type=ThreatType.DATA_EXFILTRATION,
            severity=severity,
            confidence=confidence,
            description="Potential data exfiltration attempt detected",
            indicators=detected_patterns,
            recommended_action="block"
        )
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
    auth_data: tuple[TokenData, Optional[UUID]] = Depends(get_authenticated_user)
):
    """Analyze content for security threats"""
    import time
    import hashlib
    
    start_time = time.time()
    
    # Generate content hash
    content_hash = hashlib.sha256(request.content.encode()).hexdigest()[:16]
    
    # Run security analyses
    threats = []
    
    if request.context_type in ["input", "system_prompt"]:
        # Check for prompt injection
        if threat := analyze_prompt_injection(request.content):
            threats.append(threat)
        
        # Check for jailbreak
        if threat := analyze_jailbreak(request.content):
            threats.append(threat)
    
    if request.context_type == "output":
        # Check for data exfiltration
        if threat := analyze_data_exfiltration(request.content):
            threats.append(threat)
    
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
    
    security_analyses[analysis_id] = response
    
    # Track API key usage if authenticated via API key
    current_user, api_key_id = auth_data
    if api_key_id:
        track_api_key_usage(api_key_id, "/security/analyze", tokens_used=0, cost_usd=0.0)
    
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
    incidents = list(security_incidents.values())
    
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
    """Get a specific security incident"""
    if incident_id not in security_incidents:
        raise HTTPException(status_code=404, detail="Incident not found")
    return security_incidents[incident_id]


@router.patch("/incidents/{incident_id}/status")
async def update_incident_status(
    incident_id: UUID,
    status: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Update incident status"""
    if incident_id not in security_incidents:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    valid_statuses = ["open", "investigating", "resolved", "false_positive"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    security_incidents[incident_id].status = status
    return {"message": "Status updated", "incident_id": incident_id, "status": status}


@router.get("/stats")
async def get_security_stats(current_user: TokenData = Depends(get_current_user)):
    """Get security statistics"""
    total_analyses = len(security_analyses)
    total_incidents = len(security_incidents)
    
    threat_counts = {}
    for incident in security_incidents.values():
        threat_type = incident.threat_type.value
        threat_counts[threat_type] = threat_counts.get(threat_type, 0) + 1
    
    open_incidents = len([i for i in security_incidents.values() if i.status == "open"])
    
    return {
        "total_analyses": total_analyses,
        "total_incidents": total_incidents,
        "open_incidents": open_incidents,
        "threat_distribution": threat_counts,
        "average_risk_score": round(
            sum(a.risk_score for a in security_analyses.values()) / max(total_analyses, 1),
            3
        )
    }
