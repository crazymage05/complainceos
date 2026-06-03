"""
Server-Sent Events feed backed by MongoDB Change Streams.

Subscribe with EventSource on the frontend to receive real-time updates
when this business's obligations, ripple alerts, or agent decisions change.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from auth import current_user
from events import sse_stream

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/stream")
async def stream_events(
    business_id: Optional[str] = Query(
        None,
        description="Only emit events for this business; omit for global feed",
    ),
    _user=Depends(current_user),
):
    """
    Open a long-lived SSE connection. Events are pushed when MongoDB
    Change Streams report inserts/updates on:
      - regulatory_changes (new ripple impact)
      - agent_decisions (agent ran a tool)
      - obligation_instances (decay score recomputed, status changed)

    Each event JSON has at minimum: `kind`, `collection`, `operation`,
    `business_id`, `at` (ISO timestamp), plus collection-specific fields.
    """
    return StreamingResponse(
        sse_stream(business_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
