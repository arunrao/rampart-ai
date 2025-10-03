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
from api.routes import health, traces, security, policies, content_filter, auth, providers
from api.db import init_all_tables

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
    
    # Initialize services
    # TODO: Initialize database connections, ML models, etc.
    try:
        init_all_tables()
        logger.info("Database tables initialized (users, provider_keys, policy_defaults)")
    except Exception as e:
        logger.warning(f"Failed to init database tables: {e}")
    
    yield
    
    # Cleanup
    logger.info("Shutting down Project Rampart")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI Security & Observability Platform",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
app.include_router(security.router, prefix=settings.api_prefix, tags=["security"])
app.include_router(policies.router, prefix=settings.api_prefix, tags=["policies"])
app.include_router(content_filter.router, prefix=settings.api_prefix, tags=["content-filter"])


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
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
