# Vector Search Architecture (RAG System)

## Overview

Implement a Retrieval-Augmented Generation (RAG) system that:
1. Scrapes content from trusted Ministry of Culture websites
2. Converts text into vector embeddings
3. Stores in a vector database
4. Enables semantic search for instant, relevant results

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA INGESTION PHASE                      │
│  (Run once or periodically to update knowledge base)         │
└─────────────────────────────────────────────────────────────┘

1. Web Scraper → Crawls trusted sites
   ↓
2. Text Processor → Chunks, cleans, extracts metadata
   ↓
3. Embedding Generator → Creates vector embeddings
   ↓
4. Vector DB → Stores embeddings with metadata


┌─────────────────────────────────────────────────────────────┐
│                      QUERY PHASE                             │
│  (Real-time during user requests)                            │
└─────────────────────────────────────────────────────────────┘

1. User Query → Convert to embedding
   ↓
2. Vector Search → Find top K similar chunks
   ↓
3. LLM → Generate answer using retrieved context
   ↓
4. Response → Return answer with sources
```

---

## Technology Stack

### 1. **Vector Database: ChromaDB**
**Why:**
- ✅ Lightweight, embedded database
- ✅ No separate server needed
- ✅ Persistent storage
- ✅ Built-in embedding support
- ✅ Easy to use with Python

**Alternatives:**
- FAISS (Facebook AI): Fast but requires manual persistence
- Pinecone: Cloud-based, costs money
- Weaviate: Too heavy for this use case

### 2. **Embedding Model: sentence-transformers**
**Model:** `all-MiniLM-L6-v2`
**Why:**
- ✅ Already in requirements.txt
- ✅ Fast (lightweight)
- ✅ Good for semantic similarity
- ✅ 384-dimensional vectors
- ✅ Supports Hindi/English

**Alternative:** `paraphrase-multilingual-MiniLM-L12-v2` (better for Hindi)

### 3. **Web Scraping: BeautifulSoup + Requests**
**Why:**
- ✅ Already in requirements.txt
- ✅ Simple and reliable
- ✅ Good for static content

---

## Implementation Plan

### Phase 1: Data Ingestion

#### Step 1: Web Scraper
```python
services/web_scraper.py
```
- Crawl trusted sites (culture.gov.in, indiaculture.gov.in, etc.)
- Extract main content (remove nav, footer, ads)
- Extract metadata (title, URL, date)
- Respect robots.txt and rate limits

#### Step 2: Text Chunking
```python
services/text_processor.py
```
- Split long documents into chunks (500-1000 tokens)
- Overlap chunks by 100 tokens (for context)
- Preserve paragraph boundaries
- Clean HTML artifacts

#### Step 3: Embedding Generation
```python
services/embedding_service.py
```
- Load sentence-transformer model
- Generate embeddings for each chunk
- Batch processing for efficiency

#### Step 4: Vector Storage
```python
services/vector_store.py
```
- Initialize ChromaDB collection
- Store embeddings with metadata
- Create indices for fast retrieval

---

### Phase 2: Query System

#### Step 1: Query Embedding
- Convert user query to vector embedding
- Use same model as ingestion

#### Step 2: Semantic Search
- Find top K similar chunks (K=3-5)
- Filter by relevance threshold (>0.7 similarity)
- Return chunks with metadata

#### Step 3: LLM Integration
- Pass retrieved chunks to LLM as context
- Generate answer using existing prompt system
- Include source URLs in response

---

## Data Ingestion Strategy

### Trusted Websites to Scrape:
```python
TRUSTED_SITES = [
    {
        "domain": "culture.gov.in",
        "base_url": "https://www.culture.gov.in",
        "sitemap": "https://www.culture.gov.in/sitemap.xml",
        "priority": "high"
    },
    {
        "domain": "indiaculture.gov.in",
        "base_url": "https://indiaculture.gov.in",
        "priority": "high"
    },
    {
        "domain": "vedicheritage.gov.in",
        "base_url": "https://vedicheritage.gov.in",
        "priority": "medium"
    },
    {
        "domain": "museumsofindia.gov.in",
        "base_url": "https://museumsofindia.gov.in",
        "priority": "high"
    }
]
```

### Content Types to Scrape:
1. **Museums & Monuments**
   - Names, locations, timings
   - History, architecture
   - Entry fees, contact info

2. **Schemes & Programs**
   - Eligibility criteria
   - Application process
   - Benefits, deadlines

3. **Events & Exhibitions**
   - Dates, venues
   - Descriptions

4. **General Information**
   - About Ministry
   - Policies, guidelines

---

## Text Chunking Strategy

### Chunk Size: 500-1000 characters
**Why:**
- Large enough for context
- Small enough for precise retrieval
- Fits well in LLM context window

### Overlap: 100 characters
**Why:**
- Prevents information loss at boundaries
- Better context continuity

### Example:
```
Document: "National Museum is located in New Delhi. It was established in 1949..."

