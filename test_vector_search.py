"""
Test vector search directly
"""
import asyncio
from services.vector_search_service import get_vector_search_service

async def test_search():
    service = get_vector_search_service()

    test_queries = [
        "Ministry of Culture",
        "organizations",
        "schemes for artists",
        "Taj Mahal",
        "museum"
    ]

    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print('='*60)

        # Search with lower threshold to see all results
        results = await service.search(query, top_k=5, min_similarity=0.5)

        if results:
            print(f"Found {len(results)} results:")
            for i, result in enumerate(results, 1):
                print(f"\n{i}. Similarity: {result['similarity']:.4f}")
                print(f"   Title: {result['title']}")
                print(f"   URL: {result['url']}")
                print(f"   Text preview: {result['text'][:100]}...")
        else:
            print("No results found")

if __name__ == "__main__":
    asyncio.run(test_search())
