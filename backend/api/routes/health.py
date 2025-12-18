"""
Health check endpoints
"""
from fastapi import APIRouter, status, Response
from pydantic import BaseModel
from datetime import datetime
from typing import Dict
from sqlalchemy import text
import logging

from api.db import get_engine

router = APIRouter()
logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str
    services: Dict[str, str]


class ReadinessResponse(BaseModel):
    ready: bool
    services: Dict[str, str]
    timestamp: datetime


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="0.1.0",
        services={
            "api": "operational",
            "database": "operational",
            "redis": "operational",
            "ml_models": "operational"
        }
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_check(response: Response):
    """
    Readiness check for Kubernetes

    Verifies that all critical services are ready to handle requests:
    - Database connectivity
    - ML models loaded (DeBERTa, GLiNER)

    Returns:
        200 OK if all services ready
        503 Service Unavailable if any service not ready
    """
    services_status = {}
    all_ready = True

    # Check database connection
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        services_status["database"] = "ready"
    except Exception as e:
        logger.error(f"Database readiness check failed: {e}")
        services_status["database"] = "not_ready"
        all_ready = False

    # Check DeBERTa prompt injection model
    try:
        from api.routes.security import get_detector
        detector = get_detector()
        # Test with a simple query to ensure model is loaded
        _ = detector.detect("test", fast_mode=True)
        services_status["deberta_model"] = "ready"
    except Exception as e:
        logger.error(f"DeBERTa model readiness check failed: {e}")
        services_status["deberta_model"] = "not_ready"
        all_ready = False

    # Check GLiNER PII detection model
    try:
        from models.pii_detector_gliner import get_gliner_detector
        pii_detector = get_gliner_detector()
        # Verify detector is initialized (lazy loading will trigger if needed)
        _ = pii_detector.detect("test")
        services_status["gliner_model"] = "ready"
    except Exception as e:
        logger.error(f"GLiNER model readiness check failed: {e}")
        services_status["gliner_model"] = "not_ready"
        all_ready = False

    # Set HTTP status code
    if not all_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        ready=all_ready,
        services=services_status,
        timestamp=datetime.utcnow()
    )


@router.get("/health/live")
async def liveness_check():
    """Liveness check for Kubernetes"""
    return {"alive": True}