Chunk 1: "National Museum is located in New Delhi. It was established in 1949. The museum houses over 200,000 artifacts spanning 5,000 years..."

Chunk 2 (overlap): "...established in 1949. The museum houses over 200,000 artifacts spanning 5,000 years. The collections include sculptures, paintings..."
```

---

## Vector Search API

### New Endpoint: `/chat-vector`

**Request:**
```json
{
  "message": "Where is National Museum?",
  "session_id": "optional"
}
```

**Response:**
```json
{
  "session_id": "abc-123",
  "language": "en",
  "answer": "National Museum is located in New Delhi...",
  "sources": [
    {
      "title": "National Museum - About",
      "url": "https://culture.gov.in/national-museum",
      "relevance": 0.92
    }
  ],
  "search_type": "vector"
}
```

---

## Performance Comparison

### Current (Web Search API):
```
Query → Serper API → Parse results → LLM
Time: 2-4 seconds
Cost: API call per query
Coverage: Limited to search results
```

### Proposed (Vector Search):
```
Query → Embedding (0.01s) → Vector search (0.05s) → LLM
Time: 0.5-2 seconds
Cost: One-time scraping + storage
Coverage: All scraped content
```

**Benefits:**
- ⚡ 2-5x faster
- 💰 No per-query API costs
- 🎯 More relevant results (semantic search)
- 📚 Complete knowledge base
- 🔒 Fully offline (after scraping)

---

## Storage Estimates

### Per Website:
- Average pages: 500-1000
- Average page size: 50KB
- Total raw text: 25-50 MB
- After chunking: ~10,000 chunks
- Embeddings: 10,000 × 384 × 4 bytes = ~15 MB

### All 4 Sites:
- Total chunks: ~40,000
- Total storage: ~60 MB (embeddings) + ~100 MB (text)
- **Total: ~160 MB**

Very manageable!

---

## Implementation Files

### New Files to Create:
```
services/
├── web_scraper.py          # Scrape websites
├── text_processor.py       # Chunk and clean text
├── embedding_service.py    # Generate embeddings
├── vector_store.py         # ChromaDB interface
└── vector_search.py        # Search functionality

scripts/
└── ingest_data.py          # Run data ingestion

data/
└── chroma_db/              # ChromaDB storage
```

### Files to Update:
```
routes/chat.py              # Add /chat-vector endpoint
requirements.txt            # Add chromadb
```

---

## Data Freshness Strategy

### Option 1: Periodic Re-scraping
```bash
# Run daily/weekly via cron
python scripts/ingest_data.py --update
```

### Option 2: Incremental Updates
- Track last scrape date
- Only fetch new/modified pages
- Update vector DB incrementally

### Option 3: Manual Refresh
- Admin endpoint to trigger re-scraping
- Use when Ministry updates content

---

## Hybrid Approach (Best of Both Worlds)

### Strategy:
1. **Try Vector Search First** (fast, offline)
   - If good results found (>0.7 similarity) → Use them

2. **Fallback to Web Search** (real-time, fresh)
   - If vector search fails or low confidence → Use Serper API
   - Useful for very recent updates or new topics

### Endpoint: `/chat-hybrid`
```python
async def chat_hybrid(query):
    # Try vector search first
    vector_results = await vector_search(query, threshold=0.7)

    if vector_results:
        return generate_answer(query, vector_results)
    else:
        # Fallback to web search
        web_results = await search_web(query)
        return generate_answer(query, web_results)
```

---

## Next Steps

1. ✅ **Install ChromaDB**
   ```bash
   pip install chromadb
   ```

2. **Create Services** (web scraper, embeddings, vector store)

3. **Run Data Ingestion** (one-time or scheduled)

4. **Add Vector Search Endpoint**

5. **Test and Benchmark**

6. **Optional: Implement Hybrid Search**

---

## Security & Legal Considerations

### Robots.txt Compliance:
- Check and respect robots.txt for each site
- Add delays between requests (1-2 seconds)

### Terms of Service:
- Government sites are generally open
- Only scrape publicly available content
- No authentication bypass

### Rate Limiting:
- Max 1 request per second per site
- Add exponential backoff on errors
- Use polite user agent string

---

## Monitoring & Maintenance

### Metrics to Track:
- Number of chunks stored
- Average query time
- Search accuracy (relevance scores)
- Cache hit rate

### Regular Tasks:
- Weekly: Check for broken links
- Monthly: Re-scrape for updates
- Quarterly: Review and optimize chunking strategy

---

Ready to implement? I'll create all the necessary files and services!
