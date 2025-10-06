-- Migration: Add Rampart API Keys table
-- This allows users to create API keys for their applications

CREATE TABLE rampart_api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_name VARCHAR(100) NOT NULL,
    key_prefix VARCHAR(20) NOT NULL,  -- e.g., 'rmp_' 
    key_hash VARCHAR(255) NOT NULL,   -- bcrypt hash of full key
    key_preview VARCHAR(20) NOT NULL, -- last 4 chars for display
    permissions TEXT[] DEFAULT ARRAY['security:analyze', 'filter:pii', 'llm:chat'], -- JSON array of permissions
    rate_limit_per_minute INTEGER DEFAULT 60,
    rate_limit_per_hour INTEGER DEFAULT 1000,
    is_active BOOLEAN DEFAULT true,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP, -- Optional expiration
    
    UNIQUE(key_prefix, key_hash),
    INDEX idx_rampart_api_keys_user_id (user_id),
    INDEX idx_rampart_api_keys_key_hash (key_hash),
    INDEX idx_rampart_api_keys_active (is_active)
);

-- Add usage tracking table
CREATE TABLE rampart_api_key_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    api_key_id UUID NOT NULL REFERENCES rampart_api_keys(id) ON DELETE CASCADE,
    endpoint VARCHAR(100) NOT NULL,
    requests_count INTEGER DEFAULT 1,
    tokens_used INTEGER DEFAULT 0,
    cost_usd DECIMAL(10,6) DEFAULT 0,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    hour INTEGER NOT NULL DEFAULT EXTRACT(HOUR FROM CURRENT_TIMESTAMP),
    
    UNIQUE(api_key_id, endpoint, date, hour),
    INDEX idx_api_key_usage_date (date),
    INDEX idx_api_key_usage_key_id (api_key_id)
);

-- Add permissions enum for reference
CREATE TYPE rampart_permission AS ENUM (
    'security:analyze',
    'security:batch',
    'filter:pii',
    'filter:toxicity', 
    'llm:chat',
    'llm:stream',
    'keys:manage',
    'analytics:read',
    'test:run'
);

COMMENT ON TABLE rampart_api_keys IS 'API keys for Rampart application access (separate from LLM provider keys)';
COMMENT ON COLUMN rampart_api_keys.key_prefix IS 'Key prefix like rmp_live_, rmp_test_ for easy identification';
COMMENT ON COLUMN rampart_api_keys.permissions IS 'Array of allowed endpoints/actions';
COMMENT ON COLUMN rampart_api_keys.rate_limit_per_minute IS 'Per-key rate limiting override';
