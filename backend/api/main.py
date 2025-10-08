"""
Main FastAPI application for Project Rampart
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from contextlib import asynccontextmanager
import time
import logging

from api.config import get_settings
from api.routes import health, auth, providers, traces, security, policies, content_filter, test_scenarios, api_keys, rampart_keys
from api.db import init_defaults_table, init_all_tables
from api.middleware import (
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    RequestSizeLimitMiddleware,
    APIKeyEnforcementMiddleware
)

# OpenTelemetry setup (safe if not available)
try:
    from opentelemetry import trace as otel_trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    _OTEL_AVAILABLE = True
except Exception:  # pragma: no cover
    _OTEL_AVAILABLE = False

# Prometheus metrics setup (safe if not available)
try:
    from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest
    _PROM_AVAILABLE = True
    _prom_registry = CollectorRegistry()
except Exception:  # pragma: no cover
    _PROM_AVAILABLE = False
    _prom_registry = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Initialize OTEL tracer provider (console exporter by default)
if _OTEL_AVAILABLE:
    resource = Resource.create({
        "service.name": settings.app_name,
        "service.version": settings.app_version,
        "deployment.environment": settings.environment,
    })
    provider = TracerProvider(resource=resource)
    # Choose exporter: OTLP if endpoint configured, else console
    import os
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    else:
        exporter = ConsoleSpanExporter()
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    otel_trace.set_tracer_provider(provider)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    
    # Initialize database
    try:
        init_all_tables()
        logger.info("✓ Database tables initialized (users, provider_keys, policy_defaults)")
    except Exception as e:
        logger.warning(f"Failed to init database tables: {e}")
    
    # Warmup ML models to eliminate cold start delay
    logger.info("Warming up ML models...")
    try:
        # Warmup 1: DeBERTa hybrid prompt injection detector
        from api.routes.security import get_detector
        detector = get_detector()
        # Force DeBERTa to load by using force_deberta=True
        detector.detect("warmup test query", force_deberta=True)
        logger.info("✓ DeBERTa prompt injection detector warmed up")
    except Exception as e:
        logger.warning(f"DeBERTa warmup failed: {e}")
    
    try:
        # Warmup 2: GLiNER PII detector
        from api.routes.content_filter import detect_pii
        # Use longer text with varied PII to properly warmup GLiNER
        detect_pii("Contact John Smith at john.smith@example.com or call 555-123-4567")
        logger.info("✓ GLiNER PII detector warmed up")
    except Exception as e:
        logger.warning(f"GLiNER warmup failed: {e}")
    
    logger.info("✓ All ML models ready")
    
    yield
    
    # Cleanup
    logger.info("Shutting down Project Rampart")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI Security & Observability Platform",
    docs_url=f"{settings.api_prefix}/docs",
    redoc_url=f"{settings.api_prefix}/redoc",
    openapi_url=f"{settings.api_prefix}/openapi.json",
    lifespan=lifespan
)

# Security middleware (order matters - applied in reverse)
# 1. Request size limit (first check)
app.add_middleware(RequestSizeLimitMiddleware, max_upload_size=10_000_000)

# 2. Rate limiting
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=settings.rate_limit_per_minute,
    requests_per_hour=settings.rate_limit_per_hour
)

# 3. API Key/JWT enforcement (before security headers so auth errors are properly formatted)
app.add_middleware(APIKeyEnforcementMiddleware)

# 4. Security headers (pass CORS origins for CSP)
app.add_middleware(SecurityHeadersMiddleware, cors_origins=settings.cors_origins)

# 4. CORS middleware
# Parse comma-separated origins from config
cors_origins = [origin.strip() for origin in settings.cors_origins.split(",")]

# For development, allow common local origins
if settings.debug:
    dev_origins = [
        "http://localhost:8080",  # Demo server
        "http://localhost:8081",  # Demo server (alternative port)
        "http://127.0.0.1:8080",  # Alternative localhost
        "http://127.0.0.1:8081",  # Alternative localhost
        "file://",  # Local files (though this might not work)
    ]
    cors_origins.extend(dev_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
)

# Instrument FastAPI app for tracing
if _OTEL_AVAILABLE:
    try:
        FastAPIInstrumentor.instrument_app(app)
    except Exception:
        pass


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.debug else "An error occurred"
        }
    )


# Include routers
app.include_router(health.router, prefix=settings.api_prefix, tags=["health"])
app.include_router(auth.router, prefix=settings.api_prefix, tags=["auth"])
app.include_router(providers.router, prefix=settings.api_prefix, tags=["providers"])
app.include_router(traces.router, prefix=settings.api_prefix, tags=["observability"])
app.include_router(security.router, prefix=f"{settings.api_prefix}/security", tags=["security"])
app.include_router(policies.router, prefix=settings.api_prefix, tags=["policies"])
app.include_router(content_filter.router, prefix=settings.api_prefix, tags=["content-filter"])
app.include_router(test_scenarios.router, prefix=f"{settings.api_prefix}/test", tags=["testing"])
app.include_router(api_keys.router, prefix=f"{settings.api_prefix}/api-keys", tags=["api-keys"])
app.include_router(rampart_keys.router, prefix=settings.api_prefix, tags=["rampart-keys"])


# Prometheus metrics endpoint
@app.get("/metrics")
async def metrics():
    if not _PROM_AVAILABLE or _prom_registry is None:
        return JSONResponse({"error": "prometheus_client not available"}, status_code=503)
    data = generate_latest()  # default global registry
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "operational",
        "docs": f"{settings.api_prefix}/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
