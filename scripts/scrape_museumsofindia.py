"""
Scraper for museumsofindia.gov.in (server-rendered site, no SPA).

The site redirects / -> /repository and serves plain HTML with museum
descriptions, history, and collection info. Standard httpx + BeautifulSoup
scraping works fine without Playwright.

Stores vectors in : ./data/chroma_db
Collection name   : ministry_culture_kb (shared with other scrapers)

Usage:
    python scripts/scrape_museumsofindia.py
    python scripts/scrape_museumsofindia.py --clear
    python scripts/scrape_museumsofindia.py --max-pages 100
"""

import sys
import hashlib
import time
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse

import httpx
import warnings
warnings.filterwarnings("ignore")

sys.path.append(str(Path(__file__).parent.parent))

from bs4 import BeautifulSoup
from services.text_processor import get_text_processor
from services.embedding_service import get_embedding_service
from services.vector_store import get_vector_store

# Config
BASE_URL     = "https://museumsofindia.gov.in/repository"
SOURCE_LABEL = "museumsofindia.gov.in"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Known seed pages (discovered from site map + home page links)
SEED_URLS = [
    f"{BASE_URL}/home",
    f"{BASE_URL}/page/about",
    f"{BASE_URL}/page/digitization_initiative",
    f"{BASE_URL}/page/contact",
    f"{BASE_URL}/timeline",
    f"{BASE_URL}/museum/alh_ald",   # Allahabad Museum, Prayagraj
    f"{BASE_URL}/museum/gom_goa",   # ASI Goa
    f"{BASE_URL}/museum/im_kol",    # Indian Museum, Kolkata
    f"{BASE_URL}/museum/nkm_hyd",   # ASI Nagarjunakonda
    f"{BASE_URL}/museum/nat_del",   # National Museum, New Delhi
    f"{BASE_URL}/museum/ngma_blr",  # NGMA Bengaluru
    f"{BASE_URL}/museum/ngma_del",  # NGMA New Delhi
    f"{BASE_URL}/museum/ngma_mum",  # NGMA Mumbai
    f"{BASE_URL}/museum/sjm_hyd",   # Salar Jung Museum, Hyderabad
    f"{BASE_URL}/museum/vmh_kol",   # Victoria Memorial Hall, Kolkata
    f"{BASE_URL}/museum/avm_pun",   # Ambedkar Museum, Pune
]

# Tags to strip before extracting text
_STRIP_TAGS = ["script", "style", "nav", "footer", "header", "noscript", "iframe"]


def _extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(_STRIP_TAGS):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)


def _discover_links(html: str, current_url: str) -> list[str]:
    """Extract internal /repository/ links from a page."""
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        full = urljoin(current_url, href)
        parsed = urlparse(full)
        if (
            "museumsofindia.gov.in" in parsed.netloc
            and "/repository/" in parsed.path
            and "#" not in full
            and "javascript" not in full.lower()
        ):
            found.append(full.split("?")[0].split("#")[0])
    return found


def scrape_pages(max_pages: int = 100) -> list[dict]:
    client = httpx.Client(
        verify=False,
        timeout=20,
        follow_redirects=True,
        headers=HEADERS,
    )

    to_visit = list(dict.fromkeys(SEED_URLS))
    visited  = set()
    results  = []

    while to_visit and len(visited) < max_pages:
        url = to_visit.pop(0)
        if url in visited:
            continue
        visited.add(url)

        try:
            print(f"  Fetching: {url}")
            r = client.get(url)

            if r.status_code != 200:
                print(f"    SKIP ({r.status_code})")
                continue

            text = _extract_text(r.text)
            if len(text) < 100:
                print(f"    SKIP - too short ({len(text)} chars)")
                continue

            # Discover new pages to crawl
            new_links = _discover_links(r.text, url)
            for link in new_links:
                if link not in visited and link not in to_visit:
                    to_visit.append(link)

            # Build title from <title> tag
            soup = BeautifulSoup(r.text, "html.parser")
            raw_title = soup.find("title")
            title = raw_title.get_text(strip=True) if raw_title else url
            # Clean common suffix
            for suffix in [
                ": Museums of India: National Portal & Digital Repository",
                "Museums of India: National Portal & Digital Repository",
            ]:
                title = title.replace(suffix, "").strip()
            title = title or "Museums of India"

            print(f"    OK - '{title}' ({len(text)} chars)")
            results.append({
                "url":        url,
                "title":      title,
                "content":    text,
                "is_html":    False,
                "scraped_at": datetime.now().isoformat(),
            })

        except Exception as e:
            print(f"    ERROR: {e}")

        time.sleep(0.5)  # polite crawl delay

    client.close()
    print(f"\n  Visited {len(visited)} URLs, collected {len(results)} pages")
    return results


def ingest(max_pages: int = 100, clear_existing: bool = False):
    print("\n" + "=" * 60)
    print("MUSEUMSOFINDIA.GOV.IN - INGESTION PIPELINE")
    print("=" * 60)

    text_processor    = get_text_processor(chunk_size=800, chunk_overlap=100)
    embedding_service = get_embedding_service(model_name="all-MiniLM-L6-v2")
    vector_store      = get_vector_store(persist_directory="./data/chroma_db")

    if clear_existing:
        print("\nClearing existing collection...")
        vector_store.clear_collection()
        print("[OK] Collection cleared")

    # Step 1: Scrape
    print(f"\n{'-'*60}")
    print("STEP 1: SCRAPING")
    print(f"{'-'*60}")
    scraped = scrape_pages(max_pages=max_pages)

    if not scraped:
        print("[ERROR] Nothing scraped - exiting.")
        return

    print(f"\n[OK] {len(scraped)} pages with usable content")

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

    test_q   = "museums in India history collections"
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
    print("=" * 60)
    print(f"  Pages scraped  : {len(scraped)}")
    print(f"  Chunks created : {len(all_chunks)}")
    print(f"  Docs in DB     : {stats['count']}")
    print(f"\n  chroma_db is ready.\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Scrape museumsofindia.gov.in and ingest into chroma_db"
    )
    parser.add_argument("--max-pages", type=int, default=100,
                        help="Max pages to scrape (default: 100)")
    parser.add_argument("--clear", action="store_true",
                        help="Clear existing collection first")
    args = parser.parse_args()

    try:
        ingest(max_pages=args.max_pages, clear_existing=args.clear)
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
