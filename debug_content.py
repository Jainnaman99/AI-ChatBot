"""
Debug content extraction from web scraper
"""
import asyncio
import httpx
from bs4 import BeautifulSoup
from services.text_processor import get_text_processor

async def debug_content_extraction():
    url = "https://culture.gov.in"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    async with httpx.AsyncClient(verify=False, headers=headers, timeout=30.0) as client:
        print(f"Fetching {url}...")
        response = await client.get(url, follow_redirects=True)

        soup = BeautifulSoup(response.text, 'html.parser')

        print(f"\nFull HTML length: {len(response.text)} characters")

        # Try each selector (matching web_scraper.py logic)
        selectors = ['main', 'article', '.content', '#content', '.main-content']

        main_content = None
        matched_selector = None

        for selector in selectors:
            main_content = soup.select_one(selector)
            if main_content:
                matched_selector = selector
                print(f"[OK] Found content with selector: '{selector}'")
                break

        if not main_content:
            main_content = soup.body
            matched_selector = "body (fallback)"
            print(f"[OK] Using fallback: body element")

        # Extract content (matching web_scraper.py line 123)
        content = str(main_content) if main_content else response.text

        print(f"Extracted HTML length: {len(content)} characters")

        # Now process it like the ingestion script does
        processor = get_text_processor()

        cleaned_text = processor.clean_html(content)
        print(f"After clean_html: {len(cleaned_text)} characters")

        cleaned_text = processor.clean_text(cleaned_text)
        print(f"After clean_text: {len(cleaned_text)} characters")

        print(f"\nWill be skipped? {len(cleaned_text) < 100}")

        if len(cleaned_text) < 100:
            print("[ERROR] Document too short - will be skipped!")
            print(f"Content preview: {cleaned_text[:200]}")
        else:
            print("[OK] Document has enough content")
            print(f"Content preview (first 300 chars):\n{cleaned_text[:300]}...")

            # Test chunking
            chunks = processor.chunk_text(cleaned_text, {"url": url, "title": "Test"})
            print(f"\nChunks created: {len(chunks)}")

if __name__ == "__main__":
    asyncio.run(debug_content_extraction())
