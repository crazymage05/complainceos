"""
End-to-end persona walkthrough — simulates the full user flow for 4 different
MSME archetypes against the live backend. Reports every quirk, bug, or
suspicious output for follow-up.

Run with backend up:
    python _persona_test.py
"""

import json
import sys
import time
from datetime import datetime, timedelta

import requests

BASE = "http://127.0.0.1:8000/api/v1"


def banner(text: str) -> None:
    print()
    print("=" * 78)
    print(f"  {text}")
    print("=" * 78)


def sub(text: str) -> None:
    print(f"\n--- {text} ---")


def jq(obj, indent=2):
    print(json.dumps(obj, indent=indent, default=str, ensure_ascii=False)[:2000])


PERSONAS = [
    {
        "label": "P1 SoleProp Tamil Nadu Retail",
        "incorporation_days_ago": 365 * 5,  # 5 years old
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
    },
    {
        "label": "P2 Pvt Ltd Maharashtra Food",
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
    },
    {
        "label": "P3 LLP Karnataka brand-new (2 months old — age gating test)",
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
    },
    {
        "label": "P4 Large Pvt Ltd Gujarat Manufacturer",
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
    },
]


bugs: list[str] = []


def record(msg: str) -> None:
    bugs.append(msg)
    print(f"  [BUG] {msg}")


