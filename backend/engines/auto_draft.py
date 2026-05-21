import asyncio
import json
from datetime import datetime
from typing import Any, Dict

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


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
        instance = await db.obligation_instances.find_one({"_id": ObjectId(instance_id)})
    except Exception:
        instance = None

    regulation = await db.regulatory_corpus.find_one({"_id": regulation_id})

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
    """Call Gemini for entity-specific filing advice."""
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
        return {
            "documents_required": [],
            "common_mistakes": [],
            "risk_level": "medium",
            "risk_reason": "Please verify current requirements with your CA before filing.",
            "filing_checklist": [],
        }
