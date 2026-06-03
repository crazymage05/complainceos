"""
Firebase ID-token verification.

Set ``REQUIRE_AUTH=true`` in the backend env to enforce. When unset (default),
all routes pass through with ``user_uid="anonymous"`` so local development and
the live demo keep working until a service-account key is wired up.
"""

from typing import Any, Dict, Optional

from bson import ObjectId
from fastapi import Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from config import FIREBASE_PROJECT_ID, REQUIRE_AUTH
from db.mongodb import get_db
from logging_config import get_logger

log = get_logger(__name__)

_firebase_ready = False
_firebase_init_attempted = False


def _try_init_firebase() -> bool:
    """Initialise firebase_admin once. Returns True if usable."""
    global _firebase_ready, _firebase_init_attempted
    if _firebase_init_attempted:
        return _firebase_ready
    _firebase_init_attempted = True
    try:
        import firebase_admin
        from firebase_admin import credentials

        if not firebase_admin._apps:
            try:
                # Tries GOOGLE_APPLICATION_CREDENTIALS / metadata server first.
                cred = credentials.ApplicationDefault()
                firebase_admin.initialize_app(
                    cred,
                    {"projectId": FIREBASE_PROJECT_ID} if FIREBASE_PROJECT_ID else None,
                )
            except Exception as exc:
                log.warning("Firebase application-default creds unavailable: %s", exc)
                firebase_admin.initialize_app()
        _firebase_ready = True
    except ImportError:
        log.warning("firebase_admin not installed — auth disabled")
        _firebase_ready = False
    except Exception as exc:
        log.error("Firebase init failed: %s", exc)
        _firebase_ready = False
    return _firebase_ready


def _extract_bearer(request: Request) -> Optional[str]:
    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    return header.split(" ", 1)[1].strip() or None


async def current_user(request: Request) -> Dict[str, Any]:
    """
    Returns ``{"uid": ..., "email": ...}`` on success. Anonymous when auth is
    disabled. Raises 401 only when ``REQUIRE_AUTH=true`` and the token is bad.
    """
    if not REQUIRE_AUTH:
        return {"uid": "anonymous", "email": None}

    token = _extract_bearer(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    if not _try_init_firebase():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth backend unavailable",
        )

    try:
        from firebase_admin import auth as fb_auth
        decoded = fb_auth.verify_id_token(token)
        return {"uid": decoded.get("uid"), "email": decoded.get("email")}
    except Exception as exc:
        log.warning("token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc


async def require_business_owner(
    business_id: str,
    user: Dict[str, Any] = Depends(current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> Dict[str, Any]:
    """
    Path-level ownership check. Confirms the authenticated UID matches the
    business's ``owner`` field. No-op when ``REQUIRE_AUTH=false``.
    """
    if not REQUIRE_AUTH:
        return user
    try:
        oid = ObjectId(business_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid business_id") from exc
    biz = await db.businesses.find_one({"_id": oid}, {"owner": 1})
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")
    if biz.get("owner") != user["uid"] and biz.get("owner") != user.get("email"):
        raise HTTPException(status_code=403, detail="Not the owner of this business")
    return user
