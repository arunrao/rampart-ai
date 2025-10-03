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
print("\nDone! Add these to backend/.env")
