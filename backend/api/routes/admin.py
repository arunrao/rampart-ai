"""
Super-admin endpoints — system-wide observability for platform operators.

Access is controlled by the SUPER_ADMIN_EMAILS environment variable
(comma-separated list of email addresses). No database column or schema
migration required; just set the env var and restart.

Example .env entry:
    SUPER_ADMIN_EMAILS=you@example.com,ops@yourcompany.com
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import text

from api.config import get_settings
from api.db import get_conn
from api.routes.auth import TokenData, get_current_user

router = APIRouter()
settings = get_settings()


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

def require_super_admin(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    """Raise 403 unless the caller's email is in SUPER_ADMIN_EMAILS."""
    allowed: set[str] = {
        e.strip().lower()
        for e in settings.super_admin_emails.split(",")
        if e.strip()
    }
    if not allowed or current_user.email.lower() not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super-admin access required",
        )
    return current_user


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class UserStats(BaseModel):
    total: int
    active: int
    new_last_7d: int
    new_last_30d: int


class ApiKeyStats(BaseModel):
    total: int
    active: int
    created_last_7d: int


class RequestStats(BaseModel):
    total_24h: int
    blocked_24h: int
    auth_failures_24h: int
    avg_latency_ms: Optional[float] = None


class EndpointStat(BaseModel):
    endpoint: str
    count: int


class AdminStatsResponse(BaseModel):
    users: UserStats
    api_keys: ApiKeyStats
    requests_24h: RequestStats
    top_endpoints: list[EndpointStat]
    generated_at: datetime


class AdminUserRow(BaseModel):
    id: UUID
    email: str
    created_at: datetime
    is_active: bool
    api_key_count: int
    active_api_key_count: int
    last_seen: Optional[datetime] = None


class AdminUsersResponse(BaseModel):
    total: int
    limit: int
    offset: int
    users: list[AdminUserRow]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_sqlite() -> bool:
    try:
        from api.db import DATABASE_URL  # type: ignore[attr-defined]
        return "sqlite" in DATABASE_URL.lower()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/admin/stats", response_model=AdminStatsResponse, tags=["admin"])
async def admin_stats(_admin: TokenData = Depends(require_super_admin)) -> AdminStatsResponse:
    """
    System-wide statistics for super-admins:
    - Total / active users and new signups
    - Total / active Rampart API keys
    - Request volume, error rate, avg latency (last 24 h) from audit_logs
    - Top 10 endpoints by request count (last 24 h)
    """
    now = datetime.utcnow()
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    sqlite = _is_sqlite()

    with get_conn() as conn:
        # --- User counts ---
        if sqlite:
            u = conn.execute(text("""
                SELECT
                  COUNT(*),
                  SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END),
                  SUM(CASE WHEN created_at >= :week_ago  THEN 1 ELSE 0 END),
                  SUM(CASE WHEN created_at >= :month_ago THEN 1 ELSE 0 END)
                FROM users
            """), {"week_ago": week_ago, "month_ago": month_ago}).fetchone() or (0, 0, 0, 0)
        else:
            u = conn.execute(text("""
                SELECT
                  COUNT(*),
                  COUNT(*) FILTER (WHERE is_active = TRUE),
                  COUNT(*) FILTER (WHERE created_at >= :week_ago),
                  COUNT(*) FILTER (WHERE created_at >= :month_ago)
                FROM users
            """), {"week_ago": week_ago, "month_ago": month_ago}).fetchone() or (0, 0, 0, 0)

        user_stats = UserStats(
            total=u[0] or 0,
            active=u[1] or 0,
            new_last_7d=u[2] or 0,
            new_last_30d=u[3] or 0,
        )

        # --- API key counts ---
        if sqlite:
            k = conn.execute(text("""
                SELECT
                  COUNT(*),
                  SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END),
                  SUM(CASE WHEN created_at >= :week_ago THEN 1 ELSE 0 END)
                FROM rampart_api_keys
            """), {"week_ago": week_ago}).fetchone() or (0, 0, 0)
        else:
            k = conn.execute(text("""
                SELECT
                  COUNT(*),
                  COUNT(*) FILTER (WHERE is_active = TRUE),
                  COUNT(*) FILTER (WHERE created_at >= :week_ago)
                FROM rampart_api_keys
            """), {"week_ago": week_ago}).fetchone() or (0, 0, 0)

        key_stats = ApiKeyStats(
            total=k[0] or 0,
            active=k[1] or 0,
            created_last_7d=k[2] or 0,
        )

        # --- Request stats from audit_logs (may not exist yet on fresh installs) ---
        req_stats = RequestStats(total_24h=0, blocked_24h=0, auth_failures_24h=0)
        top_endpoints: list[EndpointStat] = []
        try:
            if sqlite:
                r = conn.execute(text("""
                    SELECT
                      COUNT(*),
                      SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END),
                      SUM(CASE WHEN event_type = 'auth_failure' THEN 1 ELSE 0 END),
                      ROUND(AVG(processing_time_ms), 2)
                    FROM audit_logs
                    WHERE timestamp >= :day_ago
                """), {"day_ago": day_ago}).fetchone() or (0, 0, 0, None)
            else:
                r = conn.execute(text("""
                    SELECT
                      COUNT(*),
                      COUNT(*) FILTER (WHERE status_code >= 400),
                      COUNT(*) FILTER (WHERE event_type = 'auth_failure'),
                      ROUND(AVG(processing_time_ms)::numeric, 2)
                    FROM audit_logs
                    WHERE timestamp >= :day_ago
                """), {"day_ago": day_ago}).fetchone() or (0, 0, 0, None)

            req_stats = RequestStats(
                total_24h=r[0] or 0,
                blocked_24h=r[1] or 0,
                auth_failures_24h=r[2] or 0,
                avg_latency_ms=float(r[3]) if r[3] is not None else None,
            )

            rows = conn.execute(text("""
                SELECT endpoint, COUNT(*) AS cnt
                FROM audit_logs
                WHERE timestamp >= :day_ago
                GROUP BY endpoint
                ORDER BY cnt DESC
                LIMIT 10
            """), {"day_ago": day_ago}).fetchall()
            top_endpoints = [EndpointStat(endpoint=row[0], count=row[1]) for row in rows]

        except Exception:
            # audit_logs table may not exist on a fresh/SQLite install
            pass

    return AdminStatsResponse(
        users=user_stats,
        api_keys=key_stats,
        requests_24h=req_stats,
        top_endpoints=top_endpoints,
        generated_at=now,
    )


