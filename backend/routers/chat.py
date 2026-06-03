from datetime import datetime, timedelta
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from auth import current_user
from common import log_decision, rate_limit_gemini, serialize, valid_object_id
from config import CATEGORY_DEFAULTS, URGENCY_DAYS
from db.mongodb import get_db
from engines.circular_interpreter import interpret_circular
from engines.obligation_chat import chat_discover
from logging_config import get_logger
from schemas import ChatDiscoverRequest, CircularInterpretRequest

log = get_logger(__name__)

router = APIRouter(tags=["advisor"])

_DEFAULT_CATEGORY = {"max_penalty_inr": 10000, "frequency": "annual"}


@router.post(
    "/chat/discover",
    dependencies=[Depends(rate_limit_gemini)],
)
async def chat_discover_endpoint(
    payload: ChatDiscoverRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: Dict = Depends(current_user),
):
    """Conversational obligation discovery. Persists each find as 'proposed'."""
    business = await db.businesses.find_one({"_id": valid_object_id(payload.business_id, "business_id")})
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    context = {
        "name": business.get("name", ""),
        "industry": business.get("industry", ""),
        "state": business.get("state", ""),
        "employee_count": business.get("employee_count", 0),
        "annual_turnover_inr": business.get("annual_turnover_inr", 0),
        "registrations": business.get("registrations", []),
    }

    result = await chat_discover(
        db,
        payload.business_id,
        payload.messages,
        context,
        business_facts=payload.business_facts,
        summarise=payload.summarise,
    )

    now_ts = datetime.utcnow()
    import re as _re

    for disc in result.get("discovered", []):
        disc_name = disc.get("name", "")
        disc_cat = disc.get("category", "other")
        disc_urgency = disc.get("urgency", "annual")

        await db.chat_discoveries.insert_one({
            "business_id": payload.business_id,
            "obligation_name": disc_name,
            "reason": disc.get("reason", ""),
            "category": disc_cat,
            "urgency": disc_urgency,
            "discovered_at": now_ts,
        })

        safe_prefix = _re.escape(disc_name[:20])
        existing = await db.obligation_instances.find_one({
            "business_id": payload.business_id,
            "name": {"$regex": f"^{safe_prefix}", "$options": "i"},
        })
        if existing or not disc_name:
            continue

        cat_def = CATEGORY_DEFAULTS.get(disc_cat, _DEFAULT_CATEGORY)
        days_until_due = URGENCY_DAYS.get(disc_urgency, 90)
        due_date = now_ts + timedelta(days=days_until_due)
        await db.obligation_instances.insert_one({
            "business_id": payload.business_id,
            "regulation_id": f"ai_advisor_{disc_name[:30].lower().replace(' ', '_')}",
            "name": disc_name,
            "category": disc_cat,
            "frequency": cat_def["frequency"],
            "deadline_rule": disc.get("reason", "Discovered via AI Advisor"),
            "penalty_type": "fixed",
            "max_penalty_inr": cat_def["max_penalty_inr"],
            "complexity": 2,
            "depends_on": [],
            "imprisonment_risk": False,
            "status": "proposed",
            "source": "ai_advisor",
            "decay_score": None,
            "due_date": due_date,
            "created_at": now_ts,
        })

    await log_decision(db, payload.business_id, "chat_discover", {
        "message_count": len(payload.messages),
        "obligations_discovered": len(result.get("discovered", [])),
        "summarise": payload.summarise,
    })

    return result


@router.get("/chat-discoveries/{business_id}")
async def get_chat_discoveries(
    business_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: Dict = Depends(current_user),
):
    discoveries = []
    async for doc in db.chat_discoveries.find(
        {"business_id": business_id},
        sort=[("discovered_at", -1)],
    ):
        discoveries.append(serialize(doc))
    return {"business_id": business_id, "discoveries": discoveries}


@router.post(
    "/circular/interpret",
    dependencies=[Depends(rate_limit_gemini)],
)
async def circular_interpret_endpoint(
    payload: CircularInterpretRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: Dict = Depends(current_user),
):
    """Gemini reads raw circular text → plain-language analysis."""
    context: Dict = {}
    try:
        business = await db.businesses.find_one({"_id": valid_object_id(payload.business_id, "business_id")})
        if business:
            context = {
                "name": business.get("name", ""),
                "industry": business.get("industry", ""),
                "state": business.get("state", ""),
                "employee_count": business.get("employee_count", 0),
                "annual_turnover_inr": business.get("annual_turnover_inr", 0),
                "registrations": business.get("registrations", []),
            }
    except HTTPException:
        log.info("circular_interpret called without valid business_id; using empty context")

    result = await interpret_circular(context, payload.circular_text, payload.circular_source)

    await log_decision(db, payload.business_id, "circular_interpret", {
        "source": payload.circular_source,
        "applies": result.get("applies_to_this_business", False),
        "urgency": result.get("urgency", ""),
    })
    return result
