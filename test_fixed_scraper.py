"""
Test the fixed web scraper
"""
import asyncio
from services.web_scraper import get_web_scraper
from services.text_processor import get_text_processor

async def test_scraper():
    print("Testing fixed web scraper...\n")

    scraper = get_web_scraper(rate_limit=0.5, max_pages=5)
    processor = get_text_processor()

    # Scrape homepage
    print("Scraping https://culture.gov.in")
    scraped_data = await scraper.crawl_domain("https://culture.gov.in")

    print(f"\nPages scraped: {len(scraped_data)}")

    if scraped_data:
        # Check first page
        page = scraped_data[0]
        print(f"\nFirst page:")
        print(f"  URL: {page['url']}")
        print(f"  Title: {page['title']}")
        print(f"  Content length: {page['content_length']} chars")

        # Try to process it
        print(f"\nProcessing with text_processor...")
        chunks = processor.process_document(
            content=page['content'],
            url=page['url'],
            title=page['title'],
            is_html=True
        )

        print(f"Chunks created: {len(chunks)}")

        if chunks:
            print(f"\nFirst chunk preview:")
            print(f"  {chunks[0]['text'][:200]}...")
        else:
            print("ERROR: No chunks created!")
    else:
        print("ERROR: No pages scraped!")

if __name__ == "__main__":
    asyncio.run(test_scraper())
