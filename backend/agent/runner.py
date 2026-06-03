"""
ADK runner integration — bridges FastAPI to the multi-agent system.

Captures every reasoning step (sub-agent calls, tool invocations, partial
text) and persists them to MongoDB as agent_decisions records, AND streams
them to the frontend so users can watch the agent think.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import AsyncGenerator, Dict, List

from logging_config import get_logger

log = get_logger(__name__)

_APP_NAME = "complianceos"


def _safe_dict(obj) -> Dict:
    """Convert ADK event objects to JSON-safe dicts. Tolerates unknown types."""
    if obj is None:
        return {}
    if isinstance(obj, (str, int, float, bool)):
        return {"value": obj}
    if isinstance(obj, dict):
        return {k: _safe_dict(v) if not isinstance(v, (str, int, float, bool, list)) else v for k, v in obj.items()}
    if isinstance(obj, list):
        return {"items": [str(i)[:200] for i in obj]}
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        return {k: str(v)[:200] for k, v in vars(obj).items() if not k.startswith("_")}
    return {"value": str(obj)[:500]}


def _event_to_dict(ev) -> Dict:
    """
    Reduce an ADK event to a minimal {role, kind, content, tool, args} record.
    Different ADK versions expose slightly different shapes; we extract what
    we can without depending on a single internal schema.
    """
    out: Dict = {
        "at": datetime.utcnow().isoformat(),
    }
    out["author"] = getattr(ev, "author", None) or getattr(ev, "agent_name", None) or "agent"
    # Try common attribute names
    for k in ("kind", "type", "event_type"):
        if hasattr(ev, k):
            out["kind"] = str(getattr(ev, k))
            break

    # Text content
    content = getattr(ev, "content", None)
    if content is not None:
        if hasattr(content, "parts"):
            parts = []
            for p in content.parts or []:
                if hasattr(p, "text") and p.text:
                    parts.append({"text": p.text[:1500]})
                if hasattr(p, "function_call") and p.function_call:
                    fc = p.function_call
                    parts.append({
                        "tool": getattr(fc, "name", "?"),
                        "args": _safe_dict(getattr(fc, "args", {})),
                    })
                if hasattr(p, "function_response") and p.function_response:
                    fr = p.function_response
                    response = getattr(fr, "response", None)
                    parts.append({
                        "tool_result": getattr(fr, "name", "?"),
                        "response": _safe_dict(response) if response else {},
                    })
            out["parts"] = parts
        else:
            out["content"] = str(content)[:1500]

    return out


_PLANNER_AUTHOR = "compliance_officer"


def extract_final_answer(captured: List[Dict]) -> str:
    """
    Pick the user-facing answer out of a captured ADK event trace.

    The planner (compliance_officer) usually synthesises the final reply, but
    when it delegates to a specialist sub-agent (dna_agent, penalty_agent, …)
    the actual answer is authored by THAT sub-agent. Prefer the planner's
    synthesis; fall back to whatever text the sub-agents produced so the user
    never sees a blank reply. Pure function — unit-tested without Gemini.
    """
    officer_text_parts: List[str] = []
    all_text_parts: List[str] = []
    for rec in captured:
        for p in rec.get("parts", []) or []:
            text = p.get("text")
            if text and text.strip():
                all_text_parts.append(text)
                if rec.get("author") == _PLANNER_AUTHOR:
                    officer_text_parts.append(text)
    return ("\n".join(officer_text_parts).strip()
            or "\n".join(all_text_parts).strip())


async def run_agent_stream(
    question: str,
    business_id: str | None = None,
) -> AsyncGenerator[Dict, None]:
    """
    Run the planner agent and yield reasoning events as they happen.

    Each yielded dict is a step in the agent's thought process. The final
    dict has kind='final' with the synthesised answer.
    """
    from db.mongodb import get_db
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai.types import Content, Part

    from agent.sub_agents import get_planner

    planner = get_planner()
    session_service = InMemorySessionService()
    user_id = business_id or "anon"
    session_id = str(uuid.uuid4())
    await session_service.create_session(
        app_name=_APP_NAME, user_id=user_id, session_id=session_id,
    )

    runner = Runner(
        app_name=_APP_NAME,
        agent=planner,
        session_service=session_service,
    )

    # Inject business_id into the question so sub-agent tools can find it.
    if business_id:
        prompt = (
            f"[Context: business_id={business_id}]\n\n"
            f"User question: {question}"
        )
    else:
        prompt = question

    message = Content(role="user", parts=[Part(text=prompt)])

    db = get_db()
    captured: List[Dict] = []

    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=message,
    ):
        rec = _event_to_dict(event)
        captured.append(rec)

        # Stream the event to caller
        yield rec

    final_text = extract_final_answer(captured)

    # Persist a single decision record summarising the run
    try:
        await db.agent_decisions.insert_one({
            "business_id": business_id or "anonymous",
            "action": "agent_run",
            "payload": {
                "question": question[:500],
                "step_count": len(captured),
                "final": final_text[:2000],
            },
            "timestamp": datetime.utcnow(),
            "trace": captured,
        })
    except Exception as exc:
        log.warning("Failed to persist agent trace: %s", exc)

    yield {
        "kind": "final",
        "author": "compliance_officer",
        "answer": final_text,
        "step_count": len(captured),
        "at": datetime.utcnow().isoformat(),
    }
