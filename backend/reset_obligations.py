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

        # Idempotency check: skip if a pending instance already exists
        existing = await db.obligation_instances.find_one({
            "business_id": inst["business_id"],
            "regulation_id": inst["regulation_id"],
            "status": "pending",
            "due_date": {"$gte": now},
        })
        if existing:
            skipped += 1
            continue

        new_inst = {
            "business_id": inst["business_id"],
            "regulation_id": inst["regulation_id"],
            "name": inst["name"],
            "category": inst["category"],
            "frequency": freq,
            "deadline_rule": inst.get("deadline_rule", ""),
            "penalty_type": inst.get("penalty_type", "financial"),
            "max_penalty_inr": inst.get("max_penalty_inr", 10000),
            "complexity": inst.get("complexity", 2),
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
        print(f"  Reset: {inst['name'][:60]} -> next due {next_due.date()}")

    print(f"\nDone. Created: {created}  Skipped (already pending): {skipped}")


asyncio.run(run())
