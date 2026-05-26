# CodeSensei: Current Feature Overview

## Project Status
- **Phase 1**: ✓ Complete - Scaffolding and architecture
- **Phase 2**: ✓ Complete - Core assistant methods, caching, CLI, hybrid LLM
- **Phase 3**: ✓ Complete - Error handling, prompt refinement, performance tuning
- **Phase 4**: ✓ Complete - PyQt6 GUI with chunk visibility tools
- **Phase 5**: ✓ Complete - Benchmarking, observability metrics, CI delta reporting

**Current Test Status**: 176 passed, 2 warnings

---

## Core Features Implemented

### 1. Code Q&A Assistant (CodeQA)
**Purpose**: Answer questions about your codebase using RAG

**Location**: [src/code_sensei/assistant/qa.py](src/code_sensei/assistant/qa.py)

**Key Methods**:
- `ask(question, language_filter, path_prefix, use_llm=True)` - Main query method
- Retrieves relevant code chunks via semantic search
- Optionally synthesizes answer with LLM

**Example Usage**:
```python
qa = CodeQA(retriever=retriever, top_k=5)

# With LLM synthesis (detailed)
response = qa.ask("How does authentication work?", use_llm=True)
print(response.answer)  # Synthesized explanation

# Retrieval-only (fast, free)
response = qa.ask("Show me the login code", use_llm=False)
for result in response.retrieval_results:
    print(result.content)  # Raw code chunks
```

---

### 2. Test Generator
**Purpose**: Auto-generate unit tests from code analysis

**Location**: [src/code_sensei/assistant/test_generator.py](src/code_sensei/assistant/test_generator.py)

**Example**:
```bash
code-sensei tests -p src/myapp --language python
```

---

### 3. Doc Generator
**Purpose**: Create documentation from code and context

**Location**: [src/code_sensei/assistant/doc_generator.py](src/code_sensei/assistant/doc_generator.py)

**Example**:
```bash
code-sensei docs -p src/utils --output-format markdown
```

---

### 4. Refactor Assistant
**Purpose**: Suggest and apply code improvements

**Location**: [src/code_sensei/assistant/refactor.py](src/code_sensei/assistant/refactor.py)

**Example**:
```bash
code-sensei refactor -p src --pattern "extract-method"
```

---

### 5. Interactive Chat
**Purpose**: Multi-turn conversation with persistent memory

**Location**: [src/code_sensei/cli.py](src/code_sensei/cli.py)

**Features**:
- Session-based conversation memory
- Mode switching at runtime (`/llm-on`, `/llm-off`)
- Automatic cache of previous conversations

**Example**:
```bash
code-sensei chat -p .
> What components exist?
[receives answer]
> /llm-off
> Show me just the file structure
[switches to retrieval-only mode]
```

---

### 6. Benchmarking & Observability
**Purpose**: Measure retrieval quality and surface runtime metrics for tuning and CI visibility

**Key Capabilities**:
- `benchmark-retrieval` CLI command for dataset-driven retrieval evaluation
- Benchmark datasets stored under `benchmarks/retrieval/`
- Summary metrics:
  - Recall@k
  - mean reciprocal rank (MRR)
  - hit rate
  - average latency
- Runtime metrics surfaced in CLI output for:
  - `ask`
  - `index`
- CI benchmark delta reporting with soft regression warnings

**Relevant Files**:
- [src/code_sensei/evaluation/retrieval_benchmark.py](src/code_sensei/evaluation/retrieval_benchmark.py)
- [scripts/report_retrieval_benchmark_delta.py](scripts/report_retrieval_benchmark_delta.py)
- [benchmarks/retrieval/code_sensei_smoke.json](benchmarks/retrieval/code_sensei_smoke.json)
- [.github/workflows/ci.yml](.github/workflows/ci.yml)

**Example Usage**:
```bash
code-sensei benchmark-retrieval -p . -d benchmarks/retrieval/code_sensei_smoke.json
code-sensei ask "Which method converts Chroma cosine distance into a 0-to-1 similarity score?" -p . --no-stream
code-sensei index .
```

---

## NEW: Hybrid LLM Mode

### What It Does
Automatically selects the best LLM provider based on availability:

