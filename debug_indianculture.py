"""
Debug script to investigate indianculture.gov.in scraping issues
"""

import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import asyncio

async def debug_indianculture():
    """Debug what happens when scraping indianculture.gov.in"""

    url = "https://indianculture.gov.in"

    print("="*80)
    print(f"DEBUGGING: {url}")
    print("="*80)

    # Same headers as the scraper uses
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    try:
        async with httpx.AsyncClient(verify=False, headers=headers, timeout=30.0) as client:
            print("\n[1] Fetching URL...")
            response = await client.get(url, follow_redirects=True)
            print(f"    Status: {response.status_code}")
            print(f"    Final URL: {response.url}")
            print(f"    Content Length: {len(response.text)} characters")

            # Parse HTML
            print("\n[2] Parsing HTML...")
            soup = BeautifulSoup(response.text, 'html.parser')

            # Check for title
            title = soup.title.string if soup.title else "No title"
            print(f"    Page Title: {title}")

            # Check for popups/overlays
            print("\n[3] Checking for popups/overlays...")
            popups = soup.find_all(['div', 'section'], class_=lambda x: x and any(
                keyword in str(x).lower() for keyword in ['popup', 'modal', 'overlay', 'dialog']
            ))
            print(f"    Found {len(popups)} potential popup elements")
            for i, popup in enumerate(popups[:3], 1):
                classes = popup.get('class', [])
                print(f"      {i}. Classes: {classes}")

            # Try to find main content
            print("\n[4] Looking for main content...")
            for selector in ['main', 'article', '#content', '.main-content', 'body']:
                content = soup.select_one(selector)
                if content:
                    text = content.get_text(strip=True)
                    print(f"    Found via '{selector}': {len(text)} chars")
                    if len(text) > 0:
                        print(f"    Preview: {text[:200]}...")
                        break

            # Extract all links
            print("\n[5] Extracting links...")
            all_links = soup.find_all('a', href=True)
            print(f"    Total <a> tags found: {len(all_links)}")

            # Filter to same domain
            valid_links = []
            for link in all_links:
                href = link['href']
                absolute_url = urljoin(url, href)
                parsed = urlparse(absolute_url)
                domain = parsed.netloc.replace('www.', '')

                if domain == "indianculture.gov.in":
                    valid_links.append(absolute_url)

            print(f"    Same-domain links: {len(valid_links)}")

            # Show first 10 valid links
            if valid_links:
                print("\n[6] Sample valid links:")
                for i, link in enumerate(valid_links[:10], 1):
                    print(f"    {i}. {link}")
            else:
                print("\n[6] NO VALID LINKS FOUND!")
                print("    Showing first 10 raw hrefs:")
                for i, link in enumerate(all_links[:10], 1):
                    href = link.get('href', '')
                    print(f"    {i}. {href}")

            # Check for JavaScript-heavy page
            print("\n[7] Checking for JavaScript reliance...")
            scripts = soup.find_all('script')
            print(f"    Script tags found: {len(scripts)}")

            # Look for React/Vue/Angular
            page_text = response.text.lower()
            frameworks = {
                'React': 'react' in page_text or 'react-dom' in page_text,
                'Vue': 'vue.js' in page_text or '__vue__' in page_text,
                'Angular': 'angular' in page_text or 'ng-app' in page_text,
            }
            print("    JavaScript Frameworks detected:")
            for framework, detected in frameworks.items():
                status = "YES" if detected else "no"
                print(f"      {framework}: {status}")

            # Save HTML for inspection
            print("\n[8] Saving HTML to file...")
            with open("debug_indianculture.html", "w", encoding="utf-8") as f:
                f.write(response.text)
            print("    Saved to: debug_indianculture.html")

            # Summary
            print("\n" + "="*80)
            print("SUMMARY")
            print("="*80)
            print(f"✓ Page fetched: {response.status_code}")
            print(f"✓ Content length: {len(response.text)} chars")
            print(f"✓ Title: {title}")
            print(f"⚠ Valid links found: {len(valid_links)}")
            print(f"⚠ Popups detected: {len(popups)}")
            print(f"⚠ Script tags: {len(scripts)}")

            if len(valid_links) == 0:
                print("\n❌ PROBLEM: No internal links found!")
                print("   Possible causes:")
                print("   1. Links are generated by JavaScript")
                print("   2. Popup is blocking link extraction")
                print("   3. Links use different domain/subdomain")
                print("   4. Page structure is unusual")

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_indianculture())
