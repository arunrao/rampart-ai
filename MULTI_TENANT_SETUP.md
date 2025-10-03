# Multi-Tenant Setup Guide

Project Rampart now supports multi-tenant authentication with per-user API key management, similar to Langfuse Cloud.

## What's New

### Backend Features
- **User Authentication**: JWT-based signup/login system
- **Secure API Key Storage**: Encrypted storage of OpenAI and Anthropic keys per user
- **Provider Key Management**: CRUD endpoints for managing provider API keys
- **Per-User LLM Calls**: LLM proxy automatically uses user's API keys

### Frontend Features
- **Signup/Login Pages**: Beautiful auth UI at `/signup` and `/login`
- **Settings Page**: Manage API keys at `/settings`
- **Secure Token Storage**: JWT tokens stored in localStorage

## Quick Start

### 1. Update Environment Variables

Add the new `KEY_ENCRYPTION_SECRET` to your environment file:

```bash
# In backend/.env or root .env
SECRET_KEY=your-secret-key-change-in-production
JWT_SECRET_KEY=your-jwt-secret-key-change-in-production
KEY_ENCRYPTION_SECRET=your-key-encryption-secret-change-in-production
DATABASE_URL=postgresql://rampart:rampart_dev_password@postgres:5432/rampart
```

Generate secure secrets:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. Rebuild and Restart Docker

```bash
# Stop existing containers
docker compose down

# Rebuild with new dependencies
docker compose up -d --build

# Watch backend logs
docker compose logs -f backend
```

The backend will automatically create the new database tables (`users`, `provider_keys`) on startup.

### 3. Test the System

#### Backend API Tests

```bash
# Run auth tests
docker compose exec backend pytest tests/test_auth.py -v

# Run provider keys tests
docker compose exec backend pytest tests/test_provider_keys.py -v
```

#### Manual Testing

1. **Signup**: `POST http://localhost:8000/api/v1/auth/signup`
   ```json
   {
     "email": "user@example.com",
     "password": "securepassword123"
   }
   ```

2. **Login**: `POST http://localhost:8000/api/v1/auth/login`
   ```json
   {
     "email": "user@example.com",
     "password": "securepassword123"
   }
   ```

3. **Add API Key**: `PUT http://localhost:8000/api/v1/providers/keys/openai`
   ```json
   {
     "api_key": "sk-..."
   }
   ```
   Headers: `Authorization: Bearer <your_jwt_token>`

### 4. Use the Frontend

1. Open http://localhost:3000/signup
2. Create an account
3. You'll be redirected to `/settings`
4. Add your OpenAI and/or Anthropic API keys
5. Start using the platform!

## Architecture

### Database Schema

**users table**:
- `id` (UUID, PK)
- `email` (TEXT, UNIQUE)
- `password_hash` (TEXT)
- `created_at`, `updated_at` (TIMESTAMP)
- `is_active` (BOOLEAN)

**provider_keys table**:
- `id` (UUID, PK)
- `user_id` (UUID, FK → users.id)
- `provider` (TEXT: 'openai' | 'anthropic')
- `key_encrypted` (TEXT: AES-GCM encrypted)
- `last_4` (TEXT: last 4 chars for display)
- `status` (TEXT: 'active' | 'revoked')
- `created_at`, `updated_at` (TIMESTAMP)
- UNIQUE constraint on (user_id, provider)

### Security

- **Passwords**: Hashed with bcrypt (12 rounds)
- **API Keys**: Encrypted at rest using AES-256-GCM
- **JWT Tokens**: Signed with HS256, expire in 30 minutes (configurable)
- **Key Encryption**: Uses `KEY_ENCRYPTION_SECRET` + PBKDF2 derivation

### API Endpoints

#### Authentication
- `POST /api/v1/auth/signup` - Create account
- `POST /api/v1/auth/login` - Login
- `GET /api/v1/auth/me` - Get current user (requires auth)
- `POST /api/v1/auth/refresh` - Refresh token (requires auth)

