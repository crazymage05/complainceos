"""
ADK tools — high-level capabilities the agents can invoke.

These wrap our existing engines/* logic and expose them as plain Python
functions the Gemini agent can call via ADK's tool-use protocol. Each tool
returns a JSON-serialisable dict; ADK handles function-call routing.
"""

import asyncio
import math
from datetime import datetime
from typing import Any, Dict, List

from bson import ObjectId

from config import FREQ_DAYS
from db.mongodb import get_db
from engines.auto_draft import generate_draft as _generate_draft
from engines.decay_score import compute_decay_score, score_to_urgency
from engines.dna_builder import build_compliance_dna
from engines.obligation_chat import chat_discover
from engines.penalty_predictor import predict_penalty as _predict_penalty
from engines.ripple_detector import detect_ripple
from logging_config import get_logger

log = get_logger(__name__)


def _penalty_severity(max_penalty_inr: float) -> float:
    if max_penalty_inr <= 10_000:
        return 1.0
    return max(1.0, min(1.0 + math.log10(max_penalty_inr / 10_000), 3.0))


def _safe_oid(value: str) -> ObjectId | None:
    try:
        return ObjectId(value)
    except Exception:
        return None


# ────────────────────────────────────────────────────────────────────────────
# Tool 1 — List obligations
# ────────────────────────────────────────────────────────────────────────────

async def list_obligations(business_id: str, limit: int = 10) -> Dict[str, Any]:
    """
    Return the most urgent active obligations for a business with live decay scores.

    Args:
        business_id: MongoDB ObjectId of the business as string.
        limit: Maximum number of obligations to return (default 10).

    Returns:
        A dict with 'obligations' (list of {name, category, decay_score, urgency,
        days_remaining, max_penalty_inr}) and 'summary' counts.
    """
    db = get_db()
    oid = _safe_oid(business_id)
    if not oid:
        return {"error": f"Invalid business_id: {business_id}"}

    business = await db.businesses.find_one({"_id": oid})
    if not business:
        return {"error": "Business not found"}

    # Historical on-time rate for personalisation
    total_filed = 0
    on_time_filed = 0
    async for fh in db.filing_history.find({"business_id": business_id}):
        total_filed += 1
        if fh.get("on_time"):
            on_time_filed += 1
    historical_rate = (on_time_filed / total_filed) if total_filed > 0 else 1.0

    now = datetime.utcnow()
    rows: List[Dict] = []
    async for inst in db.obligation_instances.find({
        "business_id": business_id, "status": {"$in": [None, "pending", "draft_generated"]}
    }):
        due = inst.get("due_date")
        if isinstance(due, datetime):
            days_remaining = (due - now).total_seconds() / 86400.0
        else:
            days_remaining = 30.0

        freq = inst.get("frequency", "monthly")
        total_days = FREQ_DAYS.get(freq, 30)
        complexity = float(inst.get("complexity", 1))
        max_penalty = inst.get("max_penalty_inr", 10000)
        decay = compute_decay_score(
            days_remaining=days_remaining,
            total_days_allowed=total_days,
            complexity_weight=complexity,
            penalty_severity_multiplier=_penalty_severity(max_penalty),
            historical_on_time_rate=historical_rate,
        )
        rows.append({
            "instance_id": str(inst["_id"]),
            "name": inst.get("name", ""),
            "category": inst.get("category", ""),
            "decay_score": decay,
            "urgency": score_to_urgency(decay),
            "days_remaining": round(days_remaining, 1),
            "max_penalty_inr": max_penalty,
            "frequency": freq,
        })

    rows.sort(key=lambda r: r["decay_score"])
    top = rows[:limit]

    return {
        "obligations": top,
        "summary": {
            "total_active": len(rows),
            "urgent": sum(1 for r in rows if r["urgency"] == "red"),
            "warning": sum(1 for r in rows if r["urgency"] == "amber"),
            "on_track": sum(1 for r in rows if r["urgency"] == "green"),
        },
    }


# ────────────────────────────────────────────────────────────────────────────
# Tool 2 — Explain a decay score
# ────────────────────────────────────────────────────────────────────────────

