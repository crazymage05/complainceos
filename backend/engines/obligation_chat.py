import asyncio
import json
from typing import Any, Dict, List

from motor.motor_asyncio import AsyncIOMotorDatabase

from logging_config import get_logger

log = get_logger(__name__)


_SYSTEM_PROMPT = (
    "You are an expert Indian MSME compliance advisor conducting an onboarding interview. "
    "Your goal is to discover compliance obligations the business owner may not know about — "
    "especially non-obvious ones that standard forms miss: contract workers, delivery platforms, "
    "state-specific rules, threshold crossings, home-based operations, fire NOCs, trade licences, "
    "POSH applicability, e-commerce TCS, import/export obligations, etc.\n\n"
    "Rules:\n"
    "- Ask ONE focused follow-up question per turn.\n"
    "- ALWAYS include at least 1-2 candidate obligations in 'discovered' that are commonly "
    "  missed for THIS business's state + industry + size — even on the first turn. Examples:\n"
    "    * Tamil Nadu retail with >10 employees: POSH Internal Complaints Committee constitution\n"
    "    * Maharashtra food services with FSSAI: Maharashtra Pollution Control Board consent\n"
    "    * Karnataka services with employees: Karnataka Labour Welfare Fund\n"
    "    * Any e-commerce: GSTR-8 TCS Return\n"
    "    * Any imports/exports: IEC renewal\n"
    "  Mark these with `reason` explaining the trigger.\n"
    "- Be specific to Indian law and the business's state/industry.\n"
    "- Provide 2-3 short suggestion buttons to help the user respond quickly.\n"
    "- In 'new_facts', record any structured boolean/string facts learned THIS turn only "
    "  (e.g. uses_delivery_platforms, has_contract_workers).\n\n"
    "Respond ONLY with valid JSON — no markdown, no explanation:\n"
    '{"reply":"your message","discovered":[{"name":"obligation name","reason":"why it applies to this specific business","category":"taxation/labour/food_safety/shops_establishments/companies_act/fire_safety/other","urgency":"immediate/next_30_days/annual"}],"suggestions":["option 1","option 2","option 3"],"new_facts":{"key":value}}'
)

_SUMMARISE_PROMPT = (
    "You are an expert Indian MSME compliance advisor. "
    "The user wants a final summary of all compliance obligations discovered in this conversation.\n\n"
    "Based on the conversation and known facts below, produce a clean structured summary.\n\n"
    "Respond ONLY with valid JSON:\n"
    '{"reply":"formatted markdown-style summary listing all discovered obligations with category and urgency","discovered":[],"suggestions":[],"new_facts":{}}'
)


async def chat_discover(
    db: AsyncIOMotorDatabase,
    business_id: str,
    messages: List[Dict[str, str]],
    business_context: Dict[str, Any],
    business_facts: Dict[str, Any] | None = None,
    summarise: bool = False,
) -> Dict[str, Any]:
    from model_client import get_completion

    if business_facts is None:
        business_facts = {}

    ctx = (
        f"Business: {business_context.get('name', 'MSME')} | "
        f"Industry: {business_context.get('industry', 'general')} | "
        f"State: {business_context.get('state', 'India')} | "
        f"Employees: {business_context.get('employee_count', 0)} | "
        f"Turnover: ₹{business_context.get('annual_turnover_inr', 0):,.0f} | "
        f"Registrations: {', '.join(business_context.get('registrations', [])) or 'none declared'}"
    )

    facts_str = ""
    if business_facts:
        facts_str = f"\nAccumulated facts (do not re-ask about these): {json.dumps(business_facts)}"

    system = _SUMMARISE_PROMPT if summarise else _SYSTEM_PROMPT

    conversation = f"Business Context: {ctx}{facts_str}\n\nConversation:\n"
    for msg in messages[-12:]:
        role = "Owner" if msg["role"] == "user" else "Advisor"
        conversation += f"{role}: {msg['content']}\n"
    conversation += "Advisor (respond with JSON):"

    full_prompt = system + "\n\n" + conversation

    try:
        raw = await asyncio.to_thread(get_completion, full_prompt)
        raw = raw.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())
        result.setdefault("reply", "Tell me more about your day-to-day operations.")
        result.setdefault("discovered", [])
        result.setdefault("suggestions", [])
        result.setdefault("new_facts", {})
    except Exception as exc:
        log.warning("chat_discover fallback: %s", exc)
        result = {
            "reply": "Do you employ contract workers or gig workers alongside your full-time staff? Many businesses miss EPF/ESI obligations for this category.",
            "discovered": [],
            "suggestions": ["Yes, we use contract workers", "No, all are full-time", "Mix of both"],
            "new_facts": {},
        }

    # Merge new facts into running context and return updated set
    updated_facts = {**business_facts, **result["new_facts"]}
    result["business_facts"] = updated_facts
    return result
