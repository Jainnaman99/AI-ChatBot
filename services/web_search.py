import httpx
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
    # "indiaculture.gov.in",
    "vedicheritage.gov.in",
    "museumsofindia.gov.in"
]

# Simple in-memory cache for web search results
_search_cache = {}
CACHE_SIZE = 100
CACHE_TTL = 300  # 5 minutes in seconds

def build_site_query(user_query):

    site_filters = " OR ".join([
        f"site:{site}"
        for site in TRUSTED_SITES
    ])

    return f"{user_query} ({site_filters})"

def _get_cache_key(query: str) -> str:
    """Generate cache key from query"""
    return hashlib.md5(query.lower().strip().encode()).hexdigest()

async def search_web(query):
    """
    Async web search with caching
    """
    # Check cache first
    cache_key = _get_cache_key(query)
    if cache_key in _search_cache:
        return _search_cache[cache_key]

    query_type = get_query_type(query)

    search_query = build_site_query(query)

    url = "https://google.serper.dev/search"

    payload = {
        "q": search_query
    }

    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json"
    }

    # Use async httpx client
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

        # Ignore artifact/object pages
        if "default title" in title:
            continue

        if "record" in item.get("link", ""):
            continue

        results.append({
            "title": item.get("title"),
            "snippet": item.get("snippet"),
            "link": item.get("link")
        })

        # Only keep top 2 good results
        # Dynamic limit
        if query_type == "location" and len(results) >= 1:
            break

        if query_type == "general" and len(results) >= 3:
            break

    # Cache results (simple LRU)
    if len(_search_cache) >= CACHE_SIZE:
        # Remove oldest entry
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