async def explain_decay_score(instance_id: str) -> Dict[str, Any]:
    """
    Return a structured explanation of why an obligation has its specific
    decay score, including all formula inputs.

    Args:
        instance_id: MongoDB ObjectId of the obligation_instance as string.

    Returns:
        Dict with 'name', 'score', 'urgency', 'inputs' (the formula vars),
        and 'reasoning' (a list of human-readable bullets).
    """
    db = get_db()
    oid = _safe_oid(instance_id)
    if not oid:
        return {"error": f"Invalid instance_id: {instance_id}"}
    inst = await db.obligation_instances.find_one({"_id": oid})
    if not inst:
        return {"error": "Obligation not found"}

    business_id = inst["business_id"]
    due = inst.get("due_date")
    now = datetime.utcnow()
    if isinstance(due, datetime):
        days_remaining = (due - now).total_seconds() / 86400.0
    else:
        days_remaining = 30.0

    freq = inst.get("frequency", "monthly")
    total_days = FREQ_DAYS.get(freq, 30)
    complexity = float(inst.get("complexity", 1))
    max_penalty = inst.get("max_penalty_inr", 10000)
    penalty_sev = _penalty_severity(max_penalty)

    # Historical rate
    total_filed = 0
    on_time_filed = 0
    async for fh in db.filing_history.find({"business_id": business_id}):
        total_filed += 1
        if fh.get("on_time"):
            on_time_filed += 1
    historical = (on_time_filed / total_filed) if total_filed > 0 else 1.0

    score = compute_decay_score(
        days_remaining=days_remaining,
        total_days_allowed=total_days,
        complexity_weight=complexity,
        penalty_severity_multiplier=penalty_sev,
        historical_on_time_rate=historical,
    )

    time_ratio = max(days_remaining / total_days, 0.0)
    bullets = [
        f"Frequency '{freq}' allows {total_days} days; {round(days_remaining, 1)} remain "
        f"→ time component {round(time_ratio * 100, 1)}%.",
        f"Complexity is {int(complexity)}/5 — subtracts {round(math.log10(max(complexity, 1.0)) * 12, 1)} points.",
        f"Max penalty ₹{int(max_penalty):,} → severity {round(penalty_sev, 2)} — subtracts "
        f"{round(math.log10(max(penalty_sev, 1.0)) * 12, 1)} points.",
        f"Your on-time rate is {round(historical * 100, 0)}% across {total_filed} past filings.",
        f"Composite decay score: {score} ({score_to_urgency(score)}).",
    ]

    return {
        "name": inst.get("name", ""),
        "score": score,
        "urgency": score_to_urgency(score),
        "inputs": {
            "days_remaining": round(days_remaining, 1),
            "total_days_allowed": total_days,
            "complexity_weight": complexity,
            "penalty_severity": round(penalty_sev, 2),
            "historical_on_time_rate": round(historical, 3),
            "max_penalty_inr": max_penalty,
        },
        "reasoning": bullets,
    }


# ────────────────────────────────────────────────────────────────────────────
# Tool 3 — Predict penalty
# ────────────────────────────────────────────────────────────────────────────

async def predict_penalty_for(instance_id: str) -> Dict[str, Any]:
    """
    Predict the financial penalty if a specific obligation is missed.

    Args:
        instance_id: MongoDB ObjectId of the obligation_instance as string.

    Returns:
        Dict with 'predicted_penalty_inr', 'is_projection', breakdown components.
    """
    db = get_db()
    oid = _safe_oid(instance_id)
    if not oid:
        return {"error": f"Invalid instance_id: {instance_id}"}
    inst = await db.obligation_instances.find_one({"_id": oid})
    if not inst:
        return {"error": "Obligation not found"}

    business = await db.businesses.find_one({"_id": _safe_oid(inst["business_id"])})
    if not business:
        return {"error": "Business not found"}

    rule = await db.penalty_rules.find_one({"regulation_id": inst["regulation_id"]}) or {}
    base = rule.get("base_penalty_inr", 5000.0)
    per_day = rule.get("per_day_late_inr", 500.0)
    max_p = inst.get("max_penalty_inr", rule.get("max_penalty_inr", 100_000.0))

    times_missed = 0
    async for _ in db.filing_history.find({
        "business_id": inst["business_id"],
        "regulation_id": inst["regulation_id"],
        "on_time": False,
    }):
        times_missed += 1

    due = inst.get("due_date")
    now = datetime.utcnow()
    overdue = bool(isinstance(due, datetime) and due < now)
    actual_days_late = int((now - due).total_seconds() / 86400) + 1 if overdue else 0
    days = actual_days_late if overdue else 1

    amount = _predict_penalty(
        base_penalty_inr=base,
        per_day_late_inr=per_day,
        max_penalty_inr=max_p,
        employee_count=business.get("employee_count", 1),
        annual_turnover_inr=business.get("annual_turnover_inr", 0),
        projected_days_late=days,
        times_missed_before=times_missed,
    )
    return {
        "name": inst.get("name", ""),
        "predicted_penalty_inr": amount,
        "is_projection": not overdue,
        "projected_days_late": days,
        "actual_days_late": actual_days_late,
        "base_penalty_inr": base,
        "per_day_late_inr": per_day,
        "times_missed_before": times_missed,
    }


