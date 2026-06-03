import sys, os, asyncio
os.chdir(r'E:\google\complianceos\backend')
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()

DEMO_BIZ = "6a0ef267640ccd6825a8511a"

async def run():
    from db.mongodb import get_db
    db = get_db()

    print("=== Ripple detection (vector search) ===")
    from engines.ripple_detector import detect_ripple
    result = await detect_ripple(
        db=db,
        business_id=DEMO_BIZ,
        affected_categories=["labour"],
        affected_registrations=[],
        change_description="EPF wage ceiling enhanced from 15000 to 21000 rupees per month",
    )
    method = result.get("detection_method", "?")
    direct = result.get("directly_impacted", [])
    indirect = result.get("indirectly_impacted", [])
    print(f"Method: {method}")
    print(f"Direct ({len(direct)}): {[x['name'][:50] for x in direct]}")
    print(f"Indirect ({len(indirect)}): {[x['name'][:50] for x in indirect]}")
    print(f"Severity: {result.get('severity')}")

asyncio.run(run())
