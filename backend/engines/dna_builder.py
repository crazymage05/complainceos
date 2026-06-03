import re
from datetime import datetime
from typing import Any, Dict

from motor.motor_asyncio import AsyncIOMotorDatabase

from logging_config import get_logger

log = get_logger(__name__)


# Entity-type filters. These are the well-known filings under the
# Companies Act 2013 and LLP Act 2008 that simply do not apply to other
# entity types. The seed corpus doesn't yet carry an entity_type field,
# so we match on the regulation name pattern. Patterns are case-insensitive.

# Filings only meaningful for Companies Act entities (Pvt Ltd, Public Ltd)
_COMPANIES_ACT_ONLY = re.compile(
    r"\b("
    r"AOC-\d+|MGT-\d+|DIR-\d+|ADT-\d+|SH-\d+|MOA|AOA|"
    r"INC-\d+|DPT-\d+|CHG-\d+|MR-\d+|CRA-\d+|PAS-\d+|BEN-\d+|"
    r"Form\s+(?:INC|MGT|DIR|AOC|ADT|SH|DPT|CHG|MR|CRA|PAS|BEN)|"
    r"Beneficial Owner|Significant Beneficial Owner|"
    r"DIN(?:\s|-)?KYC|Annual Return.*Compan|Board Meeting Disclosure|"
    r"Statutory Auditor Appointment|Authorized Share Capital|"
    r"Resolution Filing|Secretarial Audit Report"
    r")\b",
    re.IGNORECASE,
)

# Filings only meaningful for LLPs
_LLP_ONLY = re.compile(
    r"\b(LLP[- ]?Form|Form\s+8\s+LLP|Form\s+11\s+LLP|LLP Agreement|"
    r"Designated Partner)\b",
    re.IGNORECASE,
)

# Event-driven filings that are NOT periodic deadlines. The seed corpus
# marks them with a frequency value so they got picked up as recurring,
# which is wrong: a Refund Application isn't due every quarter — it's filed
# when you actually have a refund to claim. Surfacing these as urgent
# deadlines on day one is the single most confusing thing in the demo.
# Legacy category aliases — the seed corpus used "corporate" for Companies
# Act filings; downstream code (penalty defaults, advisor notes) expects
# "companies_act". Normalising here keeps the rest of the app consistent
# without re-seeding 90 regulations.
_CATEGORY_ALIASES = {
    "corporate": "companies_act",
}


def _normalise_category(raw: str) -> str:
    return _CATEGORY_ALIASES.get(raw, raw)


_CONDITIONAL_ONLY = re.compile(
    r"\b("
    r"Refund Application|RFD-\d+|"
    r"Authorized Share Capital|SH-7|"
    r"Registered Office (Change|Shift)|INC-22|"
    r"Director (Appointment|Resignation|Change)|DIR-12|"
    r"Charge (Creation|Modification|Satisfaction)|CHG-\d+|"
    r"Name Change|Object Clause Change|"
    r"Letter of Undertaking|LUT|"
    r"Import Export Code Renewal|"
    r"Trademark (Registration|Renewal)|"
    r"Patent (Application|Renewal)|"
    r"Product Recall|Recall Notice|"
    r"New Registration|Registration Amendment"
    r")\b",
    re.IGNORECASE,
)

_ENTITY_KEEPS = {
    "proprietorship": {"sole_prop_safe"},
    "partnership":    {"partnership_safe"},
    "pvt_ltd":        {"companies_act_ok"},
    "public_ltd":     {"companies_act_ok"},
    "llp":            {"llp_ok"},
}


def _passes_entity_filter(reg_name: str, business_type: str | None) -> bool:
    """Return False to drop this regulation for the given business type."""
    if not business_type:
        return True
    bt = business_type.lower()
    is_companies_only = bool(_COMPANIES_ACT_ONLY.search(reg_name))
    is_llp_only = bool(_LLP_ONLY.search(reg_name))
    if is_companies_only and bt not in ("pvt_ltd", "public_ltd"):
        return False
    if is_llp_only and bt != "llp":
        return False
    return True


# Maturity gates — obligations only apply once the business is old enough
# for the first cycle of that frequency to be due.
MATURITY_GATES: Dict[str, int] = {
    "one_time":    0,
    "monthly":     1,
    "weekly":      1,
    "daily":       1,
    "quarterly":   3,
    "half_yearly": 6,
    "annual":      12,
}

