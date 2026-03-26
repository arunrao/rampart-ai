import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export function QuickStartContent() {
  return (
    <div className="prose dark:prose-invert max-w-none">
      <h1 className="text-3xl sm:text-4xl font-bold mb-4 text-marketing-heading">Quick Start Guide</h1>
      <p className="text-lg sm:text-xl text-marketing-body mb-8">
        Get started with Rampart in under 5 minutes
      </p>

      <Card className="mb-8">
        <CardHeader>
          <CardTitle>1. Get Your API Key</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-marketing-body mb-4">Sign up and generate your API key from the dashboard:</p>
          <Link href="/login">
            <Button>
              Go to Dashboard <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </Link>
        </CardContent>
      </Card>

      <Card className="mb-8">
        <CardHeader>
          <CardTitle>2. Filter User Input Before Sending to LLM</CardTitle>
          <CardDescription>Check prompts for prompt injection, PII, and other threats</CardDescription>
        </CardHeader>
        <CardContent>
          <pre className="bg-marketing-code-bg text-marketing-code-fg border border-marketing-border p-4 rounded-lg overflow-x-auto text-sm">
            <code>{`# Python example
import requests

response = requests.post(
    "https://rampart.arunrao.com/api/v1/filter",
    headers={"Authorization": "Bearer rmp_live_xxxxx"},
    json={
        "content": user_input,
        "filters": ["prompt_injection", "pii"],
        "user_id": "user_123"
    }
)

result = response.json()

# Check if content is safe
if not result["is_safe"]:
    print("⚠️ Threat detected:", result["threats"])
    print("Details:", result["prompt_injection"])
else:
    # Safe to send to your LLM
    print("✓ Content is safe - proceed to LLM")
    llm_response = call_your_llm(user_input)`}</code>
          </pre>
        </CardContent>
      </Card>

      <Card className="mb-8">
        <CardHeader>
          <CardTitle>3. Or Use the Secured LLM Proxy (Optional)</CardTitle>
          <CardDescription>Automatic security checks + LLM calls in one request</CardDescription>
        </CardHeader>
        <CardContent>
          <pre className="bg-marketing-code-bg text-marketing-code-fg border border-marketing-border p-4 rounded-lg overflow-x-auto text-sm">
            <code>{`# Combined filtering + LLM call
response = requests.post(
    "https://rampart.arunrao.com/api/v1/llm/complete",
    headers={"Authorization": "Bearer rmp_live_xxxxx"},
    json={
        "prompt": user_input,
        "model": "gpt-4",
        "provider": "openai",
        "user_id": "user_123"
    }
)

result = response.json()

if result["blocked"]:
    print("⚠️ Request blocked:", result["reason"])
else:
    print("✓ LLM Response:", result["response"])
    print("Security checks:", result["security_checks"])`}</code>
          </pre>
        </CardContent>
      </Card>

      <div className="bg-marketing-badge-bg border border-marketing-border rounded-lg p-6 mb-8">
        <h3 className="text-lg font-semibold text-marketing-heading mb-2">That&apos;s it! Your LLM calls are now protected</h3>
        <p className="text-marketing-body">
          All requests are automatically scanned for prompt injection, data exfiltration, and policy violations.
        </p>
      </div>

      <h2 className="text-xl sm:text-2xl font-bold mt-12 mb-4 text-marketing-heading">What&apos;s Next?</h2>
      <div className="grid md:grid-cols-2 gap-4">
        <Card className="hover:shadow-lg transition-shadow">
          <CardHeader>
            <CardTitle className="text-lg">Configure Policies</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-marketing-body mb-4">
              Set up custom security policies and compliance templates
            </p>
            <Button variant="outline" size="sm">
              Learn More
            </Button>
          </CardContent>
        </Card>

        <Card className="hover:shadow-lg transition-shadow">
          <CardHeader>
            <CardTitle className="text-lg">Monitor Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-marketing-body mb-4">
              View traces, security incidents, and cost analytics
            </p>
            <Link href="/observability">
              <Button variant="outline" size="sm">
                View Dashboard
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
