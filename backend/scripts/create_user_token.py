#!/usr/bin/env python3
"""
Create a JWT token for an existing user, e.g. to test dashboard analytics.

Usage: python scripts/create_user_token.py <email>
"""
import sys
from pathlib import Path
import os
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/

from api.db import get_conn
from api.routes.auth import create_access_token
from sqlalchemy import text

def create_user_token(email: str):
    """Create a JWT token for the given email"""
    with get_conn() as conn:
        # Find the user
        result = conn.execute(
            text("SELECT id, email FROM users WHERE email = :email"),
            {"email": email}
        ).fetchone()
        
        if not result:
            print(f"User {email} not found")
            return
        
        user_id, email = result
        
        # Create a JWT token
        token = create_access_token(user_id, email)
        print(f"User ID: {user_id}")
        print(f"Email: {email}")
        print(f"JWT Token: {token}")
        
        return user_id, token

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/create_user_token.py <email>")
        sys.exit(1)
    create_user_token(sys.argv[1])
