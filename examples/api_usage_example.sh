#!/bin/bash

# Project Rampart - API Usage Examples
# Shows how to use Rampart API keys in real applications

echo "🔐 PROJECT RAMPART API USAGE EXAMPLES"
echo "====================================="
echo ""

# Replace with your actual API key from the dashboard
API_KEY="rmp_live_your_api_key_here"
API_BASE="http://localhost:8000/api/v1"

echo "💡 To get your API key:"
echo "   1. Visit: http://localhost:3000"
echo "   2. Login with Google OAuth"
echo "   3. Go to: API Keys page"
echo "   4. Create a new key with desired permissions"
echo "   5. Copy the key and replace API_KEY above"
echo ""

# Example 1: Security Analysis
echo "📋 Example 1: Security Analysis"
echo "------------------------------"
echo "Checking user input for security threats..."
echo ""

cat << 'EOF'
curl -X POST http://localhost:8000/api/v1/security/analyze \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "User input to analyze",
    "context_type": "input"
  }'
EOF

echo ""
echo "Response format:"
cat << 'EOF'
{
  "is_safe": true,
  "risk_score": 0.0,
  "threats_detected": [],
  "processing_time_ms": 45.2
}
EOF

echo ""
echo ""

# Example 2: PII Filtering
echo "📋 Example 2: PII Detection & Redaction"
echo "---------------------------------------"
echo "Detecting and redacting personal information..."
echo ""

cat << 'EOF'
curl -X POST http://localhost:8000/api/v1/filter \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Contact John at john@company.com or (555) 123-4567",
    "redact": true
  }'
EOF

echo ""
echo "Response format:"
cat << 'EOF'
{
  "filtered_content": "Contact John at [EMAIL_REDACTED] or [PHONE_REDACTED]",
  "pii_detected": [
    {"type": "email", "value": "john@company.com"},
    {"type": "phone", "value": "(555) 123-4567"}
  ],
  "is_safe": true
}
EOF

echo ""
echo ""

# Example 3: Python Integration
echo "📋 Example 3: Python Integration"
echo "--------------------------------"
echo ""

cat << 'EOF'
import requests

class RampartClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "http://localhost:8000/api/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def check_security(self, content, context_type="input"):
        """Check content for security threats"""
        response = requests.post(
            f"{self.base_url}/security/analyze",
            headers=self.headers,
            json={
                "content": content,
                "context_type": context_type
            }
        )
        return response.json()
    
    def filter_pii(self, content, redact=True):
        """Filter PII from content"""
        response = requests.post(
            f"{self.base_url}/filter",
            headers=self.headers,
            json={
                "content": content,
                "redact": redact
            }
        )
        return response.json()

# Usage
client = RampartClient("rmp_live_your_api_key_here")

# Check for threats
result = client.check_security("User input here")
if not result["is_safe"]:
    print(f"⚠️ Threat detected: {result['threats_detected']}")

# Filter PII
filtered = client.filter_pii("Email me at user@example.com")
print(f"Clean content: {filtered['filtered_content']}")
EOF

echo ""
echo ""

# Example 4: JavaScript/Node.js Integration
echo "📋 Example 4: JavaScript/Node.js Integration"
echo "--------------------------------------------"
echo ""

cat << 'EOF'
class RampartClient {
    constructor(apiKey) {
        this.apiKey = apiKey;
        this.baseUrl = 'http://localhost:8000/api/v1';
    }

    async checkSecurity(content, contextType = 'input') {
        const response = await fetch(`${this.baseUrl}/security/analyze`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${this.apiKey}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                content,
                context_type: contextType
            })
        });
        return response.json();
    }

    async filterPII(content, redact = true) {
        const response = await fetch(`${this.baseUrl}/filter`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${this.apiKey}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                content,
                redact
            })
        });
        return response.json();
    }
}

// Usage
const client = new RampartClient('rmp_live_your_api_key_here');

// Check for threats
const result = await client.checkSecurity('User input here');
if (!result.is_safe) {
    console.log(`⚠️ Threat detected: ${result.threats_detected}`);
}

// Filter PII
const filtered = await client.filterPII('Email me at user@example.com');
console.log(`Clean content: ${filtered.filtered_content}`);
EOF

echo ""
echo ""

echo "🔗 More Information:"
echo "   • API Documentation: http://localhost:8000/docs"
echo "   • Dashboard: http://localhost:3000"
echo "   • Test Script: ./test_authentication.sh"
echo ""
echo "🚀 Happy coding with Rampart!"
