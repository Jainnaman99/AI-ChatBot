"""
Dedicated scraper for indianculture.gov.in using Playwright + API interception.

The site is a React SPA that fetches data from icvtestingold.nvli.in/rest-v1/.
Standard HTTP scraping returns empty shells. This script:
  1. Opens each seed URL in a real headless Chromium browser
  2. Intercepts the JSON API responses the browser receives automatically
  3. Extracts meaningful text from the JSON payloads
  4. Chunks, embeds, and stores in chroma_db

Stores vectors in : ./data/chroma_db
Collection name   : ministry_culture_kb (default)

Usage:
    python scripts/scrape_indianculture.py
    python scripts/scrape_indianculture.py --clear
    python scripts/scrape_indianculture.py --max-pages 50
"""

import asyncio
import sys
import os
import hashlib
import json
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent))

from services.text_processor import get_text_processor
from services.embedding_service import get_embedding_service
from services.vector_store import get_vector_store

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL      = "https://indianculture.gov.in"
API_HOST      = "icvtestingold.nvli.in"   # backend that serves JSON
SOURCE_LABEL  = "indianculture.gov.in"

# Pages to visit - one per section/topic
SEED_URLS = [
    f"{BASE_URL}/performing-arts",
    f"{BASE_URL}/performing-arts/dance",
    f"{BASE_URL}/performing-arts/music",
    f"{BASE_URL}/performing-arts/theatre",
    f"{BASE_URL}/performing-arts/puppetry",
    f"{BASE_URL}/visual-arts",
    f"{BASE_URL}/visual-arts/paintings",
    f"{BASE_URL}/visual-arts/sculpture",
    f"{BASE_URL}/visual-arts/crafts",
    f"{BASE_URL}/manuscripts",
    f"{BASE_URL}/monuments",
    f"{BASE_URL}/intangible-cultural-heritage",
    f"{BASE_URL}/photo-archives",
    f"{BASE_URL}/living-traditions",
    f"{BASE_URL}/living-traditions/folk-arts",
    f"{BASE_URL}/living-traditions/tribal-arts",
    f"{BASE_URL}/personalities",
    f"{BASE_URL}/freedom-movement",
    f"{BASE_URL}/museums",
    f"{BASE_URL}/vedic-heritage",
    f"{BASE_URL}/heritage-sites",
    f"{BASE_URL}/natural-heritage",
    f"{BASE_URL}/festivals",
    f"{BASE_URL}/literature",
    f"{BASE_URL}/architecture",
]


# ── JSON → plain text ─────────────────────────────────────────────────────────
# Fields that typically carry readable content in the API responses
_TEXT_FIELDS = {
    "title", "name", "heading", "label",
    "description", "body", "content", "text", "summary",
    "detail", "overview", "about", "info", "caption",
    "short_description", "long_description", "field_description",
    "field_body", "field_summary", "field_content",
}

def _extract_text_from_json(obj, depth: int = 0) -> str:
    """Recursively pull text from a JSON object."""
    if depth > 8:
        return ""
    parts = []
    if isinstance(obj, dict):
        for key, val in obj.items():
            key_lower = key.lower()
            if isinstance(val, str) and val.strip():
                if key_lower in _TEXT_FIELDS or any(f in key_lower for f in _TEXT_FIELDS):
                    parts.append(val.strip())
            elif isinstance(val, (dict, list)):
                parts.append(_extract_text_from_json(val, depth + 1))
    elif isinstance(obj, list):
        for item in obj:
            parts.append(_extract_text_from_json(item, depth + 1))
    elif isinstance(obj, str) and len(obj) > 40:
        parts.append(obj.strip())
    return " ".join(p for p in parts if p)