@router.get("/admin/users", response_model=AdminUsersResponse, tags=["admin"])
async def admin_users(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None, description="Filter by email (case-insensitive substring)"),
    _admin: TokenData = Depends(require_super_admin),
) -> AdminUsersResponse:
    """
    Paginated list of all users with their API key counts and last-seen timestamp.

    - **limit** / **offset** for pagination
    - **search** to filter by email substring
    """
    sqlite = _is_sqlite()

    with get_conn() as conn:
        if search:
            where = "WHERE LOWER(u.email) LIKE :search"
            params: dict = {"limit": limit, "offset": offset, "search": f"%{search.lower()}%"}
            count_params: dict = {"search": f"%{search.lower()}%"}
        else:
            where = ""
            params = {"limit": limit, "offset": offset}
            count_params = {}

        total = conn.execute(
            text(f"SELECT COUNT(*) FROM users u {where}"),
            count_params,
        ).scalar() or 0

        if sqlite:
            rows = conn.execute(text(f"""
                SELECT
                  u.id,
                  u.email,
                  u.created_at,
                  u.is_active,
                  COUNT(k.id)                                                     AS key_count,
                  SUM(CASE WHEN k.is_active = 1 THEN 1 ELSE 0 END)              AS active_key_count,
                  MAX(k.last_used_at)                                             AS last_seen
                FROM users u
                LEFT JOIN rampart_api_keys k ON k.user_id = u.id
                {where}
                GROUP BY u.id, u.email, u.created_at, u.is_active
                ORDER BY u.created_at DESC
                LIMIT :limit OFFSET :offset
            """), params).fetchall()
        else:
            rows = conn.execute(text(f"""
                SELECT
                  u.id,
                  u.email,
                  u.created_at,
                  u.is_active,
                  COUNT(k.id)                                                     AS key_count,
                  COUNT(k.id) FILTER (WHERE k.is_active = TRUE)                 AS active_key_count,
                  MAX(k.last_used_at)                                             AS last_seen
                FROM users u
                LEFT JOIN rampart_api_keys k ON k.user_id = u.id
                {where}
                GROUP BY u.id, u.email, u.created_at, u.is_active
                ORDER BY u.created_at DESC
                LIMIT :limit OFFSET :offset
            """), params).fetchall()

    return AdminUsersResponse(
        total=total,
        limit=limit,
        offset=offset,
        users=[
            AdminUserRow(
                id=row[0],
                email=row[1],
                created_at=row[2],
                is_active=row[3],
                api_key_count=row[4] or 0,
                active_api_key_count=row[5] or 0,
                last_seen=row[6],
            )
            for row in rows
        ],
    )
