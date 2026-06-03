import asyncio
from typing import Any, Dict, List

from motor.motor_asyncio import AsyncIOMotorDatabase

from logging_config import get_logger

log = get_logger(__name__)


# Hybrid retrieval — Vector Search + Atlas Search fused via RRF.
async def detect_ripple_hybrid(
    db: AsyncIOMotorDatabase,
    business_id: str,
    affected_categories: List[str],
    affected_registrations: List[str],
    change_description: str,
) -> Dict[str, Any]:
    """
    Hybrid ripple detection: combine $vectorSearch (semantic similarity)
    with $search (lexical relevance) via Reciprocal Rank Fusion. Only
    counts a regulation as "directly_impacted" if BOTH rankers found it,
    so the user sees fewer false positives than pure vector search.
    """
    from engines.hybrid_search import hybrid_search
    from model_client import get_embedding

    embedding: List[float] | None = None
    if change_description:
        try:
            embedding = await asyncio.to_thread(get_embedding, change_description)
        except Exception as exc:
            log.warning("embedding generation failed; falling back: %s", exc)
            embedding = None

    if embedding is None and not change_description:
        # No way to run hybrid — fall back to old category-only logic
        return await detect_ripple(
            db, business_id, affected_categories, affected_registrations, "",
        )

    result = await hybrid_search(db, change_description, embedding, limit=25)
    fused = result.get("fused", [])
    method = result.get("method", "hybrid_rrf")

    # The "found by BOTH rankers → direct" rule only makes sense when two
    # rankers actually ran. If the text index is missing (or text returned
    # nothing) hybrid_search degrades to a single ranker — and then nothing
    # could ever satisfy len(sources) >= 2, so EVERY hit would be mislabelled
    # "indirect" (direct=0). Defer to the proven vector-threshold classifier
    # in that case so the user still gets a meaningful direct/indirect split.
    if method != "hybrid_rrf":
        log.info("hybrid degraded to %s — using vector-threshold classifier", method)
        return await detect_ripple(
            db, business_id, affected_categories, affected_registrations,
            change_description,
        )

    direct: List[Dict] = []
    indirect: List[Dict] = []
    for hit in fused:
        sources = hit.get("sources", [])
        entry = {
            "_id": hit["_id"],
            "name": hit.get("name", ""),
            "category": hit.get("category", ""),
            "rrf_score": hit.get("rrf_score"),
            "found_by": sources,
        }
        # Both rankers found it → confident match
        if len(sources) >= 2:
            direct.append(entry)
        else:
            indirect.append(entry)

    return {
        "directly_impacted": direct,
        "indirectly_impacted": indirect,
        "total_impacted": len(direct) + len(indirect),
        "detection_method": result.get("method", "hybrid_rrf"),
        "severity": _compute_severity(direct, indirect),
        "rrf_k": result.get("rrf_k"),
    }


# Atlas Vector Search similarity thresholds (cosine, 0..1).
# Gemini's embedding-001 produces a tight similarity distribution: even
# unrelated regulations land in the 0.74-0.77 range. Probed scores for
# a real GST query showed ALL top-25 results between 0.766 and 0.816.
# Old thresholds (0.75/0.50) labelled all 25 as "direct" — useless signal.
# Re-tuned to discriminate inside the actual distribution.
DIRECT_MATCH_THRESHOLD = 0.79
INDIRECT_MATCH_THRESHOLD = 0.76

# Severity classification thresholds
HIGH_TOTAL = 10
HIGH_DIRECT = 5
MEDIUM_TOTAL = 4
MEDIUM_DIRECT = 2

VECTOR_INDEX_NAME = "regulation_embedding_index"
VECTOR_NUM_CANDIDATES = 60
# Pull top-20 candidates and let thresholds filter; the cap mostly bounds work,
# the thresholds decide relevance.
VECTOR_LIMIT = 20


async def detect_ripple(
    db: AsyncIOMotorDatabase,
    business_id: str,
    affected_categories: List[str],
    affected_registrations: List[str],
    change_description: str = "",
) -> Dict[str, Any]:
    """
    Vector-search-based regulatory ripple. Falls back to category match if
    the Atlas index is unreachable or returns no results.
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
                        "index": VECTOR_INDEX_NAME,
                        "path": "embedding",
                        "queryVector": embedding,
                        "numCandidates": VECTOR_NUM_CANDIDATES,
                        "limit": VECTOR_LIMIT,
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
                if score >= DIRECT_MATCH_THRESHOLD:
                    direct_matches.append(entry)
                elif score >= INDIRECT_MATCH_THRESHOLD:
                    indirect_matches.append(entry)
            detection_method = "vector_search"
            log.info(
                "vector_search direct=%d indirect=%d",
                len(direct_matches), len(indirect_matches),
            )
        except Exception as exc:
            log.warning("vector search failed, falling back to category match: %s", exc)
            direct_matches = await _category_fallback(db, business_id, affected_categories)
            indirect_matches = []
    else:
        direct_matches = await _category_fallback(db, business_id, affected_categories)

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
    if total >= HIGH_TOTAL or len(direct) >= HIGH_DIRECT:
        return "high"
    if total >= MEDIUM_TOTAL or len(direct) >= MEDIUM_DIRECT:
        return "medium"
    return "low"
