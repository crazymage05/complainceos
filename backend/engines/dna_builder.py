from typing import List, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase

# Obligations that only become relevant after the business has been operating
# for a minimum number of months
_MATURITY_GATES: Dict[str, int] = {
    "one_time":    0,   # always applicable (registration-type obligations)
    "monthly":     1,   # applicable from month 1
    "weekly":      1,
    "daily":       1,
    "quarterly":   3,   # first quarter must pass
    "half_yearly": 6,
    "annual":      12,  # first full year must pass
}

def _business_age_months(incorporation_date_str: str | None) -> int:
    """Return how many full months old the business is. None = assume established (24 months)."""
    if not incorporation_date_str:
        return 24
    try:
        inc = datetime.fromisoformat(str(incorporation_date_str))
        now = datetime.utcnow()
        return max(0, (now.year - inc.year) * 12 + (now.month - inc.month))
    except Exception:
        return 24


async def build_compliance_dna(
    db: AsyncIOMotorDatabase,
    business_id: str,
    entity_attributes: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compliance DNA Builder — Patent Claim 3.
    Generates unique obligation set for this business entity.
    Age-aware: new businesses only receive obligations they are currently eligible for.
    """
    state = entity_attributes.get("state", "")
    industry = entity_attributes.get("industry", "")
    employee_count = entity_attributes.get("employee_count", 0)
    turnover = entity_attributes.get("annual_turnover_inr", 0)
    registrations = entity_attributes.get("registrations", [])
    incorporation_date = entity_attributes.get("incorporation_date", None)

    age_months = _business_age_months(incorporation_date)

    # TODO: PATENT-PENDING — matching algorithm internals omitted
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

        # Age gate — skip obligations the business isn't old enough for yet
        freq = reg.get("frequency", "monthly")
        min_months = _MATURITY_GATES.get(freq, 1)
        if age_months < min_months:
            continue

        obligations.append({
            "obligation_id": str(reg["_id"]),
            "name": reg["name"],
            "category": reg["category"],
            "frequency": freq,
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
        "business_age_months": age_months,
    }
