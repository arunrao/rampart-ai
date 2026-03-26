import { Shield, CheckCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function SecurityFeaturesContent() {
  return (
    <div className="prose dark:prose-invert max-w-none">
      <h1 className="text-3xl sm:text-4xl font-bold mb-4 text-marketing-heading">Security Features</h1>
      <p className="text-lg sm:text-xl text-marketing-body mb-8">
        Comprehensive protection aligned with OWASP LLM Top 10
      </p>

      <div className="grid md:grid-cols-2 gap-6 mb-8">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Shield className="h-6 w-6 text-marketing-accent" />
              <span>Prompt Injection Detection</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-sm">
              {[
                "Instruction override attacks",
                "Jailbreak attempts (DAN mode, etc.)",
                "Context confusion & delimiter injection",
                "Zero-click / indirect attacks",
                "95% accuracy with DeBERTa ML",
              ].map((text) => (
                <li key={text} className="flex items-start space-x-2">
                  <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400 mt-0.5 shrink-0" />
                  <span className="text-marketing-body">{text}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Shield className="h-6 w-6 text-purple-600 dark:text-purple-400" />
              <span>Data Exfiltration Monitoring</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-sm">
              {[
                "API key & credential detection",
                "Database URL scanning",
                "Infrastructure exposure detection",
                "PII leakage prevention",
                "Automatic redaction",
              ].map((text) => (
                <li key={text} className="flex items-start space-x-2">
                  <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400 mt-0.5 shrink-0" />
                  <span className="text-marketing-body">{text}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Shield className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
              <span>PII Detection (GLiNER ML)</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-sm">
              {[
                "Email addresses & phone numbers",
                "SSNs & credit card numbers",
                "Person names & addresses (ML)",
                "93% accuracy, context-aware",
                "Zero-shot custom entities",
              ].map((text) => (
                <li key={text} className="flex items-start space-x-2">
                  <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400 mt-0.5 shrink-0" />
                  <span className="text-marketing-body">{text}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Shield className="h-6 w-6 text-green-600 dark:text-green-400" />
              <span>Policy Management</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-sm">
              {[
                "GDPR, HIPAA, SOC 2 templates",
                "Custom rule engine",
                "RBAC & rate limiting",
                "Audit trail logging",
                "Compliance reporting",
              ].map((text) => (
                <li key={text} className="flex items-start space-x-2">
                  <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400 mt-0.5 shrink-0" />
                  <span className="text-marketing-body">{text}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>

      <h2 className="text-xl sm:text-2xl font-bold mt-8 mb-4 text-marketing-heading">Detection Accuracy</h2>
      <Card className="mb-8">
        <CardContent className="pt-6">
          <div className="space-y-4">
            {[
              { label: "Prompt Injection Detection", pct: 95, bar: "bg-blue-600", text: "text-blue-600 dark:text-blue-400" },
              { label: "PII Detection (GLiNER)", pct: 93, bar: "bg-purple-600", text: "text-purple-600 dark:text-purple-400" },
              { label: "Data Exfiltration Detection", pct: 90, bar: "bg-green-600", text: "text-green-600 dark:text-green-400" },
            ].map((row) => (
              <div key={row.label}>
                <div className="flex justify-between mb-2">
                  <span className="text-sm font-medium text-marketing-body">{row.label}</span>
                  <span className={`text-sm font-bold ${row.text}`}>{row.pct}%</span>
                </div>
                <div className="w-full bg-marketing-surface rounded-full h-2">
                  <div className={`${row.bar} h-2 rounded-full`} style={{ width: `${row.pct}%` }} />
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
