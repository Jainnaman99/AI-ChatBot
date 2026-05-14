# Fixes Applied for Streaming Issues

## Problems Identified

### 1. **Language Detection Failed for Hindi/Hinglish**
**Issue:** Query "Taj Mahal kahan hai?" was detected as "en" instead of "hi"

**Root Causes:**
- Missing Hindi question words: "kahan" (where), "kab" (when), "kaun" (who)
- Punctuation breaking word matching: "hai?" didn't match " hai "

**Fix Applied in [services/language_service.py](services/language_service.py):**
- ✅ Added missing Hindi/Hinglish words: kahan, kab, kaun, bataiye, koi, yeh, woh, tha, thi, the
- ✅ Improved word boundary detection using regex `\b` instead of space matching
- ✅ Remove punctuation before checking to handle "hai?", "hai!", etc.

**Before:**
```python
HINGLISH_WORDS = ["hai", "ka", "ke", ...]  # Only 12 words
if f" {word} " in f" {lower_text} ":  # Breaks with punctuation
```

**After:**
```python
HINGLISH_WORDS = ["hai", "ka", "ke", "kahan", "kab", ...]  # 22 words
clean_text = re.sub(r'[^\w\s]', ' ', lower_text)  # Remove punctuation
if re.search(r'\b' + re.escape(word) + r'\b', clean_text):  # Proper word boundaries
```

---

### 2. **Streaming Too Granular**
**Issue:** Each token sent separately created too many events
```
event: message
data: The

event: message
data:  Taj

event: message
data:  Mah
```

**Fix Applied in [services/streaming_llm_service.py](services/streaming_llm_service.py):**
- ✅ Added buffering to accumulate 5+ characters before yielding
- ✅ Flush buffer on sentence boundaries (., !, ?, ।)
- ✅ Much smoother streaming experience

**Before:**
```python
for chunk in stream:
    if chunk.get("message", {}).get("content"):
        yield chunk["message"]["content"]  # Every single token
```

**After:**
```python
buffer = ""
for chunk in stream:
    if chunk.get("message", {}).get("content"):
        token = chunk["message"]["content"]
        buffer += token

        # Yield when we have enough content or hit punctuation
        if len(buffer) >= 5 or token in ['.', '!', '?', '\n', '।']:
            yield buffer
            buffer = ""
```

---

## Test Your Fixes

### Test 1: Language Detection
```bash
curl -X POST http://localhost:8000/chat-context/stream \
  -H 'Content-Type: application/json' \
  -d '{
    "message": "Taj Mahal kahan hai?"
  }'
```

**Expected:**
- ✅ Language should be detected as "hi" (not "en")
- ✅ Response should be in Hindi/Hinglish
- ✅ Streaming should be in larger chunks

**Example Response:**
```
event: metadata
data: {"session_id": "...", "language": "hi", "sources": [...]}

event: message
data: Taj Mahal Agra

event: message
data: , Uttar Pradesh

event: message
data:  mein hai.

event: done
data: {"complete": true}
```

---

### Test 2: English Query (should still work)
```bash
curl -X POST http://localhost:8000/chat-context/stream \
  -H 'Content-Type: application/json' \
  -d '{
    "message": "Where is the National Museum?"
  }'
```

**Expected:**
- ✅ Language: "en"
- ✅ Response in English
- ✅ Smoother streaming

---

### Test 3: Hinglish Mixed Query
```bash
curl -X POST http://localhost:8000/chat-context/stream \
  -H 'Content-Type: application/json' \
  -d '{
    "message": "Qutub Minar ke bare mein batao"
  }'
```

**Expected:**
- ✅ Language: "hi"
- ✅ Response in Hindi/Hinglish

---

## Additional Improvements Made

### Enhanced Hinglish Word List
Now includes 22 common Hindi/Hinglish words:
- Question words: kahan (where), kab (when), kaun (who), kya (what), kaise (how), kyun (why)
- Verbs: batao, bataiye (tell)
- Pronouns: aap (you), yeh (this), woh (that), koi (someone)
- Linking words: mein (in), ka/ke (of), hai (is)
- Past tense: tha, thi, the (was/were)

### Better Punctuation Handling
The system now correctly detects:
- "kahan hai?" ✅
- "batao!" ✅
- "mein, aur..." ✅

---

## What Changed in Your API

### No Breaking Changes!
All existing endpoints work exactly as before:
- ✅ `POST /chat` - Works, just better language detection
- ✅ `POST /chat-context` - Works, just better language detection
- ✅ `POST /chat/stream` - Works, better streaming
- ✅ `POST /chat-context/stream` - Works, better streaming

### Files Modified
1. [services/language_service.py](services/language_service.py) - Fixed language detection
2. [services/streaming_llm_service.py](services/streaming_llm_service.py) - Improved streaming buffering

---

## Debugging Tips

If language detection still seems wrong:

1. **Check the detected language in response:**
   ```json
   "language": "hi"  // Should be "hi" for Hindi queries
   ```

2. **Add debug logging:**
   ```python
   # In services/language_service.py
   print(f"Query: {text}")
   print(f"Detected: {detect_language(text)}")
   ```

3. **Test specific words:**
   ```python
   from services.language_service import detect_language

   print(detect_language("kahan hai?"))  # Should return "hi"
   print(detect_language("where is?"))    # Should return "en"
   ```

---

## Summary

✅ **Fixed:** Language detection for Hindi/Hinglish queries
✅ **Fixed:** Streaming too granular (now buffered)
✅ **Improved:** Better word boundary detection with punctuation handling
✅ **Improved:** Added 10+ missing Hindi/Hinglish words

**Result:** Your streaming endpoint should now correctly detect Hindi and respond appropriately with smoother streaming!
