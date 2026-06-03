"""
Multi-agent architecture for ComplianceOS.

A root Planner agent delegates to five specialist sub-agents, each focused
on one capability of the compliance pipeline. Each sub-agent has access
only to the tools it needs — the principle of least authority makes
reasoning traces clearer and reduces hallucination risk.

The structure mirrors the 5 patentable claims in the original spec:
  1. DNA Agent       — Compliance DNA Profile builder
  2. Decay Agent     — Decay Score interpreter
  3. Ripple Agent    — Regulatory Ripple Detection
  4. Penalty Agent   — Penalty Prediction
  5. Drafter Agent   — Auto-Draft Filing
Plus a non-claim:
  6. Advisor Agent   — Hidden Obligation discovery

The Planner decides which sub-agent(s) to call for any given user query.
"""

import os
from typing import Any

from logging_config import get_logger
from agent.tools import (detect_regulation_impact, discover_hidden_obligations,
                         explain_decay_score, generate_filing_draft,
                         get_filing_track_record, list_obligations,
                         predict_penalty_for)

log = get_logger(__name__)

MODEL = os.getenv("AGENT_MODEL", "gemini-2.5-flash")


def _build_agents() -> Any:
    """Lazy import + build — keeps ADK out of the import path until needed."""
    from google.adk.agents import Agent

    # ── Sub-agent 1: DNA / obligation listing ─────────────────────────────────
    dna_agent = Agent(
        name="dna_agent",
        model=MODEL,
        description=(
            "Specialist for listing a business's active compliance obligations "
            "with live decay scores. Knows what each obligation is and when it's due."
        ),
        instruction=(
            "You are the DNA Agent. When asked about a business's obligations, "
            "call list_obligations(business_id). Return a concise summary: "
            "total active, urgent count, and the top 3 most urgent items "
            "with name + days remaining + decay score. Never invent obligations."
        ),
        tools=[list_obligations],
    )

    # ── Sub-agent 2: Decay reasoning ──────────────────────────────────────────
    decay_agent = Agent(
        name="decay_agent",
        model=MODEL,
        description=(
            "Specialist for explaining WHY an obligation has its specific decay "
            "score. Walks through time, complexity, penalty severity, and "
            "history components."
        ),
        instruction=(
            "You are the Decay Agent. When asked to explain an urgency score, "
            "call explain_decay_score(instance_id). Translate the formula inputs "
            "into a 3-sentence plain-English explanation a small-business owner "
            "would understand. Always show the actual numbers."
        ),
        tools=[explain_decay_score],
    )

    # ── Sub-agent 3: Ripple detection ─────────────────────────────────────────
    ripple_agent = Agent(
        name="ripple_agent",
        model=MODEL,
        description=(
            "Specialist for tracing how a new regulation or circular ripples "
            "across a business's existing obligations using vector search."
        ),
        instruction=(
            "You are the Ripple Agent. When given a regulation change, "
            "call detect_regulation_impact(business_id, change_description). "
            "Report: directly impacted (similarity ≥0.79), indirectly impacted "
            "(≥0.76), and the overall severity. List the top 3 directly "
            "impacted obligations by name."
        ),
        tools=[detect_regulation_impact],
    )

    # ── Sub-agent 4: Penalty prediction ───────────────────────────────────────
    penalty_agent = Agent(
        name="penalty_agent",
        model=MODEL,
        description=(
            "Specialist for predicting the rupee penalty a business would pay "
            "for missing a specific obligation. Accounts for size, turnover, "
            "days late, and repeat-offender history."
        ),
        instruction=(
            "You are the Penalty Agent. When asked the financial cost of "
            "missing an obligation, call predict_penalty_for(instance_id). "
            "Always show the rupee figure and whether it's projected (not yet "
            "overdue) or actual (already late)."
        ),
        tools=[predict_penalty_for],
    )

    # ── Sub-agent 5: Auto-Draft filing ────────────────────────────────────────
    drafter_agent = Agent(
        name="drafter_agent",
        model=MODEL,
        description=(
            "Specialist for generating pre-filled filing drafts from business "
            "profile data, with a category-specific checklist."
        ),
        instruction=(
            "You are the Drafter Agent. When asked to prepare a filing, "
            "call generate_filing_draft(instance_id). Report the template "
            "name, number of pre-filled fields, and surface the 3 most "
            "important advisor checklist items."
        ),
        tools=[generate_filing_draft],
    )

    # ── Sub-agent 6: Hidden obligation discovery ─────────────────────────────
    advisor_agent = Agent(
        name="advisor_agent",
        model=MODEL,
        description=(
            "Specialist for discovering NON-OBVIOUS compliance obligations a "
            "business owner may not know about (POSH, fire NOC, state-specific "
            "pollution consent, e-commerce TCS, etc.)."
        ),
        instruction=(
            "You are the Advisor Agent. When asked what might be missing, "
            "call discover_hidden_obligations(business_id, question_or_topic). "
            "List each discovered obligation with name + 1-line reason + urgency."
        ),
        tools=[discover_hidden_obligations],
    )

    # ── Root Planner agent — delegates to sub-agents ──────────────────────────
    planner_agent = Agent(
        name="compliance_officer",
        model=MODEL,
        description=(
            "ComplianceOS — the chief compliance officer agent for an Indian "
            "MSME. Orchestrates specialist sub-agents to answer questions "
            "about obligations, urgency, penalties, regulatory changes, and "
            "filing drafts."
        ),
        instruction=(
            "You are ComplianceOS, the chief compliance officer for an Indian "
            "small or medium business.\n\n"
            "ROUTING RULES — delegate to the right specialist:\n"
            "  • List obligations / 'what do I owe' → dna_agent\n"
            "  • Explain a decay score / 'why is this urgent' → decay_agent\n"
            "  • Regulation change impact / 'this circular dropped' → ripple_agent\n"
            "  • Penalty amount / 'how much will I pay' → penalty_agent\n"
            "  • Prepare a filing / 'draft the form' → drafter_agent\n"
            "  • Find missing obligations / 'what am I missing' → advisor_agent\n"
            "  • Filing history / track record → call get_filing_track_record directly\n\n"
            "For complex questions, call MULTIPLE specialists and synthesise.\n\n"
            "TONE: Plain English. Show the money — 'this protects ₹750 in penalties'. "
            "Always cite the agent or tool you used. Never invent obligations or "
            "penalty figures. If a tool returns an error, surface it clearly.\n\n"
            "OUTPUT FORMAT: 2-4 bullet points + one closing sentence with the "
            "single most important action the owner should take."
        ),
        sub_agents=[
            dna_agent, decay_agent, ripple_agent, penalty_agent,
            drafter_agent, advisor_agent,
        ],
        tools=[get_filing_track_record],
    )
    return planner_agent


_planner = None


def get_planner():
    """Get the singleton root planner agent."""
    global _planner
    if _planner is None:
        _planner = _build_agents()
    return _planner