```
Request → No LLM? → Return code chunks (instant, free)
          ↓ No
        Try Ollama → Success? → Use local LLM (free)
          ↓ No
        Try OpenAI → Success? → Use cloud LLM (paid)
          ↓ No
        Return code chunks (instant, free)
```

### Configuration
```env
# Enable hybrid mode (default)
HYBRID_LLM_MODE=true

# Ollama configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral

# OpenAI fallback
OPENAI_API_KEY=sk-...

# Force retrieval-only
RETRIEVAL_ONLY_MODE=false
```

### Files Modified
- [config/settings.py](config/settings.py) - Added hybrid mode config
- [src/code_sensei/assistant/_base.py](src/code_sensei/assistant/_base.py) - Hybrid LLM logic
- [src/code_sensei/assistant/qa.py](src/code_sensei/assistant/qa.py) - use_llm parameter
- [src/code_sensei/cli.py](src/code_sensei/cli.py) - --no-llm flags and /llm-off/on commands

---

## NEW: Retrieval-Only Mode

### What It Does
Returns code chunks directly without LLM synthesis:
- **Speed**: Instant (no network calls)
- **Cost**: Free (no API calls)
- **Use Case**: When you just want to see the code

### Usage

**CLI Flag**:
```bash
code-sensei ask "where is the login function?" --no-llm
# Instantly returns matching code chunks
```

**Environment Variable**:
```bash
export RETRIEVAL_ONLY_MODE=true
code-sensei ask "question"
# Always returns chunks, never uses LLM
```

**Programmatic**:
```python
qa = CodeQA(retriever=retriever)
response = qa.ask("show me tests", use_llm=False)
# Returns raw code chunks
```

**Chat Toggle**:
```bash
code-sensei chat -p .
> /llm-off
> show me the utils
# Switches to retrieval-only for this session
```

---

## NEW: SQLite Cache

**Purpose**: Store embeddings and conversation history locally

**Location**: [src/code_sensei/cache/sqlite_cache.py](src/code_sensei/cache/sqlite_cache.py)

**Features**:
- Key-value storage with TTL expiration
- Automatic cleanup of old entries
- JSON serialization for complex types
- Context manager support

**Example**:
```python
from code_sensei.cache.sqlite_cache import SqliteCache

cache = SqliteCache()
cache.set("my_key", {"data": "value"}, ttl=3600)
value = cache.get("my_key")
cache.purge_expired()
```

---

## Conversation Memory

**Purpose**: Persist multi-turn conversations across sessions

**Location**: [src/code_sensei/memory/conversation.py](src/code_sensei/memory/conversation.py)

**Features**:
- Session-based persistence
- Sliding window token management
- Automatic cache integration

**Example**:
```python
from code_sensei.memory.conversation import ConversationMemory

memory = ConversationMemory(session_id="my_session")
memory.add_user_message("Question 1?")
memory.add_assistant_message("Answer 1")
# Later...
messages = memory.get_context(max_tokens=4000)
```

---

## Quick Start Guide

### 1. Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Setup Ollama (optional, for local LLM)
# Download from https://ollama.com
ollama pull mistral
ollama serve  # Keep running in background
```

### 2. Index Your Code

```bash
code-sensei index -p /path/to/project
# Chunks code, computes embeddings, stores in ChromaDB
```

### 3. Ask Questions

**Option A: Instant (Retrieval-Only)**
```bash
code-sensei ask "how does auth work?" --no-llm
# Returns: Code chunks matching your question
```

**Option B: With Local LLM (if Ollama is running)**
```bash
code-sensei ask "how does auth work?"
# Automatically uses Ollama if available
# Returns: Synthesized explanation from code
```

**Option C: With Cloud LLM**
```bash
export OPENAI_API_KEY=sk-...
code-sensei ask "how does auth work?"
# Falls back to OpenAI
# Returns: High-quality synthesized explanation
```

### 4. Interactive Chat

```bash
code-sensei chat -p .
> What are the main components?
[LLM mode]
> /llm-off
> Show me just the files
[Retrieval-only mode]
> /llm-on
> Explain the architecture
[Back to LLM mode]
```

---

## Decision Tree: Which Mode to Use

```
Do you have an OPENAI_API_KEY?
├─ YES → Want local + fallback?
│        ├─ YES → Use HYBRID_LLM_MODE=true (default)
│        │        Tries Ollama first, falls back to OpenAI
│        └─ NO → Use OPENAI_API_KEY directly
│                Skip Ollama, use OpenAI only
└─ NO → Do you have Ollama running?
        ├─ YES → Use HYBRID_LLM_MODE=true (default)
        │        Will use Ollama, skips OpenAI
        └─ NO → Use RETRIEVAL_ONLY_MODE=true or --no-llm flag
                Returns code chunks instantly, costs $0
