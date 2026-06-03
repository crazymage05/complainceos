# ComplianceOS — AI Compliance Officer for Indian MSMEs

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python](https://img.shields.io/badge/Python-3.11-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688.svg)
![MongoDB Atlas](https://img.shields.io/badge/MongoDB-Atlas-47A248.svg)
![Atlas Vector Search](https://img.shields.io/badge/Atlas%20Vector%20Search-✓-47A248.svg)
![Atlas Search](https://img.shields.io/badge/Atlas%20Search-✓-47A248.svg)
![Time Series](https://img.shields.io/badge/Time%20Series-✓-47A248.svg)
![MongoDB MCP](https://img.shields.io/badge/MongoDB%20MCP-✓-47A248.svg)
![Gemini 2.0 Flash](https://img.shields.io/badge/Gemini-2.0%20Flash-4285F4.svg)
![Google ADK](https://img.shields.io/badge/Google%20ADK-2.0-34A853.svg)
![React](https://img.shields.io/badge/React-18-61DAFB.svg)

> **Built for:** [Google Cloud Rapid Agent Hackathon — MongoDB Partner Track](https://rapid-agent.devpost.com)
> **Submission deadline:** Jun 11, 2026 @ 2:00pm PDT

---

## The numbers

| Stat | Value | Source |
|---|---|---|
| MSMEs in India | **6.45 crore** | Govt. of India MSME Registry |
| Compliance obligations per business per year | **1,450+** | TeamLease RegTech 2025 |
| Regulatory updates per day | **42** | TeamLease RegTech 2025 |
| Average annual compliance cost per MSME | **₹13–17 lakh** | TeamLease RegTech 2025 |
| Penalties collected from MSMEs annually | **₹89,000 crore** | India Economic Survey |
| Imprisonment clauses in labour law alone | **486** | TeamLease RegTech 2025 |
| Global RegTech market size by 2032 | **$82.7 billion** | Industry analysis |

**The gap:** Drata, Vanta, Sprinto cost ₹10–100 lakh/year (enterprise). ClearTax, Zoho are accounting tools, not compliance agents. **No autonomous compliance agent exists at the ₹500/month price point.** That's the market.

---

## What ComplianceOS does

ComplianceOS is a **multi-agent compliance officer** that:

1. **Builds a Compliance DNA** for your business — unique obligation set matched against 90 Indian regulations by state, entity type, age, industry, headcount, turnover, and registrations
2. **Decay-scores every obligation** — a composite urgency metric (0–100) blending time-to-deadline × complexity × penalty severity × your personal filing history
3. **Detects regulatory ripples** — when a new circular drops, Atlas Vector Search finds which of YOUR obligations are affected
4. **Predicts penalties to the rupee** — entity-specific forecasts based on size, turnover, days late, and repeat-offender history
5. **Auto-drafts filings** — pre-populated PDFs with category-specific advisor notes (documents needed, common mistakes, checklist)
6. **Discovers hidden obligations** — a conversational advisor surfaces POSH, MPCB consent, e-commerce TCS, fire NOC, etc.
7. **Explains its reasoning** — a Compliance Officer agent delegates to 6 specialist sub-agents and streams every thought to the UI

All for **₹500/month** instead of a **₹5 lakh/year** CA retainer.

---

## Multi-agent architecture

```
              ┌─────────────────────────────┐
              │  Compliance Officer (root)  │  ← Gemini 2.0 Flash via ADK 2.0
              │     Planner + Router        │
              └──────────────┬──────────────┘
                             │ delegates to
        ┌───────┬───────┬────┴────┬───────┬─────────┐
        ▼       ▼       ▼         ▼       ▼         ▼
     DNA    Decay   Ripple    Penalty  Drafter   Advisor
     Agent  Agent   Agent     Agent    Agent     Agent
        │       │       │         │       │         │
        ▼       ▼       ▼         ▼       ▼         ▼
     ┌──────────────────────────────────────────────────┐
     │     7 domain tools (engines/* wrapped)           │
     │  list_obligations · explain_decay_score          │
     │  predict_penalty_for · detect_regulation_impact  │
     │  discover_hidden_obligations · generate_draft    │
     │  get_filing_track_record                         │
     └──────────────────┬───────────────────────────────┘
                        │
                        ▼
        ┌────────────────────────────────────┐
        │  MongoDB Atlas (via MCP Server)    │
        ├────────────────────────────────────┤
        │  • businesses                      │
        │  • regulatory_corpus (vector idx)  │
        │  • obligation_instances            │
        │  • regulatory_changes              │
        │  • penalty_rules                   │
        │  • filing_templates                │
        │  • filing_history                  │
        │  • agent_decisions (audit log)     │
        │  • chat_discoveries                │
        │  • decay_score_snapshots ⏱ TS      │
        │  • regulatory_fetch_log            │
        └────────────────────────────────────┘
```

Every reasoning step writes to `agent_decisions` for auditability and streams to the dashboard's **Compliance Officer** tab in real time.

---

## MongoDB Atlas features used

| Feature | Where | Why |
|---|---|---|
| **Document database (Atlas)** | All 11 collections | Source of truth for the agent's persistent memory |
| **MCP Server** | `agent/complianceos_agent.py` + ADK MCPToolset | Gives Gemini direct CRUD access to MongoDB |
| **Atlas Vector Search** | `engines/ripple_detector.py` + `regulation_embedding_index` | Semantic ripple detection — find obligations affected by a new circular |
| **Atlas Search ($search)** | `routers/search.py` — full-text regulation finder | Lexical lookup over 90 regulations from the dashboard search bar |
| **Time Series collection** | `decay_score_snapshots` | 30-day decay sparklines on every obligation card |
| **Aggregation pipelines** | `/admin/ripple-analytics`, `/exposure/{id}`, `/filing-summary/{id}`, `/search/regulations/by-category` | Exec dashboards & per-category breakdowns |

---

## Stack

| Layer | Technology |
|---|---|
| Agent brain | **Gemini 2.0 Flash** (Google AI Studio free tier) |
| Agent framework | **Google Agent Development Kit (ADK) 2.0** |
| Agent runtime | ADK `Runner` with `InMemorySessionService` |
| Partner integration | **MongoDB Atlas MCP Server** (`npx mongodb-mcp-server`) |
| Backend | Python 3.11 + FastAPI + Motor (async MongoDB) |
| Database | MongoDB Atlas (free tier, 512 MB) |
| Frontend | React 18 + TypeScript + Tailwind + Vite |
| Auth | Firebase Authentication (Google sign-in) |
| Streaming | Server-Sent Events for reasoning trace |
| PDF generation | ReportLab |
| Deploy (backend) | Railway |
| Deploy (frontend) | Vercel |

---

## API surface

### Agent endpoints (the wow tier)

| Method | Path | What it does |
|---|---|---|
| `POST` | `/api/v1/agent/ask` | Run the multi-agent officer, return the final answer + full reasoning trace |
| `POST` | `/api/v1/agent/stream` | Server-Sent Events stream of reasoning steps in real time |

### Engine endpoints

| Method | Path | What it does |
|---|---|---|
| `POST` | `/api/v1/business` | Create business + run DNA Builder |
| `GET` | `/api/v1/business/{id}` | Read business profile |
| `PATCH` | `/api/v1/business/{id}` | Edit business profile |
| `POST` | `/api/v1/business/{id}/confirm-obligations` | Customise & set due dates |
| `GET` | `/api/v1/obligations/{id}` | All obligations with live decay scores |
| `POST` | `/api/v1/regulations/check-ripple` | Vector-search-based ripple detection |
| `GET` | `/api/v1/penalty-preview/{instance_id}` | Predicted penalty |
| `POST` | `/api/v1/draft/{instance_id}` | Generate filing draft + advisor notes |
| `GET` | `/api/v1/draft/{instance_id}/pdf` | Download draft as a real PDF |
| `POST` | `/api/v1/approve-draft/{instance_id}` | Mark filed, write to filing history |
| `POST` | `/api/v1/chat/discover` | Conversational hidden-obligation discovery |
| `POST` | `/api/v1/circular/interpret` | Plain-language analysis of a circular |
| `GET` | `/api/v1/filing-history/{id}` | Full filing history with on-time rate |
| `GET` | `/api/v1/filing-summary/{id}` | Aggregation: on-time/late breakdown per category |
| `GET` | `/api/v1/exposure/{id}` | Aggregation: total ₹ penalty exposure |
| `GET` | `/api/v1/decay-trend/{id}` | 30-day decay history per obligation (Time Series) |
| `GET` | `/api/v1/search/regulations` | Atlas Search full-text regulation finder |
| `GET` | `/api/v1/search/regulations/by-category` | Aggregation: count regulations per category |
| `POST` | `/api/v1/admin/ingest-circular` | Embed + ripple across every business |
| `GET` | `/api/v1/admin/ripple-analytics` | Cross-business ripple aggregation |
| `GET` | `/api/v1/agent-decisions/{id}` | Audit log of every agent decision |

---

## Frontend routes

| Route | Screen |
|---|---|
| `/` | Landing page (signed-out) / route to dashboard (signed-in) |
| `/welcome` | Public marketing page |
| `/login` | Google sign-in |
| `/onboarding` | 6-question business profile form |
| `/review` | AI-generated obligation review — customise & set due dates |
| `/dashboard` | Main compliance dashboard (7 tabs) |

**Dashboard tabs:** Overview · **Compliance Officer (the multi-agent panel)** · Obligations · Calendar · Ripple Alerts · Cascade Demo · Documents · History · AI Advisor · Audit Log · Profile.

---

## Set-up

### Prerequisites

- Python 3.11+
- Node.js 18+
- MongoDB Atlas account ([cloud.mongodb.com](https://cloud.mongodb.com))
- Gemini API key ([Google AI Studio](https://aistudio.google.com))
- Firebase project with Google Auth enabled

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Fill in MONGODB_URI, GEMINI_API_KEY, etc.
python db/seed_corpus.py     # seeds 90 regulations + 26 penalty rules + 10 templates
uvicorn main:app --reload    # → http://localhost:8000
# OpenAPI docs at http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
# Fill in VITE_API_URL + Firebase config
npm run dev                  # → http://localhost:3000
```

### Deployment

See **[DEPLOY.md](./DEPLOY.md)** for the full production runbook — frontend → Vercel, backend → Railway, plus the MongoDB Atlas Network Access, CORS, and Firebase authorized-domain steps.

### Atlas Vector Search index

Create in MongoDB Atlas UI → Search → Create Index → Vector Search:

```json
{
  "name": "regulation_embedding_index",
  "type": "vectorSearch",
  "definition": {
    "fields": [{
      "type": "vector",
      "path": "embedding",
      "numDimensions": 3072,
      "similarity": "cosine"
    }]
  }
}
```

### Optional — Atlas Search index for full-text regulation lookup

```json
{
  "name": "regulation_text_search",
  "mappings": {
    "dynamic": false,
    "fields": {
      "name": { "type": "string" },
      "deadline_rule": { "type": "string" },
      "source": { "type": "string" },
      "category": { "type": "string" }
    }
  }
}
```

Falls back to `$regex` if absent — the endpoint stays functional on any Atlas tier.

---

## Tests

```bash
cd backend
pytest -q                      # 42 unit tests covering decay, penalty, DNA, ripple, agent answer extraction
python _persona_full_audit.py  # end-to-end audit across 5 business personas (needs a running server)
```

GitHub Actions runs `pytest` + `tsc && vite build` on every push.

---

## What's novel in the code

1. **Decay score with overdue compounding** — most "urgency scores" go to zero past the deadline; ours degrades using actual ₹/day penalty accrual ([engines/decay_score.py](backend/engines/decay_score.py))
2. **Age-gated DNA matching** — a 2-month-old LLP doesn't see annual filings it isn't due yet for ([engines/dna_builder.py](backend/engines/dna_builder.py))
3. **Entity-type post-filter** — a sole proprietor never sees Companies Act filings even if the seed corpus didn't tag them
4. **Vector-search with graceful category fallback** — production-grade graceful degradation ([engines/ripple_detector.py](backend/engines/ripple_detector.py))
5. **Multi-agent reasoning with streaming trace** — every ADK sub-agent call surfaces in the UI ([agent/runner.py](backend/agent/runner.py))
6. **Category-specific Gemini fallbacks** — when the LLM 429s, the user still gets useful advisor content for 6 compliance categories ([engines/auto_draft.py](backend/engines/auto_draft.py))
7. **Per-business decay personalisation** — complexity drops as the user files on time, severity grows as they file late
8. **Audit log on every action** — `agent_decisions` collection records every reasoning trace for replayability

---

## License

MIT License — Copyright © 2026 Manoj Kumar S
