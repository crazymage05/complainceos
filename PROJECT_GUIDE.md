# ComplianceOS — The Complete Project Guide

> One document that explains *everything*: what it is, how to use it page by page, what happens under the hood on each screen, the tech behind it, and a ready-to-read presentation script. Written for both non-technical and technical readers.

---

## Table of contents
1. [The 30-second pitch](#1-the-30-second-pitch)
2. [The problem we solve](#2-the-problem-we-solve)
3. [How to approach the app (the user journey)](#3-how-to-approach-the-app-the-user-journey)
4. [Every page & tab — what you see and what happens under the hood](#4-every-page--tab)
5. [The 5 core capabilities (the novelty), explained](#5-the-5-core-capabilities)
6. [How it's built (architecture & data flow)](#6-how-its-built)
7. [How we use MongoDB Atlas (depth)](#7-how-we-use-mongodb-atlas)
8. [The AI agent (multi-agent + ADK + MCP)](#8-the-ai-agent)
9. [Presentation / demo script](#9-presentation--demo-script)
10. [FAQ & gotchas](#10-faq--gotchas)

---

## 1. The 30-second pitch

**ComplianceOS is an AI compliance officer for small Indian businesses.** You tell it about your business once; it figures out every government rule you must follow, tells you what's urgent, warns you before deadlines, predicts the exact penalty if you miss one, fills out the filing forms for you, and explains everything in plain language. It replaces a ₹5 lakh/year compliance consultant with a ₹500/month AI agent.

**In one line for judges:** *An autonomous Gemini agent, orchestrated with Google ADK and grounded entirely in MongoDB Atlas (Vector Search, Atlas Search, Time Series, Change Streams, and the MongoDB MCP Server), that builds a unique "Compliance DNA" per business and proactively manages its regulatory obligations.*

---

## 2. The problem we solve

A single small business in India faces:
- **1,450+ compliance obligations a year** across 7 categories of law
- **42 new regulatory updates published every single day**
- **₹13–17 lakh/year** average compliance cost
- **486 imprisonment clauses** (many for simple paperwork lapses)

Existing tools don't fit: Drata/Vanta/Sprinto are enterprise (₹10–100 lakh/yr); ClearTax/Zoho are accounting tools, not compliance agents. **Nobody serves a 5-person shop at ₹500/month.** That's the gap ComplianceOS fills.

---

## 3. How to approach the app (the user journey)

The app is a **funnel**: a visitor becomes a user in under 2 minutes, then lives on the dashboard.

```
Landing  →  Login (Google)  →  Onboarding (6 questions)  →  Review obligations  →  Dashboard (daily home)
```

| Step | What the user does | What they get |
|---|---|---|
| **Landing** | Reads the pitch, clicks "Sign in" | Understands the value |
| **Login** | Signs in with Google | Secure account (Firebase) |
| **Onboarding** | Answers 6 questions about the business | Triggers "Compliance DNA" generation |
| **Review** | Confirms / unchecks obligations, sets due dates | A personalised compliance plan |
| **Dashboard** | Returns daily to act on what's urgent | Scores, alerts, penalties, drafts |

**Mental model for the user:** *"Tell it about me once → it watches everything → I just act on what it flags."*

---

## 4. Every page & tab

For each screen below: **What you see** (user view) → **What happens under the hood** (tech).

### 🟢 Landing page  · `Landing.tsx`
- **See:** the hook ("Indian businesses owe more in penalties than income tax"), the hard stats, before/after comparison, the 6 capabilities, the tech stack, and a call-to-action.
- **Under the hood:** a static React marketing page. No backend calls. Routes to `/login` (or `/dashboard` if already signed in).

### 🔐 Login  · `Login.tsx`
- **See:** "Continue with Google" button on a dark card.
- **Under the hood:** **Firebase Authentication** opens a Google OAuth popup. On success, `App.tsx`'s `onAuthChange` listener fires; if the user has no `business_id` in local storage, they're routed to onboarding, otherwise to the dashboard. Every backend request after this carries the Firebase ID token (the backend can require it by flipping `REQUIRE_AUTH`).

### 📝 Onboarding  · `Onboarding.tsx`
- **See:** a 6-field form — business name, owner, type (proprietorship/partnership/Pvt Ltd/LLP), state, industry, employees, turnover, start date, and existing registrations (GST, FSSAI, EPF, ESI, etc.).
- **Under the hood:** submitting calls **`POST /api/v1/business`**, which runs the **Compliance DNA Builder** (`engines/dna_builder.py`):
  1. Queries the **`regulatory_corpus`** (≈90 Indian regulations) in MongoDB.
  2. Filters by industry, state (so Tamil Nadu rules don't leak into a Delhi business), required registrations, employee/turnover thresholds, **and business age** (a 2-month-old LLP doesn't get annual filings it isn't due for yet) **and entity type** (a sole proprietor never sees Companies Act forms).
  3. Creates one **`obligation_instance`** per matched rule with a due date staggered so the dashboard isn't all-red on day one.
  4. Returns a DNA summary ("47 obligations, 12 high-severity").

### ✅ Review Obligations  · `ReviewObligations.tsx`
- **See:** the generated obligations grouped by category (GST, Labour, Food Safety…), each with a checkbox and an editable due date. Uncheck anything that doesn't apply.
- **Under the hood:** loads **`GET /obligations/{id}`**; on confirm calls **`POST /business/{id}/confirm-obligations`** with the kept IDs and custom dates. This is the "human-in-the-loop" step — the AI proposes, the owner disposes.

### 📊 Dashboard  · `Dashboard.tsx`
The daily home. A **left sidebar** navigates between pages; each page is distinct. On load it fires ~7 parallel reads (obligations, filing history, exposure, decay trend, health score, forecast, benchmark) and opens a live **Server-Sent Events** stream for real-time updates.

#### • Overview
- **See:** the **Compliance Health Score** ring (0–100), the **Total Penalty Exposure** banner (what you'd owe if you missed everything), a **30/60/90-day penalty forecast**, a **peer benchmark**, KPI cards (total obligations, high-severity, due-this-week, on-time rate), the most urgent items, and a quick "check a regulation change" box.
- **Under the hood:** `GET /health-score` (composite of 4 dimensions), `GET /exposure` (aggregation summing penalties by urgency), `GET /exposure-forecast` (projection over **Time Series** snapshots), `GET /benchmark` (`$facet`/`$group` aggregation across similar businesses).

#### • Compliance Officer  *(the showcase)*
- **See:** a chat. Ask "What's most urgent this week?" and watch the agent **think step by step**, then give a plain-English answer.
- **Under the hood:** **`POST /agent/stream`** runs the **Google ADK multi-agent** (`agent/sub_agents.py`): a root **planner** delegates to 6 specialists (DNA, Decay, Ripple, Penalty, Drafter, Advisor), each with its own tool that wraps an engine and reads MongoDB. Every reasoning step streams to the UI and is logged to `agent_decisions`. (Uses Gemini; shows a friendly "busy, retrying" if Gemini is overloaded.)

#### • Obligations
- **See:** every obligation as a card with a **decay score** dial (red/amber/green), days left, predicted penalty, and "Prepare Draft"/"Explain" buttons. Filter by All/Urgent/Warning/Proposed.
- **Under the hood:** `GET /obligations/{id}`; each card's score comes from the **Decay Score engine**. "Proposed" items (discovered by the AI Advisor) can be confirmed or dismissed.

#### • Calendar
- **See:** upcoming deadlines grouped by month on a timeline, colour-coded by urgency.
- **Under the hood:** client-side grouping of the obligations by due date.

#### • Ripple Alerts
- **See:** paste/pick a regulation change → the agent shows which of *your* obligations it affects (direct vs indirect) and the severity.
- **Under the hood:** **`POST /regulations/check-ripple`** → **Ripple Detector** (`engines/ripple_detector.py`): embeds the change with Gemini, runs **Atlas Vector Search** + **Atlas Search**, fuses them with **Reciprocal Rank Fusion**, classifies direct/indirect.

#### • Cascade Demo
- **See:** one regulation change evaluated across *every* business in the platform at once, with a results table.
- **Under the hood:** **`POST /admin/ripple-cascade`** runs the ripple detector concurrently over all businesses — demonstrates MongoDB as a multi-tenant brain.

#### • Documents
- **See:** auto-generated filing drafts with pre-filled fields, an advisor checklist (documents needed, common mistakes), a **Download PDF** button, and **Approve & File**.
- **Under the hood:** **`POST /draft/{id}`** → **Auto-Draft engine** maps business data into the filing template and asks Gemini for filing advice (falls back to curated category defaults if Gemini is rate-limited). **`GET /draft/{id}/pdf`** renders a real PDF (ReportLab). **`POST /approve-draft`** writes to `filing_history`.

#### • History
- **See:** past filings, on-time rate, penalties paid/avoided.
- **Under the hood:** `GET /filing-history/{id}`.

#### • AI Advisor
- **See:** a conversational interview that uncovers **non-obvious** obligations (POSH committee, fire NOC, e-commerce TCS, pollution consent…) and adds them as proposals.
- **Under the hood:** **`POST /chat/discover`** → `engines/obligation_chat.py` (Gemini), discoveries saved to `chat_discoveries` and surfaced as "proposed" obligations.

#### • Audit Log
- **See:** every autonomous action the agent took, with the ability to **replay** a past decision against today's data and see the diff.
- **Under the hood:** `GET /agent-decisions/{id}/by-action`; **`POST /agent-decisions/replay/{id}`** re-runs a stored decision and diffs old vs current output.

#### • Profile
- **See:** your business identity, Compliance DNA version, full details, registration chips, and Edit / Sign-out.
- **Under the hood:** `GET /business/{id}`; Edit opens a modal that `PATCH`es the business and re-computes the DNA.

---

## 5. The 5 core capabilities

These are the patent-worthy methods — each is implemented, not just described.

1. **Compliance DNA** (`dna_builder.py`) — auto-generates a *unique* obligation set from entity attributes, with age gating, entity-type and state filtering, and registration gating. *Novel because:* others give generic per-industry checklists; we compute a per-entity set and re-compute it when attributes change.

2. **Regulatory Decay Score** (`decay_score.py`) — a composite 0–100 urgency score = time-to-deadline × complexity × penalty severity × *your* on-time history, with overdue penalty-accrual modelling and per-business learning (complexity drops as you file on time, severity grows as you file late). *Novel because:* others show binary due/overdue; we rank with a learned, multi-factor score.

3. **Ripple Detection** (`ripple_detector.py` + `hybrid_search.py`) — finds which of *your* obligations a new regulation hits, via **hybrid Vector + Atlas Search fused with RRF**. *Novel because:* others send "new regulation" alerts; we trace the downstream impact for a specific business.

4. **Penalty Prediction** (`penalty_predictor.py`) — entity-specific rupee forecast = base × size × turnover-band × days-late × recidivism. *Novel because:* others show generic ranges; we predict an amount for *this* business.

5. **Auto-Draft Filing** (`auto_draft.py`) — autonomously pre-populates filing templates from business data matched to filing schemas. *Novel because:* others remind or require manual entry; we fill the form.

---

## 6. How it's built

```
┌──────────────────────────┐     HTTPS      ┌──────────────────────────┐
│  Frontend (React+Vite)   │ ─────────────► │  Backend (FastAPI)       │
│  Vercel · Tailwind dark  │ ◄───────────── │  Railway · 16 routers    │
│  Firebase Auth           │   JSON / SSE   │  /api/v1/*               │
└──────────────────────────┘                └────────────┬─────────────┘
                                                          │
                              ┌───────────────────────────┼───────────────────────────┐
                              ▼                            ▼                           ▼
                    ┌──────────────────┐         ┌──────────────────┐        ┌──────────────────┐
                    │  Engines         │         │  Google ADK      │        │  MongoDB Atlas   │
                    │  (the 5 methods) │         │  multi-agent     │        │  11 collections  │
                    └──────────────────┘         │  + Gemini 2.x    │        │  Vector/Atlas/TS │
                                                 │  + MongoDB MCP   │────────►│  Change Streams  │
                                                 └──────────────────┘        └──────────────────┘
```

- **Frontend:** React 18 + TypeScript + Vite + Tailwind. One dark "Obsidian + Emerald" design system. Auth via Firebase. Real-time via SSE.
- **Backend:** Python 3.11 + FastAPI + Motor (async MongoDB). 16 routers, an `engines/` folder (one file per capability), and an `agent/` folder (the ADK multi-agent).
- **AI:** Gemini 2.x Flash, orchestrated by Google ADK; connected to MongoDB through the **MongoDB Atlas MCP Server**.

**A typical request flow** (e.g., loading the dashboard): React calls `GET /api/v1/...` → FastAPI router → engine computes (often an aggregation) over MongoDB → JSON back → React renders. **A live update** (e.g., a new ripple): a MongoDB **Change Stream** fires → backend pushes an SSE event → the dashboard toasts and refreshes without a reload.

---

## 7. How we use MongoDB Atlas

MongoDB isn't just storage here — it's the agent's brain. Eleven collections: `businesses`, `regulatory_corpus`, `obligation_instances`, `regulatory_changes`, `penalty_rules`, `filing_templates`, `filing_history`, `agent_decisions`, `chat_discoveries`, `decay_score_snapshots` (Time Series), `regulatory_fetch_log`.

| Atlas feature | Where it's used |
|---|---|
| **Vector Search** (`$vectorSearch`) | Semantic ripple detection over regulation embeddings |
| **Atlas Search** (`$search`) | Full-text regulation finder + the lexical half of hybrid search |
| **Reciprocal Rank Fusion** | Fuses Vector + Atlas Search into one ranked list (true hybrid RAG) |
| **Aggregation pipelines** (`$facet`, `$group`) | Exposure totals, peer benchmark, category rollups |
| **Time Series collection** | Decay-score snapshots → 30/60/90-day penalty forecast + sparklines |
| **Change Streams** | Real-time dashboard updates via SSE |
| **MongoDB Atlas MCP Server** | Gives the Gemini agent direct CRUD over the collections |

---

## 8. The AI agent

- **Framework:** Google **Agent Development Kit (ADK) 2.0**; brain is **Gemini 2.x Flash**.
- **Structure:** a root **planner** ("Compliance Officer") routes each question to one of **6 specialist sub-agents** — DNA, Decay, Ripple, Penalty, Drafter, Advisor — each with the *least* tools it needs (clearer reasoning, less hallucination).
- **Tools:** 7 Python functions wrapping the engines (`agent/tools.py`): list obligations, explain decay score, predict penalty, detect regulation impact, discover hidden obligations, generate draft, get filing track record.
- **MongoDB MCP:** the agent also has direct DB access through the MongoDB Atlas MCP Server (`agent/complianceos_agent.py`).
- **Transparency:** every step streams to the UI and is persisted to `agent_decisions`, so the agent's reasoning is fully auditable — and **replayable** against fresh data.

---

## 9. Presentation / demo script

A ~3-minute narration. Speak the **bold**; the *italics* are what to show on screen.

**[0:00–0:20 · The hook]**
> "In India, a single small business faces **1,450 compliance obligations a year**, **42 rules change every day**, and missing one can mean penalties — or even jail clauses. Keeping up costs **₹13 to 17 lakh a year** — more than most of these businesses earn in profit."

**[0:20–0:45 · Meet the user]**
> "Meet Priya. She runs a small restaurant in Chennai with 8 employees — GST, FSSAI, EPF, a shop licence. She has no idea she's subject to dozens of obligations."
> *Show the Landing page, then sign in.*

**[0:45–1:15 · Compliance DNA]**
> "She answers six questions about her business…"
> *Fill the onboarding form, submit.*
> "…and in seconds, ComplianceOS builds her **Compliance DNA** — a unique set of obligations matched against 90 Indian regulations, filtered by her state, industry, size, and even how new her business is."
> *Show the Review screen, then the Dashboard.*

**[1:15–1:45 · Decay scores + penalty prediction]**
> "Every obligation gets a **decay score** — a live urgency meter that learns from her filing history. This EPF filing is red. And ComplianceOS tells her exactly what it'll cost if she misses it: **₹750**."
> *Show the Obligations tab; hover the penalty badge.*

**[1:45–2:15 · Ripple detection]**
> "When a new GST circular drops, ComplianceOS uses **MongoDB Atlas Vector Search and Atlas Search together** to trace exactly which of *her* obligations are affected — directly and through dependencies."
> *Run a Ripple check; show direct + indirect impacts.*

**[2:15–2:40 · Auto-draft + the agent]**
> "It even fills the form for her. One click, review, download the PDF — filed."
> *Show Documents → download PDF. Then open Compliance Officer.*
> "And the whole thing is an autonomous agent — ask it anything and watch it reason, step by step."

**[2:40–3:00 · Impact + stack]**
> "ComplianceOS turns ₹17 lakh of compliance burden into ₹500 a month of peace of mind. Built on **MongoDB Atlas** — Vector Search, Atlas Search, Time Series, Change Streams, and the MongoDB MCP Server — powered by **Gemini** and orchestrated with **Google ADK**. For 64 million Indian businesses."

**Non-tech one-liner to close:** *"It's the compliance officer every small business needs but none can afford — now for the price of a phone plan."*

---

## 10. FAQ & gotchas

- **"Why does the AI chat sometimes say it's busy?"** Gemini's free tier allows ~20 requests/day and can be momentarily overloaded (503). The app retries automatically and shows a calm notice. A paid Gemini key removes this for production.
- **"Is the agent making up obligations?"** No — every obligation comes from the seeded `regulatory_corpus`; the agent is instructed never to invent them, and every action is logged to `agent_decisions`.
- **"What's real vs mocked?"** All scoring, penalties, ripple, drafts, PDF, search, and aggregations are real and run against live MongoDB. The regulatory corpus is seeded from publicly available Indian compliance requirements; a live feed (`fetch_circulars.py`) pulls real circulars from CBIC/EPFO/FSSAI/MCA.
- **"Does it give legal advice?"** No — it's a navigation tool. It says "confirm with your CA" when uncertain and never files anything without explicit approval.
- **Deployment:** see [DEPLOY.md](./DEPLOY.md). **Setup & API reference:** see [README.md](./README.md).
