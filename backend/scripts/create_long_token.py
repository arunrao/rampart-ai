#!/usr/bin/env python3
"""
Create a long-lived JWT token for arunrao@gmail.com for testing
"""
import sys
import os
sys.path.append('/app')

from api.db import get_conn
from api.routes.auth import create_access_token
from api.config import get_settings
from sqlalchemy import text
from datetime import datetime, timedelta
import jwt

def create_long_token():
    """Create a long-lived JWT token for arunrao@gmail.com"""
    settings = get_settings()
    
    with get_conn() as conn:
        # Find the user
        result = conn.execute(
            text("SELECT id, email FROM users WHERE email = :email"),
            {"email": "arunrao@gmail.com"}
        ).fetchone()
        
        if not result:
            print("User arunrao@gmail.com not found")
            return
        
        user_id, email = result
        
        # Create a long-lived token (24 hours)
        expire = datetime.utcnow() + timedelta(hours=24)
        payload = {
            "user_id": str(user_id),
            "email": email,
            "exp": expire,
            "iat": datetime.utcnow()
        }
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
        
        print(f"User ID: {user_id}")
        print(f"Email: {email}")
        print(f"Token expires: {expire}")
        print(f"Long-lived JWT Token:")
        print(token)
        
        return user_id, token

if __name__ == "__main__":
    create_long_token()
