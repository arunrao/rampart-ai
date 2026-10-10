FROM python:3.11-slim

WORKDIR /app

# Install minimal system dependencies and clean up in same layer
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && pip install --no-cache-dir --upgrade pip \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
# Install CPU-only PyTorch first (saves ~3GB by excluding CUDA libraries)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y gcc \
    && apt-get autoremove -y

# Copy application code
COPY . .

# Model cache lives under /app so the non-root runtime user below can read it.
# (Without HF_HOME the downloads landed in /root/.cache and were never hit at runtime.)
ENV HF_HOME=/app/.cache/huggingface
RUN mkdir -p /app/.cache/huggingface

# Pre-download the models at the commit SHAs pinned in models/pinned_revisions.py so there
# is no cold-start download and a Hub-side change cannot alter what the image executes.
# GLiNER edge: full snapshot (GLiNER.from_pretrained snapshots the whole repo, so any
# excluded file forces a network fetch at runtime); toxic-bert / DeBERTa: safetensors
# only (the .bin duplicates add ~740MB for nothing).
RUN python -c "\
from huggingface_hub import snapshot_download; \
from models.pinned_revisions import PINNED_REVISIONS as P; \
skip = ['*.bin', 'flax_model*', 'tf_model*', 'rust_model*']; \
snapshot_download('knowledgator/gliner-pii-edge-v1.0', revision=P['knowledgator/gliner-pii-edge-v1.0']); \
snapshot_download('unitary/toxic-bert', revision=P['unitary/toxic-bert'], ignore_patterns=skip); \
snapshot_download('protectai/deberta-v3-base-prompt-injection-v2', revision=P['protectai/deberta-v3-base-prompt-injection-v2'], ignore_patterns=skip); \
print('✓ Pinned models pre-downloaded')" \
  || echo "⚠ Model pre-download skipped (will download on first use)"

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app \
    && chown -R app:app /app/.cache
USER app

# Expose port
EXPOSE 8000

# Extended health check with startup period for model loading
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=2 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"

# Apply pending Alembic migrations before the workers start (docker-entrypoint.sh).
ENTRYPOINT ["./docker-entrypoint.sh"]

# Run with 2 workers — two independent GIL environments so concurrent requests
# don't queue behind each other's ML inference. Each worker loads its own model
# copies; c5.xlarge (8 GB RAM) has enough headroom for 2 × ~940 MB model sets.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
