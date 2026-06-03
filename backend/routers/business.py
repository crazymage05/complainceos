from datetime import datetime, timedelta
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from auth import current_user, require_business_owner
from common import log_decision, serialize, valid_object_id
from config import FREQ_DAYS, STAGGER_BASE_PCT, STAGGER_CYCLE, STAGGER_STEP_PCT
from db.mongodb import get_db
from engines.dna_builder import build_compliance_dna
from logging_config import get_logger
from schemas import BusinessCreate, BusinessUpdate, ConfirmObligationsRequest

log = get_logger(__name__)

router = APIRouter(prefix="/business", tags=["business"])


@router.post("", status_code=201)
async def create_business(
    payload: BusinessCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: Dict = Depends(current_user),
):
    """Persist the business, run DNA Builder, and seed staggered obligations."""
    business_doc = payload.model_dump()
    business_doc["created_at"] = datetime.utcnow()
    result = await db.businesses.insert_one(business_doc)
    business_id = str(result.inserted_id)

    entity_attrs = {
        "state": payload.state,
        "industry": payload.industry,
        "employee_count": payload.employee_count,
        "annual_turnover_inr": payload.annual_turnover_inr,
        "registrations": payload.registrations,
        "incorporation_date": payload.incorporation_date,
        "business_type": payload.business_type,
    }
    dna = await build_compliance_dna(db, business_id, entity_attrs)

    inserted_instance_ids = []
    now = datetime.utcnow()
    for i, obl in enumerate(dna["applicable_obligations"]):
        freq = obl.get("frequency", "monthly")
        days_allowed = FREQ_DAYS.get(freq, 30)
        stagger_pct = STAGGER_BASE_PCT + (i % STAGGER_CYCLE) * STAGGER_STEP_PCT
        days_until_due = max(1, int(days_allowed * stagger_pct))
        due_date = now + timedelta(days=days_until_due)

        instance_doc = {
            "business_id": business_id,
            "regulation_id": obl["obligation_id"],
            "name": obl["name"],
            "category": obl["category"],
            "frequency": freq,
            "deadline_rule": obl["deadline_rule"],
            "penalty_type": obl["penalty_type"],
            "max_penalty_inr": obl["max_penalty_inr"],
            "complexity": obl["complexity"],
            "depends_on": obl["depends_on"],
            "imprisonment_risk": obl["imprisonment_risk"],
            "status": "pending",
            "decay_score": None,
            "due_date": due_date,
            "created_at": now,
        }
        ins_result = await db.obligation_instances.insert_one(instance_doc)
        inserted_instance_ids.append(str(ins_result.inserted_id))

    await log_decision(db, business_id, "create_business", {
        "name": payload.name,
        "total_obligations": dna["total_obligations"],
        "high_severity_count": dna["high_severity_count"],
    })

    return {
        "business_id": business_id,
        "name": payload.name,
        "dna_summary": {
            "total_obligations": dna["total_obligations"],
            "high_severity_count": dna["high_severity_count"],
            "obligation_ids": inserted_instance_ids,
        },
    }


@router.get("/{business_id}")
async def get_business(
    business_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: Dict = Depends(require_business_owner),
):
    """Return the persisted business profile (used to pre-fill the edit form)."""
    oid = valid_object_id(business_id, "business_id")
    biz = await db.businesses.find_one({"_id": oid})
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")
    return serialize(biz)


@router.patch("/{business_id}")
async def update_business(
    business_id: str,
    payload: BusinessUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: Dict = Depends(require_business_owner),
):
    """
    Partial update of the business profile. Only fields explicitly provided
    are modified. Does NOT regenerate obligations — that would silently
    delete the user's customisations. If turnover/employees changed, the
    next dashboard load will recompute decay scores against the new size.
    """
    oid = valid_object_id(business_id, "business_id")
    biz = await db.businesses.find_one({"_id": oid})
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")

    updates: Dict = {
        k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None
    }
    if not updates:
        return serialize(biz)

    updates["updated_at"] = datetime.utcnow()
    await db.businesses.update_one({"_id": oid}, {"$set": updates})

    await log_decision(db, business_id, "update_business", {
        "fields_changed": list(updates.keys()),
    })

    refreshed = await db.businesses.find_one({"_id": oid})
    return serialize(refreshed or {})


@router.post("/{business_id}/confirm-obligations")
async def confirm_obligations(
    business_id: str,
    payload: ConfirmObligationsRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: Dict = Depends(require_business_owner),
):
    """Remove unchecked obligations and persist user-edited due dates."""
    valid_object_id(business_id, "business_id")
    keep_set = set(payload.keep_ids)

    all_ids = []
    async for inst in db.obligation_instances.find({"business_id": business_id}, {"_id": 1}):
        all_ids.append(str(inst["_id"]))

    remove_ids = [oid for oid in all_ids if oid not in keep_set]
    if remove_ids:
        await db.obligation_instances.delete_many({
            "_id": {"$in": [valid_object_id(oid, "instance_id") for oid in remove_ids]}
        })

    for instance_id, due_date_str in payload.due_dates.items():
        if instance_id not in keep_set:
            continue
        try:
            due_dt = datetime.fromisoformat(due_date_str)
        except ValueError as exc:
            log.warning("skipping invalid due_date %r: %s", due_date_str, exc)
            continue
        try:
            oid = valid_object_id(instance_id, "instance_id")
        except HTTPException:
            log.warning("skipping invalid instance_id %r", instance_id)
            continue
        await db.obligation_instances.update_one(
            {"_id": oid}, {"$set": {"due_date": due_dt}},
        )

    await log_decision(db, business_id, "confirm_obligations", {
        "kept": len(keep_set),
        "removed": len(remove_ids),
    })

    return {
        "business_id": business_id,
        "kept": len(keep_set),
        "removed": len(remove_ids),
    }
