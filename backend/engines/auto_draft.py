from typing import Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
from bson import ObjectId

async def generate_draft(
    db: AsyncIOMotorDatabase,
    business_id: str,
    regulation_id: str,
    instance_id: str,
) -> Dict[str, Any]:
    """
    Auto-Draft Filing Agent — Patent Claim 5.
    Pre-populates filing documents from business data.
    """
    try:
        business = await db.businesses.find_one({"_id": ObjectId(business_id)})
    except Exception:
        business = None

    template = await db.filing_templates.find_one({"regulation_id": regulation_id})

    # Fallback: use generic template if no specific one exists
    if not template:
        template = await db.filing_templates.find_one({})

    try:
        instance = await db.obligation_instances.find_one({"_id": ObjectId(instance_id)})
    except Exception:
        instance = None

    if not business or not template:
        return {"error": "Business or template not found"}

    # TODO: PATENT-PENDING — field mapping rules omitted
    populated_fields = {}
    for field in template.get("fields", []):
        fname = field["field_name"]
        maps_to = field.get("maps_to", "")
        populated_fields[fname] = _resolve_field(business, maps_to)

    draft = {
        "business_id": business_id,
        "regulation_id": regulation_id,
        "instance_id": instance_id,
        "template_name": template.get("template_name", ""),
        "populated_fields": populated_fields,
        "output_format": template.get("output_format", "pdf"),
        "authority_portal": template.get("authority_portal", ""),
        "generated_at": datetime.utcnow().isoformat(),
        "status": "pending_review",
    }
    return draft


def _resolve_field(business: Dict, maps_to: str) -> Any:
    # TODO: PATENT-PENDING — resolution logic omitted
    simple_map = {
        "businesses.name": business.get("name", ""),
        "businesses.state": business.get("state", ""),
        "businesses.employee_count": business.get("employee_count", 0),
        "businesses.annual_turnover_inr": business.get("annual_turnover_inr", 0),
    }
    return simple_map.get(maps_to, "")
