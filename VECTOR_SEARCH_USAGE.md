```markdown
# Vector Search Usage Guide

Complete guide for using the RAG (Retrieval-Augmented Generation) vector search system.

---

## 🚀 Quick Start

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Run Data Ingestion (One-Time Setup)
```bash
# Quick test (scrapes ~50 pages per domain, ~5-10 minutes)
python scripts/ingest_data.py --quick

# Full ingestion (scrapes ~500 pages per domain, ~30-60 minutes)
python scripts/ingest_data.py

# Clear existing data and re-ingest
python scripts/ingest_data.py --clear
```

### Step 3: Start Server
```bash
uvicorn main:app --reload
```

### Step 4: Use Vector Search
```bash
curl -X POST http://localhost:8000/chat-vector \
  -H 'Content-Type: application/json' \
  -d '{"message": "Where is National Museum?"}'
```

---

## 📡 API Endpoints

### 1. `/chat-vector` - Pure Vector Search
**Fastest, most accurate for scraped content**

```bash
POST /chat-vector
{
  "message": "Tell me about Taj Mahal"
}
```

**Response:**
```json
{
  "language": "en",
  "answer": "The Taj Mahal is located in Agra...",
  "sources": [
    {
      "title": "Taj Mahal - History",
      "snippet": "...",
      "link": "https://culture.gov.in/taj-mahal",
      "relevance": 0.92
    }
  ],
  "search_type": "vector"
}
```

**When to use:**
- Questions about museums, monuments, schemes
- Historical information
- General Ministry of Culture topics
- When you need fast, offline search

---

### 2. `/chat-vector-context` - Vector Search with Conversation History
**Vector search + remembers conversation**

```bash
POST /chat-vector-context
{
  "message": "Where is National Museum?",
  "session_id": null
}

# Follow-up
POST /chat-vector-context
{
  "message": "What are the timings?",
  "session_id": "abc-123"  # From previous response
}
```

**Response:**
```json
{
  "session_id": "abc-123",
  "language": "en",
  "answer": "...",
  "sources": [...],
  "search_type": "vector"
}
```

**When to use:**
- Multi-turn conversations
- Follow-up questions
- When context matters ("Tell me more", "What about that?")

---

### 3. `/chat-hybrid` - Smart Hybrid Search
**Tries vector first, falls back to web search**

```bash
POST /chat-hybrid
{
  "message": "Latest cultural events"
}
```

**Response includes `search_type`:**
- `"vector"` - Found good results in vector DB
- `"web_fallback"` - No good vector results, used web search

**When to use:**
- New or recent topics not yet in vector DB
- When you want comprehensive coverage
- Best of both worlds approach

---

### 4. `/vector-stats` - Database Statistics
**Check vector DB status**

```bash
GET /vector-stats
```

**Response:**
```json
{
  "name": "ministry_culture_kb",
  "count": 15847,
  "metadata": {
    "description": "Ministry of Culture knowledge base"
  }
}
```

---

## 📊 Performance Comparison

| Endpoint | Speed | Accuracy | Offline | Coverage |
|----------|-------|----------|---------|----------|
| `/chat` (web) | 2-4s | Good | ❌ No | Real-time web |
| `/chat-context` (web) | 2-4s | Good | ❌ No | Real-time web + history |
| **`/chat-vector`** | **0.5-2s** | **Excellent** | ✅ **Yes** | **Scraped content** |
| **`/chat-vector-context`** | **0.5-2s** | **Excellent** | ✅ **Yes** | **Scraped + history** |
| **`/chat-hybrid`** | **0.5-4s** | **Best** | ⚠️ Partial | **Everything** |

---

## 🔧 Data Ingestion Options

### Quick Mode (Testing)
```bash
python scripts/ingest_data.py --quick
```
- Scrapes ~50 pages per domain
- Takes 5-10 minutes
- Good for testing/development
- ~2,000-5,000 chunks

### Full Mode (Production)
```bash
python scripts/ingest_data.py
```
- Scrapes ~500 pages per domain
- Takes 30-60 minutes
- Complete knowledge base
- ~30,000-50,000 chunks

### Custom Limits
```bash
python scripts/ingest_data.py --max-pages 200
```
- Scrape custom number of pages per domain

### Clear and Re-ingest
```bash
python scripts/ingest_data.py --clear
```
- Deletes existing vector DB
- Performs fresh ingestion
- Use when websites update significantly

---

## 📈 Ingestion Pipeline Details

### What Gets Scraped:
```
Trusted Domains:
  ✓ culture.gov.in
  ✓ indiaculture.gov.in
  ✓ vedicheritage.gov.in
  ✓ museumsofindia.gov.in

Skipped Content:
  ✗ PDFs, images, videos
  ✗ Login/signup pages
  ✗ Search/contact pages
  ✗ Navigation/footer content
```

### Processing Steps:
```
1. Web Scraping
   └─> Rate limited (2 sec/request)
   └─> Respects robots.txt
   └─> Extracts main content only

2. Text Chunking
   └─> 800 characters per chunk
   └─> 100 character overlap
   └─> Preserves sentence boundaries

3. Embedding Generation
   └─> all-MiniLM-L6-v2 model
   └─> 384-dimensional vectors
   └─> Batch processing (32 at a time)

4. Vector Storage
   └─> ChromaDB (persistent)
   └─> Metadata: URL, title, timestamp
   └─> Fast L2 distance search
