# 🚀 START HERE - Project Rampart

Welcome to **Project Rampart**! This is your starting point.

## What is This?

Project Rampart is a comprehensive **AI Security & Observability Platform** with ML-based detection that helps you build more secure AI applications:

- 🛡️ **Hybrid prompt injection detection** - 92% accuracy with DeBERTa ML + regex (< 10ms avg)
- 🔒 **Data exfiltration monitoring** - Stops credential and PII leaks
- 🚫 **Jailbreak prevention** - Detects DAN mode and bypass attempts
- 📊 **Performance & cost tracking** - Complete observability
- 🔍 **PII detection** - GLiNER ML models (93% accuracy) + regex fallback

## Quick Start (3 Steps)

### Step 1: Run Setup
```bash
./setup.sh
```
This installs all dependencies for both backend and frontend.

### Step 2: Environment setup
Copy env examples and fill values.
```bash
# Backend env
cp backend/.env.example backend/.env
# Frontend env
cp frontend/.env.example frontend/.env.local
```

Key variables:
- Backend `backend/.env`:
  - `DATABASE_URL`, `REDIS_URL`
  - `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` (optional)
  - **Hybrid Prompt Injection Detection (DeBERTa + Regex):**
    - `PROMPT_INJECTION_DETECTOR=hybrid` (hybrid/deberta/regex - default: hybrid)
    - `PROMPT_INJECTION_USE_ONNX=true` (ONNX optimization, 3x faster)
    - `PROMPT_INJECTION_FAST_MODE=false` (skip DeBERTa for ultra-fast)
    - `PROMPT_INJECTION_THRESHOLD=0.75` (confidence threshold 0.0-1.0)
  - **GLiNER PII Detection:**
    - `PII_DETECTION_ENGINE=hybrid` (hybrid/gliner/regex - default: hybrid)
    - `PII_MODEL_TYPE=balanced` (edge/balanced/accurate - default: balanced)
    - `PII_CONFIDENCE_THRESHOLD=0.7` (0.0-1.0)
  - `OTEL_EXPORTER_OTLP_ENDPOINT` (Jaeger OTLP, e.g. http://localhost:4317)
- Frontend `frontend/.env.local`:
  - `NEXT_PUBLIC_API_URL` (defaults to http://localhost:8000/api/v1)

### Step 2b: Add API Keys (Optional)
```bash
# Edit backend/.env and add your keys
nano backend/.env

# Add these lines:
OPENAI_API_KEY=sk-your-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### Step 3: Start the Application (Dev mode)
```bash
# Terminal 1 - Backend
cd backend
source venv/bin/activate
uvicorn api.main:app --reload

# Terminal 2 - Frontend
cd frontend
npm run dev
```

## Access the Application

- **Dashboard**: http://localhost:3000
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## What Can You Do?

### 1. Test Security Features
Navigate to http://localhost:3000/security to:
- View security incidents
- See threat detection in action
- Monitor risk scores

### 2. Monitor LLM Calls
Navigate to http://localhost:3000/observability to:
- Track all LLM API calls
- Monitor token usage and costs
- View performance metrics

### 3. Manage Policies
Navigate to http://localhost:3000/policies to:
- Create custom policies
- Use compliance templates (GDPR, HIPAA, SOC 2)
- Enable/disable policies

### 4. Filter Content
Navigate to http://localhost:3000/content-filter to:
- Test PII detection
- Analyze toxicity
- See redaction in action

## Try the Examples

```bash
cd examples

# Example 1: Basic secure LLM calls
python basic_usage.py

# Example 2: Secure RAG pipeline
python rag_integration.py

# Example 3: Direct API usage
python api_client_example.py
```

## Project Structure

```
project-rampart/
├── backend/          # Python/FastAPI backend
│   ├── api/         # API routes
│   ├── models/      # ML models & detectors
│   ├── security/    # Security modules
│   └── tests/       # Test files
├── frontend/        # Next.js frontend
│   ├── app/         # Pages
│   ├── components/  # UI components
│   └── lib/         # Utilities
├── examples/        # Usage examples
└── docs/           # Documentation
```

## Documentation

- **QUICKSTART.md** - Detailed setup guide
- **PROJECT_SUMMARY.md** - Feature overview
- **ARCHITECTURE.md** - Technical details
- **TESTING_GUIDE.md** - Testing strategies
- **DEPLOYMENT_CHECKLIST.md** - Production guide

## Key Features

### 🛡️ Security
- Prompt injection detection
- Data exfiltration monitoring
- Jailbreak prevention
- Zero-click attack detection

### 📊 Observability
- Trace collection
- Token & cost tracking
- Latency monitoring
- Analytics dashboard

### 🔒 Content Filtering
- PII detection & redaction
- Toxicity analysis
- Custom policies

### 📋 Policy Management
- Compliance templates
- Custom rules
- Audit logging

## Common Commands

```bash
# Start with Docker (includes GLiNER + DeBERTa models)
docker-compose up -d

# Test GLiNER PII detection
cd backend && python test_gliner_pii.py

# Test DeBERTa hybrid prompt injection detection
cd backend && python test_deberta_integration.py

# Run security tests
make test

# View logs
docker-compose logs -f backend

# Stop services
docker-compose down
```

**First Run**: 
- GLiNER models download automatically (~200MB, 30-60 seconds)
- DeBERTa model downloads on first detection (~300MB ONNX-optimized, pre-loaded in Docker)

## Observability & Metrics

- **Tracing (Jaeger)**
  - We export OTEL traces to Jaeger by default in Docker.
  - UI: http://localhost:16686
  - Spans around `POST /api/v1/filter`: `content_filter`, `pii_detection`, `pii_redaction`, `toxicity_analysis`.

- **Metrics (Prometheus)**
  - Endpoint: `GET http://localhost:8000/metrics`
  - Includes counters/histograms for requests, unsafe rate, latency, PII counts.

## Policy Defaults (CRUD)

You can store org-wide content filter defaults in Postgres:

- Get defaults
```bash
curl -s http://localhost:8000/api/v1/policies/defaults/content-filter | jq
```

- Set defaults (partial update)
```bash
curl -s -X PUT http://localhost:8000/api/v1/policies/defaults/content-filter \
  -H "Content-Type: application/json" \
  -d '{
    "redact": true,
    "use_presidio_pii": true,
    "toxicity_threshold": 0.2,
    "custom_pii_patterns": {"order_id": "ORD-[A-Z]{3}-\\d{5}"}
  }' | jq
```

Defaults are merged with each request body; request fields override stored defaults.

## Need Help?

1. **Read the docs**: Start with QUICKSTART.md
2. **Check examples**: See the `examples/` directory
3. **API documentation**: http://localhost:8000/docs
4. **Review tests**: See `backend/tests/` for usage patterns

## Next Steps

1. ✅ Run `./setup.sh` (installs dependencies)
2. ✅ Configure `.env` (see docker-compose.yml for defaults)
3. ✅ `docker-compose up -d` (downloads GLiNER models on first run)
4. ✅ Open http://localhost:3000
5. ✅ Test GLiNER: `cd backend && python test_gliner_pii.py`
6. ✅ Try examples in `examples/` directory
7. ✅ Read README.md for full feature list
8. ✅ Integrate with your AI application

## Resources

- **Aim Security Blog**: https://www.aim.security/blog
- **Microsoft AI Red Team**: https://www.microsoft.com/en-us/security/blog
- **OWASP LLM Top 10**: https://owasp.org/www-project-top-10-for-large-language-model-applications/

---

**Ready to secure your AI applications?**

**Start with: `./setup.sh`** 🚀

For questions, see the documentation or check the examples!
