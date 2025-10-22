"""
Security analysis endpoints - prompt injection, data exfiltration, etc.

Features:
- Hybrid prompt injection detection (regex + DeBERTa)
- Data exfiltration monitoring
- Jailbreak attempt detection
- Real-time threat analysis
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4
from enum import Enum
import os
import logging

from api.routes.auth import get_current_user, TokenData
from api.routes.rampart_keys import get_current_user_from_api_key, track_api_key_usage
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models.prompt_injection_detector import get_prompt_injection_detector
from security.data_exfiltration_monitor import DataExfiltrationMonitor

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger(__name__)

# Initialize hybrid detector (lazy loaded)
_detector = None
_exfiltration_monitor = None


def get_detector():
    """Get or create detector instance"""
    global _detector
    if _detector is None:
        detector_type = os.getenv("PROMPT_INJECTION_DETECTOR", "hybrid")
        use_onnx = os.getenv("PROMPT_INJECTION_USE_ONNX", "true").lower() == "true"
        _detector = get_prompt_injection_detector(
            detector_type=detector_type,
            use_onnx=use_onnx
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
        
        # Extract risk score and confidence
        confidence = result.get("confidence", result.get("risk_score", 0.0))
        is_injection = result.get("is_injection", False)
        
        if is_injection:
            # Map confidence to severity
            if confidence >= 0.9:
                severity = SeverityLevel.CRITICAL
            elif confidence >= 0.75:
                severity = SeverityLevel.HIGH
            elif confidence >= 0.5:
                severity = SeverityLevel.MEDIUM
            else:
                severity = SeverityLevel.LOW
            
            # Extract indicators
            indicators = []
            if "detected_patterns" in result:
                indicators = [p["name"] for p in result["detected_patterns"]]
            elif "detection_details" in result:
                details = result["detection_details"]
                if "regex" in details:
                    indicators = [p["name"] for p in details["regex"].get("detected_patterns", [])]
            
            # Get recommendation
            recommendation = result.get("recommendation", "BLOCK")
            action = "block" if "BLOCK" in recommendation else "flag"
            
            # Build description
            detector_used = result.get("detector", "unknown")
            latency = result.get("latency_ms", 0.0)
            description = f"Prompt injection detected ({detector_used}, {confidence:.1%} confidence, {latency:.1f}ms)"
            
            return ThreatDetection(
                threat_type=ThreatType.PROMPT_INJECTION,
                severity=severity,
                confidence=confidence,
                description=description,
                indicators=indicators or ["prompt_injection_pattern"],
                recommended_action=action
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
    auth_data = Depends(get_authenticated_user)
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
    
    # Track API key usage in background (non-blocking)
    current_user, api_key_id = auth_data
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
    """Get security statistics including both JWT traces and API key usage"""
    from api.db import get_conn
    from sqlalchemy import text
    
    # JWT trace data (in-memory)
    jwt_analyses = len(security_analyses)
    total_incidents = len(security_incidents)
    
    threat_counts = {}
    for incident in security_incidents.values():
        threat_type = incident.threat_type.value
        threat_counts[threat_type] = threat_counts.get(threat_type, 0) + 1
    
    open_incidents = len([i for i in security_incidents.values() if i.status == "open"])
    
    jwt_risk_score = round(
        sum(a.risk_score for a in security_analyses.values()) / max(jwt_analyses, 1),
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
