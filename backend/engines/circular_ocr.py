"""
Multimodal circular ingestion via Gemini Vision.

Government circulars in India are usually published as scanned PDF
notifications, not clean text. ComplianceOS accepts the PDF/image upload,
asks Gemini 2.5 Flash to extract the structured text via its vision
capability, then pipes the extracted text through the existing embed →
upsert → ripple pipeline.

This demonstrates:
  - Gemini's multimodal capability (vision + text in one call)
  - End-to-end MSME workflow (upload what regulators publish, get what
    you need)
"""

import asyncio
from typing import Any, Dict

from logging_config import get_logger

log = get_logger(__name__)


MAX_BYTES = 12 * 1024 * 1024  # 12 MB — well under Gemini's inline limit
ACCEPTED_MIME = {
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
}


_OCR_PROMPT = (
    "You are reading an official Indian government compliance circular "
    "or notification. Extract the full text content as plain text — do "
    "NOT summarise. Preserve:\n"
    "  * The circular/notification number and date if visible\n"
    "  * The issuing authority (CBIC, EPFO, FSSAI, MCA, etc.)\n"
    "  * The subject line\n"
    "  * Numbered paragraphs and clauses\n"
    "  * Any deadlines, penalty amounts, or effective dates\n"
    "Skip page headers/footers and watermarks. Output only the extracted "
    "text — no commentary, no 'Here is the text:' preamble."
)


def validate_upload(content_type: str, size: int) -> tuple[bool, str]:
    if content_type not in ACCEPTED_MIME:
        return False, (
            f"Unsupported file type '{content_type}'. "
            f"Allowed: {', '.join(ACCEPTED_MIME.keys())}"
        )
    if size <= 0:
        return False, "Empty file."
    if size > MAX_BYTES:
        return False, f"File too large: {size} bytes (max {MAX_BYTES})."
    return True, ""


async def extract_text(file_bytes: bytes, content_type: str) -> str:
    """Run Gemini Vision over the uploaded file and return the extracted text."""
    from model_client import get_vision_completion

    if content_type not in ACCEPTED_MIME:
        raise ValueError(f"Unsupported MIME: {content_type}")

    try:
        text = await asyncio.to_thread(
            get_vision_completion, _OCR_PROMPT, file_bytes, content_type,
        )
    except Exception as exc:
        log.warning("Gemini vision OCR failed: %s", exc)
        raise

    text = (text or "").strip()
    if len(text) < 30:
        raise ValueError(
            "Gemini extracted less than 30 chars — the file may be unreadable, "
            "blank, or password-protected."
        )
    return text


async def ingest_uploaded_circular(
    db,
    source: str,
    file_bytes: bytes,
    content_type: str,
) -> Dict[str, Any]:
    """Full pipeline: OCR → existing embed/upsert/ripple."""
    from ingest_circular import run as ingest_run

    extracted = await extract_text(file_bytes, content_type)
    log.info("OCR extracted %d chars from %s upload", len(extracted), content_type)

    # Reuse the existing pipeline
    result = await ingest_run(source=source, text=extracted)
    if isinstance(result, dict):
        result["ocr_chars_extracted"] = len(extracted)
        result["ocr_preview"] = extracted[:300]
    else:
        result = {
            "ocr_chars_extracted": len(extracted),
            "ocr_preview": extracted[:300],
            "note": "Ingestion completed; ingest_circular.run() returned no dict.",
        }
    return result
