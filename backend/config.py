import os
from typing import List


def _csv_env(name: str, default: str) -> List[str]:
    raw = os.getenv(name, default)
    return [v.strip() for v in raw.split(",") if v.strip()]


# ── HTTP / CORS ────────────────────────────────────────────────────────────────
# Comma-separated origin list. Defaults cover local Vite + the Vercel preview.
CORS_ORIGINS: List[str] = _csv_env(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)

# Reject all if the env explicitly lists "*" we keep the wildcard; otherwise lock down.
ALLOW_ALL_CORS = "*" in CORS_ORIGINS

# ── Auth ───────────────────────────────────────────────────────────────────────
# When true, every /api/v1 route requires a valid Firebase ID token whose UID
# matches the business owner. When false (default in dev), auth is a no-op so
# the demo keeps working without a service-account key configured.
REQUIRE_AUTH: bool = os.getenv("REQUIRE_AUTH", "false").lower() == "true"
FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "")

# ── Pagination ─────────────────────────────────────────────────────────────────
# Most MSMEs land in the 30–120 obligation range; default high enough that the
# UI doesn't silently truncate. Frontend can still opt into smaller pages.
DEFAULT_PAGE_LIMIT = 250
MAX_PAGE_LIMIT = 500

# ── Frequency → days ───────────────────────────────────────────────────────────
FREQ_DAYS = {
    "daily": 1,
    "weekly": 7,
    "monthly": 30,
    "quarterly": 90,
    "half_yearly": 182,
    "annual": 365,
    "one_time": 365,
}

# ── Obligation onboarding stagger ──────────────────────────────────────────────
# Spread initial due dates across 40–92% of each obligation's period so the
# dashboard shows mostly green/amber on day one (the original 0.15 base put
# every monthly filing 4–8 days out, painting the dashboard red on signup).
STAGGER_BASE_PCT = 0.40
STAGGER_STEP_PCT = 0.08
STAGGER_CYCLE = 7

# ── AI Advisor defaults ────────────────────────────────────────────────────────
URGENCY_DAYS = {"immediate": 7, "next_30_days": 30, "annual": 90}
CATEGORY_DEFAULTS = {
    "taxation": {"max_penalty_inr": 50000, "frequency": "monthly"},
    "labour": {"max_penalty_inr": 25000, "frequency": "monthly"},
    "food_safety": {"max_penalty_inr": 25000, "frequency": "annual"},
    "companies_act": {"max_penalty_inr": 100000, "frequency": "annual"},
    "fire_safety": {"max_penalty_inr": 10000, "frequency": "annual"},
    "shops_establishments": {"max_penalty_inr": 5000, "frequency": "annual"},
}

# ── Decay snapshot throttling ──────────────────────────────────────────────────
SNAPSHOT_INTERVAL_SECONDS = 3600  # at most one snapshot per obligation per hour
DECAY_TREND_WINDOW_DAYS = 30

# ── Rate limiting (per-IP) for Gemini-backed endpoints ─────────────────────────
GEMINI_RPM = int(os.getenv("GEMINI_RPM", "10"))
