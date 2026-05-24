import asyncio
import json
from typing import Any, Dict


_PROMPT_TEMPLATE = (
    "You are an expert Indian tax and regulatory compliance analyst.\n"
    "A business owner pasted a government circular or notification. Analyse it and respond ONLY with valid JSON.\n\n"
    "Business context: {context}\n"
    "Circular source: {source}\n\n"
    "Circular text:\n{text}\n\n"
    "Respond with exactly this JSON shape (no markdown, no explanation):\n"
    '{{'
    '"plain_summary":"3 sentences max — what changed, who it affects, by when",'
    '"affected_business_types":["list of affected business types"],'
    '"key_changes":[{{"change":"what changed","effective_date":"date or immediate","action_required":"what business must do"}}],'
    '"applies_to_this_business":true,'
    '"reason":"one sentence — why it does or does not apply to this specific business",'
    '"urgency":"high",'
    '"affected_categories":["taxation","labour","food_safety","companies_act","other"]'
    '}}'
)


async def interpret_circular(
    business_context: Dict[str, Any],
    circular_text: str,
    circular_source: str,
) -> Dict[str, Any]:
    from model_client import get_completion

    ctx = (
        f"{business_context.get('name', 'MSME')} | "
        f"Industry: {business_context.get('industry', 'general')} | "
        f"State: {business_context.get('state', 'India')} | "
        f"Employees: {business_context.get('employee_count', 0)} | "
        f"Turnover: ₹{business_context.get('annual_turnover_inr', 0):,.0f} | "
        f"Registrations: {', '.join(business_context.get('registrations', [])) or 'none'}"
    )

    prompt = _PROMPT_TEMPLATE.format(
        context=ctx,
        source=circular_source or "Government Circular",
        text=circular_text[:8000],
    )

    try:
        raw = await asyncio.to_thread(get_completion, prompt)
        raw = raw.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())
        result.setdefault("plain_summary", "")
        result.setdefault("affected_business_types", [])
        result.setdefault("key_changes", [])
        result.setdefault("applies_to_this_business", False)
        result.setdefault("reason", "")
        result.setdefault("urgency", "medium")
        result.setdefault("affected_categories", [])
        return result
    except Exception as e:
        print(f"Gemini error in interpret_circular: {e}")
        return {
            "plain_summary": "Could not parse this circular automatically. Please consult your CA for interpretation.",
            "affected_business_types": [],
            "key_changes": [],
            "applies_to_this_business": False,
            "reason": "Gemini unavailable or response malformed — try again shortly.",
            "urgency": "medium",
            "affected_categories": [],
        }
