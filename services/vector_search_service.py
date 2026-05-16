"""
Vector search service
Performs semantic search using embeddings and vector store
"""

from typing import List, Dict, Optional
from services.embedding_service import get_embedding_service
from services.vector_store import get_vector_store


class VectorSearchService:
    """
    Service for semantic search using vector embeddings
    """

    def __init__(self, similarity_threshold: float = 0.5):
        """
        Initialize vector search service

        Args:
            similarity_threshold: Minimum similarity score (0-1)
        """
        self.embedding_service = get_embedding_service()
        # Don't cache vector_store - get it dynamically to support TEST_MODE switching
        self.similarity_threshold = similarity_threshold

    @property
    def vector_store(self):
        """Get vector store dynamically to support database switching"""
        return get_vector_store()

    async def search(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: Optional[float] = None
    ) -> List[Dict]:
        """
        Search for relevant documents

        Args:
            query: Search query
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold (overrides default)

        Returns:
            List of result dictionaries with text, metadata, and scores
        """
        # Generate query embedding
        query_embedding = self.embedding_service.generate_embedding(query)

        # Search vector store
        results = self.vector_store.search(
            query_embedding=query_embedding,
            n_results=top_k
        )

        # Process results
        processed_results = []
        threshold = min_similarity if min_similarity is not None else self.similarity_threshold

        for i, (doc, metadata, distance, doc_id) in enumerate(zip(
            results['documents'],
            results['metadatas'],
            results['distances'],
            results['ids']
        )):
            # Convert distance to similarity (ChromaDB uses L2 distance)
            # Smaller distance = higher similarity
            # Approximate similarity: 1 / (1 + distance)
            similarity = 1 / (1 + distance)

            # Filter by threshold
            if similarity >= threshold:
                processed_results.append({
                    "text": doc,
                    "title": metadata.get("title", "Untitled"),
                    "url": metadata.get("url", ""),
                    "similarity": round(similarity, 4),
                    "rank": i + 1,
                    "chunk_id": doc_id
                })

        return processed_results

    def get_stats(self) -> Dict:
        """
        Get vector store statistics

        Returns:
            Dict with stats
        """
        return self.vector_store.get_collection_stats()

    def format_context_for_llm(self, search_results: List[Dict]) -> List[Dict]:
        """
        Format search results for LLM context

        Args:
            search_results: Results from search()

        Returns:
            Formatted list for LLM (similar to web search format)
        """
        formatted = []

        for result in search_results:
            formatted.append({
                "title": result["title"],
                "snippet": result["text"][:500] + "..." if len(result["text"]) > 500 else result["text"],
                "link": result["url"],
                "relevance": result["similarity"]
            })

        return formatted


# Global instance
_vector_search_service = None

def get_vector_search_service(similarity_threshold: float = 0.5) -> VectorSearchService:
    """
    Get or create global vector search service

    Args:
        similarity_threshold: Minimum similarity score

    Returns:
        VectorSearchService instance
    """
    global _vector_search_service

    if _vector_search_service is None:
        _vector_search_service = VectorSearchService(similarity_threshold=similarity_threshold)

    return _vector_search_service
