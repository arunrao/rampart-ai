#!/usr/bin/env python3
"""
Check API keys and usage for arunrao@gmail.com
"""
import sys
import os
sys.path.append('/app')

from api.db import get_conn
from sqlalchemy import text

def check_user_api_keys():
    """Check API keys and usage for arunrao@gmail.com"""
    with get_conn() as conn:
        # Find the user and API key
        result = conn.execute(
            text("""
                SELECT k.id, k.user_id, k.key_name, k.key_preview, k.is_active, k.last_used_at, u.email
                FROM rampart_api_keys k
                JOIN users u ON k.user_id = u.id
                WHERE u.email = :email
            """),
            {"email": "arunrao@gmail.com"}
        ).fetchall()
        
        if result:
            for row in result:
                print(f"Key ID: {row[0]}")
                print(f"User ID: {row[1]}")
                print(f"Key Name: {row[2]}")
                print(f"Key Preview: {row[3]}")
                print(f"Active: {row[4]}")
                print(f"Last Used: {row[5]}")
                print(f"User Email: {row[6]}")
                print("---")
                
                # Check usage stats for this key
                usage = conn.execute(
                    text("""
                        SELECT 
                            endpoint,
                            SUM(requests_count) as total_requests,
                            SUM(tokens_used) as total_tokens,
                            SUM(cost_usd) as total_cost,
                            MAX(date) as last_date
                        FROM rampart_api_key_usage 
                        WHERE api_key_id = :key_id
                        GROUP BY endpoint
                    """),
                    {"key_id": row[0]}
                ).fetchall()
                
                if usage:
                    print("Usage Stats:")
                    for u in usage:
                        print(f"  {u[0]}: {u[1]} requests, {u[2]} tokens, ${u[3]:.4f}, last: {u[4]}")
                else:
                    print("No usage stats found")
                print("=" * 50)
        else:
            print("No API keys found for arunrao@gmail.com")

if __name__ == "__main__":
    check_user_api_keys()
