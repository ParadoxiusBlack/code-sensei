## Hybrid LLM Mode & Retrieval-Only Features

### Overview

CodeSensei now supports multiple modes of operation:

1. **Hybrid LLM Mode** (Default) - Automatically tries Ollama first, falls back to OpenAI
2. **Retrieval-Only Mode** - Show code chunks without LLM processing (free, instant)
3. **Ollama Support** - Run local LLMs with no API key needed

---

## 🚀 Hybrid LLM Mode (Default)

When enabled, CodeSensei will:

1. **Try Ollama first** (local, free) - if `ollama serve` is running
2. **Fall back to OpenAI** - if Ollama isn't available and API key is set
3. **Show raw chunks** - if neither is available (retrieval-only mode)

### Enable Hybrid Mode

Set in `.env`:

```env
HYBRID_LLM_MODE=true  # Enabled by default
```

Or disable and use OpenAI only:

```env
HYBRID_LLM_MODE=false
```

---

## 🔗 Ollama Integration

### Setup Ollama

```bash
# Install Ollama from https://ollama.com
ollama pull mistral
ollama pull nomic-embed-text
ollama serve  # Runs on http://localhost:11434 by default
```

### Configure Ollama

Set in `.env`:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral  # or neural-chat, orca-mini
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text
```

### Runtime Package Note

CodeSensei now uses `langchain-ollama` (`OllamaLLM` / `OllamaEmbeddings`) instead of deprecated
`langchain_community.llms.Ollama`.

### Supported Models

| Model | Speed | Quality | RAM |
|-------|-------|---------|-----|
| orca-mini | ⚡ Fast | ⭐⭐ | 4GB |
| neural-chat | ⚡⚡ | ⭐⭐⭐ | 6GB |
| mistral | ⚡⚡ | ⭐⭐⭐⭐ | 8GB |

---

## 📍 Retrieval-Only Mode

Get instant results without waiting for LLM processing. Shows relevant code chunks directly.

### Enable Retrieval-Only

#### Via CLI flag:
```bash
code-sensei ask "What does this function do?" --no-llm
```

#### Via .env:
```env
RETRIEVAL_ONLY_MODE=true
```

#### Via chat command:
```bash
code-sensei chat --no-llm
```

Then in chat, toggle with:
```
You: /llm-off
# Now shows raw chunks

You: /llm-on
# Switches back to LLM mode
```

### Output Example

```
❓ Question: What does TokenManager do?

💭 Answer:
# File: src/auth.py (lang: python, score: 0.95)
```python
class TokenManager:
    """Manages JWT tokens for authenticated users."""
    
    def __init__(self):
        self.tokens = {}
    
    def issue_token(self, user_id: str, expiry_hours: int = 24) -> str:
        """Issue a JWT token for the user."""
        import time
        token = f"token_{user_id}_{int(time.time())}"
        self.tokens[token] = {"user_id": user_id, "expiry": time.time() + expiry_hours * 3600}
        return token
```
```

---

## 🎯 Usage Patterns

### Pattern 1: Development (No API Key)

```bash
# Setup
ollama pull mistral
ollama serve

# Use CodeSensei
code-sensei index ./my_project
code-sensei ask "What does this do?" -p ./my_project
# ✅ Uses local Ollama, no API key needed
```

### Pattern 2: Quick Lookup (Retrieval-Only)

```bash
code-sensei ask "Find security issues" --no-llm -p ./my_project
# ✅ Instant results, just show relevant code chunks
```

### Pattern 3: Production (OpenAI)

```bash
# Setup .env with OpenAI key
export OPENAI_API_KEY=sk-...

# Use CodeSensei
code-sensei ask "What's the architecture?" -p ./my_project
# ✅ Uses OpenAI (Ollama not running)
```

### Pattern 4: Interactive with Flexibility

```bash
code-sensei chat -p ./my_project

You: /llm-on      # Start with LLM
CodeSensei: [detailed analysis]

