from typing import List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

async def build_compliance_dna(
    db: AsyncIOMotorDatabase,
    business_id: str,
    entity_attributes: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compliance DNA Builder — Patent Claim 3.
    Generates unique obligation set for this business entity.
    """
    state = entity_attributes.get("state", "")
    industry = entity_attributes.get("industry", "")
    employee_count = entity_attributes.get("employee_count", 0)
    turnover = entity_attributes.get("annual_turnover_inr", 0)
    registrations = entity_attributes.get("registrations", [])

    # TODO: PATENT-PENDING — matching algorithm internals omitted
    # Match obligations from regulatory_corpus based on entity attributes
    query = {
        "$or": [
            {"applicable_to.industries": "all"},
            {"applicable_to.industries": industry},
        ],
        "applicable_to.min_employees": {"$lte": employee_count},
        "applicable_to.min_turnover_inr": {"$lte": turnover},
    }

    obligations = []
    high_severity = 0
    async for reg in db.regulatory_corpus.find(query):
        req_regs = reg.get("applicable_to", {}).get("registrations_required", [])
        if req_regs and not any(r in registrations for r in req_regs):
            continue
        obligations.append({
            "obligation_id": str(reg["_id"]),
            "name": reg["name"],
            "category": reg["category"],
            "frequency": reg["frequency"],
            "deadline_rule": reg["deadline_rule"],
            "penalty_type": reg.get("penalty_type", "financial"),
            "max_penalty_inr": reg.get("max_penalty_inr", 0),
            "complexity": reg.get("complexity", 1),
            "depends_on": reg.get("depends_on", []),
            "imprisonment_risk": reg.get("imprisonment_risk", False),
        })
        if reg.get("imprisonment_risk") or reg.get("complexity", 1) >= 4:
            high_severity += 1

    return {
        "business_id": business_id,
        "entity_attributes": entity_attributes,
        "applicable_obligations": obligations,
        "total_obligations": len(obligations),
        "high_severity_count": high_severity,
    }
