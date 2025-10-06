# Docker Setup - Quick Start

## Start Everything (One Command)

```bash
docker-compose up -d
```

That's it! This will:
- ✅ Start PostgreSQL database
- ✅ Start Redis cache
- ✅ Start Backend API (port 8000)
- ✅ Start Frontend (port 3000)
- ✅ Start Jaeger tracing (port 16686)
- ✅ Create all database tables automatically

## Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Jaeger UI**: http://localhost:16686

## First Time Setup

1. **Start services**:
   ```bash
   docker-compose up -d
   ```

2. **Wait 30 seconds** for everything to start

3. **Open browser**: http://localhost:3000

4. **Sign up**: Create an account with any email/password

5. **Test**: Go to "Testing" page and click "Run All Tests"

## Useful Commands

```bash
# View logs
docker-compose logs -f

# View backend logs only
docker-compose logs -f backend

# Restart services
docker-compose restart

# Stop everything
docker-compose down

# Stop and remove data (fresh start)
docker-compose down -v
```

## Troubleshooting

### Backend not starting?
```bash
docker-compose logs backend
docker-compose restart backend
```

### Can't login?
```bash
# Check backend is healthy
curl http://localhost:8000/api/v1/health

# Restart if needed
docker-compose restart backend
```

### Port already in use?
```bash
# Stop everything
docker-compose down

# Kill processes on ports
lsof -ti:8000 | xargs kill -9
lsof -ti:3000 | xargs kill -9

# Start again
docker-compose up -d
```

### Fresh start?
```bash
# Remove everything including data
docker-compose down -v

# Start fresh
docker-compose up -d
```

## What Gets Created

### Database Tables (Auto-created)
- `users` - User accounts
- `provider_keys` - API keys (encrypted)
- `policy_defaults` - Security policies

### Services
- PostgreSQL on port 5432
- Redis on port 6379
- Backend API on port 8000
- Frontend on port 3000
- Jaeger on port 16686

## Configuration

All services work out of the box with default settings. No `.env` file needed for local development.

Optional: Create `.env` file to customize:
```bash
POSTGRES_PASSWORD=your_password
SECRET_KEY=your-secret-key
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

## That's It!

Just run `docker-compose up -d` and you're ready to test! 🚀
