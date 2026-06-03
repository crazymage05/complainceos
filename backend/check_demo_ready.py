import asyncio, os, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ".")
from dotenv import load_dotenv; load_dotenv()
from db.mongodb import get_db
from bson import ObjectId

DEMO_BIZ = "6a0ef267640ccd6825a8511a"

async def run():
    db = get_db()

    # Check decay score spread
    red = await db.obligation_instances.count_documents(
        {"business_id": DEMO_BIZ, "decay_score": {"$lt": 30}})
    amber = await db.obligation_instances.count_documents(
        {"business_id": DEMO_BIZ, "decay_score": {"$gte": 30, "$lt": 60}})
    green = await db.obligation_instances.count_documents(
        {"business_id": DEMO_BIZ, "decay_score": {"$gte": 60}})
    null_score = await db.obligation_instances.count_documents(
        {"business_id": DEMO_BIZ, "decay_score": None})

    print(f"Decay spread -- Red: {red}  Amber: {amber}  Green: {green}  Null: {null_score}")

    # Check discoveries
    disc = await db.chat_discoveries.count_documents({"business_id": DEMO_BIZ})
    print(f"Chat discoveries: {disc}")

    # Check decay history
    snaps = await db.decay_score_snapshots.count_documents({"business_id": DEMO_BIZ})
    print(f"Decay snapshots: {snaps}")

    # Check ripple alerts
    ripples = await db.regulatory_changes.count_documents({"business_id": DEMO_BIZ})
    print(f"Ripple alerts: {ripples}")

    # Check AI-sourced obligations
    ai_obs = await db.obligation_instances.count_documents(
        {"business_id": DEMO_BIZ, "source": "ai_advisor"})
    print(f"AI-sourced obligations: {ai_obs}")

    # Overall verdict
    issues = []
    if red < 2: issues.append("Need at least 2 red obligations for demo impact")
    if disc < 5: issues.append("Need 5+ chat discoveries pre-seeded")
    if snaps < 100: issues.append("Need 100+ decay snapshots for trend chart")
    if ripples < 1: issues.append("Need at least 1 ripple alert -- run ingest_circular.py")

    if issues:
        print("\nNOT DEMO READY:")
        for i in issues: print(f"  - {i}")
    else:
        print("\nDEMO READY")

asyncio.run(run())
