import math
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from auth import current_user, require_business_owner
from common import log_decision, pagination, serialize, valid_object_id
from config import (DECAY_TREND_WINDOW_DAYS, FREQ_DAYS,
                    SNAPSHOT_INTERVAL_SECONDS)
from db.mongodb import get_db
from engines.decay_score import compute_decay_score, score_to_urgency
from logging_config import get_logger


def _penalty_severity(max_penalty_inr: float) -> float:
    """Log-scaled severity in [1.0, 3.0].

    Old formula (max_penalty / 100000, floored at 1.0) returned 10× for a
    ₹10L max penalty — and the decay formula divides by it. That made every
    high-penalty obligation look red even when 60+ days away. Log-scaling
    keeps the signal directional but bounded.
    """
    if max_penalty_inr <= 10_000:
        return 1.0
    severity = 1.0 + math.log10(max_penalty_inr / 10_000)
    return max(1.0, min(severity, 3.0))

log = get_logger(__name__)

router = APIRouter(tags=["obligations"])


@router.get("/obligations/{business_id}")
async def get_obligations(
    business_id: str,
    page: Tuple[int, int] = Depends(pagination),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: Dict = Depends(require_business_owner),
):
    """Live decay-scored obligations, most urgent first, paginated."""
    limit, skip = page
    business = await db.businesses.find_one({"_id": valid_object_id(business_id, "business_id")})
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    total_filed = 0
    on_time_filed = 0
    async for fh in db.filing_history.find({"business_id": business_id}):
        total_filed += 1
        if fh.get("on_time"):
            on_time_filed += 1
    historical_on_time_rate = (on_time_filed / total_filed) if total_filed > 0 else 1.0

    obligations: List[Dict] = []
    now = datetime.utcnow()
    cursor = db.obligation_instances.find({"business_id": business_id})
    async for inst in cursor:
        due_dt = _parse_datetime(inst.get("due_date"))
        days_remaining = (
            (due_dt - now).total_seconds() / 86400.0 if due_dt else 30.0
        )

        frequency = inst.get("frequency", "monthly")
        total_days = FREQ_DAYS.get(frequency, 30)
        complexity = inst.get("complexity", 1)
        max_penalty = inst.get("max_penalty_inr", 10000)
        penalty_severity = _penalty_severity(max_penalty)

        decay = compute_decay_score(
            days_remaining=days_remaining,
            total_days_allowed=total_days,
            complexity_weight=float(complexity),
            penalty_severity_multiplier=penalty_severity,
            historical_on_time_rate=historical_on_time_rate,
        )
        urgency = score_to_urgency(decay)

        await db.obligation_instances.update_one(
            {"_id": inst["_id"]},
            {"$set": {"decay_score": decay, "urgency": urgency}},
        )

        await _maybe_snapshot(db, inst, business_id, decay, urgency, now)

        serialised = serialize(inst)
        serialised["decay_score"] = decay
        serialised["urgency"] = urgency
        obligations.append(serialised)

    obligations.sort(key=lambda x: x.get("decay_score", 0))
    paginated = obligations[skip:skip + limit]

    await log_decision(db, business_id, "get_obligations", {
        "count": len(obligations), "returned": len(paginated),
    })

    return {
        "business_id": business_id,
        "obligations": paginated,
        "total": len(obligations),
        "limit": limit,
        "skip": skip,
    }


@router.post("/obligations/{instance_id}/confirm")
async def confirm_obligation(
    instance_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: Dict = Depends(current_user),
):
    """Move an AI-discovered obligation from 'proposed' → 'pending'."""
    oid = valid_object_id(instance_id, "instance_id")
    inst = await db.obligation_instances.find_one({"_id": oid})
    if not inst:
        raise HTTPException(status_code=404, detail="Obligation not found")
    if inst.get("status") != "proposed":
        raise HTTPException(status_code=400, detail="Obligation is not in proposed state")
    await db.obligation_instances.update_one(
        {"_id": oid},
        {"$set": {"status": "pending", "confirmed_at": datetime.utcnow()}},
    )
    await log_decision(db, inst["business_id"], "confirm_obligation", {"instance_id": instance_id})
    return {"instance_id": instance_id, "status": "pending"}


@router.delete("/obligations/{instance_id}/dismiss")
async def dismiss_obligation(
    instance_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: Dict = Depends(current_user),
):
    """Delete a proposed obligation the user rejected."""
    oid = valid_object_id(instance_id, "instance_id")
    inst = await db.obligation_instances.find_one({"_id": oid})
    if not inst or inst.get("status") != "proposed":
        raise HTTPException(status_code=404, detail="Proposed obligation not found")
    await db.obligation_instances.delete_one({"_id": oid})
    return {"instance_id": instance_id, "status": "dismissed"}


@router.get("/decay-trend/{business_id}")
async def decay_trend(
    business_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: Dict = Depends(require_business_owner),
):
    """30-day decay-score history per obligation, for sparkline rendering."""
    window_start = datetime.utcnow() - timedelta(days=DECAY_TREND_WINDOW_DAYS)
    trends: Dict[str, List] = {}
    cursor = db.decay_score_snapshots.find(
        {"business_id": business_id, "timestamp": {"$gte": window_start}},
        sort=[("timestamp", 1)],
    )
    async for snap in cursor:
        iid = snap.get("instance_id", "")
        ts = snap.get("timestamp")
        trends.setdefault(iid, []).append({
            "t": ts.isoformat() if isinstance(ts, datetime) else str(ts),
            "score": snap.get("decay_score", 0),
        })
    return {"business_id": business_id, "trends": trends}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_datetime(raw) -> datetime | None:
    if isinstance(raw, datetime):
        return raw
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw))
    except ValueError as exc:
        log.warning("invalid date %r: %s", raw, exc)
        return None


async def _maybe_snapshot(
    db: AsyncIOMotorDatabase,
    inst: Dict,
    business_id: str,
    decay: float,
    urgency: str,
    now: datetime,
) -> None:
    """Throttled write to the Time Series snapshot collection."""
    try:
        last_snap = await db.decay_score_snapshots.find_one(
            {"instance_id": str(inst["_id"])},
            sort=[("timestamp", -1)],
        )
        if last_snap and (now - last_snap["timestamp"]).total_seconds() <= SNAPSHOT_INTERVAL_SECONDS:
            return
        await db.decay_score_snapshots.insert_one({
            "instance_id": str(inst["_id"]),
            "business_id": business_id,
            "decay_score": decay,
            "urgency": urgency,
            "timestamp": now,
        })
    except Exception as exc:
        log.warning("decay snapshot write failed: %s", exc)
