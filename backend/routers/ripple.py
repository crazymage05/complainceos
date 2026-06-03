from datetime import datetime
from typing import Dict

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from auth import current_user
from common import log_decision, rate_limit_gemini, serialize
from db.mongodb import get_db
from engines.ripple_detector import detect_ripple, detect_ripple_hybrid
from logging_config import get_logger
from schemas import RippleCheckRequest

log = get_logger(__name__)

router = APIRouter(prefix="/regulations", tags=["ripple"])


@router.post(
    "/check-ripple",
    dependencies=[Depends(rate_limit_gemini)],
)
async def check_ripple(
    payload: RippleCheckRequest,
    hybrid: bool = Query(True, description="Use hybrid Vector+Atlas Search ranking"),
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: Dict = Depends(current_user),
):
    business_id = payload.business_id
    change = payload.regulation_change

    affected_categories = change.get("affected_categories", [])
    affected_registrations = change.get("affected_registrations", [])

    change_doc = {
        **change,
        "business_id": business_id,
        "detected_at": datetime.utcnow(),
    }
    await db.regulatory_changes.insert_one(change_doc)

    detector = detect_ripple_hybrid if hybrid else detect_ripple
    ripple = await detector(
        db=db,
        business_id=business_id,
        affected_categories=affected_categories,
        affected_registrations=affected_registrations,
        change_description=change.get("title", ""),
    )

    await log_decision(db, business_id, "ripple_check", ripple)

    return {
        "business_id": business_id,
        "regulation_change": change,
        "ripple_report": ripple,
    }


admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get("/ripple-analytics")
async def ripple_analytics(
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: Dict = Depends(current_user),
):
    pipeline = [
        {"$group": {
            "_id": "$source",
            "title": {"$first": "$title"},
            "category": {"$first": "$category"},
            "businesses_affected": {"$sum": 1},
            "total_direct": {"$sum": {"$size": {"$ifNull": ["$directly_impacted", []]}}},
            "total_indirect": {"$sum": {"$size": {"$ifNull": ["$indirectly_impacted", []]}}},
            "severity": {"$first": "$severity"},
            "detected_at": {"$max": "$detected_at"},
        }},
        {"$sort": {"businesses_affected": -1}},
        {"$limit": 20},
    ]
    results = []
    async for doc in db.regulatory_changes.aggregate(pipeline):
        doc["_id"] = str(doc["_id"])
        if isinstance(doc.get("detected_at"), datetime):
            doc["detected_at"] = doc["detected_at"].isoformat()
        results.append(doc)
    return {"analytics": results, "total_regulations": len(results)}
