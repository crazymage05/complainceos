"""
Atlas Search endpoint — full-text lexical search over the regulatory corpus.

Complements Atlas Vector Search (used in ripple detection) with Lucene-backed
keyword search for direct user queries like "GSTR-9" or "FSSAI annual return".

Falls back to a $regex query if the Atlas Search index isn't available, so
the endpoint stays functional on any Atlas tier.
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from auth import current_user
from common import serialize
from db.mongodb import get_db
from logging_config import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

ATLAS_SEARCH_INDEX_NAME = "regulation_text_search"


@router.get("/regulations")
async def search_regulations(
    q: str = Query(..., min_length=2, description="Search query"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(15, ge=1, le=50),
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: Dict = Depends(current_user),
):
    """
    Search regulations by name, deadline rule, or source text.

    Tries Atlas Search ($search) first for relevance-scored results; falls
    back to a $regex query if the index isn't configured (so this works on
    any Atlas tier).
    """
    # ── Try Atlas Search first ────────────────────────────────────────────────
    search_filter = []
    if category:
        search_filter.append({"equals": {"path": "category", "value": category}})

    atlas_pipeline = [
        {
            "$search": {
                "index": ATLAS_SEARCH_INDEX_NAME,
                "compound": {
                    "should": [
                        {"text": {"query": q, "path": "name", "score": {"boost": {"value": 3}}}},
                        {"text": {"query": q, "path": "deadline_rule"}},
                        {"text": {"query": q, "path": "source"}},
                        # Wildcard recall: the standard analyzer tokenises on word
                        # boundaries, so a query like "GST" would miss "GSTR-3B".
                        # A substring wildcard on the name keeps the search box
                        # forgiving for partial / prefix queries.
                        {"wildcard": {"query": f"*{q}*", "path": "name",
                                       "allowAnalyzedField": True}},
                    ],
                    "filter": search_filter,
                },
            }
        },
        {"$limit": limit},
        {
            "$project": {
                "_id": 1, "name": 1, "category": 1, "frequency": 1,
                "deadline_rule": 1, "max_penalty_inr": 1, "source": 1,
                "state_specific": 1,
                "score": {"$meta": "searchScore"},
            }
        },
    ]

    results: List[Dict] = []
    method = "atlas_search"
    try:
        async for doc in db.regulatory_corpus.aggregate(atlas_pipeline):
            results.append(serialize(doc))
    except Exception as exc:
        log.warning("Atlas Search unavailable (%s) — falling back to $regex", str(exc)[:100])
        method = "regex_fallback"
        results = []

    # ── Fallback to regex if Atlas Search returned nothing ───────────────────
    if not results:
        method = "regex_fallback"
        import re as _re
        safe = _re.escape(q)
        regex_filter: Dict = {
            "$or": [
                {"name": {"$regex": safe, "$options": "i"}},
                {"deadline_rule": {"$regex": safe, "$options": "i"}},
                {"source": {"$regex": safe, "$options": "i"}},
            ],
        }
        if category:
            regex_filter["category"] = category
        async for doc in db.regulatory_corpus.find(regex_filter).limit(limit):
            doc["score"] = None
            results.append(serialize(doc))

    return {
        "query": q,
        "category": category,
        "count": len(results),
        "method": method,
        "results": results,
    }


@router.get("/regulations/by-category")
async def regulations_by_category(
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: Dict = Depends(current_user),
):
    """
    Aggregation: count regulations per category. Useful for UI filter chips.
    """
    pipeline = [
        {"$group": {
            "_id": "$category",
            "count": {"$sum": 1},
            "high_severity": {
                "$sum": {"$cond": [{"$gte": ["$complexity", 4]}, 1, 0]}
            },
        }},
        {"$sort": {"count": -1}},
    ]
    out = []
    async for doc in db.regulatory_corpus.aggregate(pipeline):
        out.append({
            "category": doc["_id"],
            "count": doc["count"],
            "high_severity": doc["high_severity"],
        })
    return {"categories": out, "total_regulations": sum(c["count"] for c in out)}
