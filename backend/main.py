import os
from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional

from bson import ObjectId
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

load_dotenv()

from db.mongodb import create_indexes, get_db
from engines.auto_draft import generate_draft
from engines.decay_score import compute_decay_score, score_to_urgency
from engines.dna_builder import build_compliance_dna
from engines.penalty_predictor import predict_penalty
from engines.ripple_detector import detect_ripple


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _oid(value: Any) -> str:
    """Safely convert ObjectId or str to str."""
    return str(value)


def _serialize(doc: Dict) -> Dict:
    """Recursively convert ObjectId fields to str for JSON serialisation."""
    if doc is None:
        return {}
    result = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            result[k] = str(v)
        elif isinstance(v, dict):
            result[k] = _serialize(v)
        elif isinstance(v, list):
            result[k] = [_serialize(i) if isinstance(i, dict) else (str(i) if isinstance(i, ObjectId) else i) for i in v]
        elif isinstance(v, datetime):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result


async def _log_decision(
    db: AsyncIOMotorDatabase,
    business_id: str,
    action: str,
    payload: Dict,
) -> None:
    """Write an agent decision record to agent_decisions collection."""
    await db.agent_decisions.insert_one({
        "business_id": business_id,
        "action": action,
        "payload": payload,
        "timestamp": datetime.utcnow(),
    })


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = get_db()
    await create_indexes(db)
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ComplianceOS API",
    version="1.0.0",
    description="AI-powered regulatory compliance engine for Indian SMEs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------

def db_dep() -> AsyncIOMotorDatabase:
    return get_db()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class BusinessCreate(BaseModel):
    name: str
    owner: str
    state: str
    industry: str
    employee_count: int
    annual_turnover_inr: float
    registrations: List[str] = Field(default_factory=list)
    incorporation_date: Optional[str] = None  # ISO date string e.g. "2024-03-15"


class RippleCheckRequest(BaseModel):
    business_id: str
    regulation_change: Dict[str, Any]


class ApproveDraftRequest(BaseModel):
    notes: Optional[str] = None


class ConfirmObligationsRequest(BaseModel):
    keep_ids: List[str]
    due_dates: Dict[str, str] = Field(default_factory=dict)  # instance_id -> ISO date string


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "mcp": "mongodb-atlas"}


