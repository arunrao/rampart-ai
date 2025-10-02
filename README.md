# Project Rampart 🛡️

**AI Security & Observability Platform**

Project Rampart is a comprehensive security and observability solution for AI applications that combines:
- 🔍 **Observability** (Langfuse-inspired tracing & monitoring)
- 🛡️ **Security & Trust** (Prompt injection detection, data exfiltration monitoring)
- 🔒 **Content Filtering** (PII detection, toxicity screening)
- 📋 **Policy Management** (RBAC, compliance templates, audit logging)

## Architecture

### Backend (Python/FastAPI)
- Content filtering & ML models (transformers, classifiers)
- Policy engine execution
- Security analysis (prompt injection, data exfiltration)
- Integration with LLM APIs (OpenAI, Anthropic, etc.)
- RAG pipeline instrumentation

### Frontend (Next.js 14)
- Real-time dashboard
- Policy configuration interface
- Alert management
- Observability visualizations
- API gateway/middleware

## Core Components

### 1. Observability Layer
- Trace collection for LLM calls
- Token usage & cost tracking
- Latency monitoring
- User session tracking
- RAG retrieval logging

### 2. Security & Trust Layer
- **Prompt Injection Detection**: Analyze inputs for hidden instructions
- **Scope Violation Prevention**: Monitor for mixing trusted/untrusted data
- **Data Exfiltration Detection**: Scan outputs for sensitive data leakage
- **Context Isolation Enforcement**: Ensure proper data provenance tracking
- **Zero-click Attack Prevention**: Detect suspicious indirect prompts

### 3. Content Filtering
- PII detection & redaction
- Toxicity/bias detection
- Custom content policies
- Contextual appropriateness checks

### 4. Policy Management
- Role-based access controls
- Allowlist/blocklist management
- Custom rule engine
- Compliance templates (GDPR, HIPAA, SOC 2)
- Audit logging

### 5. Response & Mitigation
- Real-time blocking/redaction
- Alert routing
- Automated remediation workflows
- Incident response playbooks

## Quick Start

### Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn api.main:app --reload
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### Environment Variables
- Backend: copy `backend/.env.example` to `backend/.env` and fill values
  - `DATABASE_URL`, `REDIS_URL`
  - `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` (optional)
  - Tracing: `OTEL_EXPORTER_OTLP_ENDPOINT` (e.g., `http://localhost:4317`)
  - Feature flags and defaults: `USE_MODEL_TOXICITY`, `USE_PRESIDIO_PII`, `CUSTOM_PII_PATTERNS`, etc.
- Frontend: copy `frontend/.env.example` to `frontend/.env.local`
  - `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000/api/v1`)

## Resources

- [Aim Security Blog](https://www.aim.security/blog)
- [Microsoft AI Red Team](https://www.microsoft.com/en-us/security/blog/microsoft-security-intelligence/)
- [Langfuse](https://langfuse.com/)

## License

MIT License
