"""
Super-admin endpoints — system-wide observability for platform operators.

Access is controlled by the SUPER_ADMIN_EMAILS environment variable
(comma-separated list of email addresses). No database column or schema
migration required; just set the env var and restart.

Example .env entry:
    SUPER_ADMIN_EMAILS=you@example.com,ops@yourcompany.com

Data sources:
    - audit_logs             every authenticated request (volume, latency, status)
    - rampart_api_key_usage  hourly rollups of requests / tokens / cost per API key
    - users / rampart_api_keys
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import text

from api.db import get_conn
from api.routes.auth import TokenData, get_current_user, is_super_admin_email

router = APIRouter()

TimeRange = Literal["24h", "7d", "30d", "90d"]
_RANGE_HOURS: dict[str, int] = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30, "90d": 24 * 90}


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

def require_super_admin(current_user: TokenData = Depends(get_current_user)) -> TokenData:
    """Raise 403 unless the caller's email is in SUPER_ADMIN_EMAILS."""
    if not is_super_admin_email(current_user.email):
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
    total: int
    errors: int
    blocked: int
    auth_failures: int
    avg_latency_ms: Optional[float] = None
    p95_latency_ms: Optional[float] = None
    unique_users: int = 0


class CostStats(BaseModel):
    requests: int
    tokens: int
    cost_usd: float
    active_keys: int


class EndpointStat(BaseModel):
    endpoint: str
    count: int
    errors: int = 0
    avg_latency_ms: Optional[float] = None


class AdminStatsResponse(BaseModel):
    range: str
    users: UserStats
    api_keys: ApiKeyStats
    requests: RequestStats
    usage: CostStats
    usage_all_time: CostStats
    top_endpoints: list[EndpointStat]
    generated_at: datetime


class TimeseriesPoint(BaseModel):
    bucket: datetime
    requests: int = 0
    errors: int = 0
    avg_latency_ms: Optional[float] = None
    tokens: int = 0
    cost_usd: float = 0.0


class TimeseriesResponse(BaseModel):
    range: str
    interval: str
    points: list[TimeseriesPoint]


class UserCostRow(BaseModel):
    user_id: UUID
    email: str
    requests: int
    tokens: int
    cost_usd: float
    active_keys: int
    last_used_at: Optional[datetime] = None


class UserCostResponse(BaseModel):
    range: str
    total_cost_usd: float
    users: list[UserCostRow]


class EndpointCostRow(BaseModel):
    endpoint: str
    requests: int
    tokens: int
    cost_usd: float
    unique_keys: int


class EndpointCostResponse(BaseModel):
    range: str
    endpoints: list[EndpointCostRow]


class AuditLogRow(BaseModel):
    id: str
    timestamp: datetime
    user_id: Optional[str] = None
    email: Optional[str] = None
    api_key_preview: Optional[str] = None
    endpoint: str
    http_method: str
    ip_address: str
    status_code: Optional[int] = None
    processing_time_ms: Optional[float] = None
    event_type: str


class AuditLogResponse(BaseModel):
    total: int
    limit: int
    offset: int
    logs: list[AuditLogRow]


class AdminUserRow(BaseModel):
    id: UUID
    email: str
    created_at: datetime
    is_active: bool
    api_key_count: int
    active_api_key_count: int
    last_seen: Optional[datetime] = None
    requests: int = 0
    tokens: int = 0
    cost_usd: float = 0.0


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


def _range_start(range_: str) -> datetime:
    return datetime.utcnow() - timedelta(hours=_RANGE_HOURS[range_])


def _f(v) -> Optional[float]:
    return float(v) if v is not None else None


def _usage_window(conn, since: Optional[datetime]) -> CostStats:
    """Aggregate rampart_api_key_usage, optionally restricted to rows at/after `since`."""
    where, params = "", {}
    if since is not None:
        # usage rows are keyed by (date, hour); compare on the hour boundary
        where = "WHERE (date > :d OR (date = :d AND hour >= :h))"
        params = {"d": since.date(), "h": since.hour}
    try:
        row = conn.execute(text(f"""
            SELECT COALESCE(SUM(requests_count), 0),
                   COALESCE(SUM(tokens_used), 0),
                   COALESCE(SUM(cost_usd), 0),
                   COUNT(DISTINCT api_key_id)
            FROM rampart_api_key_usage {where}
        """), params).fetchone() or (0, 0, 0, 0)
    except Exception:
        row = (0, 0, 0, 0)
    return CostStats(requests=int(row[0] or 0), tokens=int(row[1] or 0), cost_usd=float(row[2] or 0), active_keys=int(row[3] or 0))


