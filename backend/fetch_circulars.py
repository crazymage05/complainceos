"""
Live Regulatory Feed Ingestion — fetches new government circulars from
official Indian regulatory sources and pipes them through ComplianceOS's
embed → upsert → ripple pipeline.

Usage:
  python fetch_circulars.py              # fetch all sources
  python fetch_circulars.py --source cbic  # single source only

Designed to be run as a daily cron job. Tracks already-ingested URLs in
MongoDB (regulatory_fetch_log) so re-runs are idempotent.

Sources:
  cbic    — CBIC GST notifications (cbic.gov.in)
  epfo    — EPFO circulars (epfindia.gov.in)
  fssai   — FSSAI orders (fssai.gov.in)
  mca     — MCA circulars (mca.gov.in)
"""
import argparse
import asyncio
import os
import sys
import hashlib
import re
from datetime import datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ".")
from dotenv import load_dotenv; load_dotenv()

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing dependencies. Run: pip install requests beautifulsoup4")
    sys.exit(1)

from db.mongodb import get_db
from ingest_circular import run as ingest_run

HEADERS = {
    "User-Agent": "Mozilla/5.0 (ComplianceOS regulatory monitor; contact: crazymage05238@gmail.com)"
}
TIMEOUT = 15

# ---------------------------------------------------------------------------
# Source definitions
# ---------------------------------------------------------------------------

SOURCES = {
    "cbic": {
        "name": "CBIC GST Notifications",
        "url": "https://cbic.gov.in/htdocs-cbec/gst/notfctn-html-folder/notfctn-cgst.htm",
        "fallback_urls": [
            "https://cbic.gov.in/htdocs-cbec/gst/notfctn-html-folder/notfctn-igst.htm",
        ],
        "link_pattern": r"notfctn-\d+",
        "base_url": "https://cbic.gov.in",
        "category": "taxation",
    },
    "epfo": {
        "name": "EPFO Circulars",
        "url": "https://www.epfindia.gov.in/site_en/Circulars.php",
        "link_pattern": r"\.(pdf|PDF)",
        "base_url": "https://www.epfindia.gov.in",
        "category": "labour",
    },
    "fssai": {
        "name": "FSSAI Orders and Circulars",
        "url": "https://fssai.gov.in/cms/orders-and-circulars.php",
        "link_pattern": r"\.(pdf|PDF)",
        "base_url": "https://fssai.gov.in",
        "category": "food_safety",
    },
    "mca": {
        "name": "MCA General Circulars",
        "url": "https://www.mca.gov.in/content/mca/global/en/acts-rules/ebooks/circulars.html",
        "link_pattern": r"circular",
        "base_url": "https://www.mca.gov.in",
        "category": "companies_act",
    },
}

MAX_NEW_PER_SOURCE = 3  # cap per run to avoid API quota exhaustion


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------

def _fetch_html(url: str) -> str | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"  Fetch failed for {url}: {e}")
        return None


def _extract_links(html: str, base_url: str, link_pattern: str) -> list[tuple[str, str]]:
    """Return list of (absolute_url, link_text) matching the pattern."""
    soup = BeautifulSoup(html, "html.parser")
    results = []
    pattern = re.compile(link_pattern, re.IGNORECASE)
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if pattern.search(href) or pattern.search(a.get_text()):
            if href.startswith("http"):
                full_url = href
            elif href.startswith("//"):
                full_url = "https:" + href
            elif href.startswith("/"):
                full_url = base_url.rstrip("/") + href
            else:
                full_url = base_url.rstrip("/") + "/" + href
            text = a.get_text(strip=True) or href.split("/")[-1]
            results.append((full_url, text[:120]))
    return results


def _fetch_text(url: str) -> str:
    """Download URL and return text. Handles basic HTML; PDF extraction is best-effort."""
    if url.lower().endswith(".pdf"):
        return _fetch_pdf_text(url)
    html = _fetch_html(url)
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)[:8000]


def _fetch_pdf_text(url: str) -> str:
    """Best-effort PDF text extraction using pdfplumber if available."""
    try:
        import pdfplumber
        import io
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            text = "\n".join(
                page.extract_text() or "" for page in pdf.pages[:5]
            )
        return text[:8000]
    except ImportError:
        return f"[PDF — install pdfplumber for text extraction] {url}"
    except Exception as e:
        return f"[PDF fetch failed: {e}] {url}"


def _url_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Main async runner
# ---------------------------------------------------------------------------

async def run(source_filter: str | None = None):
    db = get_db()
    total_ingested = 0

    sources_to_run = {
        k: v for k, v in SOURCES.items()
        if source_filter is None or k == source_filter
    }

    for source_key, cfg in sources_to_run.items():
        print(f"\n[{cfg['name']}]")
        urls_to_try = [cfg["url"]] + cfg.get("fallback_urls", [])
        html = None
        for url in urls_to_try:
            html = _fetch_html(url)
            if html:
                break

        if not html:
            print("  Could not fetch — skipping")
            continue

        links = _extract_links(html, cfg["base_url"], cfg["link_pattern"])
        print(f"  Found {len(links)} candidate links")

        new_count = 0
        for circular_url, link_text in links:
            if new_count >= MAX_NEW_PER_SOURCE:
                break

            url_hash = _url_id(circular_url)
            already = await db.regulatory_fetch_log.find_one({"url_hash": url_hash})
            if already:
                continue  # already ingested

            print(f"  New circular: {link_text[:60]}")
            text = _fetch_text(circular_url)
            if len(text.strip()) < 50:
                print(f"    Too little text extracted — skipping")
                continue

            source_label = f"{cfg['name']}: {link_text}"
            try:
                await ingest_run(source=source_label, text=text)
                await db.regulatory_fetch_log.insert_one({
                    "url_hash": url_hash,
                    "url": circular_url,
                    "source_key": source_key,
                    "source_label": source_label,
                    "fetched_at": datetime.utcnow(),
                })
                new_count += 1
                total_ingested += 1
            except Exception as e:
                print(f"    Ingest failed: {e}")

        print(f"  Ingested {new_count} new circular(s)")

    print(f"\nDone. Total ingested this run: {total_ingested}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch live regulatory circulars")
    parser.add_argument("--source", choices=list(SOURCES.keys()), help="Fetch only this source")
    args = parser.parse_args()
    asyncio.run(run(source_filter=args.source))
