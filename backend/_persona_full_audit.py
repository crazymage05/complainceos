"""
Full persona audit — 4 archetypal MSMEs, every endpoint, every Tier-S feature.

For each persona we:
  1. Create the business
  2. List obligations, check decay distribution, assert what they NEED is there
  3. Assert what they should NOT see (entity type, state, conditional filings)
  4. Run ripple check (legacy + hybrid)
  5. Pull penalty preview, generate draft, download PDF, approve
  6. Test filing-summary + exposure aggregations
  7. Test decay-trend (Time Series read)
  8. Run AI advisor one-shot
  9. Test Atlas Search regulation finder
  10. Test edit-profile (PATCH)
  11. Test new RAG explain-regulation

Cross-cutting checks:
  - Multi-tenant ripple cascade across all 4
  - Change Stream SSE handshake
  - Agent ask end-to-end (will report 429 cleanly if quota exhausted)

Output: machine-readable BUG list at the end.
"""

import asyncio
import json
import os
import sys
import time
import urllib.parse
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

BASE = "http://127.0.0.1:8000/api/v1"


# ---------------------------------------------------------------------------
# Personas — each with NEEDS (must appear) and NOT_NEEDS (must NOT appear)
# ---------------------------------------------------------------------------
PERSONAS = [
    {
        "label": "P1 SoleProp TN Retail (Selvi General Store)",
        "incorporation_days_ago": 365 * 5,
        "payload": {
            "name": "Selvi General Store",
            "owner": "selvi@example.com",
            "state": "Tamil Nadu",
            "industry": "retail",
            "business_type": "proprietorship",
            "employee_count": 4,
            "annual_turnover_inr": 2_500_000,
            "registrations": ["GST", "Shop_License"],
        },
        # Substrings that SHOULD appear in at least one obligation name
        "needs_any_of": [
            ["GSTR", "GST"],          # must see GST filings
            ["Shop", "Establishment"],  # Shop Act
            ["Income Tax", "ITR"],     # income tax for proprietor
        ],
        # Substrings that MUST NOT appear (case-insensitive)
        "must_not_contain": [
            "AOC-",        # companies-act only
            "MGT-",        # companies-act only
            "BEN-",        # companies-act only
            "Form 11 LLP", # LLP only
            "Form 8 LLP",  # LLP only
            "Maharashtra", # other state
            "Gujarat",     # other state
        ],
    },
    {
        "label": "P2 Pvt Ltd Maharashtra Food (Mumbai Tiffin)",
        "incorporation_days_ago": 365 * 3,
        "payload": {
            "name": "Mumbai Tiffin Pvt Ltd",
            "owner": "ceo@mumbaitiffin.example",
            "state": "Maharashtra",
            "industry": "food_services",
            "business_type": "pvt_ltd",
            "employee_count": 30,
            "annual_turnover_inr": 50_000_000,
            "registrations": ["GST", "FSSAI", "EPF", "ESI", "Shop_License"],
        },
        "needs_any_of": [
            ["GSTR", "GST"],
            ["EPF", "PF"],
            ["ESI"],
            ["FSSAI"],
        ],
        "must_not_contain": [
            "TNPCB",       # Tamil Nadu only
            "Form 11 LLP",
            "Form 8 LLP",
            "ITR-3 — Proprietorship",  # sole-prop specific
        ],
    },
    {
        "label": "P3 LLP Karnataka brand-new (QuickCode, 2mo old)",
        "incorporation_days_ago": 60,
        "payload": {
            "name": "QuickCode LLP",
            "owner": "founder@quickcode.example",
            "state": "Karnataka",
            "industry": "services",
            "business_type": "llp",
            "employee_count": 2,
            "annual_turnover_inr": 500_000,
            "registrations": ["GST"],
        },
        "needs_any_of": [
            ["GSTR", "GST"],   # GST registered → at least GST filings
        ],
        "must_not_contain": [
            "TNPCB",
            "Maharashtra",
            "AOC-4",  # Companies Act, LLP doesn't file this
            "MGT-7",
            "BEN-2",
            # NOTE: 2-month LLP shouldn't see annual filings yet (maturity gate)
        ],
        # Expectation: brand-new should have <= 25 obligations (age gating)
        "max_obligations": 25,
    },
    {
        "label": "P4 Large Pvt Ltd Gujarat Manufacturer (Surat Steel)",
        "incorporation_days_ago": 365 * 10,
        "payload": {
            "name": "Surat Steel Industries Pvt Ltd",
            "owner": "md@suratsteel.example",
            "state": "Gujarat",
            "industry": "manufacturing",
            "business_type": "pvt_ltd",
            "employee_count": 120,
            "annual_turnover_inr": 500_000_000,
            "registrations": ["GST", "EPF", "ESI", "Shop_License", "Trade_License"],
        },
        "needs_any_of": [
            ["GSTR", "GST"],
            ["EPF"],
            ["ESI"],
        ],
        "must_not_contain": [
            "TNPCB",
            "Tamil Nadu",
            "Form 11 LLP",
            "ITR-3 — Proprietorship",
        ],
    },
    {
        "label": "P5 Partnership Delhi E-commerce (DelhiKart Traders)",
        "incorporation_days_ago": 365 * 2,
        "payload": {
            "name": "DelhiKart Traders",
            "owner": "partners@delhikart.example",
            "state": "Delhi",
            "industry": "ecommerce",
            "business_type": "partnership",
            "employee_count": 12,
            "annual_turnover_inr": 18_000_000,
            "registrations": ["GST", "EPF", "ESI", "Shop_License"],
        },
        "needs_any_of": [
            ["GSTR", "GST"],     # GST registered
            ["EPF", "PF"],       # 12 employees → EPF
            ["ESI"],             # 12 employees → ESI
        ],
        "must_not_contain": [
            "TNPCB",             # Tamil Nadu only
            "Maharashtra",       # other state
            "Tamil Nadu",        # other state
            "AOC-",              # companies-act only
            "MGT-",              # companies-act only
            "Form 11 LLP",       # LLP only
            "ITR-3 — Proprietorship",  # sole-prop specific
        ],
    },
]


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
bugs: List[str] = []


