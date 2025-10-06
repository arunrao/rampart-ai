# 🚀 Rampart Demo Applications

This directory contains comprehensive demo applications showing how to integrate with Project Rampart's security APIs.

## 📋 Available Demos

### 1. Python Demo (`demo_app.py`)
**Full-featured Python client demonstration**
- Complete security analysis workflow
- PII detection and filtering
- Performance metrics and usage tracking
- Error handling and best practices

```bash
# Run Python demo
cd demo
python demo_app.py
```

### 2. Node.js Demo (`demo_app.js`)
**JavaScript/Node.js client demonstration**
- Same features as Python demo
- Native Node.js HTTP client
- Async/await patterns
- Cross-platform compatibility

```bash
# Run Node.js demo
cd demo
node demo_app.js
```

### 3. Web Demo (`web_demo.html`)
**Interactive browser-based demonstration**
- Real-time security analysis
- PII filtering interface
- No installation required
- Visual results display

```bash
# Open web demo
cd demo
open web_demo.html
# Or visit: file:///path/to/demo/web_demo.html
```

## 🔧 Setup Instructions

### Prerequisites
1. **Backend Running**: Ensure Rampart backend is running
   ```bash
   docker-compose up -d
   ```

2. **API Key**: Get your API key from the dashboard
   - Visit: http://localhost:3000/api-keys
   - Create a new API key with required permissions
   - Copy the key (starts with `rmp_live_`)

3. **Update Configuration**: Replace the API key in demo files
   ```python
   # In demo_app.py and demo_app.js
   API_KEY = "rmp_live_your_actual_key_here"
   ```

### Python Demo Setup
```bash
# No additional dependencies required (uses standard library)
python demo_app.py
```

### Node.js Demo Setup
```bash
# No additional dependencies required (uses built-in modules)
node demo_app.js
```

### Web Demo Setup
```bash
# Option 1: Serve via HTTP (Recommended - avoids CORS issues)
cd demo
python3 serve_demo.py
# Opens automatically at http://localhost:8081/web_demo.html

# Option 2: Open directly in browser (may have CORS issues)
open web_demo.html
```

## 🎯 Demo Features

### Security Analysis
- **Prompt Injection Detection**: Identifies attempts to manipulate AI systems
- **Data Exfiltration Prevention**: Detects suspicious data requests
- **Social Engineering Detection**: Identifies manipulation attempts
- **Risk Scoring**: Quantitative threat assessment (0.0 - 1.0)

### PII Filtering
- **Email Detection**: Identifies and redacts email addresses
- **Phone Number Detection**: Finds various phone number formats
- **SSN Detection**: Identifies Social Security Numbers
- **Credit Card Detection**: Finds credit card numbers
- **Custom PII Types**: Extensible detection system

### Performance Metrics
- **Response Time Tracking**: Measures API call latency
- **Usage Statistics**: Tracks requests, tokens, and costs
- **Rate Limit Monitoring**: Shows current rate limit status
- **Error Rate Analysis**: Monitors API reliability

## 📊 Example Outputs

### Security Analysis Result
```json
{
  "is_safe": false,
  "risk_score": 1.0,
  "threats_detected": [
    {
      "threat_type": "prompt_injection",
      "severity": "high",
      "confidence": 1.0,
      "description": "Potential prompt injection attack detected"
    }
  ],
  "processing_time_ms": 45.2
}
```

### PII Filtering Result
```json
{
  "original_content": "Contact john@example.com at (555) 123-4567",
  "filtered_content": "Contact [EMAIL_REDACTED] at [PHONE_REDACTED]",
  "pii_detected": [
    {"type": "email", "value": "john@example.com"},
    {"type": "phone", "value": "(555) 123-4567"}
  ],
  "processing_time_ms": 23.1
}
```

## 🔗 Integration Patterns

### Basic Security Check
```python
client = RampartClient(api_key)
result = client.analyze_security(user_input)
if not result.is_safe:
    # Block or flag content
    handle_security_threat(result.threats)
```

### PII Sanitization Pipeline
```python
# Step 1: Detect PII
filter_result = client.filter_content(content, redact=True)

# Step 2: Use sanitized content
safe_content = filter_result.filtered_content or content
process_content(safe_content)
```

### Combined Security Workflow
```python
# Multi-layer security check
security_result = client.analyze_security(content)
filter_result = client.filter_content(content)

if security_result.is_safe and filter_result.is_safe:
    # Content is safe to process
    final_content = filter_result.filtered_content or content
    process_safely(final_content)
else:
    # Block or request revision
    reject_content(security_result.threats)
```

## 🛠️ Customization

### Adding Custom Test Cases
```python
# In demo_app.py, add to test_cases list:
{
    "name": "Custom Test",
    "content": "Your test content here",
    "expected_safe": False
}
```

### Modifying API Configuration
```python
# Custom API settings
client = RampartClient(
    api_key="your_key",
    base_url="https://your-rampart-instance.com/api/v1"
)
```

### Error Handling Patterns
```python
try:
    result = client.analyze_security(content)
except Exception as e:
    if "rate limit" in str(e).lower():
        # Handle rate limiting
        time.sleep(1)
        retry_request()
    elif "invalid api key" in str(e).lower():
        # Handle authentication
        refresh_api_key()
    else:
        # Handle other errors
        log_error(e)
```

## 🔍 Troubleshooting

### Common Issues

**1. API Key Invalid**
```
Error: Invalid API key or expired token
```
- Solution: Get fresh API key from http://localhost:3000/api-keys

**2. Connection Refused**
```
Error: Network error: connect ECONNREFUSED
```
- Solution: Start backend with `docker-compose up -d`

**3. CORS Errors (Web Demo)**
```
Error: Access to fetch blocked by CORS policy
```
- Solution: Use the HTTP server instead of opening file directly
- Run: `python3 serve_demo.py` in the demo directory
- Backend CORS is configured for localhost:8081 in development mode

**4. Rate Limit Exceeded**
```
Error: Rate limit exceeded. Please slow down your requests
```
- Solution: Add delays between requests or upgrade API key limits

### Debug Mode
Enable verbose logging in demos:
```python
# Add to demo_app.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📚 Next Steps

1. **Integrate into Your App**: Use these patterns in your application
2. **Customize Security Policies**: Adjust threat detection thresholds
3. **Monitor Usage**: Track API usage and performance
4. **Scale Up**: Deploy to production with proper API key management

## 🔗 Related Documentation

- **[API Reference](../docs/API_REFERENCE.md)** - Complete API documentation
- **[Security Features](../docs/SECURITY_FEATURES.md)** - Detailed security capabilities
- **[Developer Integration](../docs/DEVELOPER_INTEGRATION.md)** - Integration guide
- **[Dashboard](http://localhost:3000)** - Web interface for API key management

---

**Happy coding with Rampart! 🛡️**
