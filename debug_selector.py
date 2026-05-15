"""
Debug what .content selector matches
"""
import asyncio
import httpx
from bs4 import BeautifulSoup

async def debug_selector():
    url = "https://culture.gov.in"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }

    async with httpx.AsyncClient(verify=False, headers=headers, timeout=30.0) as client:
        response = await client.get(url, follow_redirects=True)
        soup = BeautifulSoup(response.text, 'html.parser')

        print("Testing each selector:\n")

        selectors = ['main', 'article', '.content', '#content', '.main-content']

        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                html_len = len(str(element))
                text_len = len(element.get_text())
                print(f"{selector:20} -> Found! HTML: {html_len:>6} chars, Text: {text_len:>6} chars")
                print(f"                     Preview: {element.get_text()[:100].strip()}...")
                print()
            else:
                print(f"{selector:20} -> Not found")
                print()

        # Check body as fallback
        if soup.body:
            html_len = len(str(soup.body))
            text_len = len(soup.body.get_text())
            print(f"{'body (fallback)':20} -> HTML: {html_len:>6} chars, Text: {text_len:>6} chars")

if __name__ == "__main__":
    asyncio.run(debug_selector())
