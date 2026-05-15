"""
Vector store service using ChromaDB
Stores and retrieves document embeddings
"""

import chromadb
from typing import List, Dict, Optional
import os
from pathlib import Path

class VectorStore:
    """
    Vector database interface using ChromaDB
    """

    def __init__(self, persist_directory: str = "./data/chroma_db", collection_name: str = "ministry_culture_kb"):
        """
        Initialize vector store

        Args:
            persist_directory: Directory to persist ChromaDB data
            collection_name: Name of the collection
        """
        # Create directory if it doesn't exist
        Path(persist_directory).mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(path=persist_directory)

        self.collection_name = collection_name

        # Get or create collection
        try:
            self.collection = self.client.get_collection(name=collection_name)
            print(f"Loaded existing collection: {collection_name}")
            print(f"Collection size: {self.collection.count()} documents")
        except:
            self.collection = self.client.create_collection(
                name=collection_name,
                metadata={"description": "Ministry of Culture knowledge base"}
            )
            print(f"Created new collection: {collection_name}")

    def add_documents(
        self,
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict],
        ids: List[str]
    ):
        """
        Add documents to vector store

        Args:
            documents: List of text chunks
            embeddings: List of embedding vectors
            metadatas: List of metadata dicts (title, url, etc.)
            ids: List of unique IDs for each document
        """
        self.collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
        print(f"Added {len(documents)} documents to collection")

    def search(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict] = None
    ) -> Dict:
        """
        Search for similar documents

        Args:
            query_embedding: Query vector embedding
            n_results: Number of results to return
            where: Optional metadata filter

        Returns:
            Dict with 'documents', 'metadatas', 'distances', and 'ids'
        """
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where
        )

        return {
            "documents": results['documents'][0] if results['documents'] else [],
            "metadatas": results['metadatas'][0] if results['metadatas'] else [],
            "distances": results['distances'][0] if results['distances'] else [],
            "ids": results['ids'][0] if results['ids'] else []
        }

    def get_collection_stats(self) -> Dict:
        """
        Get collection statistics

        Returns:
            Dict with count and other stats
        """
        return {
            "name": self.collection_name,
            "count": self.collection.count(),
            "metadata": self.collection.metadata
        }

    def delete_collection(self):
        """
        Delete the entire collection (use with caution!)
        """
        self.client.delete_collection(name=self.collection_name)
        print(f"Deleted collection: {self.collection_name}")

    def clear_collection(self):
        """
        Clear all documents from collection
        """
        # Delete and recreate
        self.client.delete_collection(name=self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"description": "Ministry of Culture knowledge base"}
        )
        print(f"Cleared collection: {self.collection_name}")


# Global instance
_vector_store = None

def get_vector_store(persist_directory: str = "./data/chroma_db") -> VectorStore:
    """
    Get or create global vector store instance

    Args:
        persist_directory: Directory to persist ChromaDB data

    Returns:
        VectorStore instance
    """
    global _vector_store

    if _vector_store is None:
        _vector_store = VectorStore(persist_directory=persist_directory)

    return _vector_store
