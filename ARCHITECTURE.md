# Project Rampart - Architecture Documentation

## Overview

Project Rampart is a hybrid Python/Next.js platform that provides comprehensive security and observability for AI applications. It combines multiple security layers with real-time monitoring to protect against AI-specific threats.

## System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        Frontend Layer                         │
│                    (Next.js 14 + React)                       │
├──────────────────────────────────────────────────────────────┤
│  Dashboard  │  Security  │  Policies  │  Content Filter      │
│  Analytics  │  Incidents │  Management│  Observability       │
└──────────────────────────────────────────────────────────────┘
                              │
                              ↓ REST API
┌──────────────────────────────────────────────────────────────┐
│                         API Layer                             │
│                      (FastAPI + Pydantic)                     │
├──────────────────────────────────────────────────────────────┤
│  /traces    │  /analyze   │  /policies  │  /filter           │
│  /spans     │  /incidents │  /evaluate  │  /pii              │
└──────────────────────────────────────────────────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ↓                 ↓                 ↓
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Security Layer │  │  Policy Engine  │  │ Content Filter  │
├─────────────────┤  ├─────────────────┤  ├─────────────────┤
│ • Prompt        │  │ • Rule Engine   │  │ • PII Detection │
│   Injection     │  │ • RBAC          │  │ • Toxicity      │
│ • Data Exfil    │  │ • Compliance    │  │ • Redaction     │
│ • Jailbreak     │  │ • Audit Logs    │  │ • Validation    │
│ • Zero-click    │  │ • Templates     │  │ • Scoring       │
└─────────────────┘  └─────────────────┘  └─────────────────┘
            │                 │                 │
            └─────────────────┼─────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│                    Observability Layer                        │
├──────────────────────────────────────────────────────────────┤
│  • Trace Collection    • Token Tracking    • Cost Analysis   │
│  • Span Management     • Latency Monitor   • Session Track   │
└──────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌──────────────────────────────────────────────────────────────┐
│                      Storage Layer                            │
├──────────────────────────────────────────────────────────────┤
│  PostgreSQL  │  Redis Cache  │  Time-Series DB (optional)    │
└──────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Security & Trust Layer

#### Prompt Injection Detector
**Location**: `backend/models/prompt_injection_detector.py`

Detects various types of prompt injection attacks:
- **Direct Instruction Override**: "Ignore previous instructions"
- **Role Manipulation**: "You are now in admin mode"
- **Context Confusion**: Delimiter injection, context switching
- **Jailbreak Attempts**: DAN mode, unrestricted mode requests
- **Zero-click Attacks**: Conditional instructions in content
- **Scope Violations**: Attempts to access system prompts

**Detection Methods**:
- Pattern-based detection with regex
- Context marker analysis
- Severity scoring (0.0 - 1.0)
- Multi-pattern aggregation

**Output**:
```python
{
    "is_injection": bool,
    "confidence": float,
    "detected_patterns": [
        {
            "name": str,
            "severity": float,
            "description": str,
            "matched_text": str
        }
    ],
    "risk_score": float,
    "recommendation": str  # BLOCK, FLAG, MONITOR, ALLOW
}
```

#### Data Exfiltration Monitor
**Location**: `backend/security/data_exfiltration_monitor.py`

Monitors LLM outputs for data leakage:
- **Credential Detection**: API keys, passwords, tokens, private keys
- **Infrastructure Exposure**: Database URLs, internal IPs
- **Exfiltration Methods**: URL embedding, email commands, webhooks
- **Suspicious Patterns**: Base64 encoding, curl commands, fetch requests

**Detection Methods**:
- Regex pattern matching for sensitive data
- URL analysis with parameter inspection
- Trusted domain whitelisting
- Risk scoring based on multiple factors

**Output**:
```python
{
    "has_exfiltration_risk": bool,
    "risk_score": float,
    "sensitive_data_found": [...],
    "exfiltration_indicators": [...],
    "urls_found": [...],
    "recommendation": str  # BLOCK, REDACT, FLAG, ALLOW
}
```

### 2. Content Filtering Layer

**Location**: `backend/api/routes/content_filter.py`

#### PII Detection
Detects and redacts personally identifiable information:
- Email addresses
- Phone numbers (US format)
- Social Security Numbers
- Credit card numbers
- IP addresses