```

---

## 💾 Storage Details

### Location:
```
./data/chroma_db/
```

### Size Estimates:
```
Quick mode (~5,000 chunks):
  Embeddings: ~8 MB
  Text: ~15 MB
  Total: ~23 MB

Full mode (~40,000 chunks):
  Embeddings: ~60 MB
  Text: ~100 MB
  Total: ~160 MB
```

### Backup:
```bash
# Backup vector DB
cp -r ./data/chroma_db ./data/chroma_db_backup

# Restore
cp -r ./data/chroma_db_backup ./data/chroma_db
```

---

## 🎯 Best Practices

### 1. When to Use Vector Search
✅ **Use vector search when:**
- Asking about museums, monuments, schemes
- Need fast responses
- Working offline
- Want high accuracy on scraped content

❌ **Don't use vector search when:**
- Asking about very recent events (last few days)
- Topic not covered by Ministry sites
- Need real-time information

### 2. When to Re-ingest
```bash
# Re-ingest when:
- Websites have major updates
- New schemes/programs announced
- Monthly or quarterly (recommended)

python scripts/ingest_data.py --clear
```

### 3. Optimizing Search Quality
```python
# Adjust similarity threshold in vector_search_service.py
similarity_threshold = 0.7  # Lower = more results, less relevant
similarity_threshold = 0.8  # Higher = fewer results, more relevant
```

### 4. Scaling for Production
```python
# Increase max pages for better coverage
python scripts/ingest_data.py --max-pages 1000

# Use hybrid search as default for comprehensive coverage
POST /chat-hybrid
```

---

## 🐛 Troubleshooting

### Problem: "Collection not found"
**Solution:**
```bash
# Run ingestion first
python scripts/ingest_data.py --quick
```

### Problem: "No results found"
**Possible causes:**
1. Topic not in scraped content
2. Similarity threshold too high
3. Empty vector DB

**Solutions:**
```bash
# Check stats
curl http://localhost:8000/vector-stats

# If count is 0, run ingestion
python scripts/ingest_data.py

# Try hybrid search instead
POST /chat-hybrid
```

### Problem: Ingestion fails
**Common issues:**
1. Network timeout → Check internet connection
2. Rate limiting → Script already has delays
3. Memory error → Reduce `--max-pages`

**Solution:**
```bash
# Try with fewer pages
python scripts/ingest_data.py --max-pages 100
```

### Problem: Slow search
**Solution:**
```bash
# Warm up the model (first search is slow)
curl -X POST http://localhost:8000/chat-vector \
  -d '{"message": "test"}' -H 'Content-Type: application/json'

# Subsequent searches will be fast
```

---

## 📚 Examples

### Example 1: Museum Information
```bash
curl -X POST http://localhost:8000/chat-vector \
  -H 'Content-Type: application/json' \
  -d '{
    "message": "Tell me about National Museum Delhi"
  }'
```

### Example 2: Scheme Information
```bash
curl -X POST http://localhost:8000/chat-vector \
  -H 'Content-Type: application/json' \
  -d '{
    "message": "What are the schemes for artists?"
  }'
```

### Example 3: Hindi Query
```bash
curl -X POST http://localhost:8000/chat-vector \
  -H 'Content-Type: application/json' \
  -d '{
    "message": "Taj Mahal ke bare mein batao"
  }'
```

### Example 4: Conversation with Context
```bash
# First message
curl -X POST http://localhost:8000/chat-vector-context \
  -H 'Content-Type: application/json' \
  -d '{
    "message": "Where is Qutub Minar?"
  }'

# Response includes session_id: "abc-123"

# Follow-up
curl -X POST http://localhost:8000/chat-vector-context \
  -H 'Content-Type: application/json' \
  -d '{
    "message": "What are the visiting hours?",
    "session_id": "abc-123"
  }'
```

### Example 5: Hybrid Search
```bash
curl -X POST http://localhost:8000/chat-hybrid \
  -H 'Content-Type: application/json' \
  -d '{
    "message": "Latest cultural festival"
  }'

# Will try vector first, fallback to web if needed
# Response includes "search_type": "vector" or "web_fallback"
```

---

## 🔄 Maintenance Schedule

### Recommended Schedule:
```
Weekly: Check vector DB stats
Monthly: Re-ingest data for updates
Quarterly: Full clear and re-ingest
Annually: Review and optimize chunking strategy
```

### Quick Health Check:
```bash
# Check DB size
curl http://localhost:8000/vector-stats

# Test search
curl -X POST http://localhost:8000/chat-vector \
  -d '{"message": "test"}' -H 'Content-Type: application/json'
```

---

## 🎓 Advanced Configuration

### Customize Embedding Model
Edit `services/embedding_service.py`:
```python
# For better Hindi support
model_name = "paraphrase-multilingual-MiniLM-L12-v2"
```

### Customize Chunk Size
Edit `services/text_processor.py`:
```python
chunk_size = 1000  # Larger chunks
chunk_overlap = 150  # More overlap
```

### Add More Domains
Edit `services/web_scraper.py`:
```python
TRUSTED_DOMAINS = [
    "culture.gov.in",
    "indiaculture.gov.in",
    "newdomain.gov.in"  # Add new domain
]
```

---

## 📞 Support

For issues or questions:
1. Check `/vector-stats` for DB status
2. Review logs during ingestion
3. Try `--quick` mode for testing
4. Use `/chat-hybrid` as fallback

**Happy vector searching! 🚀**
```
