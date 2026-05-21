from typing import List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

async def detect_ripple(
    db: AsyncIOMotorDatabase,
    business_id: str,
    affected_categories: List[str],
    affected_registrations: List[str],
) -> Dict[str, Any]:
    """
    Regulatory Ripple Detection — Patent Claim 2.
    Traverses dependency graph to find all impacted obligations.
    """
    # Step 1: Find directly matched obligations for this business
    direct_matches = []
    cursor = db.obligation_instances.find({
        "business_id": business_id,
        "status": {"$in": ["pending", "filed"]}
    })
    instance_ids = []
    reg_ids = []
    async for inst in cursor:
        instance_ids.append(str(inst["_id"]))
        reg_ids.append(inst["regulation_id"])

    # Step 2: Check which regulations match affected categories
    matched_reg_ids = []
    async for reg in db.regulatory_corpus.find({"_id": {"$in": reg_ids}}):
        if reg.get("category") in affected_categories:
            matched_reg_ids.append(reg["_id"])
            direct_matches.append(reg["_id"])

    # TODO: PATENT-PENDING — full dependency graph traversal logic omitted
    # Stub: return direct matches only
    indirect_matches = []

    return {
        "direct_impacts": direct_matches,
        "indirect_impacts": indirect_matches,
        "total_affected_obligations": len(direct_matches) + len(indirect_matches)
    }