#### Provider Keys
- `GET /api/v1/providers/supported` - List supported providers (public)
- `GET /api/v1/providers/keys` - List user's keys (requires auth)
- `GET /api/v1/providers/keys/{provider}` - Get specific key (requires auth)
- `PUT /api/v1/providers/keys/{provider}` - Set/update key (requires auth)
- `DELETE /api/v1/providers/keys/{provider}` - Delete key (requires auth)

### LLM Proxy Integration

The `LLMProxy` class now:
1. Accepts `user_id` parameter
2. Fetches user's encrypted API key from database
3. Decrypts key on-the-fly
4. Uses user's key for LLM API calls
5. Falls back to system env keys if user has no key

Example:
```python
from integrations.llm_proxy import SecureLLMClient
from uuid import UUID

client = SecureLLMClient(provider="openai")
result = await client.chat(
    prompt="What is AI security?",
    user_id=UUID("user-uuid-here"),  # Uses this user's OpenAI key
    model="gpt-4"
)
```

## Frontend Pages

### `/signup`
- Email + password signup form
- Password validation (min 8 chars)
- Auto-redirect to `/settings` after signup

### `/login`
- Email + password login form
- JWT token stored in localStorage
- Auto-redirect to `/` after login

### `/settings`
- View/manage API keys for OpenAI and Anthropic
- Add, update, or delete keys
- Keys displayed as masked (e.g., `sk-****abcd`)
- Logout button

## Migration from Single-Tenant

If you were using system-level API keys (env vars):

1. **Existing functionality preserved**: System env keys still work as fallback
2. **Users can override**: When a user adds their own key, it takes precedence
3. **Gradual migration**: Users can sign up and add keys at their own pace

## Production Considerations

### Security Hardening
1. **Use HTTPS**: Always use TLS in production
2. **Rotate secrets**: Regularly rotate `KEY_ENCRYPTION_SECRET`
3. **Rate limiting**: Add rate limits on auth endpoints
4. **CORS**: Restrict CORS origins in `backend/api/main.py`
5. **Token expiry**: Consider shorter JWT expiry for production

### Database
1. **Backups**: Regular backups of PostgreSQL
2. **Encryption**: Enable PostgreSQL encryption at rest
3. **Connection pooling**: Configure SQLAlchemy pool size

### Monitoring
1. **Failed logins**: Monitor for brute force attempts
2. **Key usage**: Track which users are using which providers
3. **API errors**: Alert on LLM API failures

## Troubleshooting

### "KEY_ENCRYPTION_SECRET environment variable not set"
- Add `KEY_ENCRYPTION_SECRET` to your `.env` file
- Restart backend: `docker compose restart backend`

### "Invalid token" errors
- Token may have expired (default 30 min)
- User needs to login again
- Check JWT_SECRET_KEY is consistent

### "Failed to decrypt API key"
- Key may have been encrypted with different secret
- Delete and re-add the key
- Check `KEY_ENCRYPTION_SECRET` hasn't changed

### Database connection errors
- Ensure PostgreSQL is running: `docker compose ps`
- Check DATABASE_URL is correct
- Verify network connectivity

## API Examples

### Complete Flow

```bash
# 1. Signup
curl -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"demo123456"}'
# Response: {"token":"eyJ...","user":{...}}

# 2. Save token
TOKEN="eyJ..."

# 3. Add OpenAI key
curl -X PUT http://localhost:8000/api/v1/providers/keys/openai \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"api_key":"sk-..."}'

# 4. List keys
curl http://localhost:8000/api/v1/providers/keys \
  -H "Authorization: Bearer $TOKEN"

# 5. Use LLM (in your app code)
# The proxy will automatically use the user's OpenAI key
```

## Next Steps

1. **Add OAuth**: Integrate Google/GitHub OAuth for easier signup
2. **Organizations**: Multi-user organizations with shared keys
3. **Usage tracking**: Per-user token usage and cost tracking
4. **Billing**: Integrate Stripe for paid plans
5. **Admin panel**: Manage users and monitor usage

## Support

- **API Docs**: http://localhost:8000/docs
- **Frontend**: http://localhost:3000
- **Tests**: `docker compose exec backend pytest tests/ -v`

---

**Built with security in mind. All API keys are encrypted at rest. 🔒**
