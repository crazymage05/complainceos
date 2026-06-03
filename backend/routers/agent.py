"""
Agent endpoints — the multi-agent Compliance Officer in front of the engines.
"""

import asyncio
import json
from typing import Any, Dict, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from auth import current_user
from common import rate_limit_gemini
from db.mongodb import get_db
from logging_config import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


def _is_quota_error(exc: BaseException) -> bool:
    s = str(exc)
    return "429" in s or "RESOURCE_EXHAUSTED" in s or "exceeded your current quota" in s.lower()


def _quota_exceeded() -> Dict[str, Any]:
    return {
        "kind": "error",
        "author": "compliance_officer",
        "message": (
            "Gemini's free-tier daily quota (20 requests/day) is exhausted. "
            "The agent's reasoning loop needs a fresh quota — try again "
            "after the quota resets (typically midnight Pacific) or "
            "configure a paid Gemini API key."
        ),
    }


class AgentAskRequest(BaseModel):
    business_id: Optional[str] = None
    question: str


class ExplainRegulationRequest(BaseModel):
    question: str
    business_id: Optional[str] = None


@router.post(
    "/ask",
    dependencies=[Depends(rate_limit_gemini)],
)
async def agent_ask(
    payload: AgentAskRequest,
    user: Dict = Depends(current_user),
):
    """
    Blocking endpoint — runs the agent end-to-end and returns the final
    answer plus the full reasoning trace.
    """
    from agent.runner import run_agent_stream

    trace = []
    final = None
    try:
        async for event in run_agent_stream(payload.question, payload.business_id):
            if event.get("kind") == "final":
                final = event
            else:
                trace.append(event)
    except BaseException as exc:
        if _is_quota_error(exc):
            log.warning("Gemini quota exhausted while running agent: %s", exc)
            raise HTTPException(
                status_code=429,
                detail=_quota_exceeded()["message"],
                headers={"Retry-After": "60"},
            ) from exc
        log.exception("agent run failed")
        raise HTTPException(status_code=500, detail=f"Agent error: {str(exc)[:200]}") from exc

    return {
        "answer": (final or {}).get("answer", ""),
        "step_count": (final or {}).get("step_count", 0),
        "trace": trace,
    }


@router.post(
    "/stream",
    dependencies=[Depends(rate_limit_gemini)],
)
async def agent_stream(
    payload: AgentAskRequest,
    user: Dict = Depends(current_user),
):
    """
    Server-Sent-Events endpoint — streams reasoning events as they happen,
    so the UI can render the agent's thoughts in real time.
    """
    from agent.runner import run_agent_stream

    async def _gen():
        try:
            async for event in run_agent_stream(payload.question, payload.business_id):
                # SSE format: each message is `data: <json>\n\n`
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except BaseException as exc:
            if _is_quota_error(exc):
                log.warning("Gemini quota exhausted during agent stream")
                yield f"data: {json.dumps(_quota_exceeded())}\n\n"
            else:
                log.exception("agent stream failed")
                err = {"kind": "error", "author": "compliance_officer",
                       "message": f"Agent error: {str(exc)[:300]}"}
                yield f"data: {json.dumps(err)}\n\n"

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering if proxied
            "Connection": "keep-alive",
        },
    )


@router.post(
    "/explain-regulation",
    dependencies=[Depends(rate_limit_gemini)],
)
async def explain_regulation_endpoint(
    payload: ExplainRegulationRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: Dict = Depends(current_user),
):
    """
    RAG over the regulatory corpus: hybrid Vector + Atlas Search retrieval,
    grounded Gemini answer with [Reg-N] citations the user can verify.

    This is the "ask anything about Indian compliance" endpoint — distinct
    from the multi-agent /ask in that it does NOT touch a specific business's
    obligations; it just answers conceptual questions about regulations.
    """
    from engines.regulation_rag import explain_regulation

    biz_ctx: Optional[Dict[str, Any]] = None
    if payload.business_id:
        try:
            biz = await db.businesses.find_one({"_id": ObjectId(payload.business_id)})
            if biz:
                biz_ctx = {
                    "industry": biz.get("industry"),
                    "state": biz.get("state"),
                    "employee_count": biz.get("employee_count"),
                    "annual_turnover_inr": biz.get("annual_turnover_inr"),
                }
        except Exception:
            biz_ctx = None

    try:
        result = await explain_regulation(db, payload.question, biz_ctx)
    except BaseException as exc:
        if _is_quota_error(exc):
            raise HTTPException(
                status_code=429,
                detail=_quota_exceeded()["message"],
                headers={"Retry-After": "60"},
            ) from exc
        log.exception("RAG explain-regulation failed")
        raise HTTPException(status_code=500, detail=str(exc)[:200]) from exc

    return result