def banner(text: str) -> None:
    print("\n" + "=" * 78)
    print(f"  {text}")
    print("=" * 78)


def sub(text: str) -> None:
    print(f"\n--- {text} ---")


def bug(text: str) -> None:
    bugs.append(text)
    print(f"  [BUG] {text}")


def ok(text: str) -> None:
    print(f"  [OK]  {text}")


# ---------------------------------------------------------------------------
# Per-persona flow
# ---------------------------------------------------------------------------
def run_persona(p: Dict) -> Dict[str, Any]:
    banner(p["label"])

    payload = dict(p["payload"])
    inc_date = (datetime.utcnow() - timedelta(days=p["incorporation_days_ago"])).date().isoformat()
    payload["incorporation_date"] = inc_date

    # ── 1. Create ────────────────────────────────────────────────────────────
    sub(f"POST /business  (incorporation_date={inc_date})")
    r = requests.post(f"{BASE}/business", json=payload, timeout=45)
    if r.status_code != 201:
        bug(f"{p['label']}: create returned {r.status_code} — {r.text[:200]}")
        return {}
    biz_id = r.json()["business_id"]
    summary = r.json()["dna_summary"]
    ok(f"created business_id={biz_id}  obligations={summary['total_obligations']}  high_severity={summary['high_severity_count']}")

    # ── 2. List obligations + expectation checks ─────────────────────────────
    sub("GET /obligations/{id}")
    r = requests.get(f"{BASE}/obligations/{biz_id}", timeout=30)
    if r.status_code != 200:
        bug(f"{p['label']}: GET obligations returned {r.status_code}")
        return {"biz_id": biz_id}
    obs = r.json().get("obligations", [])
    total = r.json().get("total", 0)
    ok(f"returned {len(obs)} of {total}  most-urgent: '{(obs[0]['name'] if obs else '?')}' decay={(obs[0].get('decay_score') if obs else '?')}")

    # Decay distribution sanity (no more than 40% urgent on a brand-new persona)
    urgent = sum(1 for o in obs if (o.get("decay_score") or 100) < 20)
    if obs and urgent / len(obs) > 0.4:
        bug(f"{p['label']}: {urgent}/{len(obs)} ({int(100*urgent/len(obs))}%) are urgent on day 1 — decay/stagger too aggressive")

    # Hard expectations
    names_lower = [o.get("name", "").lower() for o in obs]

    for needed_group in p.get("needs_any_of", []):
        if not any(any(token.lower() in n for token in needed_group) for n in names_lower):
            bug(f"{p['label']}: expected at least one of {needed_group} in obligation set, found none")
        else:
            ok(f"required category present: {needed_group[0]}")

    for forbidden in p.get("must_not_contain", []):
        leaks = [o["name"] for o in obs if forbidden.lower() in o["name"].lower()]
        if leaks:
            bug(f"{p['label']}: forbidden token '{forbidden}' found in {leaks[:3]}")
        else:
            ok(f"correctly absent: '{forbidden}'")

    max_oblig = p.get("max_obligations")
    if max_oblig and total > max_oblig:
        bug(f"{p['label']}: {total} obligations > expected max {max_oblig} (age gating may be loose)")

    # ── 3. Ripple check, legacy AND hybrid ───────────────────────────────────
    sub("POST /regulations/check-ripple  (legacy + hybrid)")
    for hybrid in (False, True):
        r = requests.post(
            f"{BASE}/regulations/check-ripple?hybrid={'true' if hybrid else 'false'}",
            json={
                "business_id": biz_id,
                "regulation_change": {
                    "title": "GST rate revised for food services and restaurants",
                    "affected_categories": ["taxation"],
                    "affected_registrations": ["GST"],
                },
            },
            timeout=60,
        )
        if r.status_code != 200:
            bug(f"{p['label']}: ripple hybrid={hybrid} returned {r.status_code}")
            continue
        rep = r.json()["ripple_report"]
        ok(f"ripple hybrid={hybrid}  method={rep.get('detection_method')}  direct={len(rep.get('directly_impacted', []))}  indirect={len(rep.get('indirectly_impacted', []))}  severity={rep.get('severity')}")

    # ── 4. Penalty preview + PDF + approve ───────────────────────────────────
    if obs:
        candidate = next((o for o in obs if o.get("status") in (None, "pending")), obs[0])
        iid = candidate["_id"]

        sub(f"GET /penalty-preview/{iid}  ({candidate['name'][:40]})")
        r = requests.get(f"{BASE}/penalty-preview/{iid}", timeout=15)
        if r.status_code != 200:
            bug(f"{p['label']}: penalty preview returned {r.status_code}")
        else:
            body = r.json()
            penalty = body.get("predicted_penalty_inr", 0)
            is_proj = body.get("is_projection")
            if penalty == 0:
                bug(f"{p['label']}: penalty preview returns ₹0 (should project even when not overdue)")
            else:
                ok(f"penalty ₹{penalty:,.0f} (projection={is_proj}) days={body.get('projected_days_late')}")

        sub(f"POST /draft/{iid}")
        r = requests.post(f"{BASE}/draft/{iid}", timeout=120)
        if r.status_code != 201:
            bug(f"{p['label']}: draft create returned {r.status_code} — {r.text[:200]}")
        else:
            d = r.json()
            tmpl = d.get("template_name", "")
            obl_name = candidate["name"]
            if "TDS" in tmpl and "TDS" not in obl_name:
                bug(f"{p['label']}: WRONG template '{tmpl}' for obligation '{obl_name}'")
            else:
                ok(f"draft template='{tmpl}'  fields={len(d.get('populated_fields', {}))}")
            if d.get("advisor_notes"):
                ok(f"advisor notes: documents={len(d['advisor_notes'].get('documents_required', []))}, checklist={len(d['advisor_notes'].get('filing_checklist', []))}")

        sub(f"GET /draft/{iid}/pdf")
        r = requests.get(f"{BASE}/draft/{iid}/pdf", timeout=60)
        if r.status_code != 200:
            bug(f"{p['label']}: PDF download returned {r.status_code}")
        else:
            head = r.content[:4]
            if head != b"%PDF":
                bug(f"{p['label']}: PDF magic bytes wrong — got {head!r}")
            else:
                ok(f"PDF generated ({len(r.content)} bytes, magic %PDF)")

        sub(f"POST /approve-draft/{iid}")
        r = requests.post(f"{BASE}/approve-draft/{iid}", json={"notes": "auto-approved by persona audit"}, timeout=15)
        if r.status_code != 200:
            bug(f"{p['label']}: approve-draft returned {r.status_code} — {r.text[:200]}")
        else:
            ok(f"approved  on_time={r.json().get('on_time')}")

    # ── 5. Filing history ────────────────────────────────────────────────────
    sub("GET /filing-history/{id}")
    r = requests.get(f"{BASE}/filing-history/{biz_id}", timeout=15)
    if r.status_code != 200:
        bug(f"{p['label']}: filing-history returned {r.status_code}")
    else:
        fh = r.json()
        ok(f"total_filings={fh.get('total_filings')}  on_time_rate={fh.get('on_time_rate')}")

    # ── 6. New aggregations: filing-summary + exposure ───────────────────────
    sub("GET /filing-summary/{id}")
    r = requests.get(f"{BASE}/filing-summary/{biz_id}", timeout=15)
    if r.status_code != 200:
        bug(f"{p['label']}: filing-summary returned {r.status_code}")
    else:
        s = r.json()
        ok(f"summary  total_filings={s.get('total_filings')}  on_time_rate={s.get('on_time_rate')}  by_category={len(s.get('by_category', []))}")

    sub("GET /exposure/{id}")
    r = requests.get(f"{BASE}/exposure/{biz_id}", timeout=15)
    if r.status_code != 200:
        bug(f"{p['label']}: exposure returned {r.status_code}")
    else:
        e = r.json()
        total_pending = e.get("total_pending", 0)
        total_exp = e.get("total_exposure_inr", 0)
        if obs and total_pending == 0:
            bug(f"{p['label']}: exposure says 0 pending but we have {len(obs)} obligations")
        else:
            ok(f"exposure ₹{total_exp:,.0f} across {total_pending} pending  buckets={list(e.get('by_urgency', {}).keys())}")

    # ── 7. Decay trend (Time Series read) ────────────────────────────────────
    sub("GET /decay-trend/{id}")
    r = requests.get(f"{BASE}/decay-trend/{biz_id}", timeout=15)
    if r.status_code != 200:
        bug(f"{p['label']}: decay-trend returned {r.status_code}")
    else:
        trends = r.json().get("trends", {})
        ok(f"trend series available for {len(trends)} obligations")

    # ── 8. Get + edit profile ────────────────────────────────────────────────
    sub(f"GET /business/{biz_id}")
    r = requests.get(f"{BASE}/business/{biz_id}", timeout=15)
    if r.status_code != 200:
        bug(f"{p['label']}: GET business returned {r.status_code}")
    else:
        biz = r.json()
        if biz.get("business_type") != p["payload"]["business_type"]:
            bug(f"{p['label']}: stored business_type {biz.get('business_type')!r} != sent {p['payload']['business_type']!r}")
        else:
            ok(f"business profile readback OK ({biz.get('business_type')}, {biz.get('state')})")

    sub(f"PATCH /business/{biz_id}  (bump employee_count)")
    new_count = p["payload"]["employee_count"] + 1
    r = requests.patch(f"{BASE}/business/{biz_id}", json={"employee_count": new_count}, timeout=15)
    if r.status_code != 200:
        bug(f"{p['label']}: PATCH business returned {r.status_code}")
    else:
        if r.json().get("employee_count") != new_count:
            bug(f"{p['label']}: PATCH did not persist employee_count")
        else:
            ok(f"profile updated to {new_count} employees")

    # ── 9. Atlas Search regulation finder ────────────────────────────────────
    sub("GET /search/regulations?q=GST")
    r = requests.get(f"{BASE}/search/regulations", params={"q": "GST"}, timeout=15)
    if r.status_code != 200:
        bug(f"{p['label']}: regulation search returned {r.status_code}")
    else:
        body = r.json()
        ok(f"regulation search method={body.get('method')}  results={body.get('count')}")
        if body.get("count", 0) == 0:
            bug(f"{p['label']}: regulation search for 'GST' returned zero results")

    # ── 10. RAG explain-regulation (Gemini, may 429) ─────────────────────────
    sub("POST /agent/explain-regulation")
    r = requests.post(
        f"{BASE}/agent/explain-regulation",
        json={"question": "What is GSTR-9 and when is it due?", "business_id": biz_id},
        timeout=60,
    )
    if r.status_code == 429:
        ok(f"RAG returned 429 cleanly (Gemini quota) — graceful")
    elif r.status_code != 200:
        bug(f"{p['label']}: explain-regulation returned {r.status_code} — {r.text[:200]}")
    else:
        body = r.json()
        ok(f"RAG  method={body.get('retrieval_method')}  citations={len(body.get('citations', []))}  answer_chars={len(body.get('answer', ''))}")

    # ── 11. Chat advisor one-shot ────────────────────────────────────────────
    sub("POST /chat/discover")
    r = requests.post(
        f"{BASE}/chat/discover",
        json={
            "business_id": biz_id,
            "messages": [{"role": "user", "content": "What obligations might I be missing?"}],
            "business_facts": {},
            "summarise": False,
        },
        timeout=60,
    )
    if r.status_code == 429:
        ok("chat/discover returned 429 cleanly (Gemini quota)")
    elif r.status_code != 200:
        bug(f"{p['label']}: chat/discover returned {r.status_code}")
    else:
        d = r.json()
        ok(f"chat reply_chars={len(d.get('reply', ''))}  discovered={len(d.get('discovered', []))}  suggestions={len(d.get('suggestions', []))}")

    # ── 12. Agent ask (multi-agent end-to-end) ──────────────────────────────
    sub("POST /agent/ask  (multi-agent planner)")
    r = requests.post(
        f"{BASE}/agent/ask",
        json={"business_id": biz_id, "question": "What's most urgent this week?"},
        timeout=180,
    )
    if r.status_code == 429:
        ok("agent/ask returned 429 cleanly (Gemini quota)")
    elif r.status_code != 200:
        bug(f"{p['label']}: agent/ask returned {r.status_code} — {r.text[:200]}")
    else:
        a = r.json()
        ok(f"agent answered  steps={a.get('step_count')}  answer_chars={len(a.get('answer', ''))}")

    # ── 13. Circular interpreter ─────────────────────────────────────────────
    sub("POST /circular/interpret")
    r = requests.post(
        f"{BASE}/circular/interpret",
        json={
            "business_id": biz_id,
            "circular_text": "CIRCULAR No. 207/2023-GST: GST rate revision for cloud kitchens. Effective 01-Apr-2024. Late fee Rs.50/day under Section 47.",
            "circular_source": "CBIC Circular 207/2023",
        },
        timeout=60,
    )
    if r.status_code == 429:
        ok("circular/interpret returned 429 cleanly (Gemini quota)")
    elif r.status_code != 200:
        bug(f"{p['label']}: circular/interpret returned {r.status_code} — {r.text[:200]}")
    else:
        ci = r.json()
        ok(f"circular interpreted  urgency={ci.get('urgency')}  applies={ci.get('applies_to_this_business')}  changes={len(ci.get('key_changes', []))}")

    # ── 14. Chat discoveries persistence ─────────────────────────────────────
    sub("GET /chat-discoveries/{business_id}")
    r = requests.get(f"{BASE}/chat-discoveries/{biz_id}", timeout=15)
    if r.status_code != 200:
        bug(f"{p['label']}: chat-discoveries returned {r.status_code}")
    else:
        ok(f"discoveries persisted: {len(r.json().get('discoveries', []))}")

    # ── 15. Confirm-obligations (review screen flow) ─────────────────────────
    sub("POST /business/{id}/confirm-obligations (trim to top 5)")
    keep_ids = [o["_id"] for o in obs[:5]]
    r = requests.post(
        f"{BASE}/business/{biz_id}/confirm-obligations",
        json={"keep_ids": keep_ids, "due_dates": {}},
        timeout=15,
    )
    if r.status_code != 200:
        bug(f"{p['label']}: confirm-obligations returned {r.status_code}")
    else:
        body = r.json()
        if body.get("kept") != len(keep_ids):
            bug(f"{p['label']}: confirm-obligations kept={body.get('kept')} != requested {len(keep_ids)}")
        else:
            ok(f"trimmed: kept={body.get('kept')}  removed={body.get('removed')}")

    # ── 16. Agent decisions audit log ────────────────────────────────────────
    sub("GET /agent-decisions/{business_id}")
    r = requests.get(f"{BASE}/agent-decisions/{biz_id}", timeout=15)
    if r.status_code != 200:
        bug(f"{p['label']}: agent-decisions returned {r.status_code}")
    else:
        decisions = r.json().get("decisions", [])
        if len(decisions) < 3:
            bug(f"{p['label']}: agent-decisions returned only {len(decisions)} entries — expected many more")
        else:
            ok(f"audit log: {len(decisions)} decisions captured")

    return {"biz_id": biz_id, "obligations": len(obs)}


