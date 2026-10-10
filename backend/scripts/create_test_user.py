#!/usr/bin/env python3
"""
Create a test user for API key testing
"""
import sys
import os
sys.path.append('/app')

from api.db import get_conn
from api.routes.auth import hash_password, create_access_token
from sqlalchemy import text
from uuid import uuid4
from datetime import datetime

def create_test_user():
    """Create a test user for API key testing"""
    user_id = uuid4()
    email = "test@example.com"
    password = "testpassword123"
    password_hash = hash_password(password)
    
    with get_conn() as conn:
        # Check if user already exists
        existing = conn.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": email}
        ).fetchone()
        
        if existing:
            print(f"Test user {email} already exists with ID: {existing[0]}")
            user_id = existing[0]
        else:
            # Create the user
            conn.execute(
                text("""
                    INSERT INTO users (id, email, password_hash, created_at, updated_at, is_active)
                    VALUES (:id, :email, :password_hash, :created_at, :updated_at, :is_active)
                """),
                {
                    "id": str(user_id),
                    "email": email,
                    "password_hash": password_hash,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "is_active": True
                }
            )
            conn.commit()
            print(f"Created test user {email} with ID: {user_id}")
        
        # Create a JWT token for testing
        token = create_access_token(user_id, email)
        print(f"JWT Token: {token}")
        
        return user_id, token

if __name__ == "__main__":
    create_test_user()
