# Secure Setup Guide

## Quick Start (Local Development)

### 1. Generate Secrets

```bash
# Generate secure secrets
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
export JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
export KEY_ENCRYPTION_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
export POSTGRES_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(16))")

# Display them (save these securely!)
echo "SECRET_KEY=$SECRET_KEY"
echo "JWT_SECRET_KEY=$JWT_SECRET_KEY"
echo "KEY_ENCRYPTION_SECRET=$KEY_ENCRYPTION_SECRET"
echo "POSTGRES_PASSWORD=$POSTGRES_PASSWORD"
```

### 2. Create .env File

```bash
# Copy example and edit
cp .env.example .env

# Edit .env and paste the generated secrets
nano .env
```

### 3. Start with Docker Compose

```bash
# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f backend

# Stop services
docker-compose down
```

### 4. Test Authentication

```bash
# Health check (no auth required)
curl http://localhost:8000/health

# Try protected endpoint without auth (should fail with 401)
curl http://localhost:8000/api/v1/security/stats

# Login via Google OAuth (in browser)
open http://localhost:3000/login

# Or create a test token manually (for development)
# See backend/api/routes/auth.py for token creation
```

## Running Backend Standalone (Without Docker)

### 1. Install Dependencies

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set Environment Variables

```bash
# Set secrets (from step 1 above)
export SECRET_KEY="your-generated-secret"
export JWT_SECRET_KEY="your-generated-jwt-secret"
export KEY_ENCRYPTION_SECRET="your-generated-encryption-secret"

# Use SQLite for local dev (no Postgres needed)
# DATABASE_URL will default to sqlite:///./rampart_dev.db if not set

# Or use local Postgres
export DATABASE_URL="postgresql://user:pass@localhost:5432/rampart"

# Set CORS for frontend
export CORS_ORIGINS="http://localhost:3000,http://localhost:3001"
```

### 3. Run Backend

```bash
cd backend
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

## Running Frontend Standalone

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Set Environment Variables

```bash
# Create .env.local
echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1" > .env.local
```

### 3. Run Frontend

```bash
npm run dev
```

Frontend will be available at http://localhost:3000

## Production Deployment

### Environment Variables Required

```bash
# Secrets (REQUIRED)
SECRET_KEY=<generate-with-secrets.token_urlsafe(32)>
JWT_SECRET_KEY=<generate-with-secrets.token_urlsafe(32)>
KEY_ENCRYPTION_SECRET=<generate-with-secrets.token_urlsafe(32)>

# Database (REQUIRED)
DATABASE_URL=postgresql://user:password@host:5432/dbname
POSTGRES_PASSWORD=<secure-password>

# CORS (REQUIRED for production)
CORS_ORIGINS=https://your-frontend.vercel.app,https://your-domain.com

# Application
ENVIRONMENT=production
DEBUG=false

# Redis (Optional but recommended)
REDIS_URL=redis://redis-host:6379/0

# LLM Providers (Optional)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# OAuth (if using Google login)
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret

# Rate Limiting (Optional - defaults shown)
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000

# Observability (Optional)
OTEL_EXPORTER_OTLP_ENDPOINT=https://your-otel-collector:4317
```

### Deployment Options

#### Option 1: Vercel (Frontend) + Cloud Run (Backend)

**Frontend (Vercel)**:
```bash
# Install Vercel CLI
npm i -g vercel

# Deploy from frontend directory
cd frontend
vercel --prod

# Set environment variable in Vercel dashboard
NEXT_PUBLIC_API_URL=https://your-backend-url.run.app/api/v1
```

**Backend (Google Cloud Run)**:
```bash
# Build and deploy
cd backend
gcloud run deploy rampart-backend \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars="SECRET_KEY=$SECRET_KEY,JWT_SECRET_KEY=$JWT_SECRET_KEY,DATABASE_URL=$DATABASE_URL,CORS_ORIGINS=https://your-frontend.vercel.app"
```

#### Option 2: AWS Amplify (Frontend) + App Runner (Backend)

**Frontend (Amplify)**:
- Connect GitHub repo in Amplify Console
- Set build settings for Next.js
- Add environment variables

**Backend (App Runner)**:
- Create App Runner service from GitHub
- Configure environment variables
- Set port to 8000

#### Option 3: Single Server (VPS/EC2)

```bash
# Clone repo
git clone https://github.com/arunrao/rampart-ai.git
cd rampart-ai

# Create .env with production values
nano .env

# Start with docker-compose
docker-compose up -d

# Set up nginx reverse proxy
# Configure SSL with Let's Encrypt
```

## Security Checklist

Before going to production:

- [ ] All secrets generated with cryptographically secure random
- [ ] `SECRET_KEY`, `JWT_SECRET_KEY`, `KEY_ENCRYPTION_SECRET` are unique and strong
- [ ] `ENVIRONMENT=production` and `DEBUG=false`
- [ ] `CORS_ORIGINS` set to actual frontend URL(s) only
- [ ] Database uses strong password and SSL connection
- [ ] HTTPS/TLS enabled (not HTTP)
- [ ] Rate limits reviewed and adjusted for expected traffic
- [ ] `/metrics` endpoint protected or on internal network only
- [ ] Firewall rules configured (only ports 80/443 public)
- [ ] Monitoring and alerting set up
- [ ] Backup strategy in place
- [ ] Secrets stored in secure vault (not in code/git)

## Troubleshooting

### "SECRET_KEY must be set" error
```bash
# Make sure secrets are exported before running docker-compose
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
export JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
export KEY_ENCRYPTION_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
docker-compose up
```

### "401 Unauthorized" on all endpoints
- Check that you're sending `Authorization: Bearer <token>` header
- Verify token is valid and not expired
- Check JWT_SECRET_KEY matches between token creation and validation

### CORS errors in browser
- Verify `CORS_ORIGINS` includes your frontend URL
- Check browser console for exact origin being blocked
- Ensure no trailing slashes in CORS_ORIGINS

### Rate limit errors (429)
- Wait for rate limit window to reset
- Adjust `RATE_LIMIT_PER_MINUTE` and `RATE_LIMIT_PER_HOUR` if needed
- Check if multiple clients sharing same IP

### Database connection errors
- Verify `DATABASE_URL` format: `postgresql://user:pass@host:port/dbname`
- Check database is running and accessible
- Verify credentials are correct
- For SQLite: ensure write permissions in directory

## Support

For issues:
1. Check logs: `docker-compose logs backend`
2. Review SECURITY_FIXES.md
3. Check GitHub issues: https://github.com/arunrao/rampart-ai/issues
