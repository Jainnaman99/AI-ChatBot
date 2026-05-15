"""
Debug script to test web scraping
"""
import asyncio
import httpx
from bs4 import BeautifulSoup
from services.text_processor import get_text_processor
from urllib.parse import urljoin

async def debug_homepage():
    url = "https://culture.gov.in"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    }

    async with httpx.AsyncClient(verify=False, headers=headers, timeout=30.0) as client:
        print(f"Fetching {url}...")
        response = await client.get(url, follow_redirects=True)

        print(f"Status: {response.status_code}")
        print(f"Content length: {len(response.text)} bytes")

        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract title
        title = soup.title.string if soup.title else "No title"
        print(f"Title: {title}")

        # Test text processing
        processor = get_text_processor()
        cleaned_text = processor.clean_html(response.text)
        print(f"\nCleaned text length: {len(cleaned_text)} characters")
        print(f"First 500 chars of cleaned text:")
        print(cleaned_text[:500])
        print("...")

        # Extract links
        print("\n" + "="*60)
        print("LINKS FOUND:")
        print("="*60)

        links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            absolute_url = urljoin(url, href)

            # Clean URL
            absolute_url = absolute_url.split('#')[0]

            # Check if it's from the same domain
            if 'culture.gov.in' in absolute_url:
                links.append(absolute_url)

        unique_links = list(set(links))
        print(f"Total unique links found: {len(unique_links)}")

        # Show first 20 links
        for i, link in enumerate(unique_links[:20], 1):
            print(f"{i}. {link}")

        if len(unique_links) > 20:
            print(f"... and {len(unique_links) - 20} more")

if __name__ == "__main__":
    asyncio.run(debug_homepage())
