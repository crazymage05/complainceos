"""
Backfill 30 days of realistic decay score history for a demo business.
Run: python backfill_decay_history.py --business-id <id>

Without this the 30-day trend sparklines on the dashboard are flat (all data
from the same day). This script generates synthetic history that shows
obligations gradually becoming more urgent as their deadlines approach.
"""
import argparse, asyncio, os, sys, random
from datetime import datetime, timedelta
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ".")
from dotenv import load_dotenv; load_dotenv()
from db.mongodb import get_db
from engines.decay_score import compute_decay_score

FREQ_DAYS = {"daily": 1, "weekly": 7, "monthly": 30, "quarterly": 90,
             "half_yearly": 182, "annual": 365, "one_time": 365, "as_needed": 365}


async def run(business_id: str, days_back: int = 30):
    db = get_db()
    now = datetime.utcnow()

    # Fetch all obligation instances for this business
    instances = []
    async for inst in db.obligation_instances.find({"business_id": business_id}):
        instances.append(inst)

    if not instances:
        print(f"No obligations found for business {business_id}")
        return

    print(f"Backfilling {days_back} days of history for {len(instances)} obligations...")

    inserted = 0
    for inst in instances:
        iid = str(inst["_id"])
        freq = inst.get("frequency", "monthly")
        total_days = FREQ_DAYS.get(freq, 30)
        complexity = float(inst.get("complexity", 2))
        max_penalty = inst.get("max_penalty_inr", 10000)
        penalty_sev = max(max_penalty / 100000, 1.0)

        due_raw = inst.get("due_date")
        if not due_raw:
            due_dt = now + timedelta(days=total_days // 2)
        else:
            due_dt = due_raw if isinstance(due_raw, datetime) else datetime.fromisoformat(str(due_raw))

        # Generate one snapshot per day for the past N days
        snapshots = []
        for d in range(days_back, 0, -1):
            ts = now - timedelta(days=d)
            days_remaining_at_ts = (due_dt - ts).total_seconds() / 86400.0

            score = compute_decay_score(
                days_remaining=days_remaining_at_ts,
                total_days_allowed=float(total_days),
                complexity_weight=complexity,
                penalty_severity_multiplier=penalty_sev,
                historical_on_time_rate=0.85,
            )
            # Add slight noise so sparklines look realistic
            noise = random.uniform(-1.5, 1.5)
            score = round(max(0.0, min(100.0, score + noise)), 2)

            snapshots.append({
                "instance_id": iid,
                "business_id": business_id,
                "decay_score": score,
                "urgency": "red" if score < 20 else ("amber" if score < 40 else "green"),
                "timestamp": ts,
            })

        if snapshots:
            await db.decay_score_snapshots.insert_many(snapshots)
            inserted += len(snapshots)

    print(f"Inserted {inserted} historical snapshots ({days_back} days x {len(instances)} obligations)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--business-id", required=True)
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    asyncio.run(run(args.business_id, args.days))