#### Toxicity Analysis
Analyzes content for harmful language:
- General toxicity
- Severe toxicity
- Obscenity
- Threats
- Insults
- Identity attacks

**Note**: Current implementation uses heuristics. For production, integrate:
- [Presidio](https://github.com/microsoft/presidio) for PII
- [Detoxify](https://github.com/unitaryai/detoxify) for toxicity
- [Perspective API](https://perspectiveapi.com/) for advanced analysis

### 3. Policy Management Layer

**Location**: `backend/api/routes/policies.py`

#### Policy Types
- **Content Filter**: PII, toxicity, profanity rules
- **Rate Limit**: Request throttling
- **Access Control**: RBAC, permissions
- **Data Governance**: Retention, privacy
- **Compliance**: GDPR, HIPAA, SOC 2

#### Policy Structure
```python
{
    "name": str,
    "policy_type": PolicyType,
    "rules": [
        {
            "condition": str,  # Rule expression
            "action": PolicyAction,  # ALLOW, BLOCK, REDACT, FLAG, ALERT
            "priority": int  # Higher = evaluated first
        }
    ],
    "enabled": bool,
    "tags": [str]
}
```

#### Compliance Templates
Pre-built policies for common frameworks:
- **GDPR**: EU data protection
- **HIPAA**: Healthcare data protection
- **SOC 2**: Service organization controls
- **PCI DSS**: Payment card security
- **CCPA**: California privacy

### 4. Observability Layer

**Location**: `backend/api/routes/traces.py`

#### Trace Collection
Langfuse-inspired tracing for LLM calls:
- **Traces**: Top-level execution context
- **Spans**: Individual operations (LLM call, retrieval, tool use)
- **Metadata**: User, session, custom tags

#### Metrics Tracked
- Token usage (input/output)
- Cost per call
- Latency (end-to-end and per-span)
- Success/error rates
- Security incidents per trace

#### Data Model
```python
Trace:
  - id, session_id, user_id
  - total_tokens, total_cost, total_latency_ms
  - status, created_at, updated_at

Span:
  - id, trace_id, parent_span_id
  - span_type (llm, retrieval, tool, agent)
  - input_data, output_data
  - tokens_used, cost, latency_ms
  - status, error_message
```

### 5. LLM Proxy Layer

**Location**: `backend/integrations/llm_proxy.py`

Wraps LLM API calls with security and observability:

#### Request Flow
```
1. User Request
   ↓
2. Input Security Check
   - Prompt injection detection
   - Policy evaluation
   ↓
3. LLM API Call (if allowed)
   - OpenAI, Anthropic, etc.
   ↓
4. Output Security Check
   - Data exfiltration scan
   - Content filtering
   ↓
5. Response (potentially redacted/blocked)
```

#### Features
- Automatic tracing
- Cost calculation
- Security checks (opt-in/out)
- Error handling
- Retry logic (future)
- Rate limiting (future)

## Frontend Architecture

### Technology Stack
- **Framework**: Next.js 14 (App Router)
- **UI Library**: React 18
- **Styling**: Tailwind CSS
- **Components**: Radix UI primitives
- **State Management**: TanStack Query (React Query)
- **API Client**: Axios

### Page Structure
```
/                    → Dashboard (overview, stats)
/observability       → Traces, spans, analytics
/security            → Incidents, threat analysis
/policies            → Policy management, templates
/content-filter      → PII detection, toxicity testing
```

### Key Components
- **Card Components**: Reusable stat cards
- **Badge Components**: Status indicators
- **Button Components**: Action triggers
- **API Hooks**: React Query wrappers

### Real-time Updates
- Polling every 5 seconds for stats
- Automatic cache invalidation
- Optimistic updates for mutations

## Data Flow

### Secure LLM Call Flow
```
1. Application → LLM Proxy
   {
     messages: [...],
     model: "gpt-4",
     user_id: "user123"
   }

2. LLM Proxy → Security Analyzer
   - Check for prompt injection
   - Evaluate policies
   - Decision: ALLOW/BLOCK/FLAG

3. If ALLOW → LLM Provider API
   - OpenAI/Anthropic/etc.
   - Get response

4. Response → Data Exfiltration Monitor
   - Scan for sensitive data
   - Check for exfiltration attempts
   - Decision: ALLOW/REDACT/BLOCK

5. Final Response → Application
   {
     response: "...",
     blocked: false,
     security_checks: {...},
     latency_ms: 234,
     cost: 0.0012
   }

6. Async → Observability Layer
   - Create trace
   - Record span
   - Update metrics
```

## Security Considerations

### Threat Model

#### Threats Addressed
1. **Prompt Injection**: Malicious instructions in user input
2. **Jailbreaking**: Attempts to bypass safety guidelines
3. **Data Exfiltration**: Leaking sensitive data through outputs
4. **PII Exposure**: Accidental disclosure of personal information
5. **Context Confusion**: Mixing trusted/untrusted data
6. **Zero-click Attacks**: Indirect prompt injection via documents

#### Defense Layers
1. **Input Validation**: Pre-flight security checks
2. **Policy Enforcement**: Rule-based blocking/redaction
3. **Output Scanning**: Post-processing security analysis
4. **Audit Logging**: Complete trace of all operations
5. **Alerting**: Real-time incident notifications

### Best Practices

#### For Developers
1. Always use the LLM proxy, never call APIs directly
2. Set appropriate `user_id` for all requests
3. Review security incidents regularly
4. Keep policies updated
5. Monitor cost and token usage

#### For Security Teams
1. Configure policies based on risk tolerance
2. Set up alert routing for critical incidents
3. Review false positives and tune detection
4. Maintain trusted domain whitelist
5. Conduct regular security audits

## Performance Considerations

### Latency Impact
- Security checks add ~10-50ms per request
- Content filtering: ~5-20ms
- Policy evaluation: ~1-5ms
- Tracing overhead: ~1-2ms

### Optimization Strategies
1. **Caching**: Cache policy evaluations
2. **Async Processing**: Move non-critical checks to background
3. **Batch Processing**: Group similar operations
4. **Model Optimization**: Use efficient ML models
5. **Database Indexing**: Optimize query performance

### Scalability
- **Horizontal Scaling**: Stateless API servers
- **Database Sharding**: Partition by user/tenant
- **Caching Layer**: Redis for hot data
- **Queue System**: Celery for async tasks
- **Load Balancing**: Distribute traffic

## Integration Patterns

### Pattern 1: Direct Proxy Usage
```python
from integrations.llm_proxy import SecureLLMClient

client = SecureLLMClient()
result = await client.chat(prompt="...", user_id="...")
```

### Pattern 2: Middleware Integration
```python
# In your LangChain/LlamaIndex pipeline
from integrations.llm_proxy import LLMProxy

proxy = LLMProxy()
# Wrap your LLM calls with proxy.complete()
```

### Pattern 3: API Gateway
```
Your App → Rampart API → LLM Provider
```

## Future Enhancements

### Planned Features
1. **ML-based Detection**: Replace heuristics with trained models
2. **Real-time Streaming**: Support for streaming LLM responses
3. **Multi-tenancy**: Tenant isolation and management
4. **Advanced Analytics**: Anomaly detection, trend analysis
5. **Integration Hub**: Pre-built connectors for popular frameworks
6. **Alert Routing**: Slack, PagerDuty, email notifications
7. **Automated Remediation**: Self-healing policies
8. **Compliance Reports**: Automated audit reports

### Research Areas
1. **Adversarial Testing**: Red team automation
2. **Context Isolation**: Better provenance tracking
3. **Semantic Analysis**: Understanding intent vs. surface patterns
4. **Privacy-Preserving**: Federated learning for detection models

## References

### Research & Resources
- [Aim Security Blog](https://www.aim.security/blog)
- [Microsoft AI Red Team](https://www.microsoft.com/en-us/security/blog)
- [OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- [Langfuse Documentation](https://langfuse.com/docs)
- [Prompt Injection Primer](https://simonwillison.net/2023/Apr/14/worst-that-can-happen/)

### Related Projects
- **Langfuse**: Observability inspiration
- **Rebuff**: Prompt injection detection
- **Presidio**: PII detection and anonymization
- **LangChain**: LLM application framework
- **LlamaIndex**: RAG framework
