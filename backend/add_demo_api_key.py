#!/usr/bin/env python3
"""
Add the demo API key to the database for usage tracking
"""
import sys
import os
sys.path.append('/app')

from api.db import get_conn
from api.routes.rampart_keys import generate_rampart_api_key, get_key_preview
from sqlalchemy import text
from uuid import uuid4
from datetime import datetime
import bcrypt

def add_demo_api_key():
    """Add the demo API key to the database"""
    # The API key you're using
    api_key = "rmp_live_q-j5HB17ojOaVP2wOt63jGwNyXxMTLQ600NbQ-o3a-U"
    
    # Get the test user ID
    with get_conn() as conn:
        user_result = conn.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": "test@example.com"}
        ).fetchone()
        
        if not user_result:
            print("Test user not found. Please run create_test_user.py first")
            return
        
        user_id = user_result[0]
        
        # Check if this API key already exists
        existing = conn.execute(
            text("SELECT id FROM rampart_api_keys WHERE key_preview LIKE :preview"),
            {"preview": "%q-j5HB17%"}
        ).fetchone()
        
        if existing:
            print(f"API key already exists with ID: {existing[0]}")
            return
        
        # Create hash for the API key
        key_hash = bcrypt.hashpw(api_key.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
        key_preview = get_key_preview(api_key)
        key_prefix = "rmp_live_"
        
        # Insert the API key
        key_id = uuid4()
        now = datetime.utcnow()
        
        conn.execute(
            text("""
                INSERT INTO rampart_api_keys (
                    id, user_id, key_name, key_prefix, key_hash, key_preview,
                    permissions, rate_limit_per_minute, rate_limit_per_hour,
                    is_active, created_at, updated_at
                ) VALUES (
                    :id, :user_id, :key_name, :key_prefix, :key_hash, :key_preview,
                    :permissions, :rate_limit_per_minute, :rate_limit_per_hour,
                    :is_active, :created_at, :updated_at
                )
            """),
            {
                "id": str(key_id),
                "user_id": str(user_id),
                "key_name": "Demo API Key",
                "key_prefix": key_prefix,
                "key_hash": key_hash,
                "key_preview": key_preview,
                "permissions": '["security:analyze", "filter:pii", "llm:chat"]',
                "rate_limit_per_minute": 60,
                "rate_limit_per_hour": 1000,
                "is_active": True,
                "created_at": now,
                "updated_at": now
            }
        )
        conn.commit()
        
        print(f"Added demo API key with ID: {key_id}")
        print(f"Key preview: {key_preview}")
        print(f"User ID: {user_id}")

if __name__ == "__main__":
    add_demo_api_key()
