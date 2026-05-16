"""
TEST Data ingestion script for vector search
Scrapes only 1 domain for quick testing (runs parallel to main ingestion)
Uses separate ChromaDB database: ./data/chroma_db_test
"""

import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from services.text_processor import get_text_processor
from services.embedding_service import get_embedding_service
from services.vector_store import get_vector_store
import hashlib
from datetime import datetime
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import warnings

# Suppress SSL warnings for government sites with certificate issues
warnings.filterwarnings('ignore', message='Unverified HTTPS request')


class TestWebScraper:
    """
    Test web scraper - only scrapes culture.gov.in
    """

    # Only 1 domain for testing
    TRUSTED_DOMAINS = [
        # "culture.gov.in"
        # "indianculture.gov.in"
        # "museumsofindia.gov.in/repository/home"
        "vedicheritage.gov.in"
    ]

    def __init__(self, rate_limit: float = 2.0, max_pages: int = 50, timeout: float = 30.0):
        """
        Initialize web scraper

        Args:
            rate_limit: Seconds to wait between requests
            max_pages: Maximum pages to scrape
            timeout: Request timeout in seconds
        """
        self.rate_limit = rate_limit
        self.max_pages = max_pages
        self.timeout = timeout
        self.visited_urls = set()
        self.scraped_data = []

    def is_valid_url(self, url: str) -> bool:
        """Check if URL is from trusted domain"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.replace('www.', '')
            return domain in self.TRUSTED_DOMAINS
        except:
            return False

    def should_skip_url(self, url: str) -> bool:
        """Check if URL should be skipped"""
        skip_patterns = [
            '/login', '/signup', '/register', '/admin',
            '.xls', '.xlsx','.pdf',
            '.jpg', '.jpeg', '.png', '.gif', '.svg',
            '.mp4', '.mp3', '.wav', '.avi', '.mov', '.wmv',
            '.zip', '.rar', '.tar', '.gz',
            '/search', '/contact', '/feedback',
            'javascript:', 'mailto:', '#'
        ]

        url_lower = url.lower()
        return any(pattern in url_lower for pattern in skip_patterns)

    async def fetch_page(self, url: str, client: httpx.AsyncClient):
        """Fetch a single page"""
        try:
            print(f"Fetching: {url}")

            response = await client.get(url, timeout=self.timeout, follow_redirects=True)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.title.string if soup.title else "Untitled"

            # Extract main content
            main_content = None
            for selector in ['main', 'article', '#content', '.main-content']:
                main_content = soup.select_one(selector)
                if main_content:
                    text_preview = main_content.get_text().strip()
                    if len(text_preview) > 100:
                        break
                    else:
                        main_content = None

            if not main_content:
                main_content = soup.body

            content = str(main_content) if main_content else response.text

            return {
                "url": url,
                "title": title.strip(),
                "content": content,
                "full_html": response.text,
                "status": "success",
                "scraped_at": datetime.now().isoformat(),
                "content_length": len(content)
            }

        except Exception as e:
            print(f"Error fetching {url}: {str(e)}")
            return {"url": url, "status": "error", "error": str(e)}

    def extract_links(self, html: str, base_url: str):
        """Extract links from HTML"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            links = []

            for link in soup.find_all('a', href=True):
                href = link['href']
                absolute_url = urljoin(base_url, href)
                absolute_url = absolute_url.split('#')[0]

                if self.is_valid_url(absolute_url) and not self.should_skip_url(absolute_url):
                    links.append(absolute_url)

            return list(set(links))

        except Exception as e:
            print(f"Error extracting links: {str(e)}")
            return []

    async def crawl_domain(self, start_url: str):
        """Crawl a domain starting from a URL"""
        to_visit = [start_url]
        domain_data = []

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }

        async with httpx.AsyncClient(
            follow_redirects=True,
            verify=False,
            headers=headers,
            timeout=30.0
        ) as client:
            while to_visit and len(self.visited_urls) < self.max_pages:
                url = to_visit.pop(0)

                if url in self.visited_urls:
                    continue

                self.visited_urls.add(url)
                page_data = await self.fetch_page(url, client)

                if page_data["status"] == "success":
                    domain_data.append(page_data)

                    full_html = page_data.get("full_html", page_data["content"])
                    new_links = self.extract_links(full_html, url)
                    print(f"  Found {len(new_links)} valid links to crawl")

                    for link in new_links:
                        if link not in self.visited_urls and link not in to_visit:
                            to_visit.append(link)

                await asyncio.sleep(self.rate_limit)

                if len(self.visited_urls) % 10 == 0:
                    print(f"Progress: {len(self.visited_urls)} pages visited, {len(to_visit)} in queue")

        return domain_data

    async def scrape_all_sites(self):
        """Scrape all trusted sites"""
        print("Starting TEST web scraping...")
        print(f"Test domain: {', '.join(self.TRUSTED_DOMAINS)}")

        all_data = []

        for domain in self.TRUSTED_DOMAINS:
            start_url = f"https://{domain}"
            print(f"\n=== Crawling {domain} (TEST MODE) ===")

            try:
                domain_data = await self.crawl_domain(start_url)
                all_data.extend(domain_data)
                print(f"Completed {domain}: {len(domain_data)} pages scraped")
            except Exception as e:
                print(f"Error crawling {domain}: {str(e)}")

        print(f"\n=== Scraping Complete ===")
        print(f"Total pages scraped: {len(all_data)}")

        return all_data