# ── Per-page scrape ───────────────────────────────────────────────────────────
async def scrape_page(page, url: str) -> dict | None:
    """
    Navigate to a page, intercept API JSON responses, extract text.
    Falls back to rendered body text if no API responses are captured.
    """
    api_payloads: list[dict] = []

    async def on_response(response):
        if API_HOST in response.url:
            try:
                ct = response.headers.get("content-type", "")
                if "json" in ct:
                    data = await response.json()
                    api_payloads.append({"api_url": response.url, "data": data})
            except Exception:
                pass

    page.on("response", on_response)

    try:
        print(f"  Fetching: {url}")
        await page.goto(url, timeout=30_000, wait_until="domcontentloaded")

        # Wait for network to settle so API calls complete
        try:
            await page.wait_for_load_state("networkidle", timeout=12_000)
        except Exception:
            pass

        # Extra buffer for late API calls
        await page.wait_for_timeout(2_000)

        title = await page.title()
        title = (
            title
            .replace(" | INDIAN CULTURE", "")
            .replace("| Indian Cultural Portal", "")
            .replace("Indian Cultural Portal", "")
            .strip()
        ) or "Indian Culture"

        # Build text from intercepted API JSON payloads
        text_parts = []
        for payload in api_payloads:
            extracted = _extract_text_from_json(payload["data"])
            if extracted:
                text_parts.append(extracted)

        combined_text = " ".join(text_parts).strip()
        print(f"    API calls intercepted: {len(api_payloads)} | text length: {len(combined_text)}")

        # Fallback: use rendered page body text
        if len(combined_text) < 100:
            try:
                body_text = await page.inner_text("body")
                # Strip boilerplate navigation noise
                combined_text = body_text.strip()
                print(f"    Fallback to body text: {len(combined_text)} chars")
            except Exception:
                pass

        if len(combined_text) < 50:
            print(f"    SKIP - insufficient content")
            return None

        return {
            "url":        url,
            "title":      title,
            "content":    combined_text,
            "is_html":    False,   # already plain text
            "scraped_at": datetime.now().isoformat(),
        }

    except Exception as e:
        print(f"    ERROR: {e}")
        return None
    finally:
        page.remove_listener("response", on_response)


# ── Crawl ─────────────────────────────────────────────────────────────────────
async def crawl(max_pages: int = 200) -> list[dict]:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("\n[ERROR] Playwright not installed.")
        print("  Run: pip install playwright && playwright install chromium\n")
        sys.exit(1)

    urls_to_visit = list(dict.fromkeys(SEED_URLS))  # deduplicate, preserve order
    visited       = set()
    results       = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            ignore_https_errors=True,
        )
        page = await context.new_page()

        for url in urls_to_visit:
            if len(visited) >= max_pages:
                break
            if url in visited:
                continue
            visited.add(url)

            data = await scrape_page(page, url)
            if data:
                results.append(data)
                print(f"    OK -'{data['title']}'")
            print(f"  Progress: {len(visited)}/{min(len(urls_to_visit), max_pages)} pages")

        await browser.close()

    return results