# ────────────────────────────────────────────────────────────────────────────
# Tool 4 — Detect ripple impact
# ────────────────────────────────────────────────────────────────────────────

async def detect_regulation_impact(
    business_id: str,
    change_description: str,
    affected_categories: List[str] | None = None,
) -> Dict[str, Any]:
    """
    Run regulatory ripple detection: find which obligations are affected
    by a regulatory change, using Atlas Vector Search.

    Args:
        business_id: MongoDB ObjectId of the business as string.
        change_description: Plain-language description or text of the new regulation.
        affected_categories: Optional list of affected categories (for fallback).

    Returns:
        Dict with 'directly_impacted', 'indirectly_impacted', 'severity'.
    """
    db = get_db()
    return await detect_ripple(
        db=db,
        business_id=business_id,
        affected_categories=affected_categories or [],
        affected_registrations=[],
        change_description=change_description,
    )


# ────────────────────────────────────────────────────────────────────────────
# Tool 5 — Discover non-obvious obligations
# ────────────────────────────────────────────────────────────────────────────

async def discover_hidden_obligations(
    business_id: str,
    question_or_topic: str = "What obligations might be missing for this business?",
) -> Dict[str, Any]:
    """
    Use the AI Advisor to discover non-obvious compliance obligations for
    a business based on its profile (state, industry, size, registrations).

    Args:
        business_id: MongoDB ObjectId of the business as string.
        question_or_topic: A natural-language prompt to seed the discovery.

    Returns:
        Dict with 'discovered' (list of {name, reason, category, urgency})
        and 'reply'.
    """
    db = get_db()
    oid = _safe_oid(business_id)
    if not oid:
        return {"error": f"Invalid business_id: {business_id}"}
    business = await db.businesses.find_one({"_id": oid})
    if not business:
        return {"error": "Business not found"}

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
        business_id,
        [{"role": "user", "content": question_or_topic}],
        context,
        business_facts={},
        summarise=False,
    )
    return {
        "reply": result.get("reply", ""),
        "discovered": result.get("discovered", []),
    }


# ────────────────────────────────────────────────────────────────────────────
# Tool 6 — Generate a filing draft
# ────────────────────────────────────────────────────────────────────────────

async def generate_filing_draft(instance_id: str) -> Dict[str, Any]:
    """
    Generate a pre-filled filing draft for an obligation, with category-
    specific advisor notes (documents needed, common mistakes, checklist).

    Args:
        instance_id: MongoDB ObjectId of the obligation_instance as string.

    Returns:
        The generated draft document with populated_fields and advisor_notes.
    """
    db = get_db()
    oid = _safe_oid(instance_id)
    if not oid:
        return {"error": f"Invalid instance_id: {instance_id}"}
    inst = await db.obligation_instances.find_one({"_id": oid})
    if not inst:
        return {"error": "Obligation not found"}

    return await _generate_draft(
        db=db,
        business_id=inst["business_id"],
        regulation_id=inst["regulation_id"],
        instance_id=instance_id,
    )


# ────────────────────────────────────────────────────────────────────────────
# Tool 7 — Filing history summary
# ────────────────────────────────────────────────────────────────────────────

async def get_filing_track_record(business_id: str) -> Dict[str, Any]:
    """
    Summarise the business's filing track record: on-time rate, total
    filings, late filings, total penalty exposure avoided.

    Args:
        business_id: MongoDB ObjectId of the business as string.

    Returns:
        Dict with on_time_rate, total_filings, late_count, penalty_avoided_estimate.
    """
    db = get_db()
    total = 0
    on_time = 0
    late = 0
    async for fh in db.filing_history.find({"business_id": business_id}):
        total += 1
        if fh.get("on_time"):
            on_time += 1
        else:
            late += 1

    return {
        "total_filings": total,
        "on_time_count": on_time,
        "late_count": late,
        "on_time_rate": round(on_time / total, 3) if total > 0 else None,
    }
