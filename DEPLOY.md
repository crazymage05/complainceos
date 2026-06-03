# Deploying ComplianceOS

Frontend → **Vercel**, backend → **Railway**, database → **MongoDB Atlas**, auth → **Firebase**.
Follow the steps **in order** — the backend must exist before the frontend can point at it.

> 🔐 **Secrets never go in the repo.** `.env` files are git-ignored. Set all secrets in the Vercel/Railway dashboards. If a key was ever committed or shared, rotate it.

---

## 0. Prerequisites
- A **Vercel** account and a **Railway** account
- A **MongoDB Atlas** cluster (free tier is fine) with the corpus seeded (`python db/seed_corpus.py`)
- A **Gemini API key** — use a **paid/billing-enabled key** for production; the free tier (20 req/day) will exhaust instantly under real traffic
- The **Atlas Vector Search** index `regulation_embedding_index` and the **Atlas Search** index `regulation_text_search` created (see README)
- Either **Git** installed (GitHub route) **or** the platform CLIs: `npm i -g vercel @railway/cli` (CLI route, no Git needed)

---

## 1. Backend → Railway
Root directory: **`complianceos/backend`** (config already in `railway.toml`, Python pinned by `.python-version`).

**Start command** (already set): `uvicorn main:app --host 0.0.0.0 --port $PORT`

**Environment variables** (Railway → Variables):
| Var | Value |
|---|---|
| `MONGODB_URI` | your Atlas SRV connection string |
| `MONGODB_DB_NAME` | `complianceos` |
| `GEMINI_API_KEY` | your (paid) Gemini key |
| `AGENT_MODEL` | `gemini-2.5-flash` |
| `PROJECT_PHASE` | `1` |
| `CORS_ORIGINS` | _(set after step 3 to your Vercel URL)_ |
| `GEMINI_RPM` | `10` (raise with a paid key) |

Deploy:
- **CLI:** `cd backend && railway up`
- **GitHub:** push repo → Railway → New Project → Deploy from repo → set root to `complianceos/backend`.

Copy the resulting URL, e.g. `https://complianceos-backend.up.railway.app`. Verify `GET /health` returns `{"status":"ok"}`.

> The two crons in `railway.toml` (nightly obligation rollover + daily circular fetch) run automatically. Both are safe — they don't delete data.

---

## 2. MongoDB Atlas → Network Access
Atlas → **Network Access → Add IP Address → `0.0.0.0/0`** (Allow from anywhere).
Railway's egress IPs are dynamic, so a single-IP allowlist will block the backend. (Access is still gated by the connection-string credentials.)

---

## 3. Frontend → Vercel
Root directory: **`complianceos/frontend`** (config in `vercel.json`: build `npm run build`, output `dist`, SPA rewrites).

**Environment variables** (Vercel → Settings → Environment Variables):
| Var | Value |
|---|---|
| `VITE_API_URL` | the Railway backend URL from step 1 |
| `VITE_FIREBASE_API_KEY` | from Firebase console |
| `VITE_FIREBASE_AUTH_DOMAIN` | `<project>.firebaseapp.com` |
| `VITE_FIREBASE_PROJECT_ID` | your Firebase project id |
| `VITE_FIREBASE_APP_ID` | from Firebase console |

Deploy:
- **CLI:** `cd frontend && vercel --prod`
- **GitHub:** Vercel → New Project → import repo → set root to `complianceos/frontend`.

Copy the Vercel URL, e.g. `https://complianceos.vercel.app`.

---

## 4. Wire the two together
1. **Railway → `CORS_ORIGINS`** = your Vercel URL (comma-separate if you have a custom domain too), then redeploy the backend.
2. **Firebase Console → Authentication → Settings → Authorized domains → Add** your Vercel domain (otherwise Google sign-in throws `auth/unauthorized-domain`).

---

## 5. Smoke test the live app
- Open the Vercel URL → sign in with Google → onboard a test business → reach the dashboard.
- ✅ Overview loads health/exposure/forecast/benchmark
- ✅ Obligations list populates with decay scores
- ✅ Regulation search returns results (Atlas Search)
- ✅ Ripple check returns impacts
- ✅ A draft generates and the PDF downloads
- ✅ Compliance Officer / AI Advisor respond (needs the paid Gemini key)

---

## Rollback
- Vercel and Railway both keep previous deployments — use **"Promote/Rollback to previous deployment"** in each dashboard if a release misbehaves.

## Common gotchas
| Symptom | Fix |
|---|---|
| Backend can't reach Atlas | Add `0.0.0.0/0` in Atlas Network Access (step 2) |
| `CORS` error in browser console | `CORS_ORIGINS` on Railway must equal the exact Vercel origin |
| Google sign-in fails (`unauthorized-domain`) | Add the Vercel domain in Firebase authorized domains |
| AI features show "quota/busy" | Use a billing-enabled Gemini key; raise `GEMINI_RPM` |
| Search falls back to regex | Create the `regulation_text_search` Atlas Search index |
| Ripple finds nothing semantically | Create `regulation_embedding_index` + run `python db/embed_regulations.py` |
