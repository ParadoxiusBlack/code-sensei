# Code Truncation & Chunk Visualization Guide

## Problem: Hidden Truncation

Previously, the GUI had **three levels of hidden truncation** that could confuse users:

### 1. **Indexing Phase (Chunking)**
Files are split into ~512 char chunks during indexing:
```
Original File (5000 chars)
    ↓ [Chunker]
    ├─ Chunk 1 (512 chars)
    ├─ Chunk 2 (512 chars) 
    └─ Chunk 3 (500 chars)
```
Users never saw this - chunks felt disconnected from full file.

### 2. **Retrieval Phase (Vector Search)**
LLM reads only the matched chunks (500-2000 chars each):
```
User Question: "How does authentication work?"
    ↓ [Vector Search]
    ├─ ✓ Returns Chunk 2 (highest score)
    ├─ ✓ Returns Chunk 5 (high score)
    └─ ✗ Ignores Chunk 1, 3, 4... (low scores)
```
Users saw isolated code with no context about what else was in the file.

### 3. **GUI Display Phase**
Source viewer truncated files to 6000 chars:
```
Full File: 15,000 chars
    ↓ [GUI Viewer]
Display: First 6000 chars + "...truncated"
    ✗ Missing the actual context!
```
Users thought they were seeing the whole file but weren't.

---

## Solution: Full File View with Chunk Indicators

### What Changed

The GUI now shows:

1. **✓ FULL FILE** - No truncation (regardless of size)
2. **✓ LINE NUMBERS** - Easy reference 
3. **✓ CHUNK MARKERS** - Visual indicators showing:
   - Which lines are part of retrieved chunks (`│`)
   - Current chunk being viewed (`▶`)
   - Chunk indices (`[1,3,5]`)
4. **✓ CLEAR LEGEND** - Header explains all symbols

### Visual Example

**Before (Truncated & Ambiguous):**
```
# File: authentication.py
# Language: python
# Score: 0.85

def verify_token(token):
    payload = jwt.decode(token, SECRET_KEY)
    if not payload:
        raise ValueError("Invalid token")
    return payload

[... rest truncated ...]
```
❌ Users don't know:
- What's before/after this snippet
- Whether there are other matching chunks
- How many chunks from this file were retrieved

---

**After (Full File with Indicators):**
```
╔════════════════════════════════════════════════════════════╗
║  File: authentication.py
║  Language: python
║  Retrieved Chunks: 3 | Avg Score: 0.87
║  ✓ Showing FULL file with chunk indicators (not truncated)
╚════════════════════════════════════════════════════════════╝

┌─ FULL FILE VIEW WITH CHUNK INDICATORS ─────────────────────┐
│ │   = Line is part of a chunk retrieved by LLM             │
│ ▶   = Line is in the CURRENT chunk being viewed            │
│ [1] = Chunk index (multiple chunks may span same lines)    │
└────────────────────────────────────────────────────────────┘

   1 | import jwt
   2 | from config import SECRET_KEY
   3 |  │ CHUNK[1] 
   4 | def verify_token(token):
   5 |  │ CHUNK[1]
   6 |     payload = jwt.decode(token, SECRET_KEY)
   7 |  ▶ CHUNK[1]
   8 |     if not payload:
   9 |  │ CHUNK[1,2]
  10 |         raise ValueError("Invalid token")
  11 |  │ CHUNK[2]
  12 |     return payload
  13 | 
  14 | def refresh_token(old_token):
  15 |  │ CHUNK[3]
  16 |     new_token = jwt.encode({"refresh": True}, SECRET_KEY)
  17 |  ▶ CHUNK[3]
  18 |     return new_token
  ...
[Full file continues - NOTHING TRUNCATED]
```

✅ Users now see:
- **Complete file context** - Nothing hidden
- **Exact chunk locations** - Where LLM read from
- **Multiple chunks** - If file has 3+ matches, they're all marked
- **Current position** - Which chunk is highlighted (▶)
- **File statistics** - How many chunks, average relevance score

---