def run_persona(p: dict) -> dict:
    banner(p["label"])
    payload = dict(p["payload"])
    inc_date = (datetime.utcnow() - timedelta(days=p["incorporation_days_ago"])).date().isoformat()
    payload["incorporation_date"] = inc_date

    # ── 1. Create business ────────────────────────────────────────────────────
    sub(f"POST /business  (incorporation_date={inc_date})")
    r = requests.post(f"{BASE}/business", json=payload, timeout=30)
    if r.status_code != 201:
        record(f"{p['label']}: POST /business returned {r.status_code} -- {r.text[:300]}")
        return {}
    body = r.json()
    biz_id = body["business_id"]
    total = body["dna_summary"]["total_obligations"]
    print(f"  business_id={biz_id}  obligations={total}  high_severity={body['dna_summary']['high_severity_count']}")

    if p["incorporation_days_ago"] < 90 and total > 25:
        record(f"{p['label']}: 2-month-old LLP got {total} obligations -- age gating may be loose")
    if total == 0:
        record(f"{p['label']}: zero obligations generated -- check applicability rules")

    # ── 2. Get obligations ────────────────────────────────────────────────────
    sub("GET /obligations/{id}")
    r = requests.get(f"{BASE}/obligations/{biz_id}", timeout=30)
    if r.status_code != 200:
        record(f"{p['label']}: GET /obligations returned {r.status_code}")
        return {"biz_id": biz_id}
    obs = r.json()["obligations"]
    print(f"  returned {len(obs)} obligations (total={r.json().get('total')})")
    if obs:
        first = obs[0]
        print(f"  most urgent: {first.get('name')} [score={first.get('decay_score')}, urgency={first.get('urgency')}]")

    # Sanity checks
    seen_categories = {o.get("category") for o in obs}
    print(f"  categories present: {sorted(seen_categories)}")

    # Sole prop should NOT see Pvt Ltd / LLP filings
    if "sole" in p["label"].lower() or "soleprop" in p["label"].lower():
        bad = [o["name"] for o in obs if any(
            tok in o.get("name", "").lower() for tok in (
                "aoc-4", "moa", "aoa", "form 11 llp", "form 8 llp",
                "din-3", "form mgt", "form adt"
            )
        )]
        if bad:
            record(f"{p['label']}: sole prop showing company/LLP filings: {bad[:5]}")

    # Pvt Ltd should see at least one Companies Act / corporate item
    if "pvt ltd" in p["label"].lower():
        ca = [o for o in obs if o.get("category") in ("companies_act", "corporate")]
        if not ca:
            record(f"{p['label']}: Pvt Ltd missing Companies Act/corporate filings entirely")

    # State-specific leakage: TNPCB (Tamil Nadu Pollution Control Board) must
    # never appear for businesses outside Tamil Nadu.
    state = p["payload"]["state"]
    if state != "Tamil Nadu":
        tn_leaks = [o["name"] for o in obs if "TNPCB" in o.get("name", "")
                    or "Tamil Nadu" in o.get("name", "")]
        if tn_leaks:
            record(f"{p['label']} (state={state}): Tamil Nadu-only filings leaked: {tn_leaks[:3]}")

    # Conditional filings should not appear as periodic obligations
    conditional_leaks = [o["name"] for o in obs if any(
        token in o.get("name", "") for token in (
            "RFD-01", "Refund Application", "SH-7", "Authorized Share Capital",
            "INC-22", "Registered Office",
        )
    )]
    if conditional_leaks:
        record(f"{p['label']}: conditional filings appearing as periodic: {conditional_leaks[:3]}")

    # Decay-score distribution sanity: a brand-new business shouldn't have
    # half of its obligations marked urgent. Expect at most ~25% urgent.
    if obs:
        urgent = sum(1 for o in obs if (o.get("decay_score") or 0) < 20)
        pct = urgent / len(obs)
        if pct > 0.4:
            record(f"{p['label']}: {urgent}/{len(obs)} ({pct:.0%}) urgent — decay scoring may be miscalibrated")


    # No template should ever come back as "TDS Return Form 26Q" unless the
    # underlying obligation actually IS the TDS return.


    # ── 3. Ripple check ──────────────────────────────────────────────────────
    sub("POST /regulations/check-ripple  (GST rate change)")
    r = requests.post(f"{BASE}/regulations/check-ripple", json={
        "business_id": biz_id,
        "regulation_change": {
            "title": "GST rate revised for retail and food services under QRMP scheme",
            "affected_categories": ["taxation"],
            "affected_registrations": ["GST"],
        },
    }, timeout=60)
    if r.status_code != 200:
        record(f"{p['label']}: ripple check returned {r.status_code} -- {r.text[:200]}")
    else:
        rep = r.json()["ripple_report"]
        print(f"  detection={rep.get('detection_method')} direct={len(rep.get('directly_impacted', []))} "
              f"indirect={len(rep.get('indirectly_impacted', []))} severity={rep.get('severity')}")
        if rep.get("detection_method") == "category_match":
            print("  note: vector search did not return results, fell back to category match")

    # ── 4. Penalty preview on the most urgent ────────────────────────────────
    if obs:
        sub(f"GET /penalty-preview/{obs[0]['_id']}")
        r = requests.get(f"{BASE}/penalty-preview/{obs[0]['_id']}", timeout=15)
        if r.status_code == 200:
            jq(r.json())
        else:
            record(f"{p['label']}: penalty-preview returned {r.status_code} -- {r.text[:200]}")

    # ── 5. Auto-draft generation on a draftable obligation ────────────────────
    if obs:
        candidate = next((o for o in obs if o.get("status") in (None, "pending")), obs[0])
        sub(f"POST /draft/{candidate['_id']}  ({candidate.get('name', '?')[:50]})")
        r = requests.post(f"{BASE}/draft/{candidate['_id']}", timeout=120)
        if r.status_code == 201:
            d = r.json()
            tmpl = d.get("template_name", "")
            print(f"  template={tmpl} fields={len(d.get('populated_fields', {}))}")
            obl_name = candidate.get("name", "")
            # Coarse sanity: TDS template should only appear for TDS-related obligations
            if "TDS" in tmpl and "TDS" not in obl_name and "26Q" not in obl_name:
                record(f"{p['label']}: wrong template '{tmpl}' for obligation '{obl_name}'")
            notes = d.get("advisor_notes") or {}
            if notes:
                print(f"  advisor: documents={len(notes.get('documents_required', []))} "
                      f"checklist={len(notes.get('filing_checklist', []))} "
                      f"risk={notes.get('risk_level')}")
            # ── 6. Approve the draft ─────────────────────────────────────────
            sub(f"POST /approve-draft/{candidate['_id']}")
            r2 = requests.post(f"{BASE}/approve-draft/{candidate['_id']}",
                               json={"notes": "approved by automated persona test"}, timeout=15)
            if r2.status_code == 200:
                print(f"  approved -- on_time={r2.json().get('on_time')}")
            else:
                record(f"{p['label']}: approve-draft returned {r2.status_code} -- {r2.text[:200]}")
        elif r.status_code == 422:
            print(f"  draft skipped (template missing for regulation_id={candidate.get('regulation_id')})")
        else:
            record(f"{p['label']}: draft returned {r.status_code} -- {r.text[:200]}")

    # ── 7. Filing history ────────────────────────────────────────────────────
    sub("GET /filing-history/{id}")
    r = requests.get(f"{BASE}/filing-history/{biz_id}", timeout=15)
    if r.status_code == 200:
        fh = r.json()
        print(f"  total_filings={fh.get('total_filings')} on_time_rate={fh.get('on_time_rate')}")
    else:
        record(f"{p['label']}: filing-history returned {r.status_code}")

    # ── 8. AI Advisor chat (one turn) ────────────────────────────────────────
    sub("POST /chat/discover  (one turn)")
    r = requests.post(f"{BASE}/chat/discover", json={
        "business_id": biz_id,
        "messages": [{"role": "user", "content": "What obligations might I be missing?"}],
        "business_facts": {},
        "summarise": False,
    }, timeout=60)
    if r.status_code == 200:
        cr = r.json()
        print(f"  reply length={len(cr.get('reply', ''))} discovered={len(cr.get('discovered', []))} "
              f"suggestions={len(cr.get('suggestions', []))}")
        if cr.get("discovered"):
            for d in cr["discovered"][:3]:
                print(f"    + {d.get('name')} ({d.get('category')}/{d.get('urgency')})")
    else:
        record(f"{p['label']}: chat/discover returned {r.status_code} -- {r.text[:200]}")

    # ── 9. Agent decisions log ───────────────────────────────────────────────
    sub("GET /agent-decisions/{id}")
    r = requests.get(f"{BASE}/agent-decisions/{biz_id}", timeout=15)
    if r.status_code == 200:
        ad = r.json()
        print(f"  decisions logged: {ad.get('count')}")
    else:
        record(f"{p['label']}: agent-decisions returned {r.status_code}")

    return {"biz_id": biz_id, "obligations": len(obs)}


def main():
    # Health
    banner("Backend health")
    r = requests.get(f"{BASE}/health", timeout=5)
    print(f"  {r.status_code} {r.json()}")

    summary = []
    for p in PERSONAS:
        try:
            res = run_persona(p)
            summary.append((p["label"], res))
        except Exception as exc:
            record(f"{p['label']}: hard exception -- {type(exc).__name__}: {exc}")
        time.sleep(0.5)  # let Gemini cool

    banner("SUMMARY")
    for label, res in summary:
        print(f"  {label}  ->  {res.get('obligations', '?')} obligations")

    banner(f"BUGS FOUND  ({len(bugs)})")
    for b in bugs:
        print(f"  * {b}")
    return len(bugs)


if __name__ == "__main__":
    sys.exit(main())
