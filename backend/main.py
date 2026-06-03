"""
ComplianceOS API — entry point.

Routes are organised under /api/v1/* in dedicated routers. This file does
nothing but wire them together, configure CORS, and run startup hooks.
"""

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from config import ALLOW_ALL_CORS, CORS_ORIGINS, REQUIRE_AUTH  # noqa: E402
from db.mongodb import create_indexes, get_db  # noqa: E402
from events import start_watchers, stop_watchers  # noqa: E402
from logging_config import get_logger, setup_logging  # noqa: E402
from routers import (admin, agent, audit_replay, benchmark, business, chat,  # noqa: E402
                     drafts, events as events_router, filing, forecast, health,
                     health_score, obligations, ripple, search)

setup_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = get_db()
    await create_indexes(db)
    watcher_tasks = []
    try:
        watcher_tasks = await start_watchers(db)
        log.info("startup complete (auth_required=%s, cors=%s, change_streams=%d)",
                 REQUIRE_AUTH, "*" if ALLOW_ALL_CORS else CORS_ORIGINS,
                 len(watcher_tasks))
    except Exception as exc:
        log.warning("Change Stream watchers failed to start: %s", exc)
    try:
        yield
    finally:
        if watcher_tasks:
            await stop_watchers(watcher_tasks)


app = FastAPI(
    title="ComplianceOS API",
    version="1.1.0",
    description="AI-powered regulatory compliance engine for Indian MSMEs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=not ALLOW_ALL_CORS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Versioned routes
API_V1 = "/api/v1"
for r in (health.router, business.router, obligations.router, ripple.router,
          ripple.admin_router, drafts.router, filing.router, chat.router,
          admin.router, agent.router, search.router, events_router.router,
          health_score.router, audit_replay.router, forecast.router,
          benchmark.router):
    app.include_router(r, prefix=API_V1)

# Health stays unversioned too so deploy probes (Railway, Vercel) work without
# knowing the API version.
app.include_router(health.router)
