"""
Live regulatory circular ingestion.
Embeds a new circular, upserts it into regulatory_corpus, then
triggers ripple detection across ALL active businesses.

Usage:
  python ingest_circular.py --source "CBIC Circular 207/2024" --file circular.txt
  python ingest_circular.py --source "EPFO Circular" --text "Enhanced wage ceiling..."

This is the script that makes ComplianceOS live — run it whenever a new
government circular is published.
"""
import argparse, asyncio, json, os, sys
from datetime import datetime
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ".")
from dotenv import load_dotenv; load_dotenv()
from db.mongodb import get_db
from model_client import get_embedding, get_completion

CATEGORY_KEYWORDS = {
    "taxation": ["gst", "cbic", "tds", "income tax", "itc", "gstr", "cgst", "igst"],
    "labour": ["epf", "esic", "epfo", "pf", "esi", "wage", "labour", "employee"],
    "food_safety": ["fssai", "food safety", "food business", "foscos"],
    "companies_act": ["mca", "companies act", "roc", "ministry of corporate"],
    "income_tax": ["income tax", "cbdt", "itr", "advance tax"],
}


def _infer_category(text: str) -> str:
    lower = text.lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(k in lower for k in keywords):
            return cat
    return "other"


def _make_reg_id(source: str) -> str:
    """Stable ID from source string for upsert idempotency."""
    import re, hashlib
    slug = re.sub(r"[^a-z0-9]", "_", source.lower())[:40]
    suffix = hashlib.md5(source.encode()).hexdigest()[:6]
    return f"ingested_{slug}_{suffix}"


async def run(source: str, text: str):
    db = get_db()

    print(f"Source: {source}")
    print(f"Text length: {len(text)} chars")

    category = _infer_category(text + " " + source)
    print(f"Inferred category: {category}")

    # Ask Gemini to extract structured metadata
    prompt = (
        "You are an Indian regulatory compliance expert. Extract structured metadata from this circular.\n"
        f"Source: {source}\nText (first 2000 chars): {text[:2000]}\n\n"
        "Respond ONLY with valid JSON:\n"
        '{"name":"short regulation name","deadline_rule":"filing deadline rule or empty","'
        'max_penalty_inr":0,"imprisonment_risk":false,"summary":"one sentence"}'
    )
    meta = {}
    try:
        raw = get_completion(prompt)
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        meta = json.loads(raw)
    except Exception as e:
        print(f"Gemini metadata extraction failed: {e} — using defaults")
        meta = {"name": source[:80], "deadline_rule": "", "max_penalty_inr": 10000, "imprisonment_risk": False}

    reg_id = _make_reg_id(source)

    # Generate embedding
    embed_text = f"{meta.get('name', source)} {category} {meta.get('deadline_rule', '')} {source}"
    print("Generating embedding...")
    embedding = get_embedding(embed_text)
    print(f"Embedding dim: {len(embedding)}")

    # Upsert into regulatory_corpus
    doc = {
        "_id": reg_id,
        "name": meta.get("name", source[:80]),
        "jurisdiction": "India",
        "state_specific": None,
        "category": category,
        "applicable_to": {"industries": ["all"], "min_turnover_inr": 0, "registrations_required": [], "min_employees": 0},
        "frequency": "one_time",
        "deadline_rule": meta.get("deadline_rule", ""),
        "complexity": 2,
        "penalty_type": "financial",
        "imprisonment_risk": meta.get("imprisonment_risk", False),
        "depends_on": [],
        "last_updated": datetime.utcnow().strftime("%Y-%m-%d"),
        "source": source,
        "max_penalty_inr": meta.get("max_penalty_inr", 10000),
        "embedding": embedding,
        "raw_text": text[:8000],
        "ingested_at": datetime.utcnow(),
    }

    existing = await db.regulatory_corpus.find_one({"_id": reg_id})
    if existing:
        await db.regulatory_corpus.replace_one({"_id": reg_id}, doc)
        print(f"Updated existing corpus doc: {reg_id}")
    else:
        await db.regulatory_corpus.insert_one(doc)
        print(f"Inserted new corpus doc: {reg_id}")

    # Trigger ripple detection across ALL active businesses
    print("\nRunning ripple detection across all businesses...")
    from engines.ripple_detector import detect_ripple

    businesses = []
    async for biz in db.businesses.find({}, {"_id": 1, "name": 1}):
        businesses.append(biz)

    ripple_summary = []
    for biz in businesses:
        bid = str(biz["_id"])
        result = await detect_ripple(
            db=db,
            business_id=bid,
            affected_categories=[category],
            affected_registrations=[],
            change_description=text[:500],
        )
        direct = len(result.get("directly_impacted", []))
        indirect = len(result.get("indirectly_impacted", []))
        if direct + indirect > 0:
            ripple_summary.append(f"  {biz.get('name', bid)}: {direct} direct, {indirect} indirect")
            # Upsert ripple result — prevents duplicate records on re-run
            await db.regulatory_changes.update_one(
                {"business_id": bid, "source": source},
                {"$set": {
                    "title": meta.get("name", source),
                    "source": source,
                    "category": category,
                    "affected_categories": [category],
                    "severity": result.get("severity", "medium"),
                    "directly_impacted": result.get("directly_impacted", []),
                    "indirectly_impacted": result.get("indirectly_impacted", []),
                    "detected_at": datetime.utcnow(),
                }},
                upsert=True,
            )

    if ripple_summary:
        print("Ripple impact:")
        for line in ripple_summary:
            print(line)
    else:
        print("No ripple impact detected across any business.")

    print(f"\nDone. Corpus: {reg_id}  Summary: {meta.get('summary', '')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="Circular source/title")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="Circular text directly")
    group.add_argument("--file", help="Path to text file containing circular")
    args = parser.parse_args()

    text = args.text if args.text else open(args.file, encoding="utf-8").read()
    asyncio.run(run(args.source, text))
