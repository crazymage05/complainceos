import asyncio
import hashlib
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from auth import current_user
from common import log_decision, rate_limit_gemini
from db.mongodb import get_db
from engines.circular_ocr import (ACCEPTED_MIME, extract_text,
                                  validate_upload)
from engines.ripple_detector import detect_ripple, detect_ripple_hybrid
from logging_config import get_logger
from schemas import IngestCircularRequest

log = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

CATEGORY_KEYWORDS = {
    "taxation": ["gst", "cbic", "tds", "income tax", "itc", "gstr"],
    "labour": ["epf", "esic", "epfo", "pf", "esi", "wage", "labour"],
    "food_safety": ["fssai", "food safety", "foscos"],
    "companies_act": ["mca", "companies act", "roc"],
    "income_tax": ["income tax", "cbdt", "itr"],
}


@router.post(
    "/ingest-circular",
    dependencies=[Depends(rate_limit_gemini)],
)
async def admin_ingest_circular(
    payload: IngestCircularRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: Dict = Depends(current_user),
):
    """Embed a circular, upsert into corpus, ripple across every business."""
    from model_client import get_completion, get_embedding

    lower = (payload.text + " " + payload.source).lower()
    category = next(
        (cat for cat, kws in CATEGORY_KEYWORDS.items() if any(k in lower for k in kws)),
        "other",
    )

    slug = re.sub(r"[^a-z0-9]", "_", payload.source.lower())[:40]
    suffix = hashlib.md5(payload.source.encode()).hexdigest()[:6]
    reg_id = f"ingested_{slug}_{suffix}"

    meta: Dict[str, Any] = {}
    try:
        prompt = (
            "Extract structured metadata from this Indian government circular. "
            "Respond ONLY with valid JSON: "
            '{"name":"short name","deadline_rule":"","max_penalty_inr":0,"imprisonment_risk":false}\n'
            f"Source: {payload.source}\nText: {payload.text[:2000]}"
        )
        raw = get_completion(prompt)
        raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        meta = json.loads(raw)
    except Exception as exc:
        log.warning("circular metadata extraction failed: %s", exc)
        meta = {"name": payload.source[:80], "deadline_rule": "", "max_penalty_inr": 10000}

    embed_text = f"{meta.get('name', payload.source)} {category} {meta.get('deadline_rule', '')} {payload.source}"
    embedding = await asyncio.to_thread(get_embedding, embed_text)

    doc = {
        "_id": reg_id,
        "name": meta.get("name", payload.source[:80]),
        "jurisdiction": "India",
        "state_specific": None,
        "category": category,
        "applicable_to": {"industries": ["all"], "min_turnover_inr": 0, "registrations_required": [], "min_employees": 0},
        "frequency": "one_time",
        "deadline_rule": meta.get("deadline_rule", ""),
        "complexity": 2,
        "penalty_type": "financial",
        "imprisonment_risk": meta.get("imprisonment_risk", False),
        "depends_on": [],
        "last_updated": datetime.utcnow().strftime("%Y-%m-%d"),
        "source": payload.source,
        "max_penalty_inr": meta.get("max_penalty_inr", 10000),
        "embedding": embedding,
        "raw_text": payload.text[:8000],
        "ingested_at": datetime.utcnow(),
    }
    if await db.regulatory_corpus.find_one({"_id": reg_id}):
        await db.regulatory_corpus.replace_one({"_id": reg_id}, doc)
    else:
        await db.regulatory_corpus.insert_one(doc)

    ripple_summary = []
    async for biz in db.businesses.find({}, {"_id": 1, "name": 1}):
        bid = str(biz["_id"])
        ripple = await detect_ripple(
            db=db,
            business_id=bid,
            affected_categories=[category],
            affected_registrations=[],
            change_description=payload.text[:500],
        )
        direct = len(ripple.get("directly_impacted", []))
        indirect = len(ripple.get("indirectly_impacted", []))
        if direct + indirect == 0:
            continue
        ripple_summary.append({
            "business_id": bid,
            "business_name": biz.get("name", bid),
            "direct": direct,
            "indirect": indirect,
            "severity": ripple.get("severity", "medium"),
        })
        await db.regulatory_changes.update_one(
            {"business_id": bid, "source": payload.source},
            {"$set": {
                "title": meta.get("name", payload.source),
                "source": payload.source,
                "category": category,
                "affected_categories": [category],
                "severity": ripple.get("severity", "medium"),
                "directly_impacted": ripple.get("directly_impacted", []),
                "indirectly_impacted": ripple.get("indirectly_impacted", []),
                "detected_at": datetime.utcnow(),
            }},
            upsert=True,
        )

    await log_decision(db, "admin", "ingest_circular", {
        "source": payload.source,
        "reg_id": reg_id,
        "category": category,
        "businesses_affected": len(ripple_summary),
    })

    return {
        "reg_id": reg_id,
        "name": meta.get("name", payload.source),
        "category": category,
        "businesses_affected": len(ripple_summary),
        "ripple_summary": ripple_summary,
    }


# ────────────────────────────────────────────────────────────────────────────
# Multi-tenant ripple cascade — the demo wow moment
# ────────────────────────────────────────────────────────────────────────────

class CascadeRequest(BaseModel):
    title: str
    description: str = ""
    category: Optional[str] = None
    affected_categories: Optional[List[str]] = None


