"""
Compliance Health Score — a single 0-100 number.

Composite of four dimensions, each contributing weight:
  * 35% — pending obligation freshness (avg decay across active obligations)
  * 30% — historical on-time filing rate
  * 20% — recent ripple alert exposure (inverse — more alerts = lower)
  * 15% — overdue/red count penalty

The score is computed via MongoDB aggregation pipelines + a tiny Python
weighted sum at the end. Demoable as "your compliance health is 87".
"""

from datetime import datetime, timedelta
from typing import Dict

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from auth import require_business_owner
from common import valid_object_id
from db.mongodb import get_db
from logging_config import get_logger

log = get_logger(__name__)

router = APIRouter(tags=["health-score"])


WEIGHTS = {
    "freshness": 0.35,
    "on_time": 0.30,
    "ripple_exposure": 0.20,
    "overdue_penalty": 0.15,
}


def _band(score: float) -> str:
    if score >= 80:
        return "excellent"
    if score >= 65:
        return "good"
    if score >= 50:
        return "fair"
    if score >= 35:
        return "poor"
    return "critical"


@router.get("/health-score/{business_id}")
async def compliance_health_score(
    business_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: Dict = Depends(require_business_owner),
):
    """
    Single 0-100 compliance health number with per-dimension breakdown.

    Aggregation pipelines used:
      - obligation_instances: avg(decay_score), red/amber counts
      - filing_history: on_time/late counts
      - regulatory_changes: recent ripple alerts in last 30 days
    """
    valid_object_id(business_id, "business_id")
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)

    # ── Dimension 1: freshness (avg decay across pending) ─────────────────────
    pipeline_freshness = [
        {"$match": {
            "business_id": business_id,
            "status": {"$in": [None, "pending", "draft_generated"]},
        }},
        {"$group": {
            "_id": None,
            "avg_decay": {"$avg": "$decay_score"},
            "total": {"$sum": 1},
            "red": {"$sum": {"$cond": [{"$lt": ["$decay_score", 20]}, 1, 0]}},
            "amber": {"$sum": {"$cond": [
                {"$and": [{"$gte": ["$decay_score", 20]}, {"$lt": ["$decay_score", 40]}]},
                1, 0,
            ]}},
            "green": {"$sum": {"$cond": [{"$gte": ["$decay_score", 40]}, 1, 0]}},
        }},
    ]
    freshness_result = await db.obligation_instances.aggregate(pipeline_freshness).to_list(1)
    f = freshness_result[0] if freshness_result else {}
    avg_decay = float(f.get("avg_decay") or 50.0)
    total_pending = int(f.get("total") or 0)
    red = int(f.get("red") or 0)
    amber = int(f.get("amber") or 0)
    green = int(f.get("green") or 0)
    # avg_decay is already 0-100; use directly
    freshness_score = max(0.0, min(100.0, avg_decay))

    # ── Dimension 2: on-time rate ─────────────────────────────────────────────
    pipeline_filing = [
        {"$match": {"business_id": business_id}},
        {"$group": {
            "_id": None,
            "total": {"$sum": 1},
            "on_time": {"$sum": {"$cond": [{"$eq": ["$on_time", True]}, 1, 0]}},
        }},
    ]
    filing_result = await db.filing_history.aggregate(pipeline_filing).to_list(1)
    fr = filing_result[0] if filing_result else {}
    total_filings = int(fr.get("total") or 0)
    on_time_count = int(fr.get("on_time") or 0)
    if total_filings == 0:
        # No history → assume neutral 75 (you haven't filed late yet)
        on_time_score = 75.0
        on_time_rate = None
    else:
        on_time_rate = on_time_count / total_filings
        on_time_score = on_time_rate * 100.0

    # ── Dimension 3: ripple exposure (inverse) ────────────────────────────────
    pipeline_ripple = [
        {"$match": {
            "business_id": business_id,
            "detected_at": {"$gte": thirty_days_ago},
        }},
        {"$group": {
            "_id": None,
            "count": {"$sum": 1},
            "high_count": {"$sum": {"$cond": [{"$eq": ["$severity", "high"]}, 1, 0]}},
        }},
    ]
    ripple_result = await db.regulatory_changes.aggregate(pipeline_ripple).to_list(1)
    rr = ripple_result[0] if ripple_result else {}
    recent_ripples = int(rr.get("count") or 0)
    high_ripples = int(rr.get("high_count") or 0)
    # Each ripple costs 4 points; each high-severity an additional 6 points
    ripple_score = max(0.0, 100.0 - 4.0 * recent_ripples - 6.0 * high_ripples)

    # ── Dimension 4: overdue/red penalty ──────────────────────────────────────
    if total_pending == 0:
        overdue_score = 80.0  # neutral when no pending
    else:
        red_pct = red / total_pending
        # 100 at 0% red, 0 at 50%+ red, linear in between
        overdue_score = max(0.0, 100.0 - 200.0 * red_pct)

    # ── Composite ─────────────────────────────────────────────────────────────
    composite = (
        WEIGHTS["freshness"] * freshness_score
        + WEIGHTS["on_time"] * on_time_score
        + WEIGHTS["ripple_exposure"] * ripple_score
        + WEIGHTS["overdue_penalty"] * overdue_score
    )
    composite = round(max(0.0, min(100.0, composite)), 1)

    return {
        "business_id": business_id,
        "health_score": composite,
        "band": _band(composite),
        "dimensions": {
            "freshness": {
                "score": round(freshness_score, 1),
                "weight": WEIGHTS["freshness"],
                "detail": f"avg decay {round(avg_decay, 1)} across {total_pending} pending obligations",
                "red": red, "amber": amber, "green": green,
            },
            "on_time_rate": {
                "score": round(on_time_score, 1),
                "weight": WEIGHTS["on_time"],
                "detail": (
                    f"{on_time_count}/{total_filings} filings on time"
                    if total_filings else "no filings yet (neutral)"
                ),
                "rate": round(on_time_rate, 3) if on_time_rate is not None else None,
            },
            "ripple_exposure": {
                "score": round(ripple_score, 1),
                "weight": WEIGHTS["ripple_exposure"],
                "detail": f"{recent_ripples} ripple alert{('' if recent_ripples == 1 else 's')} in last 30 days ({high_ripples} high)",
                "recent": recent_ripples,
                "high": high_ripples,
            },
            "overdue_penalty": {
                "score": round(overdue_score, 1),
                "weight": WEIGHTS["overdue_penalty"],
                "detail": f"{red} red of {total_pending} pending",
            },
        },
        "computed_at": now.isoformat() + "Z",
    }
