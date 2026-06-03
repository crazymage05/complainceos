"""Print raw vector-search scores for a ripple query — diagnose threshold tuning."""

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from db.mongodb import get_db
from model_client import get_embedding


async def main():
    db = get_db()
    query = "GST rate revised for retail and food services under QRMP scheme"
    embedding = await asyncio.to_thread(get_embedding, query)
    pipeline = [
        {"$vectorSearch": {
            "index": "regulation_embedding_index",
            "path": "embedding",
            "queryVector": embedding,
            "numCandidates": 60,
            "limit": 25,
        }},
        {"$project": {
            "_id": 1, "name": 1, "category": 1,
            "score": {"$meta": "vectorSearchScore"},
        }},
    ]
    print(f"Query: {query!r}")
    print("=" * 60)
    async for reg in db.regulatory_corpus.aggregate(pipeline):
        score = reg.get("score", 0)
        bucket = "DIRECT" if score >= 0.75 else "INDIRECT" if score >= 0.50 else "below"
        print(f"  {score:.4f}  [{bucket:>8}]  {reg.get('category', '?'):<20} {reg.get('name', '?')[:55]}")


asyncio.run(main())
