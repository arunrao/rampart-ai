# Application image - builds in seconds, not minutes
# Uses pre-built base image with models
# Build: docker build -f Dockerfile.app -t rampart-backend:latest .

ARG BASE_IMAGE=rampart-backend-base:latest
FROM ${BASE_IMAGE}

WORKDIR /app

# Copy ONLY application code (not requirements, already in base)
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app \
    && chown -R app:app /app/.cache
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=2 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"

# Run the application
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