# ---------------------------------------------------------------------------
# Cross-persona checks
# ---------------------------------------------------------------------------
def run_cascade_test(biz_ids: List[str]) -> None:
    banner("CROSS-PERSONA: multi-tenant ripple cascade")
    sub("POST /admin/ripple-cascade?hybrid=true")
    r = requests.post(
        f"{BASE}/admin/ripple-cascade",
        params={"hybrid": "true", "limit_businesses": "20"},
        json={
            "title": "GST rate revision for food services",
            "description": "GST rate revised for restaurant and cloud kitchen services under section 9(5)",
            "affected_categories": ["taxation", "food_safety"],
        },
        timeout=60,
    )
    if r.status_code == 429:
        bug("cascade returned 429 even though it shouldn't always hit Gemini — check rate-limit dependency")
    elif r.status_code != 200:
        bug(f"cascade returned {r.status_code} — {r.text[:200]}")
        return
    body = r.json()
    print(f"  evaluated={body.get('businesses_evaluated')}  affected={body.get('businesses_affected')}  elapsed_ms={body.get('elapsed_ms')}  hybrid={body.get('hybrid')}")
    for r_ in body.get("results", [])[:6]:
        print(f"    - {r_['business_name'][:30]:<30} state={r_['state']:<13} direct={r_['direct_count']:<3} indirect={r_['indirect_count']:<3} sev={r_['severity']}")
    if body.get("businesses_evaluated", 0) < len(biz_ids):
        bug(f"cascade evaluated {body.get('businesses_evaluated')} but we created {len(biz_ids)} personas this run")


