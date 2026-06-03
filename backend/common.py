"""Shared helpers: serialisation, audit log, pagination, in-process rate limit."""

import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Deque, Dict, Tuple

from bson import ObjectId
from fastapi import HTTPException, Query, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from config import DEFAULT_PAGE_LIMIT, GEMINI_RPM, MAX_PAGE_LIMIT
from logging_config import get_logger

log = get_logger(__name__)


def serialize(doc: Dict | None) -> Dict:
    """Recursively convert ObjectId / datetime fields to JSON-safe values."""
    if doc is None:
        return {}
    result: Dict[str, Any] = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            result[k] = str(v)
        elif isinstance(v, dict):
            result[k] = serialize(v)
        elif isinstance(v, list):
            result[k] = [
                serialize(i) if isinstance(i, dict)
                else (str(i) if isinstance(i, ObjectId) else i)
                for i in v
            ]
        elif isinstance(v, datetime):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result


async def log_decision(
    db: AsyncIOMotorDatabase,
    business_id: str,
    action: str,
    payload: Dict,
) -> None:
    await db.agent_decisions.insert_one({
        "business_id": business_id,
        "action": action,
        "payload": payload,
        "timestamp": datetime.utcnow(),
    })


def valid_object_id(value: str, field: str = "id") -> ObjectId:
    try:
        return ObjectId(value)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {field}") from exc


def pagination(
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    skip: int = Query(0, ge=0),
) -> Tuple[int, int]:
    return limit, skip


# ── Simple in-process per-IP rate limiter ─────────────────────────────────────
# Suitable for single-instance Railway deploys. For multi-instance, swap for
# Redis. Each bucket is a sliding 60-second window of timestamps.
_buckets: Dict[str, Deque[float]] = defaultdict(deque)


def rate_limit_gemini(request: Request) -> None:
    """Reject if this client has exceeded ``GEMINI_RPM`` in the last 60 seconds."""
    ip = (request.client.host if request.client else "unknown") or "unknown"
    now = time.monotonic()
    bucket = _buckets[ip]
    while bucket and now - bucket[0] > 60.0:
        bucket.popleft()
    if len(bucket) >= GEMINI_RPM:
        retry_after = int(60 - (now - bucket[0])) + 1
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )
    bucket.append(now)