def _usage_where(since: datetime, alias: str = "u") -> tuple[str, dict]:
    return (
        f"({alias}.date > :d OR ({alias}.date = :d AND {alias}.hour >= :h))",
        {"d": since.date(), "h": since.hour},
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/admin/stats", response_model=AdminStatsResponse, tags=["admin"])
async def admin_stats(
    range: TimeRange = Query("24h", description="Window for request/usage stats"),
    _admin: TokenData = Depends(require_super_admin),
) -> AdminStatsResponse:
    """
    System-wide statistics for super-admins:
    - Total / active users and new signups
    - Total / active Rampart API keys
    - Request volume, error rate, latency (avg + p95) from audit_logs within the window
    - Token usage and cost (window + all-time) from rampart_api_key_usage
    - Top 10 endpoints by request count within the window
    """
    now = datetime.utcnow()
    since = _range_start(range)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    sqlite = _is_sqlite()
    active_expr = "is_active = 1" if sqlite else "is_active = TRUE"

    with get_conn() as conn:
        u = conn.execute(text(f"""
            SELECT COUNT(*),
                   SUM(CASE WHEN {active_expr} THEN 1 ELSE 0 END),
                   SUM(CASE WHEN created_at >= :week_ago  THEN 1 ELSE 0 END),
                   SUM(CASE WHEN created_at >= :month_ago THEN 1 ELSE 0 END)
            FROM users
        """), {"week_ago": week_ago, "month_ago": month_ago}).fetchone() or (0, 0, 0, 0)
        user_stats = UserStats(total=u[0] or 0, active=u[1] or 0, new_last_7d=u[2] or 0, new_last_30d=u[3] or 0)

        k = conn.execute(text(f"""
            SELECT COUNT(*),
                   SUM(CASE WHEN {active_expr} THEN 1 ELSE 0 END),
                   SUM(CASE WHEN created_at >= :week_ago THEN 1 ELSE 0 END)
            FROM rampart_api_keys
        """), {"week_ago": week_ago}).fetchone() or (0, 0, 0)
        key_stats = ApiKeyStats(total=k[0] or 0, active=k[1] or 0, created_last_7d=k[2] or 0)

        req_stats = RequestStats(total=0, errors=0, blocked=0, auth_failures=0)
        top_endpoints: list[EndpointStat] = []
        try:
            r = conn.execute(text("""
                SELECT COUNT(*),
                       SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END),
                       SUM(CASE WHEN status_code = 403 OR event_type IN ('blocked', 'policy_block') THEN 1 ELSE 0 END),
                       SUM(CASE WHEN event_type = 'auth_failure' OR status_code = 401 THEN 1 ELSE 0 END),
                       AVG(processing_time_ms),
                       COUNT(DISTINCT user_id)
                FROM audit_logs
                WHERE timestamp >= :since
            """), {"since": since}).fetchone() or (0, 0, 0, 0, None, 0)

            p95 = None
            if sqlite:
                total = int(r[0] or 0)
                if total:
                    off = max(int(total * 0.95) - 1, 0)
                    p95 = conn.execute(text("""
                        SELECT processing_time_ms FROM audit_logs
                        WHERE timestamp >= :since AND processing_time_ms IS NOT NULL
                        ORDER BY processing_time_ms LIMIT 1 OFFSET :off
                    """), {"since": since, "off": off}).scalar()
            else:
                p95 = conn.execute(text("""
                    SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY processing_time_ms)
                    FROM audit_logs WHERE timestamp >= :since AND processing_time_ms IS NOT NULL
                """), {"since": since}).scalar()

            req_stats = RequestStats(
                total=int(r[0] or 0),
                errors=int(r[1] or 0),
                blocked=int(r[2] or 0),
                auth_failures=int(r[3] or 0),
                avg_latency_ms=round(float(r[4]), 2) if r[4] is not None else None,
                p95_latency_ms=round(float(p95), 2) if p95 is not None else None,
                unique_users=int(r[5] or 0),
            )

            rows = conn.execute(text("""
                SELECT endpoint, COUNT(*) AS cnt,
                       SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END),
                       AVG(processing_time_ms)
                FROM audit_logs
                WHERE timestamp >= :since
                GROUP BY endpoint
                ORDER BY cnt DESC
                LIMIT 10
            """), {"since": since}).fetchall()
            top_endpoints = [
                EndpointStat(endpoint=row[0], count=row[1], errors=int(row[2] or 0),
                             avg_latency_ms=round(float(row[3]), 2) if row[3] is not None else None)
                for row in rows
            ]
        except Exception:
            # audit_logs table may not exist on a fresh install
            pass

        usage = _usage_window(conn, since)
        usage_all = _usage_window(conn, None)

    return AdminStatsResponse(
        range=range,
        users=user_stats,
        api_keys=key_stats,
        requests=req_stats,
        usage=usage,
        usage_all_time=usage_all,
        top_endpoints=top_endpoints,
        generated_at=now,
    )


@router.get("/admin/timeseries", response_model=TimeseriesResponse, tags=["admin"])
async def admin_timeseries(
    range: TimeRange = Query("24h"),
    _admin: TokenData = Depends(require_super_admin),
) -> TimeseriesResponse:
    """
    Traffic and cost over time. Hourly buckets for 24h, daily buckets otherwise.
    Request/error/latency come from audit_logs; tokens/cost from rampart_api_key_usage.
    """
    since = _range_start(range)
    hourly = range == "24h"
    sqlite = _is_sqlite()

    if sqlite:
        audit_bucket = "strftime('%Y-%m-%dT%H:00:00', timestamp)" if hourly else "strftime('%Y-%m-%dT00:00:00', timestamp)"
        usage_bucket = "date || 'T' || printf('%02d', hour) || ':00:00'" if hourly else "date || 'T00:00:00'"
    else:
        audit_bucket = "date_trunc('hour', timestamp)" if hourly else "date_trunc('day', timestamp)"
        usage_bucket = "date + make_interval(hours => hour)" if hourly else "date::timestamp"

    buckets: dict[datetime, TimeseriesPoint] = {}

    def _bucket_key(raw) -> datetime:
        if isinstance(raw, datetime):
            return raw
        if isinstance(raw, date):
            return datetime(raw.year, raw.month, raw.day)
        return datetime.fromisoformat(str(raw))

    def _get(raw) -> TimeseriesPoint:
        k = _bucket_key(raw)
        if k not in buckets:
            buckets[k] = TimeseriesPoint(bucket=k)
        return buckets[k]

    with get_conn() as conn:
        try:
            rows = conn.execute(text(f"""
                SELECT {audit_bucket} AS b, COUNT(*),
                       SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END),
                       AVG(processing_time_ms)
                FROM audit_logs
                WHERE timestamp >= :since
                GROUP BY b ORDER BY b
            """), {"since": since}).fetchall()
            for b, cnt, errs, lat in rows:
                p = _get(b)
                p.requests = int(cnt or 0)
                p.errors = int(errs or 0)
                p.avg_latency_ms = round(float(lat), 2) if lat is not None else None
        except Exception:
            pass

        try:
            where, params = _usage_where(since, alias="rampart_api_key_usage")
            rows = conn.execute(text(f"""
                SELECT {usage_bucket} AS b,
                       COALESCE(SUM(tokens_used), 0), COALESCE(SUM(cost_usd), 0)
                FROM rampart_api_key_usage
                WHERE {where}
                GROUP BY b ORDER BY b
            """), params).fetchall()
            for b, tokens, cost in rows:
                p = _get(b)
                p.tokens = int(tokens or 0)
                p.cost_usd = float(cost or 0)
        except Exception:
            pass

    # Zero-fill so charts have a continuous axis
    step = timedelta(hours=1) if hourly else timedelta(days=1)
    cursor = since.replace(minute=0, second=0, microsecond=0)
    if not hourly:
        cursor = cursor.replace(hour=0)
    end = datetime.utcnow()
    while cursor <= end:
        buckets.setdefault(cursor, TimeseriesPoint(bucket=cursor))
        cursor += step

    return TimeseriesResponse(
        range=range,
        interval="hour" if hourly else "day",
        points=[buckets[k] for k in sorted(buckets)],
    )


@router.get("/admin/cost/by-user", response_model=UserCostResponse, tags=["admin"])
async def admin_cost_by_user(
    range: TimeRange = Query("30d"),
    limit: int = Query(25, ge=1, le=200),
    _admin: TokenData = Depends(require_super_admin),
) -> UserCostResponse:
    """Top users by API-key spend within the window."""
    since = _range_start(range)
    sqlite = _is_sqlite()
    active_expr = "k.is_active = 1" if sqlite else "k.is_active = TRUE"
    where, params = _usage_where(since)
    params["limit"] = limit

    with get_conn() as conn:
        try:
            rows = conn.execute(text(f"""
                SELECT usr.id, usr.email,
                       COALESCE(SUM(u.requests_count), 0),
                       COALESCE(SUM(u.tokens_used), 0),
                       COALESCE(SUM(u.cost_usd), 0) AS cost,
                       COUNT(DISTINCT CASE WHEN {active_expr} THEN k.id END),
                       MAX(k.last_used_at)
                FROM rampart_api_key_usage u
                JOIN rampart_api_keys k ON k.id = u.api_key_id
                JOIN users usr ON usr.id = k.user_id
                WHERE {where}
                GROUP BY usr.id, usr.email
                ORDER BY cost DESC, 3 DESC
                LIMIT :limit
            """), params).fetchall()
        except Exception:
            rows = []

    users = [
        UserCostRow(user_id=r[0], email=r[1], requests=int(r[2] or 0), tokens=int(r[3] or 0),
                    cost_usd=float(r[4] or 0), active_keys=int(r[5] or 0), last_used_at=r[6])
        for r in rows
    ]
    return UserCostResponse(range=range, total_cost_usd=sum(u.cost_usd for u in users), users=users)


@router.get("/admin/cost/by-endpoint", response_model=EndpointCostResponse, tags=["admin"])
async def admin_cost_by_endpoint(
    range: TimeRange = Query("30d"),
    _admin: TokenData = Depends(require_super_admin),
) -> EndpointCostResponse:
    """Requests, tokens and cost grouped by API endpoint within the window."""
    since = _range_start(range)
    where, params = _usage_where(since)

    with get_conn() as conn:
        try:
            rows = conn.execute(text(f"""
                SELECT u.endpoint,
                       COALESCE(SUM(u.requests_count), 0) AS reqs,
                       COALESCE(SUM(u.tokens_used), 0),
                       COALESCE(SUM(u.cost_usd), 0),
                       COUNT(DISTINCT u.api_key_id)
                FROM rampart_api_key_usage u
                WHERE {where}
                GROUP BY u.endpoint
                ORDER BY reqs DESC
            """), params).fetchall()
        except Exception:
            rows = []

    return EndpointCostResponse(
        range=range,
        endpoints=[
            EndpointCostRow(endpoint=r[0], requests=int(r[1] or 0), tokens=int(r[2] or 0),
                            cost_usd=float(r[3] or 0), unique_keys=int(r[4] or 0))
            for r in rows
        ],
    )


@router.get("/admin/audit-logs", response_model=AuditLogResponse, tags=["admin"])
async def admin_audit_logs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    endpoint: Optional[str] = Query(None, description="Substring filter on endpoint path"),
    user_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    errors_only: bool = Query(False, description="Only rows with status_code >= 400"),
    _admin: TokenData = Depends(require_super_admin),
) -> AuditLogResponse:
    """Paginated, filterable view of the raw audit trail (most recent first)."""
    clauses: list[str] = []
    params: dict = {}
    if endpoint:
        clauses.append("a.endpoint LIKE :endpoint")
        params["endpoint"] = f"%{endpoint}%"
    if user_id:
        clauses.append("a.user_id = :user_id")
        params["user_id"] = user_id
    if event_type:
        clauses.append("a.event_type = :event_type")
        params["event_type"] = event_type
    if errors_only:
        clauses.append("a.status_code >= 400")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_conn() as conn:
        try:
            total = conn.execute(text(f"SELECT COUNT(*) FROM audit_logs a {where}"), params).scalar() or 0
            rows = conn.execute(text(f"""
                SELECT a.id, a.timestamp, a.user_id, usr.email, a.api_key_preview, a.endpoint,
                       a.http_method, a.ip_address, a.status_code, a.processing_time_ms, a.event_type
                FROM audit_logs a
                LEFT JOIN users usr ON CAST(usr.id AS TEXT) = a.user_id
                {where}
                ORDER BY a.timestamp DESC
                LIMIT :limit OFFSET :offset
            """), {**params, "limit": limit, "offset": offset}).fetchall()
        except Exception:
            total, rows = 0, []

    return AuditLogResponse(
        total=total, limit=limit, offset=offset,
        logs=[
            AuditLogRow(id=str(r[0]), timestamp=r[1], user_id=r[2], email=r[3], api_key_preview=r[4],
                        endpoint=r[5], http_method=r[6], ip_address=r[7], status_code=r[8],
                        processing_time_ms=_f(r[9]), event_type=r[10])
            for r in rows
        ],
    )


