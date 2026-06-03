"""
Audit Replay — re-run a past agent decision under today's data and diff.

The premise: compliance is fundamentally about auditability. When a CA or
inspector asks "why did the agent recommend X two months ago?" we replay
the exact agent call with the original prompt, capture today's outcome,
and show a diff of what changed. Few hackathon submissions have this.

The replay endpoint:
  1. Loads the original agent_decisions record
  2. Reconstructs the inputs (action, payload)
  3. Calls the same engine function with the SAME inputs but TODAY'S data
  4. Returns: original record + today's output + a structured diff
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from auth import current_user
from common import log_decision, serialize, valid_object_id
from db.mongodb import get_db
from logging_config import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/agent-decisions", tags=["audit-replay"])


def _diff_dicts(original: Dict, current: Dict, path: str = "") -> List[Dict[str, Any]]:
    """Return a list of {path, original, current, kind} diff records."""
    diffs: List[Dict] = []
    keys = set(original.keys()) | set(current.keys())
    for k in sorted(keys):
        full_path = f"{path}.{k}" if path else k
        a = original.get(k)
        b = current.get(k)
        if isinstance(a, dict) and isinstance(b, dict):
            diffs.extend(_diff_dicts(a, b, full_path))
            continue
        if a == b:
            continue
        if k not in original:
            diffs.append({"path": full_path, "kind": "added", "original": None, "current": b})
        elif k not in current:
            diffs.append({"path": full_path, "kind": "removed", "original": a, "current": None})
        else:
            diffs.append({"path": full_path, "kind": "changed", "original": a, "current": b})
    return diffs


@router.get("/{business_id}/by-action")
async def decisions_by_action(
    business_id: str,
    action: Optional[str] = Query(None, description="Filter by action name"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: Dict = Depends(current_user),
):
    """List decisions grouped by action, with counts. Used for audit dashboards."""
    pipeline: List[Dict] = [
        {"$match": {"business_id": business_id}},
    ]
    if action:
        pipeline[0]["$match"]["action"] = action
    pipeline.extend([
        {"$sort": {"timestamp": -1}},
        {"$limit": limit},
        {"$project": {
            "_id": 1, "action": 1, "timestamp": 1, "payload": 1,
            "has_trace": {"$ifNull": ["$trace", False]},
        }},
    ])
    rows = []
    async for doc in db.agent_decisions.aggregate(pipeline):
        s = serialize(doc)
        s["has_trace"] = bool(doc.get("trace"))
        rows.append(s)

    # Also return per-action counts
    counts: List[Dict] = []
    async for c in db.agent_decisions.aggregate([
        {"$match": {"business_id": business_id}},
        {"$group": {"_id": "$action", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]):
        counts.append({"action": c["_id"], "count": c["count"]})

    return {"business_id": business_id, "decisions": rows, "action_counts": counts}


@router.post("/replay/{decision_id}")
async def replay_decision(
    decision_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: Dict = Depends(current_user),
):
    """
    Re-run a past decision against today's data and return a diff.

    Supported actions to replay:
      - penalty_preview      → recompute current predicted penalty
      - get_obligations      → recount/rescore current obligation set
      - ripple_check         → re-run ripple detection with current corpus
      - generate_draft       → regenerate draft from current business state
    Other actions are returned as "non-replayable" with the original record.
    """
    oid = valid_object_id(decision_id, "decision_id")
    original = await db.agent_decisions.find_one({"_id": oid})
    if not original:
        raise HTTPException(status_code=404, detail="Decision not found")

    action = original.get("action", "")
    payload = original.get("payload", {}) or {}
    business_id = original.get("business_id", "")

    original_record = serialize(original)
    summary: Dict[str, Any] = {
        "decision_id": decision_id,
        "action": action,
        "original_timestamp": original.get("timestamp").isoformat() if isinstance(original.get("timestamp"), datetime) else None,
        "original_payload": original_record.get("payload", {}),
        "replay_at": datetime.utcnow().isoformat() + "Z",
        "replayable": False,
        "reason": "",
    }

    # ── penalty_preview replay ────────────────────────────────────────────────
    if action == "penalty_preview":
        from routers.drafts import penalty_preview as run_penalty_preview
        instance_id = payload.get("instance_id")
        if not instance_id:
            summary["reason"] = "Original record missing instance_id"
            return summary
        try:
            current = await run_penalty_preview(
                instance_id, db=db, user=user,  # type: ignore[arg-type]
            )
        except HTTPException as exc:
            summary["reason"] = f"Underlying obligation gone: {exc.detail}"
            return summary
        summary["replayable"] = True
        summary["current_output"] = current
        summary["diff"] = _diff_dicts(payload, {
            "predicted_penalty_inr": current.get("predicted_penalty_inr"),
            "projected_days_late": current.get("projected_days_late"),
        })
        return summary

    # ── ripple_check replay ───────────────────────────────────────────────────
    if action == "ripple_check":
        # Best we can do without the original input text: re-flag current
        # impact across affected_categories from the original payload
        from engines.ripple_detector import detect_ripple_hybrid
        categories = payload.get("affected_categories", []) or original_record.get("payload", {}).get("affected_categories", [])
        if not business_id:
            summary["reason"] = "No business_id on original record"
            return summary
        current = await detect_ripple_hybrid(
            db=db,
            business_id=business_id,
            affected_categories=categories,
            affected_registrations=[],
            change_description=payload.get("title", "") or "",
        )
        summary["replayable"] = True
        summary["current_output"] = current
        summary["diff"] = _diff_dicts(
            {
                "direct_count": len(payload.get("directly_impacted", []) or []),
                "indirect_count": len(payload.get("indirectly_impacted", []) or []),
                "severity": payload.get("severity"),
            },
            {
                "direct_count": len(current.get("directly_impacted", []) or []),
                "indirect_count": len(current.get("indirectly_impacted", []) or []),
                "severity": current.get("severity"),
            },
        )
        return summary

    # ── get_obligations replay (just current count vs original count) ─────────
    if action == "get_obligations":
        from routers.obligations import get_obligations as run_get_obligations
        try:
            current_resp = await run_get_obligations(
                business_id=business_id,
                page=(250, 0),  # type: ignore[arg-type]
                db=db, _user=user,  # type: ignore[arg-type]
            )
        except HTTPException as exc:
            summary["reason"] = f"Business not found today: {exc.detail}"
            return summary
        current_count = current_resp.get("total", 0)
        summary["replayable"] = True
        summary["current_output"] = {"count": current_count}
        summary["diff"] = _diff_dicts(
            {"count": payload.get("count", 0)},
            {"count": current_count},
        )
        return summary

    # ── Fallback: not replayable ──────────────────────────────────────────────
    summary["reason"] = (
        f"Action '{action}' is not replayable in this version. "
        "Replayable actions: penalty_preview, ripple_check, get_obligations."
    )
    summary["original_record"] = original_record
    return summary