def run_sse_handshake() -> None:
    banner("CROSS-PERSONA: SSE event stream handshake")
    sub("GET /events/stream?business_id=any")
    # SSE keeps the connection open forever — http.client.read(N) blocks
    # waiting for N bytes (or EOF) even if the first event was 80 bytes.
    # Use the underlying socket directly so we can read whatever's already
    # in the kernel buffer without waiting for more.
    try:
        import http.client
        host_port = BASE.replace("http://", "").split("/")[0]
        host, port = host_port.split(":") if ":" in host_port else (host_port, "80")
        conn = http.client.HTTPConnection(host, int(port), timeout=10)
        conn.request("GET", "/api/v1/events/stream?business_id=test_handshake")
        resp = conn.getresponse()
        if resp.status != 200:
            bug(f"SSE handshake returned HTTP {resp.status}")
            conn.close()
            return
        # Set a short timeout on the raw socket and read whatever's there
        sock = resp.fp.raw._sock  # type: ignore[attr-defined]
        sock.settimeout(3.0)
        try:
            chunk = sock.recv(512).decode("utf-8", "ignore")
        except (OSError, AttributeError) as exc:
            # Fall back to just confirming status 200 if socket access fails
            ok(f"SSE handshake HTTP 200 OK (raw read unavailable: {exc})")
            conn.close()
            return
        finally:
            conn.close()
        if "subscribed" in chunk:
            ok(f"SSE handshake OK: {chunk.strip()[:120]}")
        elif chunk:
            ok(f"SSE first packet received ({len(chunk)} chars): {chunk[:80]!r}")
        else:
            bug("SSE connection opened but no data received")
    except Exception as exc:
        bug(f"SSE handshake exception: {type(exc).__name__}: {exc}")