@router.get("/admin/users", response_model=AdminUsersResponse, tags=["admin"])
async def admin_users(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None, description="Filter by email (case-insensitive substring)"),
    sort: Literal["created_at", "cost_usd", "requests", "last_seen"] = Query("created_at"),
    _admin: TokenData = Depends(require_super_admin),
) -> AdminUsersResponse:
    """
    Paginated list of all users with API key counts, last-seen timestamp and
    all-time usage (requests / tokens / cost).
    """
    sqlite = _is_sqlite()
    active_expr = "k.is_active = 1" if sqlite else "k.is_active = TRUE"
    order = {"created_at": "u.created_at DESC", "cost_usd": "cost_usd DESC", "requests": "requests DESC", "last_seen": "last_seen DESC"}[sort]

    where = ""
    params: Dict[str, Any] = {"limit": limit, "offset": offset}
    count_params: Dict[str, Any] = {}
    if search:
        where = "WHERE LOWER(u.email) LIKE :search"
        params["search"] = count_params["search"] = f"%{search.lower()}%"

    with get_conn() as conn:
        total = conn.execute(text(f"SELECT COUNT(*) FROM users u {where}"), count_params).scalar() or 0
        rows = conn.execute(text(f"""
            WITH key_usage AS (
                SELECT api_key_id,
                       SUM(requests_count) AS requests,
                       SUM(tokens_used)    AS tokens,
                       SUM(cost_usd)       AS cost_usd
                FROM rampart_api_key_usage
                GROUP BY api_key_id
            )
            SELECT u.id, u.email, u.created_at, u.is_active,
                   COUNT(k.id)                                             AS key_count,
                   SUM(CASE WHEN {active_expr} THEN 1 ELSE 0 END)          AS active_key_count,
                   MAX(k.last_used_at)                                     AS last_seen,
                   COALESCE(SUM(ku.requests), 0)                           AS requests,
                   COALESCE(SUM(ku.tokens), 0)                             AS tokens,
                   COALESCE(SUM(ku.cost_usd), 0)                           AS cost_usd
            FROM users u
            LEFT JOIN rampart_api_keys k ON k.user_id = u.id
            LEFT JOIN key_usage ku ON ku.api_key_id = k.id
            {where}
            GROUP BY u.id, u.email, u.created_at, u.is_active
            ORDER BY {order}
            LIMIT :limit OFFSET :offset
        """), params).fetchall()

    return AdminUsersResponse(
        total=total, limit=limit, offset=offset,
        users=[
            AdminUserRow(
                id=row[0], email=row[1], created_at=row[2], is_active=row[3],
                api_key_count=row[4] or 0, active_api_key_count=row[5] or 0, last_seen=row[6],
                requests=int(row[7] or 0), tokens=int(row[8] or 0), cost_usd=float(row[9] or 0),
            )
            for row in rows
        ],
    )