async def ingest_data_test(max_pages: int = 50, clear_existing: bool = False):
    """
    TEST data ingestion pipeline - uses separate database

    Args:
        max_pages: Maximum pages to scrape
        clear_existing: Whether to clear existing vector DB
    """
    print("\n" + "="*60)
    print("TEST MODE - DATA INGESTION PIPELINE")
    print("Database: ./data/chroma_db_test")
    print("Domain: culture.gov.in only")
    print("="*60 + "\n")

    # Initialize services with TEST database
    print("Initializing services...")
    scraper = TestWebScraper(rate_limit=2.0, max_pages=max_pages)
    text_processor = get_text_processor(chunk_size=800, chunk_overlap=100)
    embedding_service = get_embedding_service(model_name="all-MiniLM-L6-v2")
    vector_store = get_vector_store(persist_directory="./data/chroma_db_test")

    if clear_existing:
        print("\nClearing existing TEST vector database...")
        vector_store.clear_collection()
        print("[OK] TEST vector database cleared")

    # Step 1: Scrape website
    print("\n" + "-"*60)
    print("STEP 1: WEB SCRAPING (TEST)")
    print("-"*60)
    print(f"Scraping up to {max_pages} pages from culture.gov.in...\n")

    scraped_data = await scraper.scrape_all_sites()

    if not scraped_data:
        print("[ERROR] No data scraped. Exiting.")
        return

    print(f"\n[OK] Scraped {len(scraped_data)} pages successfully")

    # Step 2: Process and chunk text
    print("\n" + "-"*60)
    print("STEP 2: TEXT PROCESSING & CHUNKING")
    print("-"*60)

    all_chunks = []
    for page_data in scraped_data:
        try:
            chunks = text_processor.process_document(
                content=page_data['content'],
                url=page_data['url'],
                title=page_data['title'],
                is_html=True
            )
            all_chunks.extend(chunks)
        except Exception as e:
            print(f"Error processing {page_data['url']}: {str(e)}")

    if not all_chunks:
        print("[ERROR] No text chunks created. Exiting.")
        return

    print(f"\n[OK] Created {len(all_chunks)} text chunks")

    # Step 3: Generate embeddings
    print("\n" + "-"*60)
    print("STEP 3: GENERATING EMBEDDINGS")
    print("-"*60)

    texts = [chunk['text'] for chunk in all_chunks]

    embeddings = embedding_service.generate_embeddings_batch(
        texts,
        batch_size=32,
        show_progress=True
    )

    print(f"\n[OK] Generated {len(embeddings)} embeddings")

    # Step 4: Store in vector database
    print("\n" + "-"*60)
    print("STEP 4: STORING IN VECTOR DATABASE (TEST)")
    print("-"*60)

    documents = texts
    metadatas = []
    ids = []

    for i, chunk in enumerate(all_chunks):
        chunk_id = hashlib.md5(f"{chunk['url']}_{i}".encode()).hexdigest()
        ids.append(chunk_id)

        metadata = {
            "url": chunk['url'],
            "title": chunk['title'],
            "chunk_index": i,
            "chunk_length": chunk['chunk_length'],
            "ingested_at": datetime.now().isoformat()
        }
        metadatas.append(metadata)

    # Add to vector store
    BATCH_SIZE = 5000
    total_docs = len(documents)

    try:
        for i in range(0, total_docs, BATCH_SIZE):
            end_idx = min(i + BATCH_SIZE, total_docs)
            batch_docs = documents[i:end_idx]
            batch_embeddings = embeddings[i:end_idx]
            batch_metadatas = metadatas[i:end_idx]
            batch_ids = ids[i:end_idx]

            print(f"  Storing batch {i//BATCH_SIZE + 1} ({len(batch_docs)} documents)...")

            vector_store.add_documents(
                documents=batch_docs,
                embeddings=batch_embeddings,
                metadatas=batch_metadatas,
                ids=batch_ids
            )

        print(f"\n[OK] Successfully stored {total_docs} documents in TEST database")
    except Exception as e:
        print(f"[ERROR] Error storing documents: {str(e)}")
        return

    # Step 5: Verification
    print("\n" + "-"*60)
    print("STEP 5: VERIFICATION (TEST)")
    print("-"*60)

    stats = vector_store.get_collection_stats()
    print(f"\nTEST Vector Database Statistics:")
    print(f"  Collection name: {stats['name']}")
    print(f"  Total documents: {stats['count']}")
    print(f"  Storage location: ./data/chroma_db_test")

    # Summary
    print("\n" + "="*60)
    print("TEST INGESTION COMPLETE!")
    print("="*60)
    print(f"\n=== Summary ===")
    print(f"   Pages scraped: {len(scraped_data)}")
    print(f"   Text chunks created: {len(all_chunks)}")
    print(f"   Documents stored: {stats['count']}")
    print(f"\n>>> To use this TEST database:")
    print(f"   1. Set environment variable: set TEST_MODE=1")
    print(f"   2. Restart API server")
    print(f"   3. Test your endpoints with test data")
    print()


def main():
    """Main entry point for TEST ingestion"""
    import argparse

    parser = argparse.ArgumentParser(description="TEST data ingestion (1 domain only)")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=500,
        help="Maximum pages to scrape (default: 500 for full scrape)"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing TEST vector database before ingestion"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: only scrape 50 pages for fast testing"
    )

    args = parser.parse_args()

    # Adjust max pages for quick mode
    max_pages = 50 if args.quick else args.max_pages

    if args.quick:
        print("\n>>> QUICK TEST MODE: Scraping only 50 pages from culture.gov.in")
    else:
        print("\n>>> TEST MODE: Full scrape of culture.gov.in")

    print(f">>> Max pages: {max_pages}")
    print(f">>> Database: ./data/chroma_db_test\n")

    try:
        asyncio.run(ingest_data_test(
            max_pages=max_pages,
            clear_existing=args.clear
        ))
    except KeyboardInterrupt:
        print("\n\n[WARNING] TEST ingestion interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[ERROR] Error during TEST ingestion: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
