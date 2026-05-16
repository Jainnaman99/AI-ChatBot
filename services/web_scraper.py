"""
Web scraping service for Ministry of Culture websites
Crawls and extracts content from trusted government sites
"""

import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Set
from urllib.parse import urljoin, urlparse
import asyncio
import time
from datetime import datetime
import warnings

# Suppress SSL warnings for government sites with certificate issues
warnings.filterwarnings('ignore', message='Unverified HTTPS request')


class WebScraper:
    """
    Web scraper for Ministry of Culture websites
    """

    # Trusted domains to scrape
    TRUSTED_DOMAINS = [
        "culture.gov.in",
        "indianculture.gov.in",
        "vedicheritage.gov.in",
        "museumsofindia.gov.in/repository"
    ]

    def __init__(self, rate_limit: float = 2.0, max_pages: int = 500, timeout: float = 30.0):
        """
        Initialize web scraper

        Args:
            rate_limit: Seconds to wait between requests
            max_pages: Maximum pages to scrape per domain
            timeout: Request timeout in seconds
        """
        self.rate_limit = rate_limit
        self.max_pages = max_pages
        self.timeout = timeout
        self.visited_urls: Set[str] = set()
        self.scraped_data: List[Dict] = []

    def is_valid_url(self, url: str) -> bool:
        """
        Check if URL is from trusted domain

        Args:
            url: URL to check

        Returns:
            True if valid, False otherwise
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.replace('www.', '')
            return domain in self.TRUSTED_DOMAINS
        except:
            return False

    def should_skip_url(self, url: str) -> bool:
        """
        Check if URL should be skipped

        Args:
            url: URL to check

        Returns:
            True if should skip, False otherwise
        """
        # Skip common non-content URLs and media files
        skip_patterns = [
            '/login', '/signup', '/register', '/admin',
            # '.pdf', '.doc', '.docx', '.xls', '.xlsx',
            '.xls', '.xlsx',
            '.jpg', '.jpeg', '.png', '.gif', '.svg',
            '.mp4', '.mp3', '.wav', '.avi', '.mov', '.wmv',  # Video/audio files
            '.zip', '.rar', '.tar', '.gz',  # Archives
            '/search', '/contact', '/feedback',
            'javascript:', 'mailto:', '#'
        ]

        url_lower = url.lower()
        return any(pattern in url_lower for pattern in skip_patterns)

    async def fetch_page(self, url: str, client: httpx.AsyncClient) -> Dict:
        """
        Fetch a single page

        Args:
            url: URL to fetch
            client: HTTP client

        Returns:
            Dict with URL, content, title, and status
        """
        try:
            print(f"Fetching: {url}")

            response = await client.get(url, timeout=self.timeout, follow_redirects=True)
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract title
            title = soup.title.string if soup.title else "Untitled"

            # Extract main content
            # Try to find main content area
            main_content = None
            for selector in ['main', 'article', '#content', '.main-content']:
                main_content = soup.select_one(selector)
                if main_content:
                    # Check if content is substantial enough
                    text_preview = main_content.get_text().strip()
                    if len(text_preview) > 100:  # Only use if has meaningful content
                        break
                    else:
                        main_content = None  # Too small, try next selector

            # If no main content found, use body
            if not main_content:
                main_content = soup.body

            content = str(main_content) if main_content else response.text

            return {
                "url": url,
                "title": title.strip(),
                "content": content,
                "full_html": response.text,  # Store full HTML for link extraction
                "status": "success",
                "scraped_at": datetime.now().isoformat(),
                "content_length": len(content)
            }

        except httpx.HTTPStatusError as e:
            print(f"HTTP error for {url}: {e.response.status_code}")
            return {"url": url, "status": "error", "error": f"HTTP {e.response.status_code}"}
        except httpx.TimeoutException:
            print(f"Timeout for {url}")
            return {"url": url, "status": "error", "error": "Timeout"}
        except Exception as e:
            print(f"Error fetching {url}: {str(e)}")
            return {"url": url, "status": "error", "error": str(e)}

    def extract_links(self, html: str, base_url: str) -> List[str]:
        """
        Extract links from HTML

        Args:
            html: HTML content
            base_url: Base URL for resolving relative links

        Returns:
            List of absolute URLs
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            links = []

            for link in soup.find_all('a', href=True):
                href = link['href']

                # Convert relative URLs to absolute
                absolute_url = urljoin(base_url, href)

                # Clean URL (remove fragments)
                absolute_url = absolute_url.split('#')[0]

                # Validate and filter
                if self.is_valid_url(absolute_url) and not self.should_skip_url(absolute_url):
                    links.append(absolute_url)

            return list(set(links))  # Remove duplicates

        except Exception as e:
            print(f"Error extracting links: {str(e)}")
            return []

    async def crawl_domain(self, start_url: str) -> List[Dict]:
        """
        Crawl a domain starting from a URL

        Args:
            start_url: Starting URL

        Returns:
            List of scraped page data
        """
        to_visit = [start_url]
        domain_data = []

        # Browser-like headers to avoid being blocked
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

        # Disable SSL verification for government sites with certificate issues
        async with httpx.AsyncClient(
            follow_redirects=True,
            verify=False,
            headers=headers,
            timeout=30.0
        ) as client:
            while to_visit and len(self.visited_urls) < self.max_pages:
                url = to_visit.pop(0)

                # Skip if already visited
                if url in self.visited_urls:
                    continue

                self.visited_urls.add(url)

                # Fetch page
                page_data = await self.fetch_page(url, client)

                # Add to results if successful
                if page_data["status"] == "success":
                    domain_data.append(page_data)

                    # Extract links for further crawling (use full HTML, not just main content)
                    full_html = page_data.get("full_html", page_data["content"])
                    new_links = self.extract_links(full_html, url)
                    print(f"  Found {len(new_links)} valid links to crawl")

                    # Add new links to queue
                    for link in new_links:
                        if link not in self.visited_urls and link not in to_visit:
                            to_visit.append(link)

                # Rate limiting
                await asyncio.sleep(self.rate_limit)

                # Progress
                if len(self.visited_urls) % 10 == 0:
                    print(f"Progress: {len(self.visited_urls)} pages visited, {len(to_visit)} in queue")

        return domain_data

    async def scrape_all_sites(self) -> List[Dict]:
        """
        Scrape all trusted sites

        Returns:
            List of all scraped page data
        """
        print("Starting web scraping...")
        print(f"Trusted domains: {', '.join(self.TRUSTED_DOMAINS)}")

        all_data = []

        for domain in self.TRUSTED_DOMAINS:
            start_url = f"https://{domain}"
            print(f"\n=== Crawling {domain} ===")

            try:
                domain_data = await self.crawl_domain(start_url)
                all_data.extend(domain_data)
                print(f"Completed {domain}: {len(domain_data)} pages scraped")
            except Exception as e:
                print(f"Error crawling {domain}: {str(e)}")

        print(f"\n=== Scraping Complete ===")
        print(f"Total pages scraped: {len(all_data)}")
        print(f"Total URLs visited: {len(self.visited_urls)}")

        return all_data


def get_web_scraper(rate_limit: float = 2.0, max_pages: int = 500) -> WebScraper:
    """
    Get web scraper instance

    Args:
        rate_limit: Seconds between requests
        max_pages: Max pages per domain

    Returns:
        WebScraper instance
    """
    return WebScraper(rate_limit=rate_limit, max_pages=max_pages)
