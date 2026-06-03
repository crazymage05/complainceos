"""
RAG over the regulatory corpus.

The flow:
  1. Embed the user's question
  2. Run hybrid retrieval ($vectorSearch + $search) against regulatory_corpus
  3. Pull the top-K full documents (name, deadline_rule, source, raw_text)
  4. Pass them as grounding context to Gemini with a strict citation prompt
  5. Return the answer + the citations the model relied on

Why this is the right pattern for a hackathon demo:
  - Vector Search is fired (judges see it in action)
  - Atlas Search is fired (judges see it in action — both in one call)
  - Gemini is grounded in actual corpus documents, not hallucinated answers
  - Every response shows the regulations it cited, so judges can verify
"""

import asyncio
import json
from typing import Any, Dict, List

from motor.motor_asyncio import AsyncIOMotorDatabase

from engines.hybrid_search import hybrid_search
from logging_config import get_logger

log = get_logger(__name__)


RAG_TOP_K = 6
RAG_MAX_CONTEXT_CHARS = 4500


def _format_context(docs: List[Dict[str, Any]]) -> str:
    """Stringify retrieved docs into a concise, model-friendly context block."""
    lines: List[str] = []
    used = 0
    for i, d in enumerate(docs, start=1):
        snippet = (d.get("deadline_rule") or "")[:300]
        block = (
            f"[Reg-{i}] {d.get('name', '')} "
            f"(category: {d.get('category', '')}, "
            f"max_penalty: ₹{d.get('max_penalty_inr', 0):,}, "
            f"state: {d.get('state_specific') or 'pan-India'})\n"
            f"Deadline rule: {snippet}\n"
        )
        if used + len(block) > RAG_MAX_CONTEXT_CHARS:
            break
        lines.append(block)
        used += len(block)
    return "\n".join(lines)


async def explain_regulation(
    db: AsyncIOMotorDatabase,
    question: str,
    business_context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Answer a natural-language question about Indian compliance regulations.
    Retrieval is hybrid; the answer is grounded in the retrieved set with
    visible citations.
    """
    from model_client import get_completion, get_embedding

    # 1. Embed
    try:
        embedding = await asyncio.to_thread(get_embedding, question)
    except Exception as exc:
        log.warning("RAG embedding failed: %s", exc)
        embedding = None

    # 2. Hybrid retrieve
    retrieval = await hybrid_search(db, question, embedding, limit=RAG_TOP_K)
    fused = retrieval.get("fused", [])

    if not fused:
        return {
            "question": question,
            "answer": "I couldn't find relevant regulations in the corpus. Try rephrasing — for example: 'What is GSTR-9?' or 'When is the FSSAI annual return due?'",
            "citations": [],
            "retrieval_method": retrieval.get("method", "empty"),
        }

    # 3. Build the grounding context
    context = _format_context(fused)

    # 4. Build business context line if provided
    biz_line = ""
    if business_context:
        biz_line = (
            "\nThe person asking runs this business:\n"
            f"  - Industry: {business_context.get('industry', 'unknown')}\n"
            f"  - State: {business_context.get('state', 'unknown')}\n"
            f"  - Employees: {business_context.get('employee_count', 0)}\n"
            f"  - Turnover: ₹{business_context.get('annual_turnover_inr', 0):,}\n"
        )

    # 5. Call Gemini grounded in retrieved docs
    prompt = (
        "You are a compliance expert for Indian small businesses (MSMEs). "
        "Answer the question using ONLY the regulations provided below as "
        "context. Cite each fact with [Reg-N] where N is the regulation "
        "number from the context. If the context doesn't contain the "
        "answer, say so honestly rather than guessing.\n\n"
        f"CONTEXT — Top {len(fused)} relevant regulations:\n"
        f"{context}\n"
        f"{biz_line}\n"
        f"Question: {question}\n\n"
        "Answer in 3-5 plain-English sentences. End with a one-line action "
        "(\"What to do next: ...\"). Cite with [Reg-N] inline."
    )

    answer = ""
    try:
        answer = await asyncio.to_thread(get_completion, prompt)
        answer = (answer or "").strip()
    except Exception as exc:
        log.warning("RAG completion failed: %s", exc)
        # Graceful fallback — just return the top hits as a list
        answer = (
            f"I found {len(fused)} relevant regulations but couldn't generate a "
            f"narrative answer right now (the LLM is temporarily unavailable). "
            f"Top match: {fused[0].get('name', 'unknown')}."
        )

    citations = [
        {
            "label": f"Reg-{i+1}",
            "regulation_id": d.get("_id"),
            "name": d.get("name", ""),
            "category": d.get("category", ""),
            "found_by": d.get("sources", []),
            "rrf_score": d.get("rrf_score"),
        }
        for i, d in enumerate(fused)
    ]

    return {
        "question": question,
        "answer": answer,
        "citations": citations,
        "retrieval_method": retrieval.get("method", "hybrid_rrf"),
        "retrieved_count": len(fused),
    }