You: /llm-off     # Switch to fast mode
CodeSensei: [raw code chunks]

You: /llm-on      # Back to detailed
```

---

## 🔧 Environment Variables

### LLM Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `HYBRID_LLM_MODE` | `true` | Try Ollama, then OpenAI, then retrieval-only |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `OLLAMA_MODEL` | `mistral` | Model to use |
| `OPENAI_API_KEY` | `` | OpenAI API key (optional) |
| `RETRIEVAL_ONLY_MODE` | `false` | Always show raw chunks |

### Embedding Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_PROVIDER` | `ollama` | Embedding backend (`ollama`, `openai`, `azure_openai`) |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model name |

### Example .env

```env
# Hybrid mode (recommended)
HYBRID_LLM_MODE=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral

# Local embeddings (default, fully offline)
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text

# Fallback to OpenAI if Ollama not available
OPENAI_API_KEY=sk-your-key-here

# Chat settings
CHAT_MODEL=gpt-4o
TEMPERATURE=0.2
MAX_TOKENS=2048
```

---

## 📊 Decision Tree

```
User runs: code-sensei ask "question"
  │
  ├─ HYBRID_LLM_MODE=true?
  │  │
  │  ├─ YES → Try Ollama
  │  │  │
  │  │  ├─ Ollama available? → Use it ✅
  │  │  └─ No → Try OpenAI
  │  │     │
  │  │     ├─ OpenAI key set? → Use it ✅
  │  │     └─ No → Show raw chunks ✅
  │  │
  │  └─ NO → Only try OpenAI
  │     │
  │     ├─ OpenAI key set? → Use it ✅
  │     └─ No → Error
  │
  └─ RETRIEVAL_ONLY_MODE=true?
     └─ YES → Always show raw chunks ✅

CLI flag --no-llm?
  └─ YES → Show raw chunks (override config) ✅
```

---

## 🐛 Troubleshooting

### "Ollama not available" but I have it running

**Check:**
```bash
curl http://localhost:11434/api/tags
# Should return list of models
```

**If that fails:**
- Make sure `ollama serve` is running
- Check port is 11434 (or update `OLLAMA_BASE_URL`)
- Check firewall isn't blocking localhost

### Embedding warning about missing OpenAI key

If you previously used OpenAI embeddings, set local embeddings explicitly:

```bash
# Add to .env
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text
```

Then ensure the embedding model is downloaded:

```bash
ollama pull nomic-embed-text
```

### "No LLM available" error

**Solution 1 - Use Ollama:**
```bash
ollama pull mistral
ollama serve
```

**Solution 2 - Use OpenAI:**
```bash
# Add to .env
OPENAI_API_KEY=sk-...
```

**Solution 3 - Use retrieval-only:**
```bash
code-sensei ask "question" --no-llm
```

### Responses are slow

**Try retrieval-only mode:**
```bash
code-sensei ask "question" --no-llm
# Instant response with code chunks
```

---

## 💡 Performance Tips

| Mode | Speed | Quality | Cost |
|------|-------|---------|------|
| Retrieval-only | ⚡⚡⚡ Instant | ⭐⭐ Basic | 💰 Free |
| Ollama (local) | ⚡⚡ 2-5s | ⭐⭐⭐ Good | 💰 Free |
| OpenAI | ⚡ 3-10s | ⭐⭐⭐⭐⭐ Excellent | 💰 Cheap |

**Recommendation:** Start with Ollama for development, use OpenAI for production when LLM quality matters most.

---

## 🧪 Testing

All 108 tests pass with new features:

```bash
python -m pytest tests/ -v
# ✅ All modes tested (Ollama, OpenAI, retrieval-only)
```

---

## What's Next?

Potential enhancements:
- Support for more local LLMs (LLaMA, Phi, etc.)
- Response caching to avoid duplicate queries
- Custom model endpoints
- Response streaming for large outputs
