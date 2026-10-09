#!/usr/bin/env python3
"""
Generate secure secrets for Project Rampart
"""
import secrets

print("=== Project Rampart - Secret Generator ===\n")
print("Copy these values to your backend/.env file:\n")
print(f"SECRET_KEY={secrets.token_urlsafe(32)}")
print(f"JWT_SECRET_KEY={secrets.token_urlsafe(32)}")
print(f"KEY_ENCRYPTION_SECRET={secrets.token_urlsafe(32)}")
print(f"KEY_ENCRYPTION_SALT={secrets.token_urlsafe(16)}  # new installs only; never change on an existing DB")
print(f"POSTGRES_PASSWORD={secrets.token_urlsafe(16)}")
print("\nDone! Add these to backend/.env")
