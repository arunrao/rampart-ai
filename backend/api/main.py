"""
Main FastAPI application for Project Rampart
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from contextlib import asynccontextmanager
import time
import logging
from typing import Any, Callable, Optional

from api.config import get_settings
from api.routes import health, auth, providers, traces, security, policies, content_filter, test_scenarios, api_keys, rampart_keys, admin
from api.db import init_defaults_table, init_all_tables
from api.middleware import (
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    RequestSizeLimitMiddleware,
    APIKeyEnforcementMiddleware,
    AuditLogMiddleware,
)

# OpenTelemetry setup (safe if not available)
_OTEL_AVAILABLE = False
try:
    import os as _otel_os

    from opentelemetry import trace as otel_trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    _otel_settings = get_settings()
    _otel_resource = Resource.create(
        {
            "service.name": _otel_settings.app_name,
            "service.version": _otel_settings.app_version,
            "deployment.environment": _otel_settings.environment,
        }
    )
    _otel_provider = TracerProvider(resource=_otel_resource)
    _otlp_endpoint = _otel_os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if _otlp_endpoint:
        _otlp_insecure = _otel_os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "").lower() in (
            "1",
            "true",
            "yes",
        )
        _otel_exporter = OTLPSpanExporter(endpoint=_otlp_endpoint, insecure=_otlp_insecure)
    else:
        _otel_exporter = ConsoleSpanExporter()
    _otel_processor = BatchSpanProcessor(_otel_exporter)
    _otel_provider.add_span_processor(_otel_processor)
    otel_trace.set_tracer_provider(_otel_provider)
    _OTEL_AVAILABLE = True
except Exception:  # pragma: no cover
    _OTEL_AVAILABLE = False

# Prometheus metrics setup (safe if not available)
_PROM_AVAILABLE = False
_prom_registry: Optional[Any] = None
_prom_generate_latest: Optional[Callable[[], bytes]] = None
_prom_content_type: Optional[str] = None
try:
    from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest

    _prom_registry = CollectorRegistry()
    _prom_generate_latest = generate_latest
    _prom_content_type = CONTENT_TYPE_LATEST
    _PROM_AVAILABLE = True
except Exception:  # pragma: no cover
    pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Global readiness flag — False while ML models are still loading.
# The /health endpoint always returns 200 so the ALB accepts the instance
# immediately.  All other API routes return 503 + a friendly maintenance page
# until this flips to True (typically ~2-3 min after container start).
_models_ready: bool = False

_MAINTENANCE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="15">
  <title>Rampart – Starting up</title>
  <style>
    body { font-family: system-ui, sans-serif; background: #0f1117; color: #e2e8f0;
           display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }
    .card { text-align: center; max-width: 420px; padding: 2.5rem; }
    .logo { font-size: 2rem; font-weight: 800; color: #6366f1; margin-bottom: .5rem; }
    h1 { font-size: 1.25rem; margin: 0 0 1rem; }
    p  { color: #94a3b8; font-size: .9rem; line-height: 1.6; }
    .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%;
           background: #6366f1; margin: 0 3px; animation: pulse 1.4s infinite; }
    .dot:nth-child(2) { animation-delay: .2s; }
    .dot:nth-child(3) { animation-delay: .4s; }
    @keyframes pulse { 0%,80%,100% { opacity: .2; } 40% { opacity: 1; } }
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">⚡ Rampart</div>
    <h1>Loading AI security models…</h1>
    <p>We're warming up our ML models.<br>This takes about 2–3 minutes.<br>
       This page refreshes automatically.</p>
    <br>
    <span class="dot"></span><span class="dot"></span><span class="dot"></span>
  </div>
</body>
</html>"""


def _warmup_models_sync() -> None:
    """Run all ML warmups synchronously in a background thread."""
    global _models_ready
    logger.info("Warming up ML models in background thread…")
    try:
        from api.routes.security import get_detector
        detector = get_detector()
        detector.detect("warmup test query", force_deberta=True)
        logger.info("✓ DeBERTa prompt injection detector warmed up")
    except Exception as e:
        logger.warning(f"DeBERTa warmup failed: {e}")

    try:
        from api.routes.content_filter import detect_pii
        detect_pii("Contact John Smith at john.smith@example.com or call 555-123-4567")
        logger.info("✓ GLiNER PII detector warmed up")
    except Exception as e:
        logger.warning(f"GLiNER warmup failed: {e}")

    try:
        from models.toxicity_detector import warmup as toxicity_warmup
        toxicity_warmup()
    except Exception as e:
        logger.warning(f"Toxicity model warmup failed: {e}")

    _models_ready = True
    logger.info("✓ All ML models ready — serving traffic")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    import asyncio, threading
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")

    # Initialize database synchronously (fast, must complete before serving)
    try:
        init_all_tables()
        logger.info("✓ Database tables initialized")
    except Exception as e:
        logger.warning(f"Failed to init database tables: {e}")

    # Load ML models in a background thread so the app starts accepting
    # requests (and ALB health checks) immediately.  API routes return a
    # friendly 503 maintenance page until _models_ready flips to True.
    thread = threading.Thread(target=_warmup_models_sync, daemon=True, name="ml-warmup")
    thread.start()

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

# Maintenance-mode middleware — outermost so it runs before all other middleware.
# Passes /health through unconditionally (ALB needs it to register the instance).
# All other paths get a friendly 503 HTML page until _models_ready is True.
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import HTMLResponse

class MaintenanceModeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        health_path = f"{settings.api_prefix}/health"
        if not _models_ready and not request.url.path.startswith(health_path):
            return HTMLResponse(
                content=_MAINTENANCE_HTML,
                status_code=503,
                headers={"Retry-After": "30"},
            )
        return await call_next(request)

app.add_middleware(MaintenanceModeMiddleware)

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

# 4. Audit logging (SOC2 Type II — runs after auth so user context is available)
app.add_middleware(AuditLogMiddleware)

# 5. Security headers (pass CORS origins for CSP)
app.add_middleware(SecurityHeadersMiddleware, cors_origins=settings.cors_origins)

# 6. CORS middleware
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
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

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
app.include_router(admin.router, prefix=settings.api_prefix, tags=["admin"])


# Prometheus metrics endpoint
@app.get("/metrics")
async def metrics():
    if (
        not _PROM_AVAILABLE
        or _prom_registry is None
        or _prom_generate_latest is None
        or _prom_content_type is None
    ):
        return JSONResponse({"error": "prometheus_client not available"}, status_code=503)
    data = _prom_generate_latest()
    return Response(content=data, media_type=_prom_content_type)


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