```

---

## File Structure

```
src/code_sensei/
├── __init__.py
├── cli.py                          # Command-line interface
├── assistant/
│   ├── _base.py                   # Base class with hybrid LLM logic
│   ├── qa.py                      # Code Q&A with use_llm param
│   ├── test_generator.py          # Test generation
│   ├── doc_generator.py           # Documentation generation
│   └── refactor.py                # Code refactoring suggestions
├── indexer/
│   ├── file_loader.py             # Load source files
│   ├── chunker.py                 # Split files into chunks
│   ├── embedder.py                # Generate embeddings
│   └── watcher.py                 # Watch for file changes
├── memory/
│   └── conversation.py            # Conversation history + cache
├── retrieval/
│   ├── vector_store.py            # ChromaDB wrapper
│   └── retriever.py               # Semantic search
└── cache/
    └── sqlite_cache.py            # Persistent cache

config/
├── __init__.py
└── settings.py                    # Hybrid LLM + Ollama config

tests/
├── conftest.py
├── test_assistant.py
├── test_chunker.py
├── test_conversation_memory.py
├── test_file_loader.py
├── test_retriever.py
└── test_sqlite_cache.py           # 14 cache tests
```

---

## Test Coverage

**Total**: 108 tests passing

```
test_assistant.py                   16 tests
test_chunker.py                      8 tests
test_file_loader.py                  9 tests
test_retriever.py                   12 tests
test_conversation_memory.py         15 tests
test_sqlite_cache.py                14 tests
test_qa_hybrid_modes.py             16 tests
test_cli_integration.py             18 tests
```

---

## Performance Notes

| Mode | Speed | Cost | Quality |
|------|-------|------|---------|
| Retrieval-Only | <100ms | Free | Shows raw code |
| Ollama Local | 1-5s | Free | Good (local) |
| OpenAI API | 2-10s | ~$0.001-0.01 | Excellent |

---

## Common Issues & Solutions

### Issue: "No module named 'ollama'"
```bash
# This is optional. Hybrid mode gracefully falls back if Ollama isn't available
# If you want Ollama support:
pip install ollama
```

### Issue: "OPENAI_API_KEY not set"
```bash
# Option 1: Use retrieval-only mode
export RETRIEVAL_ONLY_MODE=true
code-sensei ask "question"

# Option 2: Use Ollama (free)
ollama pull mistral
ollama serve
code-sensei ask "question"

# Option 3: Set your API key
export OPENAI_API_KEY=sk-...
code-sensei ask "question"
```

### Issue: Ollama not responding
```bash
# Make sure Ollama is running
ollama serve

# Check it's accessible
curl http://localhost:11434/api/tags

# If still failing, hybrid mode will automatically fall back to OpenAI or retrieval-only
```

---

## Next Steps (Phase 3)

Potential enhancements:
- [ ] File watcher with auto-reindex
- [ ] Response streaming for large outputs
- [ ] Batch processing mode
- [ ] Web UI dashboard
- [ ] VS Code extension integration
- [ ] Performance optimization (caching, batching)
- [ ] Custom embedding models

---

## Documentation Files

- [HYBRID_LLM_GUIDE.md](HYBRID_LLM_GUIDE.md) - Ollama & hybrid mode detailed guide
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Feature summary with examples
- [demo_hybrid_modes.py](demo_hybrid_modes.py) - Working demonstration script

---

## Support

For detailed setup instructions, see [HYBRID_LLM_GUIDE.md](HYBRID_LLM_GUIDE.md)

For feature details, see [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)

For code examples, run: `python demo_hybrid_modes.py`
