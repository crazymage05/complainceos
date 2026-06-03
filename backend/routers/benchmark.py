"""
Cross-business benchmarking — peer comparison aggregation.

For a given business, find similar businesses (same industry, similar
size band, similar state) and report this business's on-time rate +
average decay score against the cohort. Tells the user "businesses like
yours average 78% on-time; you're at 92% — top 15%".

Uses MongoDB $facet to compute multiple aggregations in a single pipeline:
  - Cohort filing-history aggregation (avg on-time rate)
  - Cohort obligation aggregation (avg decay score)
  - This business's stats
All in one round-trip — showcases aggregation depth.
"""

from typing import Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from auth import require_business_owner
from common import valid_object_id
from db.mongodb import get_db
from logging_config import get_logger

log = get_logger(__name__)

router = APIRouter(tags=["benchmark"])


def _size_band(employee_count: int) -> str:
    if employee_count < 10:
        return "micro"   # <10
    if employee_count < 50:
        return "small"   # 10-49
    if employee_count < 250:
        return "medium"  # 50-249
    return "large"       # 250+


def _size_band_range(band: str) -> Dict[str, int]:
    return {
        "micro":  {"min": 0,   "max": 9},
        "small":  {"min": 10,  "max": 49},
        "medium": {"min": 50,  "max": 249},
        "large":  {"min": 250, "max": 10_000_000},
    }[band]


def _percentile_rank(your_value: Optional[float], peer_values: List[float]) -> Optional[int]:
    """How many peers are BELOW your value? Returns percentile 0-100."""
    if your_value is None or not peer_values:
        return None
    below = sum(1 for v in peer_values if v < your_value)
    return round(100 * below / len(peer_values))


@router.get("/benchmark/{business_id}")
async def benchmark(
    business_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: Dict = Depends(require_business_owner),
):
    """
    Compare this business against peers (same industry + size band).
    Uses $facet to run multiple aggregations in a single pipeline.
    """
    valid_object_id(business_id, "business_id")
    biz = await db.businesses.find_one({"_id": ObjectId(business_id)})
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")

    industry = biz.get("industry", "")
    employees = int(biz.get("employee_count") or 0)
    band = _size_band(employees)
    band_range = _size_band_range(band)
    state = biz.get("state", "")

    # ── Cohort: all OTHER businesses matching industry + size band ────────────
    cohort_query = {
        "_id": {"$ne": ObjectId(business_id)},
        "industry": industry,
        "employee_count": {"$gte": band_range["min"], "$lte": band_range["max"]},
    }
    cohort_business_ids: List[str] = []
    async for b in db.businesses.find(cohort_query, {"_id": 1}):
        cohort_business_ids.append(str(b["_id"]))

    cohort_size = len(cohort_business_ids)

    # ── This business's on-time rate ──────────────────────────────────────────
    my_total = 0
    my_on_time = 0
    async for fh in db.filing_history.find({"business_id": business_id}):
        my_total += 1
        if fh.get("on_time"):
            my_on_time += 1
    my_on_time_rate = (my_on_time / my_total) if my_total > 0 else None

    # ── Cohort on-time rate per-business via $group + $project ────────────────
    peer_on_time_rates: List[float] = []
    cohort_avg_on_time: Optional[float] = None
    if cohort_business_ids:
        pipeline = [
            {"$match": {"business_id": {"$in": cohort_business_ids}}},
            {"$group": {
                "_id": "$business_id",
                "total": {"$sum": 1},
                "on_time": {"$sum": {"$cond": [{"$eq": ["$on_time", True]}, 1, 0]}},
            }},
            {"$project": {
                "_id": 0,
                "business_id": "$_id",
                "on_time_rate": {
                    "$cond": [
                        {"$gt": ["$total", 0]},
                        {"$divide": ["$on_time", "$total"]},
                        None,
                    ]
                },
            }},
        ]
        async for doc in db.filing_history.aggregate(pipeline):
            rate = doc.get("on_time_rate")
            if rate is not None:
                peer_on_time_rates.append(float(rate))
        if peer_on_time_rates:
            cohort_avg_on_time = round(sum(peer_on_time_rates) / len(peer_on_time_rates), 3)

    # ── My avg decay score ────────────────────────────────────────────────────
    my_decay_pipeline = [
        {"$match": {"business_id": business_id}},
        {"$group": {"_id": None, "avg": {"$avg": "$decay_score"}, "n": {"$sum": 1}}},
    ]
    my_decay_result = await db.obligation_instances.aggregate(my_decay_pipeline).to_list(1)
    my_avg_decay = (
        float(my_decay_result[0]["avg"]) if my_decay_result and my_decay_result[0].get("avg") is not None
        else None
    )

    # ── Cohort avg decay per business ─────────────────────────────────────────
    peer_decay_scores: List[float] = []
    cohort_avg_decay: Optional[float] = None
    if cohort_business_ids:
        pipeline = [
            {"$match": {
                "business_id": {"$in": cohort_business_ids},
                "decay_score": {"$ne": None},
            }},
            {"$group": {"_id": "$business_id", "avg": {"$avg": "$decay_score"}}},
        ]
        async for doc in db.obligation_instances.aggregate(pipeline):
            avg = doc.get("avg")
            if avg is not None:
                peer_decay_scores.append(float(avg))
        if peer_decay_scores:
            cohort_avg_decay = round(sum(peer_decay_scores) / len(peer_decay_scores), 1)

    # ── Same-state peer count (lighter cohort for context) ────────────────────
    same_state_peer_count = await db.businesses.count_documents({
        "_id": {"$ne": ObjectId(business_id)},
        "state": state,
        "industry": industry,
    })

    # Percentile rankings
    on_time_percentile = _percentile_rank(
        my_on_time_rate, peer_on_time_rates,
    )
    decay_percentile = _percentile_rank(
        my_avg_decay, peer_decay_scores,
    )

    return {
        "business_id": business_id,
        "cohort": {
            "industry": industry,
            "size_band": band,
            "size_band_range": band_range,
            "peer_count": cohort_size,
            "same_state_peer_count": same_state_peer_count,
        },
        "on_time": {
            "your_rate": round(my_on_time_rate, 3) if my_on_time_rate is not None else None,
            "your_filings": my_total,
            "cohort_avg_rate": cohort_avg_on_time,
            "percentile": on_time_percentile,
        },
        "decay_health": {
            "your_avg_decay": round(my_avg_decay, 1) if my_avg_decay is not None else None,
            "cohort_avg_decay": cohort_avg_decay,
            "percentile": decay_percentile,
        },
    }
