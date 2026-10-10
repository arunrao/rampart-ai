#!/usr/bin/env python3
"""
Create a JWT token for arunrao@gmail.com to test dashboard analytics
"""
import sys
from pathlib import Path
import os
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/

from api.db import get_conn
from api.routes.auth import create_access_token
from sqlalchemy import text

def create_arun_token():
    """Create a JWT token for arunrao@gmail.com"""
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
        
        # Create a JWT token
        token = create_access_token(user_id, email)
        print(f"User ID: {user_id}")
        print(f"Email: {email}")
        print(f"JWT Token: {token}")
        
        return user_id, token

if __name__ == "__main__":
    create_arun_token()