# ── Ingest pipeline ───────────────────────────────────────────────────────────
async def ingest(max_pages: int = 200, clear_existing: bool = False):
    print("\n" + "=" * 60)
    print("INDIANCULTURE.GOV.IN - PLAYWRIGHT INGESTION PIPELINE")
    print("=" * 60)

    text_processor    = get_text_processor(chunk_size=800, chunk_overlap=100)
    embedding_service = get_embedding_service(model_name="all-MiniLM-L6-v2")
    vector_store      = get_vector_store(persist_directory="./data/chroma_db")

    if clear_existing:
        print("\nClearing existing test collection...")
        vector_store.clear_collection()
        print("[OK] Collection cleared")

    # Step 1: Scrape
    print(f"\n{'-'*60}")
    print("STEP 1: SCRAPING  (Playwright + API interception)")
    print(f"{'-'*60}")
    scraped = await crawl(max_pages=max_pages)
    print(f"\n[OK] {len(scraped)} pages with usable content")

    if not scraped:
        print("[ERROR] Nothing scraped - exiting.")
        return

    # Step 2: Chunk
    print(f"\n{'-'*60}")
    print("STEP 2: TEXT PROCESSING & CHUNKING")
    print(f"{'-'*60}")
    all_chunks = []
    for page_data in scraped:
        try:
            chunks = text_processor.process_document(
                content=page_data["content"],
                url=page_data["url"],
                title=page_data["title"],
                is_html=page_data.get("is_html", False),
            )
            all_chunks.extend(chunks)
        except Exception as e:
            print(f"  Error processing {page_data['url']}: {e}")

    if not all_chunks:
        print("[ERROR] No chunks created - exiting.")
        return

    avg = sum(len(c["text"]) for c in all_chunks) // len(all_chunks)
    print(f"[OK] {len(all_chunks)} chunks | avg size: {avg} chars")

    # Step 3: Embeddings
    print(f"\n{'-'*60}")
    print("STEP 3: GENERATING EMBEDDINGS")
    print(f"{'-'*60}")
    texts      = [c["text"] for c in all_chunks]
    embeddings = embedding_service.generate_embeddings_batch(texts, batch_size=32, show_progress=True)
    print(f"[OK] {len(embeddings)} embeddings (dim={embedding_service.embedding_dimension})")

    # Step 4: Store
    print(f"\n{'-'*60}")
    print("STEP 4: STORING IN chroma_db")
    print(f"{'-'*60}")

    now_iso   = datetime.now().isoformat()
    documents = texts
    metadatas = []
    ids       = []

    for i, chunk in enumerate(all_chunks):
        chunk_id = hashlib.md5(f"{chunk['url']}_{chunk.get('start_pos', i)}".encode()).hexdigest()
        ids.append(chunk_id)
        metadatas.append({
            "url":          chunk["url"],
            "title":        chunk["title"],
            "chunk_index":  i,
            "chunk_length": chunk["chunk_length"],
            "source":       SOURCE_LABEL,
            "ingested_at":  now_iso,
        })

    BATCH_SIZE = 5000
    total      = len(documents)
    for i in range(0, total, BATCH_SIZE):
        end = min(i + BATCH_SIZE, total)
        print(f"  Storing batch {i // BATCH_SIZE + 1} ({end - i} docs)...")
        vector_store.add_documents(
            documents  = documents[i:end],
            embeddings = embeddings[i:end],
            metadatas  = metadatas[i:end],
            ids        = ids[i:end],
        )
    print(f"[OK] {total} documents stored")

    # Step 5: Verify
    print(f"\n{'-'*60}")
    print("STEP 5: VERIFICATION")
    print(f"{'-'*60}")
    stats = vector_store.get_collection_stats()
    print(f"  Collection : {stats['name']}")
    print(f"  Total docs : {stats['count']}")
    print(f"  Location   : ./data/chroma_db")

    test_q   = "classical dance forms India"
    test_emb = embedding_service.generate_embedding(test_q)
    results  = vector_store.search(test_emb, n_results=3)
    if results["documents"]:
        print(f"\n[OK] Test search '{test_q}':")
        for i, (doc, meta) in enumerate(zip(results["documents"], results["metadatas"]), 1):
            print(f"  {i}. {meta.get('title')} | {meta.get('url')}")
            print(f"     {doc[:100]}...")
    else:
        print("\n[WARNING] Test search returned no results")

    print(f"\n{'='*60}")
    print("INGESTION COMPLETE")
    print("="*60)
    print(f"  Pages scraped  : {len(scraped)}")
    print(f"  Chunks created : {len(all_chunks)}")
    print(f"  Docs in DB     : {stats['count']}")
    print(f"\n  chroma_db is ready.\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Scrape indianculture.gov.in and ingest into chroma_db"
    )
    parser.add_argument("--max-pages", type=int, default=200,
                        help="Max pages to scrape (default: 25 seed URLs)")
    parser.add_argument("--clear", action="store_true",
                        help="Clear existing chroma_db collection first")
    args = parser.parse_args()

    try:
        asyncio.run(ingest(max_pages=args.max_pages, clear_existing=args.clear))
    except KeyboardInterrupt:
        print("\n[WARNING] Interrupted by user")
        sys.exit(1)
    except Exception as e:
        import traceback
        print(f"\n[ERROR] {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
