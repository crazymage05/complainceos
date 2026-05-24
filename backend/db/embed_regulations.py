"""
ComplianceOS — Regulation Embedding Script
Generates Gemini text-embedding-004 vectors for all regulatory_corpus documents.
Run ONCE after seeding: python db/embed_regulations.py

After this script completes, create the Atlas Vector Search index:
  1. Atlas UI → Search → Create Search Index
  2. Select collection: complianceos.regulatory_corpus
  3. Choose "JSON Editor" and paste contents of db/atlas_vector_index.json
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

from motor.motor_asyncio import AsyncIOMotorClient
from google import genai


MONGO_URI = os.getenv("MONGODB_URI", "")
DB_NAME = os.getenv("MONGODB_DB_NAME", "complianceos")
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")


def embed_text(client: genai.Client, text: str) -> list:
    response = client.models.embed_content(
        model="models/gemini-embedding-001",
        contents=text,
    )
    return list(response.embeddings[0].values)


async def main():
    if not GEMINI_KEY:
        print("ERROR: GEMINI_API_KEY not set in .env")
        return

    gem = genai.Client(api_key=GEMINI_KEY)
    mongo = AsyncIOMotorClient(MONGO_URI)
    db = mongo[DB_NAME]

    count = await db.regulatory_corpus.count_documents({})
    print(f"Found {count} regulations to embed...")

    done = 0
    skipped = 0
    async for reg in db.regulatory_corpus.find({}):
        if reg.get("embedding"):
            skipped += 1
            continue

        text = " ".join(filter(None, [
            reg.get("name", ""),
            reg.get("category", ""),
            reg.get("deadline_rule", ""),
            reg.get("source", ""),
            reg.get("jurisdiction", ""),
        ]))

        try:
            embedding = embed_text(gem, text)
            await db.regulatory_corpus.update_one(
                {"_id": reg["_id"]},
                {"$set": {"embedding": embedding}},
            )
            done += 1
            print(f"  [{done}] {reg.get('name', '')[:70]}")
            # Respect free-tier rate limit (1500 RPM for embedding)
            time.sleep(0.05)
        except Exception as e:
            print(f"  FAILED {reg['_id']}: {e}")

    mongo.close()
    print(f"\n✅ Done. {done} embedded, {skipped} already had embeddings.")
    print("\nNext step — create Atlas Vector Search index:")
    print("  1. Atlas UI → Search → Create Search Index")
    print("  2. Collection: regulatory_corpus")
    print("  3. JSON Editor → paste contents of db/atlas_vector_index.json")
    print("  4. Name the index: regulation_embedding_index")


if __name__ == "__main__":
    asyncio.run(main())