## Use Cases

### Case 1: Understanding Search Results
**Scenario:** "Why did the LLM include this file in the results?"
- Look at the file
- See chunk markers showing exactly what lines matched
- Scroll to see if there's related code nearby

### Case 2: Large Files
**Before:** Got "...truncated" message on big files
**After:** See entire file with context, find what matters

### Case 3: Multiple Chunks from Same File  
**Before:** Only saw one chunk at a time
**After:** See ALL chunks marked `[1]`, `[2]`, `[3]` so you understand the full picture

### Case 4: Verifying Relevance
**Before:** Couldn't tell if chunks were actually related
**After:** See related code nearby marked with `│` 

---

## Technical Details

### Chunk Metadata Flow

```
Chunker (chunks file)
    ├─ chunk.start_char = 256
    ├─ chunk.end_char = 768
    └─ chunk.content = "code here"
            ↓
VectorStore (stores + embeds)
    ├─ metadata["start_char"] = 256
    ├─ metadata["end_char"] = 768
    └─ metadata["source_path"] = "auth.py"
            ↓
Retriever (searches & returns)
    └─ RetrievalResult.metadata 
            ├─ start_char = 256
            ├─ end_char = 768
            └─ language = "python"
            ↓
GUI (displays with indicators)
    └─ Uses start_char/end_char to annotate full file
```

### New GUI Functions

#### `_read_full_file(path, base_dir)`
Reads complete file without any truncation.
```python
content = _read_full_file("src/auth.py", base_dir=project_root)
# Returns: entire file, no "...truncated" suffix
```

#### `_annotate_file_with_chunks(file_content, chunk_ranges, current_chunk)`
Annotates file with line numbers and chunk indicators.
```python
annotated = _annotate_file_with_chunks(
    file_content="def foo(): ...",
    chunk_ranges=[(0, 150), (140, 300), (280, 450)],
    current_chunk=(140, 300)
)
# Returns: file with markers, line numbers, chunk legend
```

#### `_on_source_selected()` (Updated)
Now displays:
- Full file (not truncated)
- All chunks from that file (not just one)
- Chunk boundary indicators
- Retrieved chunk statistics

---

## Configuration

Truncation behavior can be customized in chunk settings:

**`.env` file:**
```
# Chunker settings
CHUNK_SIZE=512          # Characters per chunk (was already configurable)
CHUNK_OVERLAP=64        # Overlap between chunks (was already configurable)

# GUI display
# NOTE: GUI now shows FULL files (no truncation)
# To see only first N chars, scroll and find the section you want
```

---

## FAQ

**Q: Isn't showing huge files slow?**
A: No, PyQt6 handles thousands of lines efficiently. Rendering is instant.

**Q: How do I search within the file?**
A: Use Ctrl+F in the code viewer (standard PyQt6 feature).

**Q: Can I go back to truncated view?**
A: The full file is now standard - users wanted context. If you need to limit display, modify `_annotate_file_with_chunks()` to only show lines near chunk boundaries.

**Q: What if metadata is missing?**
A: Falls back to showing full file without chunk indicators (still not truncated).

**Q: Can I copy the full file?**
A: Yes! Select all with Ctrl+A, copy with Ctrl+C. Full content is copied.

---

## Future Improvements

1. **Clickable chunks** - Click `[1]` to jump to chunk 1
2. **Chunk scoring** - Show relevance score on each chunk
3. **Source diff** - Highlight changes between chunks
4. **Minimap** - Visual overview of chunk density
5. **Export** - Save annotated file with chunk markers

---

## Summary

| Aspect | Before | After |
|--------|--------|-------|
| **File Display** | Truncated at 6K chars | Full file, no limit |
| **Chunks Shown** | 1 at a time | All chunks visible |
| **Indicators** | None | Visual markers + legend |
| **Context** | Hidden | Clear and visible |
| **Searching** | Guesswork | Exact boundaries shown |
| **Large Files** | Broken | Works perfectly |

Users now get **full transparency** into what the LLM read and why files were included in results.
