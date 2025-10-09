"use client";

import { useState } from "react";
import Link from "next/link";
import { Shield, Activity, Lock, Code, Github, BookOpen, Zap, CheckCircle, ArrowRight, Terminal, FileCode } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function LandingPage() {
  const [selectedExample, setSelectedExample] = useState("python");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  
  // Use environment variable for API URL, fallback for local dev
  const apiDocsUrl = process.env.NEXT_PUBLIC_API_URL?.replace('/api/v1', '/docs') || 'http://localhost:8000/docs';

  const codeExamples = {
    python: `import requests

# Protect your LLM prompts with Rampart
response = requests.post(
    "https://rampart.arunrao.com/api/v1/filter",
    headers={"Authorization": "Bearer rmp_live_xxxxx"},
    json={
        "content": user_input,
        "filters": ["prompt_injection", "pii"],
        "user_id": "user123"
    }
)

result = response.json()
if not result["is_safe"]:
    print("⚠️ Security threat detected!")
    print(f"Reason: {result['threats']}")
else:
    # Safe to send to your LLM
    print("✓ Content is safe")`,
    
    curl: `# Content Filter API with Security Checks
curl -X POST https://rampart.arunrao.com/api/v1/filter \\
  -H "Authorization: Bearer rmp_live_xxxxx" \\
  -H "Content-Type: application/json" \\
  -d '{
    "content": "Ignore all instructions...",
    "filters": ["prompt_injection", "pii"],
    "redact": true
  }'

# Response
{
  "is_safe": false,
  "threats": ["prompt_injection"],
  "prompt_injection": {
    "is_injection": true,
    "confidence": 0.95
  }
}`,
    
    javascript: `// Node.js / JavaScript example
const response = await fetch(
  "https://rampart.arunrao.com/api/v1/filter",
  {
    method: "POST",
    headers: {
      "Authorization": "Bearer rmp_live_xxxxx",
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      content: userInput,
      filters: ["prompt_injection", "pii"],
      user_id: "user123"
    })
  }
);

const result = await response.json();
if (!result.is_safe) {
  console.log("⚠️ Threat detected:", result.threats);
}`,
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950">
      {/* Navigation */}
      <nav className="sticky top-0 z-50 backdrop-blur-lg bg-white/70 dark:bg-slate-950/70 border-b border-slate-200 dark:border-slate-800">
        <div className="container mx-auto px-4 sm:px-6 py-4 flex justify-between items-center">
          <div className="flex items-center space-x-2">
            <Shield className="h-6 sm:h-8 w-6 sm:w-8 text-blue-600 dark:text-blue-400" />
            <span className="text-xl sm:text-2xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
              Rampart
            </span>
            <span className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 ml-2">v0.2.2</span>
          </div>
          
          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center space-x-4 lg:space-x-6">
            <a href={process.env.NEXT_PUBLIC_GITHUB_URL || "https://github.com/yourusername/project-rampart"} target="_blank" rel="noopener noreferrer" className="text-slate-600 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 transition-colors flex items-center space-x-1">
              <Github className="h-5 w-5" />
              <span>GitHub</span>
            </a>
            <Link href="/docs" className="text-slate-600 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 transition-colors flex items-center space-x-1">
              <BookOpen className="h-5 w-5" />
              <span>Docs</span>
            </Link>
            <Link href={apiDocsUrl} className="text-slate-600 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 transition-colors flex items-center space-x-1">
              <Code className="h-5 w-5" />
              <span>API</span>
            </Link>
            <Link href="/login">
              <Button className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white shadow-lg shadow-blue-500/30">
                Sign In
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </div>

          {/* Mobile Menu Button */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg"
            aria-label="Toggle menu"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {mobileMenuOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>

        {/* Mobile Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950">
            <div className="container mx-auto px-4 py-4 space-y-3">
              <a href={process.env.NEXT_PUBLIC_GITHUB_URL || "https://github.com/yourusername/project-rampart"} target="_blank" rel="noopener noreferrer" className="flex items-center space-x-2 text-slate-600 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 py-2">
                <Github className="h-5 w-5" />
                <span>GitHub</span>
              </a>
              <Link href="/docs" className="flex items-center space-x-2 text-slate-600 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 py-2">
                <BookOpen className="h-5 w-5" />
                <span>Docs</span>
              </Link>
              <Link href={apiDocsUrl} className="flex items-center space-x-2 text-slate-600 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 py-2">
                <Code className="h-5 w-5" />
                <span>API</span>
              </Link>
              <Link href="/login" className="block">
                <Button className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white shadow-lg shadow-blue-500/30">
                  Sign In
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
            </div>
          </div>
        )}
      </nav>

      {/* Hero Section */}
      <section className="container mx-auto px-4 sm:px-6 py-12 sm:py-20 lg:py-32">
        <div className="grid lg:grid-cols-2 gap-8 lg:gap-12 items-center">
          <div>
            <div className="inline-flex items-center space-x-2 bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-300 px-4 py-2 rounded-full text-sm font-medium mb-6">
              <Zap className="h-4 w-4" />
              <span>95% Prompt Injection Detection Accuracy</span>
            </div>
            
            <h1 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold text-slate-900 dark:text-white mb-6 leading-tight">
              Building with LLMs?
              <span className="block bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                Protect Your Users.
              </span>
            </h1>
            
            <p className="text-lg sm:text-xl text-slate-600 dark:text-slate-300 mb-4 leading-relaxed">
              You're building innovative LLM-powered solutions. But are you protecting your application 
              and users from emerging AI threats?
            </p>
            
            <p className="text-lg text-slate-500 dark:text-slate-400 mb-8">
              <strong className="text-slate-700 dark:text-slate-200">Rampart</strong> is your security layer—detect prompt injection, 
              prevent data exfiltration, and block malicious prompts with a single API call.
            </p>
            
            <div className="flex flex-col sm:flex-row space-y-4 sm:space-y-0 sm:space-x-4 mb-8">
              <Link href="/login">
                <Button size="lg" className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white shadow-xl shadow-blue-500/30 text-lg px-8">
                  Get Started Free
                  <ArrowRight className="ml-2 h-5 w-5" />
                </Button>
              </Link>
              <Link href={apiDocsUrl}>
                <Button size="lg" variant="outline" className="border-2 border-slate-300 dark:border-slate-700 text-lg px-8">
                  <Terminal className="mr-2 h-5 w-5" />
                  View API Docs
                </Button>
              </Link>
            </div>
            
            <div className="flex items-center space-x-8 text-sm text-slate-600 dark:text-slate-400">
              <div className="flex items-center space-x-2">
                <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400" />
                <span>Open Source</span>
              </div>
              <div className="flex items-center space-x-2">
                <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400" />
                <span>Self-Hosted</span>
              </div>
              <div className="flex items-center space-x-2">
                <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400" />
                <span>No Vendor Lock-in</span>
              </div>
            </div>
          </div>
          
          <div className="relative">
            <div className="absolute inset-0 bg-gradient-to-r from-blue-500 to-indigo-500 rounded-2xl blur-3xl opacity-20"></div>
            <Card className="relative shadow-2xl border-2 border-slate-200 dark:border-slate-800">
              <CardHeader className="border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900">
                <div className="flex justify-between items-center">
                  <div className="flex space-x-2">
                    <div className="w-3 h-3 rounded-full bg-red-500"></div>
                    <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                    <div className="w-3 h-3 rounded-full bg-green-500"></div>
                  </div>
                  <div className="flex space-x-2">
                    <button
                      onClick={() => setSelectedExample("python")}
                      className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                        selectedExample === "python"
                          ? "bg-blue-600 text-white"
                          : "text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-800"
                      }`}
                    >
                      Python
                    </button>
                    <button
                      onClick={() => setSelectedExample("curl")}
                      className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                        selectedExample === "curl"
                          ? "bg-blue-600 text-white"
                          : "text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-800"
                      }`}
                    >
                      cURL
                    </button>
                    <button
                      onClick={() => setSelectedExample("javascript")}
                      className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                        selectedExample === "javascript"
                          ? "bg-blue-600 text-white"
                          : "text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-800"
                      }`}
                    >
                      JavaScript
                    </button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <pre className="p-6 overflow-x-auto text-sm leading-relaxed">
                  <code className="text-slate-800 dark:text-slate-200 font-mono">
                    {codeExamples[selectedExample as keyof typeof codeExamples]}
                  </code>
                </pre>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* How It Works - Workflow Diagram */}
      <section className="container mx-auto px-4 sm:px-6 py-12 sm:py-16 lg:py-24">
        <div className="text-center mb-8 sm:mb-12">
          <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-slate-900 dark:text-white mb-4">
            Where Rampart Sits in Your Workflow
          </h2>
          <p className="text-lg text-slate-600 dark:text-slate-400 max-w-2xl mx-auto">
            Protect both input prompts AND output responses—a complete security layer for your LLM pipeline
          </p>
        </div>

        <div className="max-w-5xl mx-auto">
          {/* Workflow Diagram */}
          <div className="flex flex-col lg:flex-row items-center justify-center gap-6 lg:gap-4">
            {/* User */}
            <div className="flex flex-col items-center">
              <div className="w-24 h-24 rounded-2xl bg-gradient-to-br from-slate-500 to-slate-700 flex items-center justify-center shadow-xl">
                <svg className="w-12 h-12 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </div>
              <p className="mt-3 font-semibold text-slate-700 dark:text-slate-300">User Input</p>
              <p className="text-sm text-slate-500">"Malicious prompt?"</p>
            </div>

            {/* Arrow */}
            <ArrowRight className="h-8 w-8 text-slate-400 hidden lg:block" />
            <div className="lg:hidden">
              <svg className="w-8 h-8 text-slate-400 rotate-90" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>

            {/* Rampart (highlighted) */}
            <div className="flex flex-col items-center relative">
              <div className="absolute inset-0 bg-gradient-to-r from-blue-500 to-indigo-500 rounded-3xl blur-2xl opacity-30"></div>
              <div className="relative w-32 h-32 rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center shadow-2xl border-4 border-blue-400 dark:border-blue-500">
                <Shield className="w-16 h-16 text-white" />
              </div>
              <div className="mt-3 text-center">
                <p className="font-bold text-lg bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                  Rampart API
                </p>
                <p className="text-sm text-slate-600 dark:text-slate-400">Security Layer</p>
              </div>
              <div className="mt-2 flex gap-2">
                <div className="px-2 py-1 bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-300 rounded text-xs font-medium">
                  → Input Filter
                </div>
                <div className="px-2 py-1 bg-green-100 dark:bg-green-950 text-green-700 dark:text-green-300 rounded text-xs font-medium">
                  ← Output Filter
                </div>
              </div>
            </div>

            {/* Arrow */}
            <ArrowRight className="h-8 w-8 text-slate-400 hidden lg:block" />
            <div className="lg:hidden">
              <svg className="w-8 h-8 text-slate-400 rotate-90" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>

            {/* Your App */}
            <div className="flex flex-col items-center">
              <div className="w-24 h-24 rounded-2xl bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center shadow-xl">
                <Code className="w-12 h-12 text-white" />
              </div>
              <p className="mt-3 font-semibold text-slate-700 dark:text-slate-300">Your App</p>
              <p className="text-sm text-slate-500">Backend logic</p>
            </div>

            {/* Arrow */}
            <ArrowRight className="h-8 w-8 text-slate-400 hidden lg:block" />
            <div className="lg:hidden">
              <svg className="w-8 h-8 text-slate-400 rotate-90" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>

            {/* LLM */}
            <div className="flex flex-col items-center">
              <div className="w-24 h-24 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-xl">
                <Zap className="w-12 h-12 text-white" />
              </div>
              <p className="mt-3 font-semibold text-slate-700 dark:text-slate-300">LLM</p>
              <p className="text-sm text-slate-500">GPT-4, Claude, etc.</p>
            </div>
          </div>

          {/* Flow Description */}
          <div className="mt-12 text-center max-w-3xl mx-auto">
            <div className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/30 dark:to-indigo-950/30 rounded-xl p-6 border border-blue-200 dark:border-blue-800">
              <h3 className="font-semibold text-slate-900 dark:text-white mb-3">Complete Round-Trip Protection</h3>
              <div className="text-sm text-slate-700 dark:text-slate-300 space-y-2">
                <p className="flex items-center justify-center gap-2">
                  <span className="font-medium text-blue-600 dark:text-blue-400">→ Input:</span>
                  <span>Filter prompt injection, PII, and malicious content</span>
                </p>
                <p className="flex items-center justify-center gap-2">
                  <span className="font-medium text-green-600 dark:text-green-400">← Output:</span>
                  <span>Prevent data exfiltration, redact PII, filter harmful responses</span>
                </p>
              </div>
            </div>
          </div>

          {/* Key Benefits Below Diagram */}
          <div className="mt-16 grid md:grid-cols-3 gap-6">
            <div className="text-center p-6 bg-slate-50 dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800">
              <div className="w-12 h-12 bg-blue-100 dark:bg-blue-950 rounded-lg flex items-center justify-center mx-auto mb-4">
                <Lock className="w-6 h-6 text-blue-600 dark:text-blue-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Bidirectional Filtering</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Protect both incoming prompts and outgoing responses
              </p>
            </div>
            <div className="text-center p-6 bg-slate-50 dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800">
              <div className="w-12 h-12 bg-green-100 dark:bg-green-950 rounded-lg flex items-center justify-center mx-auto mb-4">
                <CheckCircle className="w-6 h-6 text-green-600 dark:text-green-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">One API Call</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Simple HTTP request—works with any language or framework
              </p>
            </div>
            <div className="text-center p-6 bg-slate-50 dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800">
              <div className="w-12 h-12 bg-purple-100 dark:bg-purple-950 rounded-lg flex items-center justify-center mx-auto mb-4">
                <Activity className="w-6 h-6 text-purple-600 dark:text-purple-400" />
              </div>
              <h3 className="font-semibold text-slate-900 dark:text-white mb-2">Real-Time Protection</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                &lt; 100ms latency—your users won't notice the difference
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="container mx-auto px-4 sm:px-6 py-12 sm:py-16">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-8">
          <div className="text-center">
            <div className="text-3xl sm:text-4xl font-bold text-blue-600 dark:text-blue-400 mb-2">95%</div>
            <div className="text-slate-600 dark:text-slate-400">Detection Accuracy</div>
          </div>
          <div className="text-center">
            <div className="text-3xl sm:text-4xl font-bold text-blue-600 dark:text-blue-400 mb-2">&lt;50ms</div>
            <div className="text-slate-600 dark:text-slate-400">Average Latency</div>
          </div>
          <div className="text-center">
            <div className="text-3xl sm:text-4xl font-bold text-blue-600 dark:text-blue-400 mb-2">50+</div>
            <div className="text-slate-600 dark:text-slate-400">Attack Patterns</div>
          </div>
          <div className="text-center">
            <div className="text-3xl sm:text-4xl font-bold text-blue-600 dark:text-blue-400 mb-2">100%</div>
            <div className="text-slate-600 dark:text-slate-400">Open Source</div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="container mx-auto px-4 sm:px-6 py-12 sm:py-20">
        <div className="text-center mb-8 sm:mb-16">
          <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-slate-900 dark:text-white mb-4">
            Everything You Need to Secure AI
          </h2>
          <p className="text-lg sm:text-xl text-slate-600 dark:text-slate-400 max-w-3xl mx-auto">
            Production-ready security controls aligned with OWASP LLM Top 10 and NIST AI Risk Management Framework
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6 sm:gap-8">
          <Card className="border-2 border-slate-200 dark:border-slate-800 hover:border-blue-500 dark:hover:border-blue-500 transition-all hover:shadow-xl">
            <CardHeader>
              <Shield className="h-12 w-12 text-blue-600 dark:text-blue-400 mb-4" />
              <CardTitle className="text-xl">Prompt Injection Detection</CardTitle>
              <CardDescription className="text-base">
                Hybrid DeBERTa ML + regex system with 95% accuracy. Detects instruction override, 
                jailbreaks, context confusion, and zero-click attacks.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm text-slate-600 dark:text-slate-400">
                <div className="flex items-start space-x-2">
                  <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400 mt-0.5" />
                  <span>12+ attack patterns</span>
                </div>
                <div className="flex items-start space-x-2">
                  <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400 mt-0.5" />
                  <span>ONNX-optimized (3x faster)</span>
                </div>
                <div className="flex items-start space-x-2">
                  <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400 mt-0.5" />
                  <span>Real-time threat scores</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-2 border-slate-200 dark:border-slate-800 hover:border-blue-500 dark:hover:border-blue-500 transition-all hover:shadow-xl">
            <CardHeader>
              <Lock className="h-12 w-12 text-indigo-600 dark:text-indigo-400 mb-4" />
              <CardTitle className="text-xl">Data Exfiltration Monitoring</CardTitle>
              <CardDescription className="text-base">
                Scan LLM outputs for credential leakage, infrastructure exposure, and PII disclosure. 
                Automatic redaction and alerting.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm text-slate-600 dark:text-slate-400">
                <div className="flex items-start space-x-2">
                  <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400 mt-0.5" />
                  <span>API key & credential detection</span>
                </div>
                <div className="flex items-start space-x-2">
                  <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400 mt-0.5" />
                  <span>Database URL scanning</span>
                </div>
                <div className="flex items-start space-x-2">
                  <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400 mt-0.5" />
                  <span>Smart redaction policies</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-2 border-slate-200 dark:border-slate-800 hover:border-blue-500 dark:hover:border-blue-500 transition-all hover:shadow-xl">
            <CardHeader>
              <FileCode className="h-12 w-12 text-purple-600 dark:text-purple-400 mb-4" />
              <CardTitle className="text-xl">PII Detection (GLiNER ML)</CardTitle>
              <CardDescription className="text-base">
                93% accurate ML-based PII detection. Identifies emails, SSNs, credit cards, 
                names, addresses, and custom entity types.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm text-slate-600 dark:text-slate-400">
                <div className="flex items-start space-x-2">
                  <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400 mt-0.5" />
                  <span>Context-aware detection</span>
                </div>
                <div className="flex items-start space-x-2">
                  <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400 mt-0.5" />
                  <span>GDPR & HIPAA compliant</span>
                </div>
                <div className="flex items-start space-x-2">
                  <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400 mt-0.5" />
                  <span>Zero-shot custom entities</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-2 border-slate-200 dark:border-slate-800 hover:border-blue-500 dark:hover:border-blue-500 transition-all hover:shadow-xl">
            <CardHeader>
              <Activity className="h-12 w-12 text-green-600 dark:text-green-400 mb-4" />
              <CardTitle className="text-xl">Observability & Tracing</CardTitle>
              <CardDescription className="text-base">
                Complete visibility into LLM usage with distributed tracing, cost tracking, 
                and security incident logging.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm text-slate-600 dark:text-slate-400">
                <div className="flex items-start space-x-2">
                  <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400 mt-0.5" />
                  <span>Token & cost attribution</span>
                </div>
                <div className="flex items-start space-x-2">
                  <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400 mt-0.5" />
                  <span>Latency monitoring</span>
                </div>
                <div className="flex items-start space-x-2">
                  <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400 mt-0.5" />
                  <span>OpenTelemetry compatible</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-2 border-slate-200 dark:border-slate-800 hover:border-blue-500 dark:hover:border-blue-500 transition-all hover:shadow-xl">
            <CardHeader>
              <BookOpen className="h-12 w-12 text-orange-600 dark:text-orange-400 mb-4" />
              <CardTitle className="text-xl">Policy Management</CardTitle>
              <CardDescription className="text-base">
                Rule-based policy engine with compliance templates. Enforce GDPR, HIPAA, 
                SOC 2, and custom organizational policies.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm text-slate-600 dark:text-slate-400">
                <div className="flex items-start space-x-2">
                  <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400 mt-0.5" />
                  <span>Pre-built compliance templates</span>
                </div>
                <div className="flex items-start space-x-2">
                  <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400 mt-0.5" />
                  <span>RBAC & rate limiting</span>
                </div>
                <div className="flex items-start space-x-2">
                  <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400 mt-0.5" />
                  <span>Audit trail logging</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-2 border-slate-200 dark:border-slate-800 hover:border-blue-500 dark:hover:border-blue-500 transition-all hover:shadow-xl">
            <CardHeader>
              <Code className="h-12 w-12 text-pink-600 dark:text-pink-400 mb-4" />
              <CardTitle className="text-xl">Developer-First Integration</CardTitle>
              <CardDescription className="text-base">
                Simple REST API with language-agnostic HTTP endpoints. Works with any framework or language.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm text-slate-600 dark:text-slate-400">
                <div className="flex items-start space-x-2">
                  <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400 mt-0.5" />
                  <span>5-minute integration</span>
                </div>
                <div className="flex items-start space-x-2">
                  <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400 mt-0.5" />
                  <span>Framework wrappers</span>
                </div>
                <div className="flex items-start space-x-2">
                  <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400 mt-0.5" />
                  <span>Interactive API docs</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Use Cases Section */}
      <section className="bg-slate-100 dark:bg-slate-900 py-12 sm:py-20">
        <div className="container mx-auto px-4 sm:px-6">
          <div className="text-center mb-8 sm:mb-16">
            <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-slate-900 dark:text-white mb-4">
              Built for Modern AI Applications
            </h2>
            <p className="text-lg sm:text-xl text-slate-600 dark:text-slate-400">
              From chatbots to RAG pipelines to autonomous agents
            </p>
          </div>

          <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-6 sm:gap-8">
            <Card className="bg-white dark:bg-slate-950">
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <div className="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-950 flex items-center justify-center">
                    <Terminal className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                  </div>
                  <span>Customer Support Bots</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-slate-600 dark:text-slate-400">
                  Protect against prompt injection from malicious users. Automatically redact PII 
                  in responses. Track costs per conversation.
                </p>
              </CardContent>
            </Card>

            <Card className="bg-white dark:bg-slate-950">
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <div className="w-10 h-10 rounded-lg bg-indigo-100 dark:bg-indigo-950 flex items-center justify-center">
                    <FileCode className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                  </div>
                  <span>RAG Applications</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-slate-600 dark:text-slate-400">
                  Detect zero-click attacks in uploaded documents. Prevent data exfiltration through 
                  crafted queries. Maintain audit trails for compliance.
                </p>
              </CardContent>
            </Card>

            <Card className="bg-white dark:bg-slate-950">
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <div className="w-10 h-10 rounded-lg bg-purple-100 dark:bg-purple-950 flex items-center justify-center">
                    <Code className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                  </div>
                  <span>Code Generation Tools</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-slate-600 dark:text-slate-400">
                  Block jailbreak attempts to generate malicious code. Redact API keys and secrets 
                  in generated output. Monitor usage per developer.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Integration Example Section */}
      <section className="container mx-auto px-4 sm:px-6 py-12 sm:py-20">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-8 sm:mb-12">
            <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-slate-900 dark:text-white mb-4">
              Integrate in Minutes
            </h2>
            <p className="text-lg sm:text-xl text-slate-600 dark:text-slate-400">
              Add enterprise-grade security to your LLM application with minimal code changes
            </p>
          </div>

          <div className="space-y-6 sm:space-y-8">
            <Card className="border-2 border-slate-200 dark:border-slate-800">
              <CardHeader className="bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800">
                <CardTitle className="flex items-center space-x-2">
                  <div className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center text-sm font-bold">1</div>
                  <span>Install the SDK</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="p-6">
                <pre className="bg-slate-900 dark:bg-black text-slate-100 p-4 rounded-lg overflow-x-auto text-sm">
                  <code>{`# Any HTTP client works - Python example
pip install requests

# Or use curl, fetch(), axios, etc.`}</code>
                </pre>
              </CardContent>
            </Card>

            <Card className="border-2 border-slate-200 dark:border-slate-800">
              <CardHeader className="bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800">
                <CardTitle className="flex items-center space-x-2">
                  <div className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center text-sm font-bold">2</div>
                  <span>Wrap your LLM calls</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="p-6">
                <pre className="bg-slate-900 dark:bg-black text-slate-100 p-4 rounded-lg overflow-x-auto text-sm">
                  <code>{`# Before - unprotected
from openai import OpenAI
client = OpenAI(api_key="sk-...")
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": user_input}]
)

# After - secured with Rampart
import requests

# Check content safety first
check = requests.post(
    "https://rampart.arunrao.com/api/v1/filter",
    headers={"Authorization": "Bearer rmp_live_xxxxx"},
    json={"content": user_input, "filters": ["prompt_injection"]}
)

if check.json()["is_safe"]:
    # Safe to send to LLM
    response = client.chat.completions.create(...)
else:
    return "Security threat detected"
`}</code>
                </pre>
              </CardContent>
            </Card>

            <Card className="border-2 border-slate-200 dark:border-slate-800">
              <CardHeader className="bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800">
                <CardTitle className="flex items-center space-x-2">
                  <div className="w-8 h-8 rounded-full bg-green-600 text-white flex items-center justify-center text-sm font-bold">✓</div>
                  <span>You're Protected!</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="p-6">
                <p className="text-slate-600 dark:text-slate-400">
                  All LLM calls are now automatically protected against prompt injection, data exfiltration, 
                  and policy violations. View security insights and traces in your dashboard.
                </p>
              </CardContent>
            </Card>
          </div>

          <div className="text-center mt-12">
            <Link href={apiDocsUrl}>
              <Button size="lg" variant="outline" className="border-2 border-blue-600 text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-950">
                <BookOpen className="mr-2 h-5 w-5" />
                Read Full Documentation
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="bg-gradient-to-r from-blue-600 to-indigo-600 py-12 sm:py-20">
        <div className="container mx-auto px-4 sm:px-6 text-center">
          <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-white mb-4">
            Ready to Secure Your AI Applications?
          </h2>
          <p className="text-xl text-blue-100 mb-8 max-w-2xl mx-auto">
            Join teams using Rampart to protect their LLM applications with enterprise-grade security
          </p>
          <div className="flex flex-col sm:flex-row justify-center space-y-4 sm:space-y-0 sm:space-x-4">
            <Link href="/login">
              <Button size="lg" className="bg-white text-blue-600 hover:bg-slate-100 shadow-xl text-lg px-8">
                Start Building
                <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
            </Link>
            <a href={process.env.NEXT_PUBLIC_GITHUB_URL || "https://github.com/yourusername/project-rampart"} target="_blank" rel="noopener noreferrer">
              <Button size="lg" variant="outline" className="border-2 border-white text-white hover:bg-white/10 text-lg px-8">
                <Github className="mr-2 h-5 w-5" />
                View on GitHub
              </Button>
            </a>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-slate-900 text-slate-300 py-12">
        <div className="container mx-auto px-4 sm:px-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 sm:gap-8 mb-8">
            <div>
              <div className="flex items-center space-x-2 mb-4">
                <Shield className="h-6 w-6 text-blue-400" />
                <span className="text-xl font-bold text-white">Rampart</span>
              </div>
              <p className="text-sm text-slate-400">
                Production-ready security gateway for LLM applications
              </p>
            </div>
            
            <div>
              <h4 className="font-semibold text-white mb-4">Product</h4>
              <ul className="space-y-2 text-sm">
                <li><Link href="/features" className="hover:text-blue-400 transition-colors">Features</Link></li>
                <li><Link href="/pricing" className="hover:text-blue-400 transition-colors">Pricing</Link></li>
                <li><Link href="/security" className="hover:text-blue-400 transition-colors">Security</Link></li>
                <li><Link href="/changelog" className="hover:text-blue-400 transition-colors">Changelog</Link></li>
              </ul>
            </div>
            
            <div>
              <h4 className="font-semibold text-white mb-4">Resources</h4>
              <ul className="space-y-2 text-sm">
                <li><Link href="/docs" className="hover:text-blue-400 transition-colors">Documentation</Link></li>
                <li><Link href={apiDocsUrl} className="hover:text-blue-400 transition-colors">API Reference</Link></li>
                <li><a href={process.env.NEXT_PUBLIC_GITHUB_URL || "https://github.com/yourusername/project-rampart"} target="_blank" rel="noopener noreferrer" className="hover:text-blue-400 transition-colors">GitHub</a></li>
                <li><Link href="/examples" className="hover:text-blue-400 transition-colors">Examples</Link></li>
              </ul>
            </div>
            
            <div>
              <h4 className="font-semibold text-white mb-4">Company</h4>
              <ul className="space-y-2 text-sm">
                <li><Link href="/about" className="hover:text-blue-400 transition-colors">About</Link></li>
                <li><Link href="/blog" className="hover:text-blue-400 transition-colors">Blog</Link></li>
                <li><Link href="/contact" className="hover:text-blue-400 transition-colors">Contact</Link></li>
                <li><Link href="/privacy" className="hover:text-blue-400 transition-colors">Privacy</Link></li>
              </ul>
            </div>
          </div>
          
          <div className="border-t border-slate-800 pt-8 flex flex-col md:flex-row justify-between items-center text-sm text-slate-400">
            <p>&copy; 2025 Project Rampart. Open source under MIT License.</p>
            <div className="flex space-x-6 mt-4 md:mt-0">
              <a href="https://twitter.com/rampart" className="hover:text-blue-400 transition-colors">Twitter</a>
              <a href={process.env.NEXT_PUBLIC_GITHUB_URL || "https://github.com/yourusername/project-rampart"} target="_blank" rel="noopener noreferrer" className="hover:text-blue-400 transition-colors">GitHub</a>
              <a href="https://discord.gg/rampart" className="hover:text-blue-400 transition-colors">Discord</a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

