"""
Event bus + MongoDB Change Streams watcher.

Watches `regulatory_changes`, `obligation_instances`, and `agent_decisions`
collections via Atlas Change Streams (free-tier M0 supports this because
the cluster runs as a 3-node replica set). When a change is detected, an
event is published to per-business subscriber queues so connected SSE
clients receive it in real time.

This is the MongoDB feature flagship of the project: real-time data is the
defining capability of MongoDB Atlas that other databases can't match
without bolting on a separate queue.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, AsyncIterator, Dict, Set

from motor.motor_asyncio import AsyncIOMotorDatabase

from logging_config import get_logger

log = get_logger(__name__)


# ────────────────────────────────────────────────────────────────────────────
# In-process event bus — per-business subscriber queues
# ────────────────────────────────────────────────────────────────────────────

class EventBus:
    """Per-business fan-out for Change Stream events.

    Each SSE client opens a subscription for a specific business_id; the
    Change Stream watcher publishes to the matching queues.
    """

    def __init__(self) -> None:
        # business_id -> set of asyncio.Queue (one per connected client)
        self._subs: Dict[str, Set[asyncio.Queue]] = {}
        # Special "*" topic — subscribers to ALL events (admin views)
        self._global: Set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self, business_id: str | None) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            if business_id:
                self._subs.setdefault(business_id, set()).add(q)
            else:
                self._global.add(q)
        return q

    async def unsubscribe(self, business_id: str | None, q: asyncio.Queue) -> None:
        async with self._lock:
            if business_id and business_id in self._subs:
                self._subs[business_id].discard(q)
                if not self._subs[business_id]:
                    del self._subs[business_id]
            else:
                self._global.discard(q)

    async def publish(self, business_id: str | None, event: Dict[str, Any]) -> None:
        # Always emit to globals
        for q in list(self._global):
            self._safe_put(q, event)
        # Targeted business subscribers
        if business_id and business_id in self._subs:
            for q in list(self._subs[business_id]):
                self._safe_put(q, event)

    @staticmethod
    def _safe_put(q: asyncio.Queue, event: Dict) -> None:
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            log.warning("SSE subscriber queue full — dropping event")


bus = EventBus()


# ────────────────────────────────────────────────────────────────────────────
# Change Stream watchers
# ────────────────────────────────────────────────────────────────────────────

_WATCHED_COLLECTIONS = ("regulatory_changes", "agent_decisions", "obligation_instances")


def _extract_business_id(doc: Dict | None) -> str | None:
    if not doc:
        return None
    bid = doc.get("business_id")
    if isinstance(bid, str):
        return bid
    return None


def _summarise(event_doc: Dict) -> Dict[str, Any]:
    """Convert raw Change Stream payload to a slim, JSON-safe event."""
    op = event_doc.get("operationType", "update")
    ns = event_doc.get("ns", {})
    coll = ns.get("coll", "")
    full = event_doc.get("fullDocument") or {}
    business_id = _extract_business_id(full)

    summary: Dict[str, Any] = {
        "at": datetime.utcnow().isoformat() + "Z",
        "kind": f"{coll}.{op}",
        "collection": coll,
        "operation": op,
        "business_id": business_id,
    }

    if coll == "regulatory_changes":
        summary["title"] = full.get("title", "")
        summary["category"] = full.get("category", "")
        summary["severity"] = full.get("severity", "")
        summary["direct_count"] = len(full.get("directly_impacted", []) or [])
        summary["indirect_count"] = len(full.get("indirectly_impacted", []) or [])
    elif coll == "agent_decisions":
        summary["action"] = full.get("action", "")
        payload = full.get("payload", {}) or {}
        summary["preview"] = str(payload.get("final") or payload.get("template_name") or "")[:140]
    elif coll == "obligation_instances":
        summary["name"] = full.get("name", "")
        summary["urgency"] = full.get("urgency", "")
        summary["decay_score"] = full.get("decay_score")
        # If only the score updated, surface the diff for the UI
        updated = (event_doc.get("updateDescription") or {}).get("updatedFields") or {}
        if updated:
            summary["changed_fields"] = list(updated.keys())[:5]

    return summary


async def _watch_collection(db: AsyncIOMotorDatabase, collection_name: str) -> None:
    """One coroutine per collection — runs forever, reconnecting on errors."""
    collection = db[collection_name]
    backoff = 1
    while True:
        try:
            log.info("Change Stream OPEN on %s", collection_name)
            async with collection.watch(
                full_document="updateLookup",
                max_await_time_ms=2000,
            ) as stream:
                backoff = 1  # reset on successful open
                async for raw in stream:
                    try:
                        event = _summarise(raw)
                        await bus.publish(event["business_id"], event)
                    except Exception as exc:
                        log.warning("event publish failed: %s", exc)
        except asyncio.CancelledError:
            log.info("Change Stream watcher cancelled for %s", collection_name)
            raise
        except Exception as exc:
            log.warning(
                "Change Stream on %s failed (%s) — reconnecting in %ds",
                collection_name, exc, backoff,
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)


async def start_watchers(db: AsyncIOMotorDatabase) -> list[asyncio.Task]:
    """Spawn one watcher per collection. Caller stores the tasks for shutdown."""
    tasks = []
    for coll in _WATCHED_COLLECTIONS:
        tasks.append(asyncio.create_task(
            _watch_collection(db, coll), name=f"change_stream_{coll}",
        ))
    return tasks


async def stop_watchers(tasks: list[asyncio.Task]) -> None:
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


# ────────────────────────────────────────────────────────────────────────────
# SSE iterator helper
# ────────────────────────────────────────────────────────────────────────────

async def sse_stream(business_id: str | None) -> AsyncIterator[str]:
    """Yield SSE-formatted strings for a subscriber's lifetime.

    Emits a keepalive comment every 25 seconds to defeat proxy timeouts.
    """
    q = await bus.subscribe(business_id)
    try:
        # Initial handshake event
        yield f"data: {json.dumps({'kind': 'subscribed', 'business_id': business_id})}\n\n"
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=25.0)
                yield f"data: {json.dumps(event, default=str)}\n\n"
            except asyncio.TimeoutError:
                # Keep the connection alive through proxies
                yield ": keepalive\n\n"
    finally:
        await bus.unsubscribe(business_id, q)
