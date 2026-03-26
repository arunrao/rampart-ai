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

# Create model cache directory
RUN mkdir -p /app/.cache/huggingface

# Pre-download GLiNER edge model (ONNX UINT8, ~197MB) so there is no cold-start
# download on first request.  The knowledgator edge model is PII-specialized and
# ships a quantized ONNX file — faster and smaller than the old gravitee default.
RUN python -c "\
from models.pii_detector_gliner import GLiNERPIIDetector; \
d = GLiNERPIIDetector(model_type='edge', use_onnx=True); \
_ = d.model; \
print('✓ GLiNER edge model (ONNX) pre-downloaded')" \
  || echo "⚠ GLiNER pre-download skipped (will download on first use)"

# Toxicity model (unitary/toxic-bert, ~420MB, multi-label Jigsaw fine-tune)
# Replaces citizenlab/distilbert which had false positives on common short phrases.
# Pre-downloading eliminates cold-start download delay.
RUN python -c "\
from models.toxicity_detector import detect_toxicity; \
detect_toxicity('warmup'); \
print('✓ Toxicity model (unitary/toxic-bert) pre-downloaded')" \
  || echo "⚠ Toxicity pre-download skipped (will download on first use)"

# DeBERTa model warmup (~300MB with ONNX)
# Pre-downloads ProtectAI DeBERTa model for prompt injection detection
# This adds ~300MB to image size but eliminates first-run download (3-5s cold start)
# Recommended for production environments
RUN python -c "from transformers import AutoTokenizer, AutoModelForSequenceClassification; \
    model_name = 'protectai/deberta-v3-base-prompt-injection-v2'; \
    AutoTokenizer.from_pretrained(model_name); \
    AutoModelForSequenceClassification.from_pretrained(model_name); \
    print('✓ DeBERTa model pre-downloaded')" || echo "⚠ DeBERTa pre-download skipped (will download on first use)"

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

# Run the application
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
