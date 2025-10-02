# 🚀 START HERE - Project Rampart

Welcome to **Project Rampart**! This is your starting point.

## What is This?

Project Rampart is a comprehensive **AI Security & Observability Platform** that helps you build more secure AI applications by detecting:
- 🛡️ Prompt injection attacks
- 🔒 Data exfiltration attempts
- 🚫 Jailbreak attempts
- 📊 Performance & cost metrics
- 🔍 PII and sensitive data

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
  - `OTEL_EXPORTER_OTLP_ENDPOINT` (Jaeger OTLP, e.g. http://localhost:4317)
  - Flags/defaults: `USE_MODEL_TOXICITY`, `USE_PRESIDIO_PII`, `CUSTOM_PII_PATTERNS`
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
# Start with Docker
make docker-up

# Rebuild images after backend changes
make docker-rebuild

# Run tests
make test

# Stop services
make stop

# Clean build artifacts
make clean

# View help
make help
```

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

1. ✅ Run `./setup.sh`
2. ✅ Start backend and frontend
3. ✅ Open http://localhost:3000
4. ✅ Try the examples
5. ✅ Read ARCHITECTURE.md for deep dive
6. ✅ Integrate with your AI application

## Resources

- **Aim Security Blog**: https://www.aim.security/blog
- **Microsoft AI Red Team**: https://www.microsoft.com/en-us/security/blog
- **OWASP LLM Top 10**: https://owasp.org/www-project-top-10-for-large-language-model-applications/

---

**Ready to secure your AI applications?**

**Start with: `./setup.sh`** 🚀

For questions, see the documentation or check the examples!
