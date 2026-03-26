import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function DeploymentContent() {
  return (
    <div className="prose dark:prose-invert max-w-none">
      <h1 className="text-3xl sm:text-4xl font-bold mb-4 text-marketing-heading">Deployment Guide</h1>
      <p className="text-lg sm:text-xl text-marketing-body mb-8">
        Deploy Rampart to production with Docker or cloud platforms
      </p>

      <h2 className="text-xl sm:text-2xl font-bold mt-8 mb-4 text-marketing-heading">Docker Compose (Recommended)</h2>
      <Card className="mb-8">
        <CardHeader>
          <CardTitle>Quick Setup</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="bg-marketing-code-bg text-marketing-code-fg border border-marketing-border p-4 rounded-lg overflow-x-auto text-sm">
            <code>{`# Clone repository
git clone https://github.com/arunrao/rampart-ai.git
cd project-rampart

# Generate secrets
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
export JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Access application
open http://localhost:3000`}</code>
          </pre>
        </CardContent>
      </Card>

      <h2 className="text-xl sm:text-2xl font-bold mt-8 mb-4 text-marketing-heading">Environment Variables</h2>
      <Card className="mb-8">
        <CardHeader>
          <CardTitle>Required Configuration</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="bg-marketing-code-bg text-marketing-code-fg border border-marketing-border p-4 rounded-lg overflow-x-auto text-sm">
            <code>{`# .env file
SECRET_KEY=<cryptographically-secure-random-value>
JWT_SECRET_KEY=<cryptographically-secure-random-value>
KEY_ENCRYPTION_SECRET=<cryptographically-secure-random-value>

# Database
DATABASE_URL=postgresql://user:pass@localhost/rampart
POSTGRES_PASSWORD=<secure-password>

# CORS (production)
CORS_ORIGINS=https://your-domain.com

# LLM Providers (optional)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...`}</code>
          </pre>
        </CardContent>
      </Card>

      <h2 className="text-xl sm:text-2xl font-bold mt-8 mb-4 text-marketing-heading">Cloud Deployment</h2>
      <div className="grid md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>AWS Deployment</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-marketing-body mb-4">
              Deploy to AWS with EC2 + Auto Scaling Groups using CloudFormation
            </p>
            <pre className="bg-marketing-code-bg text-marketing-code-fg border border-marketing-border p-3 rounded-lg text-xs overflow-x-auto">
              <code>{`cd aws
./deploy.sh`}</code>
            </pre>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Google Cloud Run</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-marketing-body mb-4">Serverless deployment on Google Cloud Run</p>
            <pre className="bg-marketing-code-bg text-marketing-code-fg border border-marketing-border p-3 rounded-lg text-xs overflow-x-auto">
              <code>{`gcloud run deploy rampart \\
  --source . \\
  --region us-central1`}</code>
            </pre>
          </CardContent>
        </Card>
      </div>

      <div className="bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-lg p-6 mt-8">
        <h3 className="text-lg font-semibold text-amber-900 dark:text-amber-100 mb-2">Production Security Checklist</h3>
        <ul className="space-y-2 text-sm text-amber-900 dark:text-amber-200">
          <li>Use strong, random secrets for all keys</li>
          <li>Enable HTTPS/TLS (never use HTTP in production)</li>
          <li>Configure CORS with specific allowed origins</li>
          <li>Set up monitoring and alerting</li>
          <li>Implement database backups</li>
          <li>Review and adjust rate limits</li>
        </ul>
      </div>
    </div>
  );
}
