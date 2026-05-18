import httpx
from urllib.parse import urlparse
from services.query_classifier import get_query_type
from dotenv import load_dotenv
import os
from functools import lru_cache
import hashlib

load_dotenv(dotenv_path=".env")

SERPER_API_KEY = os.getenv("SERPER_API_KEY")

print("SERPER_API_KEY:", SERPER_API_KEY)

TRUSTED_SITES = [
    # "abhilekh-patal.in",
    "culture.gov.in",
    # "gandhimuseum.org",
    "indianculture.gov.in",
    "vedicheritage.gov.in",
    "museumsofindia.gov.in"
]

# Simple in-memory cache for web search results
_search_cache = {}
CACHE_SIZE = 100
CACHE_TTL = 300  # 5 minutes in seconds

def _is_trusted_domain(url: str) -> bool:
    """Return True only if URL's domain exactly matches a trusted site (no subdomains)."""
    try:
        netloc = urlparse(url).netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc in TRUSTED_SITES
    except Exception:
        return False

def build_site_query(user_query):

    site_filters = " OR ".join([
        f"site:{site}"
        for site in TRUSTED_SITES
    ])

    return f"{user_query} ({site_filters})"

def _get_cache_key(query: str) -> str:
    """Generate cache key from query"""
    return hashlib.md5(query.lower().strip().encode()).hexdigest()

async def search_web(query, max_results: int = None):
    """
    Async web search with caching.
    max_results: override the default per-query-type cap (use for /search endpoint).
    """
    # Cache key includes max_results so different limits cache separately
    cache_key = _get_cache_key(f"{query}:{max_results}")
    if cache_key in _search_cache:
        return _search_cache[cache_key]

    query_type = get_query_type(query)

    # Default caps per query type (kept low for chat speed)
    if max_results is None:
        if query_type == "location":
            max_results = 1
        else:
            max_results = 3

    search_query = build_site_query(query)

    url = "https://google.serper.dev/search"

    payload = {
        "q": search_query
    }

    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            url,
            headers=headers,
            json=payload
        )

    data = response.json()

    results = []

    organic = data.get("organic", [])

    for item in organic:

        title = item.get("title", "").lower()

        if "default title" in title:
            continue

        if "record" in item.get("link", ""):
            continue

        if not _is_trusted_domain(item.get("link", "")):
            continue

        results.append({
            "title": item.get("title"),
            "snippet": item.get("snippet"),
            "link": item.get("link")
        })

        if len(results) >= max_results:
            break

    # Cache results
    if len(_search_cache) >= CACHE_SIZE:
        _search_cache.pop(next(iter(_search_cache)))
    _search_cache[cache_key] = results

    return results

    # for item in organic[:2]:

    #     results.append({
    #         "title": item.get("title"),
    #         "snippet": item.get("snippet"),
    #         "link": item.get("link")
    #     })

    # return results

# import requests
# import os
# from dotenv import load_dotenv
# load_dotenv(dotenv_path=".env")

# SERPER_API_KEY = os.getenv("SERPER_API_KEY")

# print("SERPER_API_KEY:", SERPER_API_KEY)

# def build_site_query(user_query):

#     return f"{user_query} site:culture.gov.in"


# def search_web(query):

#     search_query = build_site_query(query)

#     print("SEARCH QUERY:", search_query)

#     url = "https://google.serper.dev/search"

#     payload = {
#         "q": search_query
#     }

#     headers = {
#         "X-API-KEY": SERPER_API_KEY,
#         "Content-Type": "application/json"
#     }

#     response = requests.post(
#         url,
#         headers=headers,
#         json=payload
#     )

#     print("STATUS CODE:", response.status_code)

#     print("RAW RESPONSE:")
#     print(response.text)

#     data = response.json()

#     organic = data.get("organic", [])

#     print("ORGANIC RESULTS:", organic)

#     results = []

#     for item in organic[:5]:

#         results.append({
#             "title": item.get("title"),
#             "snippet": item.get("snippet"),
#             "link": item.get("link")
#         })

#     print("FINAL RESULTS:", results)

#     return results