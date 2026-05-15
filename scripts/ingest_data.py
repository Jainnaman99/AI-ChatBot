"""
Data ingestion script for vector search
Scrapes websites, processes text, generates embeddings, and stores in vector DB
"""

import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from services.web_scraper import get_web_scraper
from services.text_processor import get_text_processor
from services.embedding_service import get_embedding_service
from services.vector_store import get_vector_store
import hashlib
from datetime import datetime


async def ingest_data(max_pages_per_domain: int = 500, clear_existing: bool = False):
    """
    Main data ingestion pipeline

    Args:
        max_pages_per_domain: Maximum pages to scrape per domain
        clear_existing: Whether to clear existing vector DB
    """
    print("\n" + "="*60)
    print("MINISTRY OF CULTURE - DATA INGESTION PIPELINE")
    print("="*60 + "\n")

    # Initialize services
    print("Initializing services...")
    scraper = get_web_scraper(rate_limit=2.0, max_pages=max_pages_per_domain)
    text_processor = get_text_processor(chunk_size=800, chunk_overlap=100)
    embedding_service = get_embedding_service(model_name="all-MiniLM-L6-v2")
    vector_store = get_vector_store()

    # Clear existing data if requested
    if clear_existing:
        print("\nClearing existing vector database...")
        vector_store.clear_collection()
        print("[OK] Vector database cleared")

    # Step 1: Scrape websites
    print("\n" + "-"*60)
    print("STEP 1: WEB SCRAPING")
    print("-"*60)
    print(f"Scraping up to {max_pages_per_domain} pages per domain...")
    print(f"Rate limit: 2 seconds between requests\n")

    scraped_data = await scraper.scrape_all_sites()

    if not scraped_data:
        print("[ERROR] No data scraped. Exiting.")
        return

    print(f"\n[OK] Scraped {len(scraped_data)} pages successfully")

    # Step 2: Process and chunk text
    print("\n" + "-"*60)
    print("STEP 2: TEXT PROCESSING & CHUNKING")
    print("-"*60)
    print("Processing HTML and chunking text...\n")

    all_chunks = []
    for page_data in scraped_data:
        try:
            chunks = text_processor.process_document(
                content=page_data['content'],
                url=page_data['url'],
                title=page_data['title'],
                is_html=True
            )
            all_chunks.extend(chunks)
        except Exception as e:
            print(f"Error processing {page_data['url']}: {str(e)}")

    if not all_chunks:
        print("[ERROR] No text chunks created. Exiting.")
        return

    print(f"\n[OK] Created {len(all_chunks)} text chunks")
    print(f"   Average chunk size: {sum(len(c['text']) for c in all_chunks) // len(all_chunks)} characters")

    # Step 3: Generate embeddings
    print("\n" + "-"*60)
    print("STEP 3: GENERATING EMBEDDINGS")
    print("-"*60)
    print("Converting text to vector embeddings...")
    print("This may take a few minutes...\n")

    # Extract texts for embedding
    texts = [chunk['text'] for chunk in all_chunks]

    # Generate embeddings in batches
    embeddings = embedding_service.generate_embeddings_batch(
        texts,
        batch_size=32,
        show_progress=True
    )

    print(f"\n[OK] Generated {len(embeddings)} embeddings")
    print(f"   Embedding dimension: {embedding_service.embedding_dimension}")

    # Step 4: Store in vector database
    print("\n" + "-"*60)
    print("STEP 4: STORING IN VECTOR DATABASE")
    print("-"*60)
    print("Saving to ChromaDB...\n")

    # Prepare data for storage
    documents = texts
    metadatas = []
    ids = []

    for i, chunk in enumerate(all_chunks):
        # Create unique ID
        chunk_id = hashlib.md5(f"{chunk['url']}_{i}".encode()).hexdigest()
        ids.append(chunk_id)

        # Prepare metadata
        metadata = {
            "url": chunk['url'],
            "title": chunk['title'],
            "chunk_index": i,
            "chunk_length": chunk['chunk_length'],
            "ingested_at": datetime.now().isoformat()
        }
        metadatas.append(metadata)

    # Add to vector store in batches (ChromaDB has a max batch size)
    BATCH_SIZE = 5000  # Safe batch size for ChromaDB
    total_docs = len(documents)

    try:
        for i in range(0, total_docs, BATCH_SIZE):
            end_idx = min(i + BATCH_SIZE, total_docs)
            batch_docs = documents[i:end_idx]
            batch_embeddings = embeddings[i:end_idx]
            batch_metadatas = metadatas[i:end_idx]
            batch_ids = ids[i:end_idx]

            print(f"  Storing batch {i//BATCH_SIZE + 1}/{(total_docs + BATCH_SIZE - 1)//BATCH_SIZE} ({len(batch_docs)} documents)...")

            vector_store.add_documents(
                documents=batch_docs,
                embeddings=batch_embeddings,
                metadatas=batch_metadatas,
                ids=batch_ids
            )

        print(f"\n[OK] Successfully stored {total_docs} documents in vector database")
    except Exception as e:
        print(f"[ERROR] Error storing documents: {str(e)}")
        return

    # Step 5: Verify and show statistics
    print("\n" + "-"*60)
    print("STEP 5: VERIFICATION & STATISTICS")
    print("-"*60)

    stats = vector_store.get_collection_stats()
    print(f"\nVector Database Statistics:")
    print(f"  Collection name: {stats['name']}")
    print(f"  Total documents: {stats['count']}")
    print(f"  Storage location: ./data/chroma_db")

    # Test search
    print("\n" + "-"*60)
    print("TESTING VECTOR SEARCH")
    print("-"*60)
    print("Running test query: 'National Museum'\n")

    test_query = "National Museum"
    test_embedding = embedding_service.generate_embedding(test_query)
    test_results = vector_store.search(test_embedding, n_results=3)

    if test_results['documents']:
        print("[OK] Test search successful!")
        print(f"  Found {len(test_results['documents'])} results\n")
        for i, (doc, metadata) in enumerate(zip(test_results['documents'], test_results['metadatas']), 1):
            print(f"  Result {i}:")
            print(f"    Title: {metadata.get('title', 'N/A')}")
            print(f"    URL: {metadata.get('url', 'N/A')}")
            print(f"    Preview: {doc[:100]}...")
            print()
    else:
        print("[WARNING] No results found for test query")

    # Summary
    print("\n" + "="*60)
    print("INGESTION COMPLETE!")
    print("="*60)
    print(f"\n=== Summary ===")
    print(f"   Pages scraped: {len(scraped_data)}")
    print(f"   Text chunks created: {len(all_chunks)}")
    print(f"   Embeddings generated: {len(embeddings)}")
    print(f"   Documents stored: {stats['count']}")
    print(f"\n>>> Vector search API is ready to use!")
    print(f"   Try: POST /chat-vector")
    print(f"   Try: POST /chat-hybrid")
    print()


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Ingest data for vector search")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=500,
        help="Maximum pages to scrape per domain (default: 500)"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing vector database before ingestion"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: only scrape 50 pages per domain for testing"
    )

    args = parser.parse_args()

    # Adjust max pages for quick mode
    max_pages = 50 if args.quick else args.max_pages

    if args.quick:
        print("\n>>> QUICK MODE: Scraping only 50 pages per domain for testing\n")

    # Run ingestion
    try:
        asyncio.run(ingest_data(
            max_pages_per_domain=max_pages,
            clear_existing=args.clear
        ))
    except KeyboardInterrupt:
        print("\n\n[WARNING] Ingestion interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[ERROR] Error during ingestion: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
