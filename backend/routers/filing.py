from datetime import datetime
from typing import Dict, Tuple

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from auth import require_business_owner
from common import log_decision, pagination, serialize, valid_object_id
from db.mongodb import get_db
from logging_config import get_logger

log = get_logger(__name__)

router = APIRouter(tags=["filing"])


@router.get("/filing-history/{business_id}")
async def filing_history(
    business_id: str,
    page: Tuple[int, int] = Depends(pagination),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: Dict = Depends(require_business_owner),
):
    limit, skip = page
    business = await db.businesses.find_one({"_id": valid_object_id(business_id, "business_id")})
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    history = []
    total = 0
    on_time_count = 0
    async for fh in db.filing_history.find(
        {"business_id": business_id},
        sort=[("filed_at", -1)],
    ):
        total += 1
        if fh.get("on_time"):
            on_time_count += 1
        history.append(serialize(fh))

    on_time_rate = round(on_time_count / total, 4) if total > 0 else None
    paginated = history[skip:skip + limit]

    await log_decision(db, business_id, "get_filing_history", {
        "total_filings": total, "on_time_rate": on_time_rate,
    })

    return {
        "business_id": business_id,
        "total_filings": total,
        "on_time_count": on_time_count,
        "on_time_rate": on_time_rate,
        "history": paginated,
        "limit": limit,
        "skip": skip,
    }


@router.get("/filing-summary/{business_id}")
async def filing_summary(
    business_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: Dict = Depends(require_business_owner),
):
    """
    Aggregation: on-time/late breakdown per category + per quarter.
    Powers the executive dashboard card showing compliance health by area.
    """
    pipeline = [
        {"$match": {"business_id": business_id}},
        {"$lookup": {
            "from": "obligation_instances",
            "localField": "instance_id",
            "foreignField": "_id",
            "as": "instance",
        }},
        {"$addFields": {
            "category": {"$ifNull": [
                {"$arrayElemAt": ["$instance.category", 0]}, "other"
            ]},
        }},
        {"$group": {
            "_id": "$category",
            "total": {"$sum": 1},
            "on_time": {"$sum": {"$cond": [{"$eq": ["$on_time", True]}, 1, 0]}},
            "late": {"$sum": {"$cond": [{"$eq": ["$on_time", False]}, 1, 0]}},
        }},
        {"$project": {
            "_id": 0,
            "category": "$_id",
            "total": 1,
            "on_time": 1,
            "late": 1,
            "on_time_rate": {
                "$cond": [
                    {"$gt": ["$total", 0]},
                    {"$divide": ["$on_time", "$total"]},
                    None,
                ]
            },
        }},
        {"$sort": {"total": -1}},
    ]

    by_category = []
    overall_total = 0
    overall_on_time = 0
    async for doc in db.filing_history.aggregate(pipeline):
        by_category.append(doc)
        overall_total += doc.get("total", 0)
        overall_on_time += doc.get("on_time", 0)

    overall_rate = round(overall_on_time / overall_total, 3) if overall_total > 0 else None

    return {
        "business_id": business_id,
        "by_category": by_category,
        "total_filings": overall_total,
        "on_time_count": overall_on_time,
        "on_time_rate": overall_rate,
    }


@router.get("/exposure/{business_id}")
async def total_exposure(
    business_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: Dict = Depends(require_business_owner),
):
    """
    Aggregation: total ₹ penalty exposure across all pending obligations
    (sum of max_penalty_inr) + breakdown by urgency band.
    Single most demo-able number: "you owe ₹X if you do nothing".
    """
    pipeline = [
        {"$match": {
            "business_id": business_id,
            "status": {"$in": [None, "pending", "draft_generated"]},
        }},
        {"$group": {
            "_id": "$urgency",
            "count": {"$sum": 1},
            "max_penalty_total": {"$sum": {"$ifNull": ["$max_penalty_inr", 0]}},
            "avg_decay": {"$avg": "$decay_score"},
        }},
    ]
    by_urgency: Dict[str, Dict] = {}
    total_exposure = 0
    total_pending = 0
    async for doc in db.obligation_instances.aggregate(pipeline):
        band = doc["_id"] or "unrated"
        by_urgency[band] = {
            "count": doc["count"],
            "max_penalty_total": doc["max_penalty_total"],
            "avg_decay": round(doc.get("avg_decay") or 0.0, 1),
        }
        total_exposure += doc["max_penalty_total"]
        total_pending += doc["count"]

    return {
        "business_id": business_id,
        "total_pending": total_pending,
        "total_exposure_inr": total_exposure,
        "by_urgency": by_urgency,
    }


@router.get("/agent-decisions/{business_id}")
async def agent_decisions(
    business_id: str,
    page: Tuple[int, int] = Depends(pagination),
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: Dict = Depends(require_business_owner),
):
    limit, skip = page
    decisions = []
    cursor = db.agent_decisions.find(
        {"business_id": business_id},
        sort=[("timestamp", -1)],
    ).skip(skip).limit(limit)
    async for dec in cursor:
        decisions.append(serialize(dec))

    return {
        "business_id": business_id,
        "count": len(decisions),
        "decisions": decisions,
        "limit": limit,
        "skip": skip,
    }
