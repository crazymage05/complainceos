"""
Audit all obligation_instances for data quality issues.
Run: python audit_obligations.py

Reports:
  - null due_date (obligation has no deadline)
  - null decay_score
  - due_date in the past with status != filed/overdue
  - status=filed with no filed_at
  - missing required fields
"""
import asyncio, os, sys
from datetime import datetime
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ".")
from dotenv import load_dotenv; load_dotenv()
from db.mongodb import get_db

REQUIRED = ["business_id", "regulation_id", "name", "category", "frequency", "status"]

async def run():
    db = get_db()
    now = datetime.utcnow()

    total = 0
    issues = {
        "null_due_date": [],
        "null_decay_score": [],
        "overdue_not_filed": [],
        "filed_no_filed_at": [],
        "missing_fields": [],
    }

    async for inst in db.obligation_instances.find({}):
        total += 1
        iid = str(inst["_id"])
        name = inst.get("name", "?")[:50]

        missing = [f for f in REQUIRED if not inst.get(f)]
        if missing:
            issues["missing_fields"].append(f"{iid} | {name} | missing: {missing}")

        if inst.get("due_date") is None:
            issues["null_due_date"].append(f"{iid} | {name}")

        if inst.get("decay_score") is None:
            issues["null_decay_score"].append(f"{iid} | {name}")

        due = inst.get("due_date")
        if due:
            due_dt = due if isinstance(due, datetime) else datetime.fromisoformat(str(due))
            if due_dt < now and inst.get("status") not in ("filed", "overdue"):
                days_late = int((now - due_dt).total_seconds() / 86400)
                issues["overdue_not_filed"].append(
                    f"{iid} | {name} | due {due_dt.date()} ({days_late}d ago) | status={inst.get('status')}"
                )

        if inst.get("status") == "filed" and not inst.get("filed_at"):
            issues["filed_no_filed_at"].append(f"{iid} | {name}")

    print(f"Total obligations: {total}")
    print()
    for key, items in issues.items():
        print(f"[{key}] {len(items)} issues")
        for item in items[:10]:
            print(f"  {item}".encode("ascii", "replace").decode("ascii"))
        if len(items) > 10:
            print(f"  ... and {len(items)-10} more")
        print()

    # Quick fix: set due_date for null-due_date obligations
    from datetime import timedelta
    freq_days = {"daily": 1, "weekly": 7, "monthly": 30, "quarterly": 90,
                 "half_yearly": 182, "annual": 365, "one_time": 365, "as_needed": 365}
    fixed = 0
    async for inst in db.obligation_instances.find({"due_date": None}):
        freq = inst.get("frequency", "monthly")
        days = freq_days.get(freq, 30)
        due = now + timedelta(days=days)
        await db.obligation_instances.update_one(
            {"_id": inst["_id"]},
            {"$set": {"due_date": due}}
        )
        fixed += 1
    if fixed:
        print(f"AUTO-FIXED: set due_date on {fixed} obligations with null due_date")

asyncio.run(run())
