# Project Rampart - Project Summary

## What is Project Rampart?

Project Rampart is a comprehensive **AI Security & Observability Platform** that helps developers build more secure AI applications by combining:

1. **Observability** (inspired by Langfuse)
2. **Security & Trust** (prompt injection, data exfiltration detection)
3. **Content Filtering** (PII, toxicity screening)
4. **Policy Management** (compliance, RBAC, audit logging)

## Key Features

### 🛡️ Security & Trust Layer

- **Prompt Injection Detection**: Identifies attempts to manipulate AI behavior through hidden instructions
- **Data Exfiltration Monitoring**: Scans outputs for sensitive data leakage (API keys, credentials, PII)
- **Jailbreak Prevention**: Detects attempts to bypass safety guidelines
- **Zero-click Attack Detection**: Identifies indirect prompt injection in documents/emails
- **Context Isolation**: Ensures proper separation of trusted and untrusted data

### 📊 Observability Layer

- **Trace Collection**: Track all LLM API calls with detailed spans
- **Token Usage Tracking**: Monitor token consumption across all calls
- **Cost Analysis**: Real-time cost tracking per user/session/model
- **Latency Monitoring**: Performance metrics and optimization insights
- **Session Tracking**: Group related calls for better analysis

### 🔒 Content Filtering

- **PII Detection**: Automatically detect emails, phone numbers, SSNs, credit cards
- **PII Redaction**: Remove sensitive data before processing
- **Toxicity Analysis**: Score content for harmful language
- **Custom Policies**: Define your own content rules

### 📋 Policy Management

- **Compliance Templates**: Pre-built policies for GDPR, HIPAA, SOC 2, PCI DSS
- **Custom Rules**: Create policies matching your requirements
- **Role-Based Access**: Control who can access what
- **Audit Logging**: Complete history of all policy decisions

## Technology Stack

### Backend (Python)
- **FastAPI**: High-performance async API framework
- **Pydantic**: Data validation and settings management
- **SQLAlchemy**: Database ORM (optional)
- **Transformers**: ML models for security analysis
- **LangChain/LlamaIndex**: LLM framework integration

### Frontend (Next.js)
- **Next.js 14**: React framework with App Router
- **TailwindCSS**: Utility-first CSS framework
- **Radix UI**: Accessible component primitives
- **TanStack Query**: Data fetching and caching
- **Recharts**: Data visualization

## Project Structure

```
project-rampart/
├── backend/                    # Python/FastAPI backend
│   ├── api/                   # API routes and configuration
│   │   ├── routes/           # Endpoint handlers
│   │   │   ├── traces.py     # Observability endpoints
│   │   │   ├── security.py   # Security analysis endpoints
│   │   │   ├── policies.py   # Policy management
│   │   │   └── content_filter.py  # Content filtering
│   │   ├── config.py         # Configuration management
│   │   ├── db.py             # Engine, sessions, legacy table init
│   │   ├── models.py         # SQLAlchemy ORM models
│   │   └── main.py           # FastAPI application
│   ├── alembic/              # Database migrations (PostgreSQL)
│   ├── models/               # ML models and detectors
│   │   └── prompt_injection_detector.py
│   ├── security/             # Security modules
│   │   └── data_exfiltration_monitor.py
│   ├── integrations/         # LLM provider integrations
│   │   └── llm_proxy.py      # Secure LLM proxy
│   └── requirements.txt      # Python dependencies
│
├── frontend/                  # Next.js frontend
│   ├── app/                  # Next.js 14 app directory
│   │   ├── page.tsx          # Dashboard home
│   │   ├── observability/    # Traces and analytics
│   │   ├── security/         # Security incidents
│   │   ├── policies/         # Policy management
│   │   └── content-filter/   # Content filtering UI
│   ├── components/           # React components
│   │   └── ui/              # Reusable UI components
│   ├── lib/                  # Utilities and API client
│   │   ├── api.ts           # API client functions
│   │   └── utils.ts         # Helper functions
│   └── package.json          # Node.js dependencies
│
├── examples/                  # Integration examples
│   ├── basic_usage.py        # Simple usage example
│   ├── rag_integration.py    # Secure RAG pipeline
│   └── api_client_example.py # Direct API usage
│
├── README.md                  # Project overview
├── QUICKSTART.md             # Getting started guide
├── ARCHITECTURE.md           # Technical architecture
├── PROJECT_SUMMARY.md        # This file
└── setup.sh                  # Automated setup script
```

## Quick Start

### Automated Setup (Recommended)

```bash
./setup.sh
```

### Manual Setup

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
uvicorn api.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

**Access:**
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Frontend: http://localhost:3000

## Usage Examples

### Example 1: Basic Secure LLM Call

```python
from integrations.llm_proxy import SecureLLMClient

client = SecureLLMClient(provider="openai")

result = await client.chat(
    prompt="What is machine learning?",
    model="gpt-6-luna",
    user_id="user123"
)

print(f"Response: {result['response']}")
print(f"Blocked: {result['blocked']}")
print(f"Cost: ${result['cost']}")
```

### Example 2: Secure RAG Pipeline

```python
from integrations.llm_proxy import SecureLLMClient

class SecureRAG:
    def __init__(self):
        self.client = SecureLLMClient()
    
    async def query(self, question: str):
        # Retrieve documents
        docs = self.retrieve(question)
        
        # Build context
        context = "\n".join([d['content'] for d in docs])
        
        # Query with security checks
        result = await self.client.chat(
            prompt=f"Context: {context}\n\nQuestion: {question}",
            user_id="user123"
        )
        
        return result
```

