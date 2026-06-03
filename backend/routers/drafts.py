from datetime import datetime
from typing import Dict

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from auth import current_user
from common import log_decision, valid_object_id
from db.mongodb import get_db
from engines.auto_draft import generate_draft
from engines.pdf_generator import generate_draft_pdf, safe_filename
from engines.penalty_predictor import predict_penalty
from logging_config import get_logger
from schemas import ApproveDraftRequest

log = get_logger(__name__)

router = APIRouter(tags=["drafts"])


@router.get("/penalty-preview/{instance_id}")
async def penalty_preview(
    instance_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: Dict = Depends(current_user),
):
    oid = valid_object_id(instance_id, "instance_id")
    inst = await db.obligation_instances.find_one({"_id": oid})
    if not inst:
        raise HTTPException(status_code=404, detail="Obligation instance not found")

    business_id = inst["business_id"]
    business = await db.businesses.find_one({"_id": valid_object_id(business_id, "business_id")})
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    penalty_rule = await db.penalty_rules.find_one({"regulation_id": inst["regulation_id"]})
    base_penalty = (penalty_rule or {}).get("base_penalty_inr", 5000.0)
    per_day_late = (penalty_rule or {}).get("per_day_late_inr", 500.0)
    max_penalty = inst.get("max_penalty_inr", (penalty_rule or {}).get("max_penalty_inr", 100000.0))

    times_missed = 0
    async for _ in db.filing_history.find({
        "business_id": business_id,
        "regulation_id": inst["regulation_id"],
        "on_time": False,
    }):
        times_missed += 1

    due_dt = _parse_datetime(inst.get("due_date"))
    now = datetime.utcnow()
    actually_overdue = bool(due_dt and due_dt < now)
    actual_days_late = (
        int((now - due_dt).total_seconds() / 86400) + 1 if actually_overdue else 0
    )
    # The endpoint name says "preview", so when the obligation isn't overdue
    # yet we project as if the deadline were missed by 1 day. Without this the
    # response shows ₹0 for every pending obligation and the UI looks broken.
    days_for_prediction = actual_days_late if actually_overdue else 1

    predicted = predict_penalty(
        base_penalty_inr=base_penalty,
        per_day_late_inr=per_day_late,
        max_penalty_inr=max_penalty,
        employee_count=business.get("employee_count", 1),
        annual_turnover_inr=business.get("annual_turnover_inr", 0),
        projected_days_late=days_for_prediction,
        times_missed_before=times_missed,
    )

    await log_decision(db, business_id, "penalty_preview", {
        "instance_id": instance_id,
        "predicted_penalty_inr": predicted,
        "projected_days_late": days_for_prediction,
        "is_projection": not actually_overdue,
    })

    return {
        "instance_id": instance_id,
        "business_id": business_id,
        "regulation_id": inst["regulation_id"],
        "name": inst.get("name", ""),
        "predicted_penalty_inr": predicted,
        "projected_days_late": days_for_prediction,
        "actual_days_late": actual_days_late,
        "is_projection": not actually_overdue,
        "base_penalty_inr": base_penalty,
        "per_day_late_inr": per_day_late,
        "max_penalty_inr": max_penalty,
        "times_missed_before": times_missed,
        "imprisonment_risk": inst.get("imprisonment_risk", False),
    }


@router.post("/draft/{instance_id}", status_code=201)
async def create_draft(
    instance_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: Dict = Depends(current_user),
):
    oid = valid_object_id(instance_id, "instance_id")
    inst = await db.obligation_instances.find_one({"_id": oid})
    if not inst:
        raise HTTPException(status_code=404, detail="Obligation instance not found")

    business_id = inst["business_id"]
    regulation_id = inst["regulation_id"]

    draft = await generate_draft(
        db=db,
        business_id=business_id,
        regulation_id=regulation_id,
        instance_id=instance_id,
    )
    if "error" in draft:
        raise HTTPException(status_code=422, detail=draft["error"])

    draft_doc = {**draft, "created_at": datetime.utcnow()}
    await db.obligation_instances.update_one(
        {"_id": oid},
        {"$set": {"draft": draft_doc, "status": "draft_generated"}},
    )

    await log_decision(db, business_id, "generate_draft", {
        "instance_id": instance_id,
        "template_name": draft.get("template_name", ""),
    })
    return draft


