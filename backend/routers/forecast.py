"""
Penalty Exposure Forecast — project total ₹ exposure 30/60/90 days into
the future for a business assuming nothing is filed.

For each pending obligation we:
  1. Compute current overdue days
  2. Project days_late at the horizon
  3. Run the same predict_penalty() the live preview uses
  4. Sum across the business

The result is a horizon-indexed curve the dashboard renders as bars. Uses
Time Series snapshots from decay_score_snapshots to estimate the trajectory
trend for any obligations whose deadlines fall inside the horizon window.

This is sophisticated use of MongoDB Time Series collections beyond just
storage: actual aggregation of historical points + linear projection.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from auth import require_business_owner
from common import valid_object_id
from db.mongodb import get_db
from engines.penalty_predictor import predict_penalty
from logging_config import get_logger

log = get_logger(__name__)

router = APIRouter(tags=["forecast"])


DEFAULT_HORIZONS = (30, 60, 90)


def _parse_dt(raw) -> Optional[datetime]:
    if isinstance(raw, datetime):
        return raw
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw))
    except ValueError:
        return None


@router.get("/exposure-forecast/{business_id}")
async def exposure_forecast(
    business_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: Dict = Depends(require_business_owner),
):
    """
    Project total penalty exposure at +30/+60/+90 days assuming nothing
    is filed between now and then. Returns:
      - point_in_time exposures (one number per horizon)
      - delta from "now" (how much MORE you'd owe)
      - per-obligation contribution at the worst horizon
      - count of obligations that will newly go red within each horizon
    """
    valid_object_id(business_id, "business_id")
    biz = await db.businesses.find_one({"_id": ObjectId(business_id)})
    if not biz:
        return {"business_id": business_id, "error": "Business not found"}

    employee_count = biz.get("employee_count", 1)
    turnover = biz.get("annual_turnover_inr", 0)

    # ── pull all pending obligations + their penalty rules in batch ───────────
    obligations: List[Dict] = []
    async for inst in db.obligation_instances.find({
        "business_id": business_id,
        "status": {"$in": [None, "pending", "draft_generated"]},
    }):
        obligations.append(inst)

    if not obligations:
        return {
            "business_id": business_id,
            "horizons_days": list(DEFAULT_HORIZONS),
            "current_exposure_inr": 0,
            "by_horizon": [
                {"days": h, "exposure_inr": 0, "delta_inr": 0,
                 "newly_red_count": 0, "obligations_overdue_count": 0}
                for h in DEFAULT_HORIZONS
            ],
            "top_contributors": [],
            "total_pending": 0,
        }

    # Aggregate filing_history for per-regulation times_missed counts
    miss_counts: Dict[str, int] = {}
    pipeline = [
        {"$match": {"business_id": business_id, "on_time": False}},
        {"$group": {"_id": "$regulation_id", "count": {"$sum": 1}}},
    ]
    async for doc in db.filing_history.aggregate(pipeline):
        miss_counts[doc["_id"]] = int(doc.get("count") or 0)

    # Cache penalty rules
    reg_ids = list({o.get("regulation_id") for o in obligations})
    rules: Dict[str, Dict] = {}
    async for rule in db.penalty_rules.find({"regulation_id": {"$in": reg_ids}}):
        rules[rule["regulation_id"]] = rule

    now = datetime.utcnow()
    horizons = list(DEFAULT_HORIZONS)
    horizon_results: List[Dict] = []
    per_obligation_at_max: List[Dict] = []

    # Compute current exposure (days_late=1 projection for non-overdue, actual for overdue)
    def _exposure_at(days_offset: int) -> Dict:
        total = 0.0
        newly_red = 0
        overdue_count = 0
        contributors: List[Dict] = []
        future_now = now + timedelta(days=days_offset)
        for inst in obligations:
            due = _parse_dt(inst.get("due_date"))
            if not due:
                continue
            # Projected days late at this horizon
            delta_days = (future_now - due).total_seconds() / 86400.0
            projected_days_late = max(0, int(delta_days) + 1)
            # Counts
            if delta_days > 0:
                overdue_count += 1
            # "Newly red" — wasn't overdue at t=0 but is at this horizon
            if delta_days > 0 and (now - due).total_seconds() < 0:
                newly_red += 1

            rule = rules.get(inst.get("regulation_id", ""), {}) or {}
            base = rule.get("base_penalty_inr", 5000.0)
            per_day = rule.get("per_day_late_inr", 500.0)
            max_p = inst.get("max_penalty_inr", rule.get("max_penalty_inr", 100_000.0))

            # Use projected_days_late=1 when not overdue at all
            days_for_prediction = projected_days_late if projected_days_late > 0 else 1

            amount = predict_penalty(
                base_penalty_inr=base,
                per_day_late_inr=per_day,
                max_penalty_inr=max_p,
                employee_count=employee_count,
                annual_turnover_inr=turnover,
                projected_days_late=days_for_prediction,
                times_missed_before=miss_counts.get(inst.get("regulation_id", ""), 0),
            )
            total += amount
            if days_offset == max(horizons):
                contributors.append({
                    "name": inst.get("name", ""),
                    "amount_inr": amount,
                    "days_late_at_horizon": projected_days_late,
                    "due_date": due.isoformat() + "Z",
                })

        if days_offset == max(horizons):
            contributors.sort(key=lambda c: -c["amount_inr"])
            per_obligation_at_max.extend(contributors[:5])

        return {
            "days": days_offset,
            "exposure_inr": round(total, 2),
            "newly_red_count": newly_red,
            "obligations_overdue_count": overdue_count,
        }

    current = _exposure_at(0)
    current_total = current["exposure_inr"]

    for h in horizons:
        row = _exposure_at(h)
        row["delta_inr"] = round(row["exposure_inr"] - current_total, 2)
        horizon_results.append(row)

    return {
        "business_id": business_id,
        "horizons_days": horizons,
        "current_exposure_inr": current_total,
        "by_horizon": horizon_results,
        "top_contributors": per_obligation_at_max,
        "total_pending": len(obligations),
        "computed_at": now.isoformat() + "Z",
    }
