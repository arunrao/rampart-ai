"""
Observability endpoints - traces, spans, analytics
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4

from api.routes.auth import get_current_user, TokenData

router = APIRouter()


class Trace(BaseModel):
    """Trace model"""
    id: UUID
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    name: str
    created_at: datetime
    updated_at: datetime
    status: str
    total_tokens: int = 0
    total_cost: float = 0.0
    total_latency_ms: float = 0.0
    metadata: Optional[Dict[str, Any]] = None


class TraceCreate(BaseModel):
    """Create a new trace"""
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    name: str
    metadata: Optional[Dict[str, Any]] = None


class Span(BaseModel):
    """Span model"""
    id: UUID
    trace_id: UUID
    parent_span_id: Optional[UUID] = None
    name: str
    span_type: str
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    tokens_used: Optional[int] = None
    cost: Optional[float] = None
    latency_ms: Optional[float] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict[str, Any]] = None


class SpanCreate(BaseModel):
    """Create a new span"""
    trace_id: UUID
    parent_span_id: Optional[UUID] = None
    name: str
    span_type: str
    input_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class SpanUpdate(BaseModel):
    """Update a span"""
    output_data: Optional[Dict[str, Any]] = None
    tokens_used: Optional[int] = None
    cost: Optional[float] = None
    latency_ms: Optional[float] = None
    status: str = "completed"
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# In-memory storage
traces_db: Dict[UUID, Trace] = {}
spans_db: Dict[UUID, Span] = {}


@router.post("/traces", response_model=Trace, status_code=201)
async def create_trace(
    trace: TraceCreate,
    current_user: TokenData = Depends(get_current_user)
):
    """Create a new trace for observability"""
    trace_id = uuid4()
    new_trace = Trace(
        id=trace_id,
        session_id=trace.session_id,
        user_id=trace.user_id,
        name=trace.name,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        status="active",
        metadata=trace.metadata
    )
    traces_db[trace_id] = new_trace
    return new_trace


@router.get("/traces", response_model=List[Trace])
async def list_traces(
    current_user: TokenData = Depends(get_current_user),
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """List traces with optional filtering"""
    filtered_traces = list(traces_db.values())
    
    if user_id:
        filtered_traces = [t for t in filtered_traces if t.user_id == user_id]
    if session_id:
        filtered_traces = [t for t in filtered_traces if t.session_id == session_id]
    
    # Sort by created_at descending
    filtered_traces.sort(key=lambda x: x.created_at, reverse=True)
    
    return filtered_traces[offset:offset + limit]


@router.get("/traces/{trace_id}", response_model=Trace)
async def get_trace(
    trace_id: UUID,
    current_user: TokenData = Depends(get_current_user)
):
    """Get a specific trace by ID"""
    if trace_id not in traces_db:
        raise HTTPException(status_code=404, detail="Trace not found")
    return traces_db[trace_id]


@router.post("/spans", response_model=Span, status_code=201)
async def create_span(
    span: SpanCreate,
    current_user: TokenData = Depends(get_current_user)
):
    """Create a new span within a trace"""
    if span.trace_id not in traces_db:
        raise HTTPException(status_code=404, detail="Trace not found")
    
    span_id = uuid4()
    new_span = Span(
        id=span_id,
        trace_id=span.trace_id,
        parent_span_id=span.parent_span_id,
        name=span.name,
        span_type=span.span_type,
        input_data=span.input_data,
        output_data=None,
        tokens_used=None,
        cost=None,
        latency_ms=None,
        status="active",
        error_message=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        metadata=span.metadata
    )
    spans_db[span_id] = new_span
    return new_span


@router.patch("/spans/{span_id}", response_model=Span)
async def update_span(
    span_id: UUID,
    update: SpanUpdate,
    current_user: TokenData = Depends(get_current_user)
):
    """Update span with completion data"""
    if span_id not in spans_db:
        raise HTTPException(status_code=404, detail="Span not found")
    
    span = spans_db[span_id]
    
    # Update fields
    if update.output_data is not None:
        span.output_data = update.output_data
    if update.tokens_used is not None:
        span.tokens_used = update.tokens_used
    if update.cost is not None:
        span.cost = update.cost
    if update.latency_ms is not None:
        span.latency_ms = update.latency_ms
    span.status = update.status
    if update.error_message is not None:
        span.error_message = update.error_message
    if update.metadata is not None:
        span.metadata = {**(span.metadata or {}), **update.metadata}
    
    span.updated_at = datetime.utcnow()
    
    # Update trace totals
    trace = traces_db[span.trace_id]
    trace_spans = [s for s in spans_db.values() if s.trace_id == span.trace_id]
    trace.total_tokens = sum(s.tokens_used or 0 for s in trace_spans)
    trace.total_cost = sum(s.cost or 0.0 for s in trace_spans)
    trace.total_latency_ms = sum(s.latency_ms or 0.0 for s in trace_spans)
    trace.updated_at = datetime.utcnow()
    
    return span


@router.get("/traces/{trace_id}/spans", response_model=List[Span])
async def get_trace_spans(
    trace_id: UUID,
    current_user: TokenData = Depends(get_current_user)
):
    """Get all spans for a trace"""
    if trace_id not in traces_db:
        raise HTTPException(status_code=404, detail="Trace not found")
    
    trace_spans = [s for s in spans_db.values() if s.trace_id == trace_id]
    trace_spans.sort(key=lambda x: x.created_at)
    return trace_spans


@router.get("/analytics/summary")
async def get_analytics_summary(current_user: TokenData = Depends(get_current_user)):
    """Get comprehensive analytics summary including both JWT and API key activity"""
    from api.db import get_conn
    from sqlalchemy import text
    
    # Get trace-based analytics (JWT activity)
    total_traces = len(traces_db)
    total_spans = len(spans_db)
    trace_tokens = sum(t.total_tokens for t in traces_db.values())
    trace_cost = sum(t.total_cost for t in traces_db.values())
    avg_latency = sum(t.total_latency_ms for t in traces_db.values()) / max(total_traces, 1)
    
    # Get API key usage analytics (includes web demo and application usage)
    api_key_requests = 0
    api_key_tokens = 0
    api_key_cost = 0.0
    
    try:
        with get_conn() as conn:
            # Get all API keys for this user
            api_keys_result = conn.execute(
                text("""
                    SELECT total_requests, tokens_used, cost_usd 
                    FROM rampart_api_keys 
                    WHERE user_id = :user_id AND is_active = true
                """),
                {"user_id": current_user.user_id}
            ).fetchall()
            
            for key_stats in api_keys_result:
                api_key_requests += key_stats[0] or 0
                api_key_tokens += key_stats[1] or 0
                api_key_cost += key_stats[2] or 0.0
    except Exception:
        # If database query fails, continue with trace data only
        pass
    
    # Aggregate totals
    total_requests = total_traces + api_key_requests
    total_tokens = trace_tokens + api_key_tokens
    total_cost = trace_cost + api_key_cost
    
    return {
        "total_requests": total_requests,
        "total_traces": total_traces,
        "total_spans": total_spans,
        "total_tokens": total_tokens,
        "total_cost": round(total_cost, 4),
        "average_latency_ms": round(avg_latency, 2),
        "api_key_requests": api_key_requests,
        "jwt_requests": total_traces,
        "breakdown": {
            "dashboard_activity": {
                "requests": total_traces,
                "tokens": trace_tokens,
                "cost": round(trace_cost, 4)
            },
            "api_key_activity": {
                "requests": api_key_requests,
                "tokens": api_key_tokens,
                "cost": round(api_key_cost, 4)
            }
        }
    }
