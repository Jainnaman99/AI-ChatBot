"""
Debug script to investigate museumsofindia.gov.in connection issues
"""

import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import asyncio
import socket

async def debug_museumsofindia():
    """Debug what happens when trying to connect to museumsofindia.gov.in"""

    url = "https://museumsofindia.gov.in"

    print("="*80)
    print(f"DEBUGGING: {url}")
    print("="*80)

    # First, try DNS resolution
    print("\n[1] Testing DNS resolution...")
    try:
        domain = "museumsofindia.gov.in"
        ip_address = socket.gethostbyname(domain)
        print(f"    [OK] DNS resolved: {domain} -> {ip_address}")
    except socket.gaierror as e:
        print(f"    [ERROR] DNS resolution failed: {str(e)}")
        print("    This domain may not exist or DNS is not accessible")
        return

    # Same headers as the scraper uses
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    # Try different protocol combinations
    test_urls = [
        "https://museumsofindia.gov.in",
        "http://museumsofindia.gov.in",
        "https://www.museumsofindia.gov.in",
        "http://www.museumsofindia.gov.in",
    ]

    print("\n[2] Testing different URL variations...")
    for test_url in test_urls:
        print(f"\n  Testing: {test_url}")
        try:
            async with httpx.AsyncClient(
                verify=False,
                headers=headers,
                timeout=30.0,
                follow_redirects=True
            ) as client:
                response = await client.get(test_url)
                print(f"    [OK] Status: {response.status_code}")
                print(f"    [OK] Final URL: {response.url}")
                print(f"    [OK] Content Length: {len(response.text)} characters")

                # Parse and check content
                soup = BeautifulSoup(response.text, 'html.parser')
                title = soup.title.string if soup.title else "No title"
                print(f"    [OK] Page Title: {title}")

                # This URL works - use it for further testing
                working_url = str(response.url)

                # Extract some content
                text = soup.get_text(strip=True)
                print(f"    [OK] Text content: {len(text)} chars")
                if len(text) > 0:
                    print(f"    [OK] Preview: {text[:200]}...")

                # Check for links
                all_links = soup.find_all('a', href=True)
                print(f"    [OK] Total <a> tags found: {len(all_links)}")

                # Filter valid links
                valid_links = []
                for link in all_links[:20]:  # Check first 20 links
                    href = link['href']
                    absolute_url = urljoin(working_url, href)
                    parsed = urlparse(absolute_url)
                    domain_check = parsed.netloc.replace('www.', '')

                    if "museumsofindia.gov.in" in domain_check:
                        valid_links.append(absolute_url)

                print(f"    [OK] Same-domain links (sample): {len(valid_links)}")

                if valid_links:
                    print("\n    Sample links:")
                    for i, link in enumerate(valid_links[:5], 1):
                        print(f"      {i}. {link}")

                # Save HTML
                print("\n[3] Saving HTML to file...")
                with open("debug_museumsofindia.html", "w", encoding="utf-8") as f:
                    f.write(response.text)
                print("    [OK] Saved to: debug_museumsofindia.html")

                # Success - exit
                print("\n" + "="*80)
                print("SUCCESS!")
                print("="*80)
                print(f"[OK] Working URL: {working_url}")
                print(f"[OK] Status: {response.status_code}")
                print(f"[OK] Content available: YES")
                print(f"[OK] Links found: {len(valid_links)} (sample of {len(all_links)} total)")
                return

        except httpx.ConnectError as e:
            print(f"    [ERROR] Connection error: {str(e)}")
        except httpx.TimeoutException:
            print(f"    [ERROR] Timeout (30 seconds)")
        except Exception as e:
            print(f"    [ERROR] Error: {str(e)}")

    # If we get here, all URLs failed
    print("\n" + "="*80)
    print("FAILURE - ALL CONNECTION ATTEMPTS FAILED")
    print("="*80)
    print("\nPossible causes:")
    print("1. Website is down or not accessible")
    print("2. Server is blocking automated requests")
    print("3. Network/firewall blocking the domain")
    print("4. SSL/TLS certificate issues")
    print("5. Domain configuration issues")
    print("\nRecommendations:")
    print("- Try accessing the website in a browser to verify it's online")
    print("- Check if the domain exists: https://museumsofindia.gov.in")
    print("- Try using a different network or VPN")

if __name__ == "__main__":
    asyncio.run(debug_museumsofindia())