# When incorporation date is missing, assume the business has been operating
# long enough that every gate is satisfied.
DEFAULT_BUSINESS_AGE_MONTHS = 24

# A regulation is "high severity" if it carries imprisonment risk OR has
# complexity at or above this threshold.
HIGH_SEVERITY_COMPLEXITY = 4


def _business_age_months(incorporation_date_str: str | None) -> int:
    """Whole months between incorporation and now. Missing date → default."""
    if not incorporation_date_str:
        return DEFAULT_BUSINESS_AGE_MONTHS
    try:
        inc = datetime.fromisoformat(str(incorporation_date_str))
    except (TypeError, ValueError) as exc:
        log.warning("invalid incorporation_date %r: %s", incorporation_date_str, exc)
        return DEFAULT_BUSINESS_AGE_MONTHS
    now = datetime.utcnow()
    return max(0, (now.year - inc.year) * 12 + (now.month - inc.month))


async def build_compliance_dna(
    db: AsyncIOMotorDatabase,
    business_id: str,
    entity_attributes: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build the unique obligation set for a business. Age-aware: filings the
    business is too young for are excluded until the first cycle is due.
    """
    state = entity_attributes.get("state", "")
    industry = entity_attributes.get("industry", "")
    employee_count = entity_attributes.get("employee_count", 0)
    turnover = entity_attributes.get("annual_turnover_inr", 0)
    registrations = entity_attributes.get("registrations", [])
    incorporation_date = entity_attributes.get("incorporation_date", None)
    business_type = entity_attributes.get("business_type", None)

    age_months = _business_age_months(incorporation_date)

    query = {
        "$and": [
            {"$or": [
                {"applicable_to.industries": "all"},
                {"applicable_to.industries": industry},
            ]},
            # State-specific filings (TNPCB, Maharashtra Shops Act, etc.) must
            # not leak into other states' obligation sets. null/missing means
            # pan-India and always applies.
            {"$or": [
                {"state_specific": None},
                {"state_specific": {"$exists": False}},
                {"state_specific": state},
            ]},
        ],
        "applicable_to.min_employees": {"$lte": employee_count},
        "applicable_to.min_turnover_inr": {"$lte": turnover},
    }

    obligations = []
    high_severity = 0
    skipped_entity = 0
    skipped_conditional = 0
    async for reg in db.regulatory_corpus.find(query):
        req_regs = reg.get("applicable_to", {}).get("registrations_required", [])
        has_required_reg = bool(req_regs) and any(r in registrations for r in req_regs)
        if req_regs and not has_required_reg:
            continue

        freq = reg.get("frequency", "monthly")
        min_months = MATURITY_GATES.get(freq, 1)
        # Age gate intentionally skipped for obligations the business has
        # explicitly registered for. Rationale: if you registered for GST,
        # you have GST filings regardless of how old the business is. The
        # gate exists to avoid overwhelming brand-new businesses with
        # annual filings whose first cycle hasn't started — not to hide
        # obligations they actively signed up for.
        if age_months < min_months and not has_required_reg:
            continue

        reg_name = reg.get("name", "")
        if not _passes_entity_filter(reg_name, business_type):
            skipped_entity += 1
            continue
        if _CONDITIONAL_ONLY.search(reg_name):
            skipped_conditional += 1
            continue

        obligations.append({
            "obligation_id": str(reg["_id"]),
            "name": reg["name"],
            "category": _normalise_category(reg["category"]),
            "frequency": freq,
            "deadline_rule": reg["deadline_rule"],
            "penalty_type": reg.get("penalty_type", "financial"),
            "max_penalty_inr": reg.get("max_penalty_inr", 0),
            "complexity": reg.get("complexity", 1),
            "depends_on": reg.get("depends_on", []),
            "imprisonment_risk": reg.get("imprisonment_risk", False),
        })
        if reg.get("imprisonment_risk") or reg.get("complexity", 1) >= HIGH_SEVERITY_COMPLEXITY:
            high_severity += 1

    log.info(
        "dna_built business=%s type=%s obligations=%d high_severity=%d age_months=%d entity_filtered=%d",
        business_id, business_type, len(obligations), high_severity, age_months, skipped_entity,
    )

    return {
        "business_id": business_id,
        "entity_attributes": entity_attributes,
        "applicable_obligations": obligations,
        "total_obligations": len(obligations),
        "high_severity_count": high_severity,
        "business_age_months": age_months,
    }
