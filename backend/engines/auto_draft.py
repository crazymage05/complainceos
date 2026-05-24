import asyncio
import json
from datetime import datetime
from typing import Any, Dict

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


# Category-specific filing defaults — used when Gemini is unavailable
_CATEGORY_DEFAULTS: Dict[str, Dict] = {
    "taxation": {
        "documents_required": [
            "GSTIN registration certificate",
            "Sales & purchase invoices for the period",
            "Bank statements",
            "Previous period's filed return copy",
        ],
        "common_mistakes": [
            "Mismatch between GSTR-1 outward supplies and GSTR-3B summary",
            "Missing ITC reversal for exempt or blocked supplies",
            "Filing after deadline — ₹50/day late fee accrues immediately",
        ],
        "risk_reason": "GSTN auto-matches returns across taxpayers — mismatches trigger automated notices.",
        "filing_checklist": [
            "Reconcile sales register with GSTR-1 figures",
            "Verify ITC claims against GSTR-2B auto-drafted credits",
            "Pay tax liability before submitting to avoid interest at 18% p.a.",
        ],
    },
    "labour": {
        "documents_required": [
            "Employee wage register for the period",
            "Attendance register",
            "EPF / ESI registration certificate (EPFO/ESIC portal)",
        ],
        "common_mistakes": [
            "Missing contributions for employees who resigned mid-month",
            "Incorrect UAN/IP number mapping for new joiners",
            "Not filing a zero return in months with no employees",
        ],
        "risk_reason": "PF/ESI defaults can lead to criminal prosecution with imprisonment under the Act.",
        "filing_checklist": [
            "Match employee list with EPFO/ESIC portal records",
            "Generate ECR/return file from wage register",
            "Pay challan first — upload return only after payment confirms",
        ],
    },
    "food_safety": {
        "documents_required": [
            "FSSAI license / registration certificate",
            "Food safety management system records",
            "Annual turnover figure for the financial year",
        ],
        "common_mistakes": [
            "Filing Form D-1 with incorrect annual turnover — triggers scrutiny",
            "Not updating product categories when business expands",
            "Missing renewal 30 days before expiry — late renewal attracts penalty",
        ],
        "risk_reason": "FSSAI violations can lead to product seizure, license cancellation, and up to 6 years imprisonment.",
        "filing_checklist": [
            "Log in to FSSAI FoSCoS portal (foscos.fssai.gov.in)",
            "Update product list and turnover for the financial year",
            "Pay renewal fee and submit — retain acknowledgement",
        ],
    },
    "shops_establishments": {
        "documents_required": [
            "Existing Shop & Establishment registration certificate",
            "Proof of business premises (rent agreement / ownership deed)",
            "Updated employee count with designations",
        ],
        "common_mistakes": [
            "Not renewing before December 31 — Labour Dept levies late penalty",
            "Not updating employee headcount when it crosses slab thresholds",
            "Filing under wrong category (manufacturing vs retail vs services)",
        ],
        "risk_reason": "Operating with an expired certificate can attract closure notices from Labour Department.",
        "filing_checklist": [
            "Visit state Labour Department e-service portal",
            "Fill renewal form with current employee count and address",
            "Pay slab-based renewal fee and download renewed certificate",
        ],
    },
    "companies_act": {
        "documents_required": [
            "Audited financial statements (if applicable)",
            "Board resolution for the relevant filing",
            "Director identification numbers (DIN) and digital signatures",
        ],
        "common_mistakes": [
            "Missing additional attachment requirements (e.g. balance sheet for ROC forms)",
            "DIN or DSC expired — causes filing rejection",
            "Filing with incorrect financial year dates",
        ],
        "risk_reason": "ROC non-compliance leads to strike-off proceedings and director disqualification.",
        "filing_checklist": [
            "Verify DSC validity for all authorised signatories",
            "Check MCA21 portal for current form version — versions change",
            "Pre-scrutinise form using MCA checker before final submission",
        ],
    },
    "income_tax": {
        "documents_required": [
            "Audited accounts / profit & loss statement",
            "Form 26AS and AIS (from income tax portal)",
            "TDS certificates (Form 16 / 16A) if applicable",
        ],
        "common_mistakes": [
            "Not reconciling TDS credits in Form 26AS before filing",
            "Missing advance tax payments — interest u/s 234B/234C applies",
            "Incorrect ITR form selection based on business structure",
        ],
        "risk_reason": "Defective return notices are common when TDS credits don't match — respond within 15 days.",
        "filing_checklist": [
            "Download Form 26AS and AIS from income tax portal and reconcile",
            "Compute advance tax paid — top up if shortfall exists",
            "Select correct ITR form (ITR-3 for proprietorship, ITR-6 for companies)",
        ],
    },
}

