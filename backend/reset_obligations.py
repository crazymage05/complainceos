"""
Nightly obligation reset scheduler.
Run manually or via cron: python reset_obligations.py

For each recurring obligation that is filed or overdue and past its due_date,
creates a new obligation_instance for the next period with a fresh decay score.
Idempotent — skips if a pending instance already exists for the same
business + regulation + next period.
"""
import asyncio, os, sys
from datetime import datetime, timedelta
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ".")
from dotenv import load_dotenv; load_dotenv()
from db.mongodb import get_db

FREQ_DAYS = {
    "daily": 1,
    "weekly": 7,
    "monthly": 30,
    "quarterly": 90,
    "half_yearly": 182,
    "annual": 365,
}
# one_time and as_needed never reset
RECURRING = set(FREQ_DAYS.keys())


async def run():
    db = get_db()
    now = datetime.utcnow()
    created = 0
    skipped = 0

    cursor = db.obligation_instances.find({
        "frequency": {"$in": list(RECURRING)},
        "status": {"$in": ["filed", "overdue"]},
    })

    async for inst in cursor:
        due_raw = inst.get("due_date")
        if not due_raw:
            continue
        due_dt = due_raw if isinstance(due_raw, datetime) else datetime.fromisoformat(str(due_raw))

        if due_dt > now:
            continue  # not yet due for reset

        freq = inst.get("frequency", "monthly")
        period_days = FREQ_DAYS[freq]
        next_due = due_dt + timedelta(days=period_days)

        # Idempotency check: skip if a pending instance exists within ±3 days
        # of the specific next period (not just any future pending instance)
        existing = await db.obligation_instances.find_one({
            "business_id": inst["business_id"],
            "regulation_id": inst["regulation_id"],
            "status": "pending",
            "due_date": {
                "$gte": next_due - timedelta(days=3),
                "$lte": next_due + timedelta(days=3),
            },
        })
        if existing:
            skipped += 1
            continue

        # Personalised complexity: each late filing adds 0.5 to complexity weight
        times_late = await db.filing_history.count_documents({
            "business_id": inst["business_id"],
            "regulation_id": inst["regulation_id"],
            "on_time": False,
        })
        adjusted_complexity = inst.get("complexity", 2) + (times_late * 0.5)

        new_inst = {
            "business_id": inst["business_id"],
            "regulation_id": inst["regulation_id"],
            "name": inst["name"],
            "category": inst["category"],
            "frequency": freq,
            "deadline_rule": inst.get("deadline_rule", ""),
            "penalty_type": inst.get("penalty_type", "financial"),
            "max_penalty_inr": inst.get("max_penalty_inr", 10000),
            "complexity": adjusted_complexity,
            "depends_on": inst.get("depends_on", []),
            "imprisonment_risk": inst.get("imprisonment_risk", False),
            "status": "pending",
            "decay_score": None,
            "due_date": next_due,
            "created_at": now,
            "reset_from": str(inst["_id"]),
        }
        await db.obligation_instances.insert_one(new_inst)
        created += 1
        print(f"  Reset: {inst['name'][:60]} -> next due {next_due.date()} complexity={adjusted_complexity}")

    # Escalate overdue obligations: mark status=overdue and compute live penalty
    escalated = 0
    async for inst in db.obligation_instances.find({
        "status": "pending",
        "due_date": {"$lt": now},
    }):
        due_dt = inst["due_date"] if isinstance(inst["due_date"], datetime) else datetime.fromisoformat(str(inst["due_date"]))
        days_late = max(int((now - due_dt).total_seconds() / 86400), 1)
        max_pen = inst.get("max_penalty_inr", 10000)
        per_day = max_pen / 100
        projected = min(round(days_late * per_day, 2), max_pen)
        await db.obligation_instances.update_one(
            {"_id": inst["_id"]},
            {"$set": {
                "status": "overdue",
                "days_late": days_late,
                "projected_penalty_inr": projected,
            }},
        )
        escalated += 1

    print(f"\nDone. Created: {created}  Skipped (already pending): {skipped}  Escalated overdue: {escalated}")


asyncio.run(run())