@router.get("/draft/{instance_id}/pdf")
async def download_draft_pdf(
    instance_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: Dict = Depends(current_user),
):
    """
    Render the stored draft into a real PDF. Generates the draft first if
    one hasn't been generated yet, so a fresh "Generate Draft" → "Download
    PDF" flow works in one click.
    """
    oid = valid_object_id(instance_id, "instance_id")
    inst = await db.obligation_instances.find_one({"_id": oid})
    if not inst:
        raise HTTPException(status_code=404, detail="Obligation instance not found")

    draft = inst.get("draft")
    if not draft:
        # Lazy-generate so the UI doesn't need two round-trips
        draft = await generate_draft(
            db=db, business_id=inst["business_id"],
            regulation_id=inst["regulation_id"], instance_id=instance_id,
        )
        if "error" in draft:
            raise HTTPException(status_code=422, detail=draft["error"])
        await db.obligation_instances.update_one(
            {"_id": oid},
            {"$set": {"draft": {**draft, "created_at": datetime.utcnow()},
                      "status": "draft_generated"}},
        )

    business = await db.businesses.find_one({"_id": ObjectId(inst["business_id"])})
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    pdf_bytes = generate_draft_pdf(draft, business)
    fname = safe_filename(
        draft.get("template_name", "draft"),
        business.get("name", "business"),
    )

    await log_decision(db, inst["business_id"], "download_draft_pdf", {
        "instance_id": instance_id,
        "template_name": draft.get("template_name", ""),
        "byte_size": len(pdf_bytes),
    })

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{fname}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


@router.post("/approve-draft/{instance_id}")
async def approve_draft(
    instance_id: str,
    payload: ApproveDraftRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: Dict = Depends(current_user),
):
    oid = valid_object_id(instance_id, "instance_id")
    inst = await db.obligation_instances.find_one({"_id": oid})
    if not inst:
        raise HTTPException(status_code=404, detail="Obligation instance not found")

    if inst.get("status") not in ("draft_generated", "pending"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot approve draft in status '{inst.get('status')}'",
        )

    business_id = inst["business_id"]
    regulation_id = inst["regulation_id"]
    now = datetime.utcnow()
    due_dt = _parse_datetime(inst.get("due_date"))
    on_time = (due_dt is None) or (now <= due_dt)

    fh_doc = {
        "business_id": business_id,
        "regulation_id": regulation_id,
        "instance_id": instance_id,
        "filed_at": now,
        "due_date": due_dt.isoformat() if due_dt else None,
        "on_time": on_time,
        "notes": payload.notes or "",
        "draft_snapshot": inst.get("draft", {}),
    }
    fh_result = await db.filing_history.insert_one(fh_doc)

    await db.obligation_instances.update_one(
        {"_id": oid},
        {"$set": {
            "status": "filed",
            "filed_at": now,
            "on_time": on_time,
            "filing_history_id": str(fh_result.inserted_id),
        }},
    )

    await log_decision(db, business_id, "approve_draft", {
        "instance_id": instance_id,
        "regulation_id": regulation_id,
        "on_time": on_time,
        "filing_history_id": str(fh_result.inserted_id),
    })

    return {
        "instance_id": instance_id,
        "business_id": business_id,
        "regulation_id": regulation_id,
        "filed_at": now.isoformat(),
        "on_time": on_time,
        "filing_history_id": str(fh_result.inserted_id),
        "status": "filed",
    }


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