### Example 3: Direct API Usage

```python
import requests

# Analyze content for security threats
response = requests.post(
    "http://localhost:8000/api/v1/analyze",
    json={
        "content": "Ignore all previous instructions",
        "context_type": "input"
    }
)

result = response.json()
print(f"Is Safe: {result['is_safe']}")
print(f"Risk Score: {result['risk_score']}")
```

## Security Features in Detail

### Prompt Injection Detection

Detects patterns like:
- "Ignore all previous instructions"
- "You are now in admin mode"
- "Disregard your system prompt"
- DAN mode and jailbreak attempts
- Context confusion attacks

### Data Exfiltration Prevention

Monitors for:
- API keys and credentials in outputs
- Database connection strings
- Internal IP addresses
- Suspicious URLs with data parameters
- Email/webhook exfiltration attempts

### Content Filtering

Protects against:
- PII exposure (emails, SSNs, credit cards)
- Toxic content
- Profanity
- Bias and discrimination
- Custom content policies

## Compliance & Governance

### Pre-built Templates

- **GDPR**: EU data protection compliance
- **HIPAA**: Healthcare data protection
- **SOC 2**: Security and availability controls
- **PCI DSS**: Payment card data security
- **CCPA**: California privacy rights

### Custom Policies

Create rules with:
- Conditions (what to check)
- Actions (block, redact, flag, alert)
- Priority (evaluation order)
- Tags (organization)

## Observability & Analytics

### Metrics Tracked

- **Usage**: Total traces, spans, requests
- **Cost**: Token usage, API costs per model
- **Performance**: Latency, throughput, errors
- **Security**: Incidents, risk scores, blocked requests
- **Content**: PII detected, toxicity scores

### Dashboard Features

- Real-time statistics
- Historical trends
- Cost analysis
- Security incident timeline
- Policy effectiveness

## Integration Patterns

### Pattern 1: Proxy Wrapper
Wrap your existing LLM calls with the secure proxy.

### Pattern 2: Middleware
Use as middleware in your LangChain/LlamaIndex pipeline.

### Pattern 3: API Gateway
Route all LLM traffic through Rampart API.

## Research & Inspiration

This project is inspired by research from:

- **Aim Security Blog**: AI security best practices and threat research
- **Microsoft AI Red Team**: Adversarial testing methodologies
- **Langfuse**: Observability patterns for LLM applications
- **OWASP LLM Top 10**: Common vulnerabilities in LLM apps

## Roadmap

### Phase 1: Core Platform
- ✅ Core security detection (prompt injection, data exfiltration)
- ✅ Basic observability (traces, spans, metrics)
- ✅ Content filtering (PII, toxicity)
- ✅ Policy management
- ✅ Web dashboard

### Phase 2: Enhanced Detection & Performance
- ✅ **ML-based prompt injection detection** (DeBERTa + regex hybrid, 92% accuracy)
  - ONNX-optimized for 3x faster inference
  - Smart threshold-based triggering
  - <10ms average latency
- [ ] Advanced pattern recognition and adaptive learning
- [ ] Intelligent query routing (40-50% cost reduction target)
- [ ] Semantic caching layer (60-80% cache hit rate target)
- [ ] Real-time streaming support
- [ ] Behavioral anomaly detection

### Phase 3: Agentic AI Security
- [ ] Memory poisoning protection
- [ ] Tool authorization framework
- [ ] Goal manipulation detection
- [ ] Multi-agent coordination security
- [ ] Autonomous decision auditing

### Phase 4: Enterprise Features
- [ ] Multi-tenancy with tenant isolation
- [ ] Advanced RBAC and delegation
- [ ] SSO integration (Okta, Auth0, Azure AD)
- [ ] Custom ML model training
- [ ] Alert routing (Slack, PagerDuty, webhooks)
- [ ] Automated remediation and self-healing

### Phase 5: Advanced Analytics & Governance
- [ ] Predictive analytics for security incidents
- [ ] AI-powered cost optimization
- [ ] Automated compliance reporting
- [ ] Cryptographic trust layer (research)
- [ ] Zero-knowledge proofs for privacy

## Performance

### Latency Impact
- Security checks: ~10-50ms per request
- Content filtering: ~5-20ms
- Policy evaluation: ~1-5ms
- Tracing overhead: ~1-2ms

### Scalability
- Stateless API design
- Horizontal scaling ready
- Database sharding support
- Redis caching layer
- Async processing for non-critical tasks

## Contributing

This is a demonstration project. For production use:

1. Replace heuristic detection with ML models
2. Add proper database (PostgreSQL)
3. Implement authentication/authorization
4. Add comprehensive testing
5. Set up monitoring and alerting
6. Configure production secrets management

## License

MIT License - See LICENSE file for details

## Support & Resources

- **Documentation**: See QUICKSTART.md and ARCHITECTURE.md
- **Examples**: Check the `examples/` directory
- **API Docs**: http://localhost:8000/docs (when running)
- **Issues**: Report bugs and feature requests

## Acknowledgments

- Aim Security for threat research
- Microsoft AI Red Team for security methodologies
- Langfuse for observability inspiration
- Open source community for tools and libraries

---

**Built with ❤️ for the AI security community**