_DEFAULT_FALLBACK: Dict[str, Any] = {
    "documents_required": [
        "Registration certificate for the applicable authority",
        "Financial / operational records for the filing period",
        "Previous period's filed return / acknowledgement copy",
    ],
    "common_mistakes": [
        "Missing the deadline — penalties start from day one of default",
        "Entity name or address mismatch with registration records",
        "Not retaining the acknowledgement receipt after submission",
    ],
    "risk_reason": "Verify current filing requirements with your CA before submitting.",
    "filing_checklist": [
        "Gather all documents listed above",
        "Confirm portal credentials are active and DSC (if required) is valid",
        "Submit before the deadline and save the acknowledgement",
    ],
}


async def generate_draft(
    db: AsyncIOMotorDatabase,
    business_id: str,
    regulation_id: str,
    instance_id: str,
) -> Dict[str, Any]:
    """
    Auto-Draft Filing Agent — Patent Claim 5.
    Pre-populates filing documents from business data, then calls Gemini
    for structured filing advice specific to this business and obligation.
    """
    try:
        business = await db.businesses.find_one({"_id": ObjectId(business_id)})
    except Exception:
        business = None

    template = await db.filing_templates.find_one({"regulation_id": regulation_id})
    if not template:
        template = await db.filing_templates.find_one({})

    try:
        regulation = await db.regulatory_corpus.find_one({"_id": ObjectId(regulation_id)})
    except Exception:
        regulation = None

    if not business or not template:
        return {"error": "Business or template not found"}

    # TODO: PATENT-PENDING — field mapping rules omitted
    populated_fields: Dict[str, Any] = {}
    for field in template.get("fields", []):
        fname = field["field_name"]
        maps_to = field.get("maps_to", "")
        populated_fields[fname] = _resolve_field(business, maps_to)

    # Gemini filing advisor — entity-specific reasoning
    advisor_notes = await _get_advisor_notes(business, regulation or {}, template)

    return {
        "business_id": business_id,
        "regulation_id": regulation_id,
        "instance_id": instance_id,
        "template_name": template.get("template_name", ""),
        "populated_fields": populated_fields,
        "output_format": template.get("output_format", "pdf"),
        "authority_portal": template.get("authority_portal", ""),
        "generated_at": datetime.utcnow().isoformat(),
        "status": "pending_review",
        "advisor_notes": advisor_notes,
    }


def _resolve_field(business: Dict, maps_to: str) -> Any:
    # TODO: PATENT-PENDING — resolution logic omitted
    simple_map = {
        "businesses.name": business.get("name", ""),
        "businesses.state": business.get("state", ""),
        "businesses.employee_count": business.get("employee_count", 0),
        "businesses.annual_turnover_inr": business.get("annual_turnover_inr", 0),
    }
    return simple_map.get(maps_to, "")


async def _get_advisor_notes(
    business: Dict, regulation: Dict, template: Dict
) -> Dict[str, Any]:
    """Call Gemini for entity-specific filing advice. Falls back to category defaults."""
    from model_client import get_completion

    turnover = business.get("annual_turnover_inr", 0)
    prompt = (
        "You are an Indian MSME compliance advisor. A business needs to file a document."
        " Respond ONLY with valid JSON, no markdown, no explanation.\n\n"
        f"Business: {business.get('name', 'MSME')} | "
        f"Industry: {business.get('industry', 'general')} | "
        f"State: {business.get('state', 'India')} | "
        f"Employees: {business.get('employee_count', 0)} | "
        f"Turnover: ₹{turnover:,.0f}\n"
        f"Filing: {template.get('template_name', 'Compliance Filing')}\n"
        f"Regulation: {regulation.get('name', '')} | "
        f"Category: {regulation.get('category', '')} | "
        f"Deadline rule: {regulation.get('deadline_rule', '')} | "
        f"Max penalty: ₹{regulation.get('max_penalty_inr', 0):,.0f}\n\n"
        'Return exactly this JSON shape:\n'
        '{"documents_required":["...","..."],'
        '"common_mistakes":["...","...","..."],'
        '"risk_level":"low",'
        '"risk_reason":"one sentence",'
        '"filing_checklist":["Step 1: ...","Step 2: ...","Step 3: ..."]}'
    )

    try:
        raw = await asyncio.to_thread(get_completion, prompt)
        raw = raw.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception:
        # Gemini unavailable (rate limit / quota) — serve category-specific defaults
        cat = regulation.get("category", "")
        defaults = _CATEGORY_DEFAULTS.get(cat, _DEFAULT_FALLBACK)
        return {
            "documents_required": defaults["documents_required"],
            "common_mistakes": defaults["common_mistakes"],
            "risk_level": "medium",
            "risk_reason": defaults["risk_reason"],
            "filing_checklist": defaults["filing_checklist"],
        }
