import sys, os, asyncio, json
os.chdir(r'E:\google\complianceos\backend')
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
from db.mongodb import get_db

async def run():
    db = get_db()

    print("=== 1. Sample obligation_instance (full doc) ===")
    doc = await db.obligation_instances.find_one({})
    if doc:
        doc["_id"] = str(doc["_id"])
        if "due_date" in doc and hasattr(doc["due_date"], "isoformat"):
            doc["due_date"] = doc["due_date"].isoformat()
        if "created_at" in doc and hasattr(doc["created_at"], "isoformat"):
            doc["created_at"] = doc["created_at"].isoformat()
        print(json.dumps(doc, indent=2, default=str))

    print()
    print("=== 2. Distinct frequency values ===")
    freqs = await db.obligation_instances.distinct("frequency")
    print(freqs)

    print()
    print("=== 3. Sample regulatory_corpus doc (no embedding) ===")
    corpus_doc = await db.regulatory_corpus.find_one({})
    if corpus_doc:
        corpus_doc.pop("embedding", None)
        corpus_doc["_id"] = str(corpus_doc["_id"])
        print(json.dumps(corpus_doc, indent=2, default=str))

    print()
    print("=== 4. Sample decay_score_snapshot + count ===")
    snap = await db.decay_score_snapshots.find_one({})
    if snap:
        snap["_id"] = str(snap["_id"])
        if "timestamp" in snap and hasattr(snap["timestamp"], "isoformat"):
            snap["timestamp"] = snap["timestamp"].isoformat()
        print(json.dumps(snap, indent=2, default=str))
    count = await db.decay_score_snapshots.count_documents({})
    print(f"Total snapshots: {count}")

asyncio.run(run())
