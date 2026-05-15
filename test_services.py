"""Test service initialization"""
import sys

print("Testing embedding service...")
from services.embedding_service import get_embedding_service
emb = get_embedding_service()
print(f"Embedding service OK! Dimension: {emb.embedding_dimension}")

print("\nTesting vector store...")
from services.vector_store import get_vector_store
vec = get_vector_store()
print(f"Vector store OK! Collection: {vec.collection_name}")

print("\nAll services initialized successfully!")