def run_atlas_search_aggregation_test() -> None:
    banner("INFRASTRUCTURE: aggregation pipelines")
    sub("GET /search/regulations/by-category")
    r = requests.get(f"{BASE}/search/regulations/by-category", timeout=15)
    if r.status_code != 200:
        bug(f"regulations by-category returned {r.status_code}")
        return
    body = r.json()
    cats = body.get("categories", [])
    total = body.get("total_regulations", 0)
    print(f"  category aggregation: {len(cats)} categories, {total} total regulations")
    for c in cats[:5]:
        print(f"    - {c['category']:<25} count={c['count']:<3} high_severity={c['high_severity']}")
    if total < 50:
        bug(f"only {total} regulations in corpus — expected ~90")


def run_admin_endpoints_test() -> None:
    banner("ADMIN: ripple-analytics + text circular ingestion")

    sub("GET /admin/ripple-analytics")
    r = requests.get(f"{BASE}/admin/ripple-analytics", timeout=15)
    if r.status_code != 200:
        bug(f"ripple-analytics returned {r.status_code}")
    else:
        body = r.json()
        ok(f"analytics  regulations={body.get('total_regulations')}  analytics_rows={len(body.get('analytics', []))}")

    sub("POST /admin/ingest-circular (text-only path)")
    r = requests.post(
        f"{BASE}/admin/ingest-circular",
        json={
            "source": "AUDIT TEST: CBIC notification dated 2026-05-30",
            "text": (
                "CIRCULAR No. AUDIT-1/2026-GST. Government of India, CBIC. "
                "Subject: Clarification on cloud-kitchen GST applicability. "
                "Effective from 01-Jun-2026. Late fee of Rs. 50 per day under Section 47 of CGST Act. "
                "All restaurant services supplied through electronic commerce operators "
                "shall be liable under Section 9(5)."
            ),
        },
        timeout=120,
    )
    if r.status_code == 429:
        ok("ingest-circular returned 429 cleanly (Gemini quota)")
    elif r.status_code != 200:
        bug(f"ingest-circular returned {r.status_code} — {r.text[:200]}")
    else:
        body = r.json()
        ok(f"ingested  reg_id={body.get('reg_id')}  category={body.get('category')}  businesses_affected={body.get('businesses_affected')}")