# POST /business
@app.post("/business", status_code=201)
async def create_business(
    payload: BusinessCreate,
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    """
    Create a business profile, run Compliance DNA Builder, persist obligation
    instances, and return a summary.
    """
    # Persist business
    business_doc = payload.model_dump()
    business_doc["created_at"] = datetime.utcnow()
    result = await db.businesses.insert_one(business_doc)
    business_id = str(result.inserted_id)

    # Build DNA
    entity_attrs = {
        "state": payload.state,
        "industry": payload.industry,
        "employee_count": payload.employee_count,
        "annual_turnover_inr": payload.annual_turnover_inr,
        "registrations": payload.registrations,
        "incorporation_date": payload.incorporation_date,
    }
    dna = await build_compliance_dna(db, business_id, entity_attrs)

    # Frequency → days until next due date (staggered so scores spread naturally)
    _freq_days = {
        "daily": 1, "weekly": 7, "monthly": 30, "quarterly": 90,
        "half_yearly": 182, "annual": 365, "one_time": 365,
    }

    # Create obligation instances from DNA
    inserted_instance_ids = []
    now = datetime.utcnow()
    for i, obl in enumerate(dna["applicable_obligations"]):
        freq = obl.get("frequency", "monthly")
        days_allowed = _freq_days.get(freq, 30)
        # Stagger due dates: spread obligations across 10–100% of their period
        # so the dashboard shows a realistic mix of urgent/warning/on-track
        stagger_pct = 0.15 + (i % 7) * 0.12   # cycles through 15%, 27%, 39%, 51%, 63%, 75%, 87%
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

    await _log_decision(
        db,
        business_id,
        "create_business",
        {
            "name": payload.name,
            "total_obligations": dna["total_obligations"],
            "high_severity_count": dna["high_severity_count"],
        },
    )

    return {
        "business_id": business_id,
        "name": payload.name,
        "dna_summary": {
            "total_obligations": dna["total_obligations"],
            "high_severity_count": dna["high_severity_count"],
            "obligation_ids": inserted_instance_ids,
        },
    }


# POST /business/{business_id}/confirm-obligations
@app.post("/business/{business_id}/confirm-obligations")
async def confirm_obligations(
    business_id: str,
    payload: ConfirmObligationsRequest,
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    """
    User reviews AI-generated obligations and confirms their actual set.
    Deletes unchecked obligations and updates due dates on confirmed ones.
    """
    try:
        ObjectId(business_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid business_id")

    keep_set = set(payload.keep_ids)

    # Delete obligations the user removed
    all_ids = []
    async for inst in db.obligation_instances.find({"business_id": business_id}, {"_id": 1}):
        all_ids.append(str(inst["_id"]))

    remove_ids = [oid for oid in all_ids if oid not in keep_set]
    if remove_ids:
        await db.obligation_instances.delete_many({
            "_id": {"$in": [ObjectId(oid) for oid in remove_ids]}
        })

    # Update due dates for confirmed obligations
    for instance_id, due_date_str in payload.due_dates.items():
        if instance_id in keep_set:
            try:
                due_dt = datetime.fromisoformat(due_date_str)
                await db.obligation_instances.update_one(
                    {"_id": ObjectId(instance_id)},
                    {"$set": {"due_date": due_dt}},
                )
            except Exception:
                pass

    await _log_decision(db, business_id, "confirm_obligations", {
        "kept": len(keep_set),
        "removed": len(remove_ids),
    })

    return {
        "business_id": business_id,
        "kept": len(keep_set),
        "removed": len(remove_ids),
    }


# GET /obligations/{business_id}
@app.get("/obligations/{business_id}")
async def get_obligations(
    business_id: str,
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    """
    Return all obligation instances for a business, with decay scores,
    sorted ascending (most urgent first).
    """
    business = await db.businesses.find_one({"_id": ObjectId(business_id)})
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    # Fetch filing history to compute historical_on_time_rate
    total_filed = 0
    on_time_filed = 0
    async for fh in db.filing_history.find({"business_id": business_id}):
        total_filed += 1
        if fh.get("on_time"):
            on_time_filed += 1
    historical_on_time_rate = (on_time_filed / total_filed) if total_filed > 0 else 1.0

    obligations = []
    now = datetime.utcnow()
    cursor = db.obligation_instances.find({"business_id": business_id})
    async for inst in cursor:
        due_date_raw = inst.get("due_date")
        if due_date_raw:
            if isinstance(due_date_raw, datetime):
                due_dt = due_date_raw
            else:
                try:
                    due_dt = datetime.fromisoformat(str(due_date_raw))
                except Exception:
                    due_dt = None
        else:
            due_dt = None
        if due_dt:
            days_remaining = (due_dt - now).total_seconds() / 86400.0
        else:
            days_remaining = 30.0  # default if no due date set

        # Derive total_days_allowed from frequency
        frequency = inst.get("frequency", "monthly")
        freq_map = {
            "daily": 1,
            "weekly": 7,
            "monthly": 30,
            "quarterly": 90,
            "half_yearly": 182,
            "annual": 365,
            "one_time": 365,
        }
        total_days = freq_map.get(frequency, 30)

        complexity = inst.get("complexity", 1)
        max_penalty = inst.get("max_penalty_inr", 10000)
        penalty_severity = max(max_penalty / 100000, 1.0)  # normalise to 1-based scale

        decay = compute_decay_score(
            days_remaining=days_remaining,
            total_days_allowed=total_days,
            complexity_weight=float(complexity),
            penalty_severity_multiplier=penalty_severity,
            historical_on_time_rate=historical_on_time_rate,
        )
        urgency = score_to_urgency(decay)

        # Update decay score in DB
        await db.obligation_instances.update_one(
            {"_id": inst["_id"]},
            {"$set": {"decay_score": decay, "urgency": urgency}},
        )

        # Write time series snapshot (fire-and-forget; non-blocking on failure)
        try:
            await db.decay_score_snapshots.insert_one({
                "instance_id": str(inst["_id"]),
                "business_id": business_id,
                "decay_score": decay,
                "urgency": urgency,
                "timestamp": now,
            })
        except Exception:
            pass

        serialised = _serialize(inst)
        serialised["decay_score"] = decay
        serialised["urgency"] = urgency
        obligations.append(serialised)

    # Sort ascending by decay_score (most urgent = lowest score first)
    obligations.sort(key=lambda x: x.get("decay_score", 0))

    await _log_decision(
        db,
        business_id,
        "get_obligations",
        {"count": len(obligations)},
    )

    return {"business_id": business_id, "obligations": obligations}


# POST /regulations/check-ripple
@app.post("/regulations/check-ripple")
async def check_ripple(
    payload: RippleCheckRequest,
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    """
    Run Regulatory Ripple Detection for a given regulation change.
    """
    business_id = payload.business_id
    change = payload.regulation_change

    affected_categories = change.get("affected_categories", [])
    affected_registrations = change.get("affected_registrations", [])

    # Persist the change record
    change_doc = {
        **change,
        "business_id": business_id,
        "detected_at": datetime.utcnow(),
    }
    await db.regulatory_changes.insert_one(change_doc)

    ripple = await detect_ripple(
        db=db,
        business_id=business_id,
        affected_categories=affected_categories,
        affected_registrations=affected_registrations,
        change_description=change.get("title", ""),
    )

    await _log_decision(
        db,
        business_id,
        "ripple_check",
        ripple,
    )

    return {
        "business_id": business_id,
        "regulation_change": change,
        "ripple_report": ripple,
    }


# GET /penalty-preview/{instance_id}
@app.get("/penalty-preview/{instance_id}")
async def penalty_preview(
    instance_id: str,
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    """
    Return predicted penalty for an obligation instance.
    """
    try:
        inst = await db.obligation_instances.find_one({"_id": ObjectId(instance_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid instance_id")
    if not inst:
        raise HTTPException(status_code=404, detail="Obligation instance not found")

    business_id = inst["business_id"]
    business = await db.businesses.find_one({"_id": ObjectId(business_id)})
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    # Fetch penalty rule for this regulation
    penalty_rule = await db.penalty_rules.find_one({"regulation_id": inst["regulation_id"]})

    base_penalty = (penalty_rule or {}).get("base_penalty_inr", 5000.0)
    per_day_late = (penalty_rule or {}).get("per_day_late_inr", 500.0)
    max_penalty = inst.get("max_penalty_inr", (penalty_rule or {}).get("max_penalty_inr", 100000.0))

    # Count times missed
    times_missed = 0
    async for fh in db.filing_history.find({
        "business_id": business_id,
        "regulation_id": inst["regulation_id"],
        "on_time": False,
    }):
        times_missed += 1

    # Estimate projected_days_late from due_date
    due_date_raw = inst.get("due_date")
    if due_date_raw:
        if isinstance(due_date_raw, datetime):
            due_dt = due_date_raw
        else:
            try:
                due_dt = datetime.fromisoformat(str(due_date_raw))
            except Exception:
                due_dt = None
    else:
        due_dt = None

    now = datetime.utcnow()
    if due_dt and due_dt < now:
        projected_days_late = int((now - due_dt).total_seconds() / 86400) + 1
    else:
        projected_days_late = 0  # Not yet overdue

    predicted = predict_penalty(
        base_penalty_inr=base_penalty,
        per_day_late_inr=per_day_late,
        max_penalty_inr=max_penalty,
        employee_count=business.get("employee_count", 1),
        annual_turnover_inr=business.get("annual_turnover_inr", 0),
        projected_days_late=projected_days_late,
        times_missed_before=times_missed,
    )

    await _log_decision(
        db,
        business_id,
        "penalty_preview",
        {
            "instance_id": instance_id,
            "predicted_penalty_inr": predicted,
            "projected_days_late": projected_days_late,
        },
    )

    return {
        "instance_id": instance_id,
        "business_id": business_id,
        "regulation_id": inst["regulation_id"],
        "name": inst.get("name", ""),
        "predicted_penalty_inr": predicted,
        "projected_days_late": projected_days_late,
        "base_penalty_inr": base_penalty,
        "per_day_late_inr": per_day_late,
        "max_penalty_inr": max_penalty,
        "times_missed_before": times_missed,
        "imprisonment_risk": inst.get("imprisonment_risk", False),
    }


# POST /draft/{instance_id}
@app.post("/draft/{instance_id}", status_code=201)
async def create_draft(
    instance_id: str,
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    """
    Generate an auto-draft filing document for an obligation instance.
    """
    try:
        inst = await db.obligation_instances.find_one({"_id": ObjectId(instance_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid instance_id")
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

    # Persist draft to DB
    draft_doc = {**draft, "created_at": datetime.utcnow()}
    await db.obligation_instances.update_one(
        {"_id": ObjectId(instance_id)},
        {"$set": {"draft": draft_doc, "status": "draft_generated"}},
    )

    await _log_decision(
        db,
        business_id,
        "generate_draft",
        {"instance_id": instance_id, "template_name": draft.get("template_name", "")},
    )

    return draft


# POST /approve-draft/{instance_id}
@app.post("/approve-draft/{instance_id}")
async def approve_draft(
    instance_id: str,
    payload: ApproveDraftRequest,
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    """
    Approve a draft, record to filing_history, mark obligation as filed.
    """
    try:
        inst = await db.obligation_instances.find_one({"_id": ObjectId(instance_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid instance_id")
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

    due_date_raw = inst.get("due_date")
    if due_date_raw:
        if isinstance(due_date_raw, datetime):
            due_dt = due_date_raw
        else:
            try:
                due_dt = datetime.fromisoformat(str(due_date_raw))
            except Exception:
                due_dt = None
    else:
        due_dt = None

    on_time = (due_dt is None) or (now <= due_dt)

    # Write to filing_history
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

    # Mark obligation as filed
    await db.obligation_instances.update_one(
        {"_id": ObjectId(instance_id)},
        {
            "$set": {
                "status": "filed",
                "filed_at": now,
                "on_time": on_time,
                "filing_history_id": str(fh_result.inserted_id),
            }
        },
    )

    await _log_decision(
        db,
        business_id,
        "approve_draft",
        {
            "instance_id": instance_id,
            "regulation_id": regulation_id,
            "on_time": on_time,
            "filing_history_id": str(fh_result.inserted_id),
        },
    )

    return {
        "instance_id": instance_id,
        "business_id": business_id,
        "regulation_id": regulation_id,
        "filed_at": now.isoformat(),
        "on_time": on_time,
        "filing_history_id": str(fh_result.inserted_id),
        "status": "filed",
    }


# GET /filing-history/{business_id}
@app.get("/filing-history/{business_id}")
async def filing_history(
    business_id: str,
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    """
    Return full filing history for a business with on-time rate.
    """
    business = await db.businesses.find_one({"_id": ObjectId(business_id)})
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
        history.append(_serialize(fh))

    on_time_rate = round(on_time_count / total, 4) if total > 0 else None

    await _log_decision(
        db,
        business_id,
        "get_filing_history",
        {"total_filings": total, "on_time_rate": on_time_rate},
    )

    return {
        "business_id": business_id,
        "total_filings": total,
        "on_time_count": on_time_count,
        "on_time_rate": on_time_rate,
        "history": history,
    }


# GET /decay-trend/{business_id}
@app.get("/decay-trend/{business_id}")
async def decay_trend(
    business_id: str,
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    """
    Return 30-day decay score history per obligation (from Time Series collection).
    Used to render sparkline trend lines on the dashboard.
    """
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    trends: Dict[str, List] = {}
    cursor = db.decay_score_snapshots.find(
        {"business_id": business_id, "timestamp": {"$gte": thirty_days_ago}},
        sort=[("timestamp", 1)],
    )
    async for snap in cursor:
        iid = snap.get("instance_id", "")
        if iid not in trends:
            trends[iid] = []
        ts = snap.get("timestamp")
        trends[iid].append({
            "t": ts.isoformat() if isinstance(ts, datetime) else str(ts),
            "score": snap.get("decay_score", 0),
        })

    return {"business_id": business_id, "trends": trends}


# GET /agent-decisions/{business_id}
@app.get("/agent-decisions/{business_id}")
async def agent_decisions(
    business_id: str,
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    """
    Return the last 20 agent decisions for a business.
    """
    decisions = []
    cursor = db.agent_decisions.find(
        {"business_id": business_id},
        sort=[("timestamp", -1)],
        limit=20,
    )
    async for dec in cursor:
        decisions.append(_serialize(dec))

    return {
        "business_id": business_id,
        "count": len(decisions),
        "decisions": decisions,
    }
