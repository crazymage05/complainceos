"""
Regression tests for the multi-agent answer extraction.

The original bug: `/agent/ask` returned HTTP 200 with an empty answer because
the runner only captured text authored by the planner ("compliance_officer").
When the planner delegated to a specialist sub-agent, the real answer was
authored by the sub-agent and got dropped — the user saw a blank reply.

These tests exercise the pure `extract_final_answer` helper against
representative ADK event traces, so the fix is verified without spending any
Gemini quota.
"""

from agent.runner import extract_final_answer


def test_subagent_answer_is_captured():
    # Planner only emits a tool transfer (no text); the sub-agent produces the
    # actual answer. This is the exact shape that used to yield "".
    trace = [
        {"author": "compliance_officer", "parts": [
            {"tool": "transfer_to_agent", "args": {"agent_name": "dna_agent"}}]},
        {"author": "dna_agent", "parts": [
            {"text": "You have 37 active obligations. The most urgent is GSTR-9."}]},
    ]
    answer = extract_final_answer(trace)
    assert "37 active obligations" in answer


def test_planner_synthesis_is_preferred():
    # When the planner DOES synthesise a final answer, prefer it over the
    # intermediate sub-agent chatter.
    trace = [
        {"author": "dna_agent", "parts": [{"text": "raw obligation dump"}]},
        {"author": "compliance_officer", "parts": [
            {"text": "Top priority: file GSTR-9 before Dec 31."}]},
    ]
    answer = extract_final_answer(trace)
    assert answer == "Top priority: file GSTR-9 before Dec 31."


def test_tool_only_trace_returns_empty_not_crash():
    # A trace with no text at all (pure tool calls) must return "" cleanly.
    trace = [
        {"author": "compliance_officer", "parts": [
            {"tool": "get_filing_track_record", "args": {}}]},
        {"author": "penalty_agent", "parts": [
            {"tool_result": "predict_penalty_for", "response": {"x": 1}}]},
    ]
    assert extract_final_answer(trace) == ""


def test_multiple_subagents_concatenated_when_no_planner_text():
    trace = [
        {"author": "penalty_agent", "parts": [{"text": "Penalty ~Rs.750."}]},
        {"author": "drafter_agent", "parts": [{"text": "Draft ready, 4 fields."}]},
    ]
    answer = extract_final_answer(trace)
    assert "Penalty ~Rs.750." in answer
    assert "Draft ready, 4 fields." in answer


def test_blank_and_whitespace_text_ignored():
    trace = [
        {"author": "dna_agent", "parts": [{"text": "   "}, {"text": ""}]},
        {"author": "decay_agent", "parts": [{"text": "Score 28 — amber."}]},
    ]
    assert extract_final_answer(trace) == "Score 28 — amber."


def test_empty_trace():
    assert extract_final_answer([]) == ""