def run_proposed_flow_test() -> None:
    """Insert a fake 'proposed' obligation directly then exercise confirm + dismiss."""
    banner("PROPOSED OBLIGATION LIFECYCLE")
    # Easiest path: create a dummy business + manually insert a proposed
    # obligation via the chat advisor (which is wired to insert proposed
    # rows). Skipping the manual route here since /chat/discover already
    # inserts proposed rows when Gemini works; we just need to confirm the
    # endpoints respond.
    sub("POST /obligations/<bogus>/confirm (should 404, not 500)")
    r = requests.post(f"{BASE}/obligations/000000000000000000000000/confirm", timeout=15)
    if r.status_code not in (400, 404):
        bug(f"confirm bogus instance returned {r.status_code} — expected 4xx")
    else:
        ok(f"confirm bogus returned {r.status_code}")

    sub("DELETE /obligations/<bogus>/dismiss (should 404, not 500)")
    r = requests.delete(f"{BASE}/obligations/000000000000000000000000/dismiss", timeout=15)
    if r.status_code not in (400, 404):
        bug(f"dismiss bogus instance returned {r.status_code} — expected 4xx")
    else:
        ok(f"dismiss bogus returned {r.status_code}")


def run_validation_test() -> None:
    """Negative / boundary tests — these often surface bugs."""
    banner("VALIDATION & ERROR HANDLING")

    sub("GET /obligations/<not-an-objectid>  (should 400)")
    r = requests.get(f"{BASE}/obligations/not-an-objectid", timeout=15)
    if r.status_code not in (400, 404, 422):
        bug(f"bad business_id returned {r.status_code} — expected 4xx")
    else:
        ok(f"bad business_id returned {r.status_code}")

    sub("GET /penalty-preview/<not-an-objectid>  (should 400)")
    r = requests.get(f"{BASE}/penalty-preview/not-an-objectid", timeout=15)
    if r.status_code not in (400, 404, 422):
        bug(f"bad instance_id returned {r.status_code} — expected 4xx")
    else:
        ok(f"bad instance_id returned {r.status_code}")

    sub("POST /business with empty body  (should 422)")
    r = requests.post(f"{BASE}/business", json={}, timeout=15)
    if r.status_code != 422:
        bug(f"empty body create returned {r.status_code} — expected 422 validation error")
    else:
        ok("empty body correctly rejected with 422")

    sub("GET /search/regulations?q=a  (should 422 — min_length=2)")
    r = requests.get(f"{BASE}/search/regulations", params={"q": "a"}, timeout=15)
    if r.status_code != 422:
        bug(f"single-char search returned {r.status_code} — expected 422 (min_length=2)")
    else:
        ok("single-char search correctly rejected")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    banner("Backend health")
    try:
        h = requests.get(f"{BASE}/health", timeout=5).json()
        print(f"  {h}")
    except Exception as exc:
        print(f"  BACKEND DEAD: {exc}")
        return 1

    biz_ids: List[str] = []
    for p in PERSONAS:
        try:
            r = run_persona(p)
            if r.get("biz_id"):
                biz_ids.append(r["biz_id"])
            time.sleep(0.5)  # let Gemini cool a bit between personas
        except Exception as exc:
            bug(f"{p['label']}: hard exception — {type(exc).__name__}: {exc}")

    if biz_ids:
        run_cascade_test(biz_ids)

    run_sse_handshake()
    run_atlas_search_aggregation_test()
    run_admin_endpoints_test()
    run_proposed_flow_test()
    run_validation_test()

    banner(f"BUGS FOUND: {len(bugs)}")
    if not bugs:
        print("  No bugs.")
    for b in bugs:
        print(f"  * {b}")
    return len(bugs)


if __name__ == "__main__":
    sys.exit(main())
