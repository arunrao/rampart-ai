"""
Dedicated prompt-injection scanning endpoints.

    POST /scan/injection           single document
    POST /scan/injection/batch     up to ``scan_injection_batch_max`` documents
    POST /scan/injection/feedback  label a previous result by content_sha256
    GET  /scan/injection/results/{id}  stored result (only when store=true was requested)

Privacy defaults: content is never echoed and never retained unless the caller
opts in with ``return_content`` / ``store``. Logs carry hashes and verdicts only.

Rate limits: the global per-IP limiter and each API key's own per-minute /
per-hour limits apply. Exceeding either returns 429 with a ``Retry-After``
header (seconds). Batch requests count as one request against those limits.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.config import get_settings
from api.db import get_db
from api.memstore import BoundedDict
from api.models import InjectionFeedback
from api.routes.auth import TokenData, get_current_user
from api.routes.rampart_keys import track_api_key_usage
from api.routes.security import get_detector, require_auth
from models.injection_policy import PROFILES, POLICY_VERSION

router = APIRouter()
logger = logging.getLogger(__name__)

SCAN_PERMISSION = "scan:injection"


class ScanProfile(str, Enum):
    THIRD_PARTY_DOCUMENT = "third_party_document"
    USER_BRIEF = "user_brief"
    CODE_DOCS = "code_docs"


class ScanVerdict(str, Enum):
    ALLOW = "allow"
    MONITOR = "monitor"
    FLAG = "flag"
    BLOCK = "block"
    UNAVAILABLE = "unavailable"


class ScanReason(BaseModel):
    code: str
    strong: bool
    tier: str
    severity: float
    channel: str
    quoted: bool
    position: Tuple[int, int]


class ChunkSpan(BaseModel):
    source: str
    start: int
    end: int
    score: float


class ChunkReport(BaseModel):
    total: int
    scanned: int
    failed: int
    flagged: int
    spans: List[ChunkSpan] = Field(default_factory=list)


class ScanRequest(BaseModel):
    content: str = Field(..., description="Document to scan")
    profile: Optional[ScanProfile] = Field(
        default=None,
        description="Source profile. Fetched pages / uploads = third_party_document (default); "
                    "a user's own brief = user_brief; READMEs, API docs, AGENTS.md = code_docs.",
    )
    return_content: bool = Field(default=False, description="Echo the content back (default: never)")
    store: bool = Field(default=False, description="Retain the result server-side so GET /results/{id} works (default: never)")
    fast_mode: bool = Field(default=False, description="Regex only; skips the classifier. Not marked degraded.")
    source_id: Optional[str] = Field(default=None, max_length=200, description="Opaque caller-side id echoed back (batch correlation)")


class ScanResponse(BaseModel):
    id: UUID
    source_id: Optional[str] = None
    verdict: ScanVerdict
    score: float = Field(..., ge=0.0, le=1.0)
    degraded: bool
    degraded_reason: Optional[str] = None
    reasons: List[ScanReason]
    chunks: ChunkReport
    signals: Dict[str, Any]
    arbiter: Optional[Dict[str, Any]] = None
    model_version: Optional[str]
    policy_version: str
    profile: str
    content_sha256: str
    content_length: int
    detector: str
    latency_ms: float
    analyzed_at: datetime
    content: Optional[str] = None


class BatchScanRequest(BaseModel):
    documents: List[ScanRequest] = Field(..., min_length=1)
    profile: Optional[ScanProfile] = Field(default=None, description="Default profile for documents that omit one")


class BatchScanResponse(BaseModel):
    id: UUID
    results: List[ScanResponse]
    worst_verdict: ScanVerdict
    analyzed_at: datetime
    latency_ms: float


class FeedbackLabel(str, Enum):
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"
    TRUE_POSITIVE = "true_positive"
    TRUE_NEGATIVE = "true_negative"


class FeedbackRequest(BaseModel):
    content_sha256: str = Field(..., min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    label: FeedbackLabel
    verdict_seen: Optional[ScanVerdict] = None
    profile: Optional[ScanProfile] = None
    category: Optional[str] = Field(default=None, max_length=64, description="e.g. benign_technical, benign_about_ai, attack_indirect")
    notes: Optional[str] = Field(default=None, max_length=1000)
    model_version: Optional[str] = Field(default=None, max_length=200)
    policy_version: Optional[str] = Field(default=None, max_length=64)


class FeedbackResponse(BaseModel):
    id: UUID
    content_sha256: str
    label: FeedbackLabel
    recorded_at: datetime


# Opt-in storage only (store=true). Bounded; evicted FIFO. Stored as (owner_user_id, response).
scan_results: "BoundedDict[UUID, Tuple[str, ScanResponse]]" = BoundedDict(10_000)

_VERDICT_RANK = {"allow": 0, "monitor": 1, "unavailable": 2, "flag": 3, "block": 4}


def _run_scan(req: ScanRequest, default_profile: Optional[str]) -> Dict[str, Any]:
    detector = get_detector()
    profile = (req.profile.value if req.profile else None) or default_profile
    kwargs: Dict[str, Any] = {"fast_mode": req.fast_mode}
    if profile:
        kwargs["profile"] = profile
    try:
        return detector.detect(req.content, **kwargs)
    except Exception as exc:
        # The detector is designed not to raise; if it does, fail closed.
        logger.error("Injection scan raised %s", type(exc).__name__)
        return {
            "verdict": "unavailable", "score": 0.0, "degraded": True,
            "degraded_reason": f"detector_exception:{type(exc).__name__}", "reasons": [],
            "chunks": {"total": 0, "scanned": 0, "failed": 0, "flagged": 0, "spans": []},
            "signals": {}, "model_version": None, "policy_version": POLICY_VERSION,
            "profile": profile or "third_party_document", "detector": "none", "latency_ms": 0.0,
            "content_sha256": hashlib.sha256(req.content.encode("utf-8")).hexdigest(),
        }


def _to_response(req: ScanRequest, result: Dict[str, Any]) -> ScanResponse:
    return ScanResponse(
        id=uuid4(),
        source_id=req.source_id,
        verdict=ScanVerdict(result["verdict"]),
        score=float(result.get("score", 0.0)),
        degraded=bool(result.get("degraded", False)),
        degraded_reason=result.get("degraded_reason"),
        reasons=[ScanReason(**r) for r in result.get("reasons", [])],
        chunks=ChunkReport(**result.get("chunks", {"total": 0, "scanned": 0, "failed": 0, "flagged": 0, "spans": []})),
        signals=result.get("signals", {}),
        arbiter=result.get("arbiter"),
        model_version=result.get("model_version"),
        policy_version=result.get("policy_version", POLICY_VERSION),
        profile=result.get("profile", "third_party_document"),
        content_sha256=result.get("content_sha256") or hashlib.sha256(req.content.encode("utf-8")).hexdigest(),
        content_length=len(req.content),
        detector=result.get("detector", "unknown"),
        latency_ms=float(result.get("latency_ms", 0.0)),
        analyzed_at=datetime.utcnow(),
        content=req.content if req.return_content else None,
    )


def _check_length(content: str) -> None:
    max_len = get_settings().max_filter_content_chars
    if len(content) > max_len:
        raise HTTPException(status_code=413, detail=f"Content exceeds maximum length ({max_len} characters)")


def _status_for(verdict: ScanVerdict) -> int:
    # Clients that only look at status codes can still fail closed.
    return status.HTTP_503_SERVICE_UNAVAILABLE if verdict == ScanVerdict.UNAVAILABLE else status.HTTP_200_OK


@router.post(
    "/scan/injection",
    response_model=ScanResponse,
    summary="Scan a document for prompt injection",
    tags=["Injection Scan"],
    responses={503: {"description": "Scanner degraded; verdict is `unavailable`. Do not treat as safe."}},
)
async def scan_injection(
    request: ScanRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    auth_data=Depends(require_auth(SCAN_PERMISSION)),
):
    """
    Machine-readable prompt-injection verdict for one document.

    - `verdict`: `allow | monitor | flag | block | unavailable`
    - `degraded: true` means part of the scan did not run; `unavailable` is returned
      (with HTTP 503) instead of `allow` in that case. Never treat it as safe.
    - `reasons[].strong` marks rule hits that are sufficient on their own for `flag`.
    - `chunks` reports coverage (`scanned` vs `total`) and per-chunk scores so a
      caller can tell "1 of 12 chunks" from "pervasive".
    - Content is not echoed or retained unless `return_content` / `store` is set.
    """
    _check_length(request.content)
    current_user, api_key_id = auth_data
    settings = get_settings()

    result = await asyncio.to_thread(_run_scan, request, settings.prompt_injection_default_profile)
    resp = _to_response(request, result)

    logger.info("injection scan sha=%s verdict=%s score=%.3f degraded=%s chunks=%d/%d",
                resp.content_sha256[:16], resp.verdict.value, resp.score, resp.degraded,
                resp.chunks.scanned, resp.chunks.total)

    if request.store:
        scan_results[resp.id] = (str(current_user.user_id), resp)
    if api_key_id:
        background_tasks.add_task(track_api_key_usage, api_key_id, "/scan/injection", 0, 0.0)

    response.status_code = _status_for(resp.verdict)
    return resp


@router.post(
    "/scan/injection/batch",
    response_model=BatchScanResponse,
    summary="Scan up to N documents in one request",
    tags=["Injection Scan"],
)
async def scan_injection_batch(
    request: BatchScanRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    auth_data=Depends(require_auth(SCAN_PERMISSION)),
):
    settings = get_settings()
    if len(request.documents) > settings.scan_injection_batch_max:
        raise HTTPException(status_code=422, detail=f"At most {settings.scan_injection_batch_max} documents per batch")
    for doc in request.documents:
        _check_length(doc.content)

    current_user, api_key_id = auth_data
    default_profile = (request.profile.value if request.profile else None) or settings.prompt_injection_default_profile
    started = time.perf_counter()

    results = await asyncio.gather(*(asyncio.to_thread(_run_scan, d, default_profile) for d in request.documents))
    responses = [_to_response(d, r) for d, r in zip(request.documents, results)]

    for d, r in zip(request.documents, responses):
        if d.store:
            scan_results[r.id] = (str(current_user.user_id), r)
    if api_key_id:
        background_tasks.add_task(track_api_key_usage, api_key_id, "/scan/injection/batch", 0, 0.0)

    worst = max((r.verdict for r in responses), key=lambda v: _VERDICT_RANK[v.value])
    logger.info("injection batch n=%d worst=%s", len(responses), worst.value)
    response.status_code = _status_for(worst) if all(r.verdict == ScanVerdict.UNAVAILABLE for r in responses) else status.HTTP_200_OK
    return BatchScanResponse(
        id=uuid4(), results=responses, worst_verdict=worst,
        analyzed_at=datetime.utcnow(), latency_ms=round((time.perf_counter() - started) * 1000, 2),
    )


@router.get("/scan/injection/results/{result_id}", response_model=ScanResponse, tags=["Injection Scan"])
async def get_scan_result(result_id: UUID, current_user: TokenData = Depends(get_current_user)):
    """Fetch a stored result. Only exists if the scan was made with `store: true`."""
    entry = scan_results.get(result_id)
    if not entry or entry[0] != str(current_user.user_id):
        raise HTTPException(status_code=404, detail="Scan result not found")
    return entry[1]


@router.post(
    "/scan/injection/feedback",
    response_model=FeedbackResponse,
    summary="Label a scan outcome (false positive / negative) to grow the eval set",
    tags=["Injection Scan"],
)
async def scan_injection_feedback(
    request: FeedbackRequest,
    auth_data=Depends(require_auth(SCAN_PERMISSION)),
    db: Session = Depends(get_db),
):
    """
    Records a label keyed by `content_sha256`. The content itself is **not** sent or
    stored; the caller keeps it and can match it to the hash when building a corpus.
    """
    current_user, _ = auth_data
    row = InjectionFeedback(
        user_id=str(current_user.user_id),
        content_sha256=request.content_sha256,
        label=request.label.value,
        verdict_seen=request.verdict_seen.value if request.verdict_seen else None,
        profile=request.profile.value if request.profile else None,
        category=request.category,
        notes=request.notes,
        model_version=request.model_version,
        policy_version=request.policy_version,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return FeedbackResponse(id=row.id, content_sha256=row.content_sha256, label=request.label, recorded_at=row.created_at)


@router.get("/scan/injection/profiles", tags=["Injection Scan"])
async def list_profiles(current_user: TokenData = Depends(get_current_user)):
    """Thresholds behind each profile, for transparency and client-side tuning."""
    return {
        "policy_version": POLICY_VERSION,
        "profiles": {
            name: {
                "block_deberta": p.block_deberta, "flag_deberta": p.flag_deberta,
                "monitor_deberta": p.monitor_deberta, "strong_alone": p.strong_alone.value,
                "weak_alone": p.weak_alone.value, "supply_chain": p.supply_chain.value,
            }
            for name, p in PROFILES.items()
        },
    }