@router.post(
    "/ripple-cascade",
    dependencies=[Depends(rate_limit_gemini)],
)
async def ripple_cascade(
    payload: CascadeRequest,
    hybrid: bool = Query(True, description="Use hybrid Vector + Atlas Search"),
    limit_businesses: int = Query(
        20, ge=1, le=100, description="Max businesses to cascade across",
    ),
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: Dict = Depends(current_user),
):
    """
    Single API call → ripple a regulation change across every active
    business in parallel. Returns a per-business impact breakdown so the
    UI can render a split-screen demo.

    The cascade runs detect_ripple_hybrid() for each business concurrently
    via asyncio.gather, so latency is dominated by the slowest tenant,
    not the sum. With 4 demo businesses on a free-tier cluster the whole
    cascade typically finishes in 2-4 seconds (one embedding call shared,
    then 4 parallel vector + text searches).
    """
    categories = payload.affected_categories or ([payload.category] if payload.category else [])

    # Pull active businesses (limit defends against accidentally fanning out
    # to thousands of businesses on a busy cluster)
    businesses: List[Dict] = []
    cursor = db.businesses.find({}, {"_id": 1, "name": 1, "industry": 1, "state": 1})
    async for biz in cursor.limit(limit_businesses):
        businesses.append({
            "id": str(biz["_id"]),
            "name": biz.get("name", ""),
            "industry": biz.get("industry", ""),
            "state": biz.get("state", ""),
        })

    if not businesses:
        return {
            "title": payload.title,
            "businesses_evaluated": 0,
            "businesses_affected": 0,
            "results": [],
        }

    detector = detect_ripple_hybrid if hybrid else detect_ripple
    started = datetime.utcnow()

    async def _one(biz: Dict) -> Dict:
        ripple = await detector(
            db=db,
            business_id=biz["id"],
            affected_categories=categories,
            affected_registrations=[],
            change_description=payload.description or payload.title,
        )
        return {
            "business_id": biz["id"],
            "business_name": biz["name"],
            "industry": biz["industry"],
            "state": biz["state"],
            "direct_count": len(ripple.get("directly_impacted", [])),
            "indirect_count": len(ripple.get("indirectly_impacted", [])),
            "severity": ripple.get("severity", "low"),
            "detection_method": ripple.get("detection_method", "?"),
            "top_direct": [
                d.get("name", "") for d in (ripple.get("directly_impacted") or [])[:3]
            ],
        }

    # Run all businesses in parallel — this is the lever that makes a
    # 4-business cascade feel instant in the demo
    results = await asyncio.gather(*[_one(b) for b in businesses], return_exceptions=True)
    clean: List[Dict] = []
    errors = 0
    for r in results:
        if isinstance(r, Exception):
            errors += 1
            log.warning("cascade tenant failed: %s", r)
            continue
        clean.append(r)

    # Sort by impact severity then total count, so the demo shows
    # highest-impact businesses first
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    clean.sort(key=lambda r: (
        severity_rank.get(r["severity"], 99),
        -(r["direct_count"] + r["indirect_count"]),
    ))

    affected = sum(1 for r in clean if (r["direct_count"] + r["indirect_count"]) > 0)
    elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)

    await log_decision(db, "admin", "ripple_cascade", {
        "title": payload.title,
        "businesses_evaluated": len(businesses),
        "businesses_affected": affected,
        "errors": errors,
        "elapsed_ms": elapsed_ms,
    })

    return {
        "title": payload.title,
        "businesses_evaluated": len(businesses),
        "businesses_affected": affected,
        "elapsed_ms": elapsed_ms,
        "results": clean,
        "hybrid": hybrid,
    }


# ────────────────────────────────────────────────────────────────────────────
# Multimodal: upload a circular as PDF / image — Gemini Vision extracts text
# ────────────────────────────────────────────────────────────────────────────

@router.post(
    "/upload-circular",
    dependencies=[Depends(rate_limit_gemini)],
)
async def upload_circular(
    file: UploadFile = File(..., description="PDF or image of the circular"),
    source: str = Form(..., description="Human-readable source label, e.g. 'CBIC Circular 207/2023'"),
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: Dict = Depends(current_user),
):
    """
    Upload a scanned PDF or photo of a government circular. Gemini 2.5
    Flash extracts the text via its vision capability, then the existing
    embed → upsert → ripple pipeline runs across every business.

    Demonstrates Gemini's multimodal capability end-to-end — this is the
    real-world workflow: government publishes a scan, owner snaps a photo,
    the agent ingests it.
    """
    content_type = file.content_type or "application/octet-stream"
    file_bytes = await file.read()
    valid, err = validate_upload(content_type, len(file_bytes))
    if not valid:
        raise HTTPException(status_code=400, detail=err)

    # 1) OCR via Gemini Vision
    try:
        extracted = await extract_text(file_bytes, content_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        s = str(exc)
        if "429" in s or "RESOURCE_EXHAUSTED" in s:
            raise HTTPException(
                status_code=429,
                detail="Gemini quota exhausted — try again after the daily reset.",
                headers={"Retry-After": "60"},
            ) from exc
        log.exception("OCR failed")
        raise HTTPException(status_code=500, detail=f"OCR failed: {s[:200]}") from exc

    log.info("OCR success: %d chars extracted from %s", len(extracted), content_type)

    # 2) Delegate to the existing text-based ingestion pipeline.
    # We re-invoke the in-router handler directly so the OCR endpoint
    # benefits from any future changes to ingestion logic for free.
    ingest_payload = IngestCircularRequest(source=source, text=extracted)
    ingestion_result = await admin_ingest_circular(  # type: ignore[name-defined]
        payload=ingest_payload, db=db, user=user,
    )

    return {
        "source": source,
        "ocr_extracted_chars": len(extracted),
        "ocr_preview": extracted[:500],
        "ocr_mime_type": content_type,
        "ingestion": ingestion_result,
    }
