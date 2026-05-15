"""
Debug link extraction and filtering
"""
import asyncio
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

TRUSTED_DOMAINS = [
    "culture.gov.in",
]

def is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')
        return domain in TRUSTED_DOMAINS
    except:
        return False

def should_skip_url(url: str) -> bool:
    skip_patterns = [
        '/login', '/signup', '/register', '/admin',
        '.pdf', '.doc', '.docx', '.xls', '.xlsx',
        '.jpg', '.jpeg', '.png', '.gif', '.svg',
        '.mp4', '.mp3', '.wav', '.avi', '.mov', '.wmv',
        '.zip', '.rar', '.tar', '.gz',
        '/search', '/contact', '/feedback',
        'javascript:', 'mailto:', '#'
    ]

    url_lower = url.lower()
    return any(pattern in url_lower for pattern in skip_patterns)

async def debug_link_extraction():
    url = "https://culture.gov.in"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    async with httpx.AsyncClient(verify=False, headers=headers, timeout=30.0) as client:
        print(f"Fetching {url}...")
        response = await client.get(url, follow_redirects=True)

        soup = BeautifulSoup(response.text, 'html.parser')

        all_links = []
        valid_links = []
        skipped_links = []

        for link in soup.find_all('a', href=True):
            href = link['href']
            absolute_url = urljoin(url, href)
            absolute_url = absolute_url.split('#')[0]

            if not absolute_url or absolute_url == url:
                continue

            all_links.append(absolute_url)

            # Check validation
            if not is_valid_url(absolute_url):
                skipped_links.append((absolute_url, "invalid domain"))
                continue

            if should_skip_url(absolute_url):
                skipped_links.append((absolute_url, "skip pattern matched"))
                continue

            valid_links.append(absolute_url)

        # Remove duplicates
        all_links = list(set(all_links))
        valid_links = list(set(valid_links))

        print(f"\n" + "="*80)
        print(f"SUMMARY:")
        print("="*80)
        print(f"Total links found: {len(all_links)}")
        print(f"Valid links to crawl: {len(valid_links)}")
        print(f"Filtered out: {len(all_links) - len(valid_links)}")

        print(f"\n" + "="*80)
        print(f"VALID LINKS TO CRAWL ({len(valid_links)}):")
        print("="*80)
        for i, link in enumerate(valid_links[:30], 1):
            print(f"{i}. {link}")

        if len(valid_links) > 30:
            print(f"... and {len(valid_links) - 30} more")

        print(f"\n" + "="*80)
        print(f"SAMPLE OF FILTERED OUT LINKS:")
        print("="*80)
        sample_skipped = {}
        for link, reason in skipped_links[:20]:
            if reason not in sample_skipped:
                sample_skipped[reason] = []
            sample_skipped[reason].append(link)

        for reason, links in sample_skipped.items():
            print(f"\n{reason.upper()}:")
            for link in links[:5]:
                print(f"  - {link}")

if __name__ == "__main__":
    asyncio.run(debug_link_extraction())
