import asyncio
from typing import Any, Dict, List

from motor.motor_asyncio import AsyncIOMotorDatabase


async def detect_ripple(
    db: AsyncIOMotorDatabase,
    business_id: str,
    affected_categories: List[str],
    affected_registrations: List[str],
    change_description: str = "",
) -> Dict[str, Any]:
    """
    Regulatory Ripple Detection — Patent Claim 2.
    Uses Atlas Vector Search for semantic similarity when change_description
    is provided; falls back to category matching otherwise.
    """
    direct_matches: List[Dict] = []
    indirect_matches: List[Dict] = []
    detection_method = "category_match"

    if change_description:
        try:
            from model_client import get_embedding
            embedding = await asyncio.to_thread(get_embedding, change_description)
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "regulation_embedding_index",
                        "path": "embedding",
                        "queryVector": embedding,
                        "numCandidates": 60,
                        "limit": 25,
                    }
                },
                {
                    "$project": {
                        "_id": 1,
                        "name": 1,
                        "category": 1,
                        "score": {"$meta": "vectorSearchScore"},
                    }
                },
            ]
            async for reg in db.regulatory_corpus.aggregate(pipeline):
                score = reg.get("score", 0)
                entry = {
                    "_id": str(reg["_id"]),
                    "name": reg.get("name", ""),
                    "category": reg.get("category", ""),
                    "similarity_score": round(score, 3),
                }
                if score >= 0.80:
                    direct_matches.append(entry)
                elif score >= 0.60:
                    indirect_matches.append(entry)
            detection_method = "vector_search"
        except Exception:
            # Atlas Vector Search index not yet configured — fall back gracefully
            direct_matches = await _category_fallback(db, business_id, affected_categories)

    else:
        direct_matches = await _category_fallback(db, business_id, affected_categories)

    # TODO: PATENT-PENDING — full dependency graph traversal logic omitted

    return {
        "directly_impacted": direct_matches,
        "indirectly_impacted": indirect_matches,
        "total_impacted": len(direct_matches) + len(indirect_matches),
        "detection_method": detection_method,
        "severity": _compute_severity(direct_matches, indirect_matches),
    }


async def _category_fallback(
    db: AsyncIOMotorDatabase,
    business_id: str,
    affected_categories: List[str],
) -> List[Dict]:
    matches: List[Dict] = []
    async for inst in db.obligation_instances.find({"business_id": business_id}):
        if inst.get("category") in affected_categories:
            matches.append({
                "_id": str(inst["_id"]),
                "name": inst.get("name", ""),
                "category": inst.get("category", ""),
            })
    return matches


def _compute_severity(direct: List, indirect: List) -> str:
    total = len(direct) + len(indirect)
    if total >= 10 or len(direct) >= 5:
        return "high"
    if total >= 4 or len(direct) >= 2:
        return "medium"
    return "low"
