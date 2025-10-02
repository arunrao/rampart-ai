"""
Health check endpoints
"""
from fastapi import APIRouter, status
from pydantic import BaseModel
from datetime import datetime
from typing import Dict

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str
    services: Dict[str, str]


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


@router.get("/health/ready")
async def readiness_check():
    """Readiness check for Kubernetes"""
    # TODO: Check if all services are ready
    return {"ready": True}


@router.get("/health/live")
async def liveness_check():
    """Liveness check for Kubernetes"""
    return {"alive": True}
