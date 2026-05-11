"""
Demonstration of Hybrid LLM Mode and Retrieval-Only features.

This script shows:
1. Hybrid mode with fallback logic
2. Retrieval-only mode for instant results
3. Chat mode with LLM toggle
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

# Import CodeSensei components
from code_sensei.assistant.qa import CodeQA
from code_sensei.cache.sqlite_cache import SqliteCache
from code_sensei.memory.conversation import ConversationMemory
from code_sensei.indexer.file_loader import FileLoader
from code_sensei.indexer.chunker import Chunker
from code_sensei.indexer.embedder import Embedder
from code_sensei.retrieval.vector_store import VectorStore
from code_sensei.retrieval.retriever import Retriever

print("=" * 80)
print("HYBRID LLM MODE & RETRIEVAL-ONLY DEMO")
print("=" * 80)

# Setup
DEMO_PROJECT = Path(__file__).parent / "src" / "code_sensei"

loader = FileLoader(root=DEMO_PROJECT)
chunker = Chunker()
embedder = Embedder()

print(f"\n[FILE] Loading codebase from: {DEMO_PROJECT}")
print("   Indexing files...")

files_loaded = 0
total_chunks = 0

for source_file in loader.load():
    files_loaded += 1
    chunks = chunker.chunk_file(source_file)
    total_chunks += len(chunks)

print(f"[OK] Indexed {files_loaded} files -> {total_chunks} chunks")

# Build retriever
vector_store = VectorStore(collection_name="demo_hybrid")
vector_store.connect()
retriever = Retriever(vector_store=vector_store, embedder=embedder)

# Mock LLM responses
def mock_invoke(self, prompt):
    if "Question" in prompt:
        return "The CodeQA assistant answers questions about your codebase using RAG (Retrieval-Augmented Generation). It retrieves relevant code chunks and uses an LLM to synthesize answers. Learn more in src/code_sensei/assistant/qa.py."
    else:
        return "[LLM Response]"

with patch.object(CodeQA, '_build_llm', return_value=None), \
     patch.object(CodeQA, '_invoke', mock_invoke):

    print("\n" + "=" * 80)
    print("SCENARIO 1: RETRIEVAL-ONLY MODE (Fast, Free)")
    print("=" * 80)
    
    qa = CodeQA(retriever=retriever, top_k=3)
    response = qa.ask(
        question="How does CodeQA work?",
        use_llm=False  # Retrieval-only mode
    )
    
    print(f"\n[Q] Question: How does CodeQA work?")
    print(f"[FAST] Mode: Retrieval-Only (instant, no LLM)")
    print(f"\n[RESULTS] Retrieved {len(response.retrieval_results)} code chunks:\n")
    
    for i, result in enumerate(response.retrieval_results[:2], 1):
        print(f"  Chunk {i}: {result.source_path}")
        print(f"  Relevance: {result.relevance_label} ({result.score:.2f})")
        print(f"  Preview: {result.content[:120]}...\n")
    
    print("\n" + "=" * 80)
    print("SCENARIO 2: LLM MODE (Detailed, Synthesized)")
    print("=" * 80)
    
    response = qa.ask(
        question="How does CodeQA work?",
        use_llm=True  # LLM synthesis mode
    )
    
    print(f"\n[Q] Question: How does CodeQA work?")
    print(f"[BRAIN] Mode: LLM Synthesis (detailed analysis)")
    print(f"\n[RESPONSE] LLM Response:")
    print(f"   {response.answer}")
    print(f"\n[SOURCES] Sources: {', '.join(response.sources[:3])}")
    
    print("\n" + "=" * 80)
    print("SCENARIO 3: INTERACTIVE CHAT WITH MODE TOGGLE")
    print("=" * 80)
    
    cache = SqliteCache()
    memory = ConversationMemory(session_id="demo_hybrid", cache=cache)
    
    print(f"\n[CHAT] Starting chat session (demo_hybrid)")
    print(f"   Initial: LLM mode enabled\n")
    
    # Simulate user input with mode changes
    interactions = [
        ("LLM ON", "What are the main components?", True),
        ("LLM OFF", "What files exist?", False),
        ("LLM ON", "Best practices?", True),
    ]
    
    for mode_name, question, use_llm in interactions:
        memory.add_user_message(question)
        response = qa.ask(question=question, use_llm=use_llm)
        memory.add_assistant_message(response.answer)
        
        mode_indicator = "[BRAIN]" if use_llm else "[FAST]"
        print(f"{mode_indicator} [{mode_name}] You: {question}")
        print(f"   CodeSensei: {response.answer[:80]}...")
        print()
    
    print(f"[SAVE] Conversation saved to cache:")
    print(f"   Session ID: {memory.session_id}")
    print(f"   Messages: {memory.message_count}")
    print(f"   Can be restored on next session")

print("\n" + "=" * 80)
print("FALLBACK LOGIC DEMONSTRATION")
print("=" * 80)

print("""
When you run: code-sensei ask "question"

CodeSensei tries in this order:

  1. Is --no-llm flag set?
     └─ YES -> Use retrieval-only mode (instant)

  2. Is RETRIEVAL_ONLY_MODE=true in .env?
     └─ YES -> Use retrieval-only mode

  3. Is HYBRID_LLM_MODE=true? (default)
     └─ YES
        a) Try Ollama first
           └─ Is ollama serve running?
              [YES] -> Use local LLM (free)
              [NO] -> Continue to step 3b
        
        b) Try OpenAI
           └─ Is OPENAI_API_KEY set?
              [YES] -> Use OpenAI (paid, high quality)
              [NO] -> Fall back to retrieval-only

  4. If HYBRID_LLM_MODE=false
     └─ Only try OpenAI
        └─ If OPENAI_API_KEY not set -> Error
""")

print("\n" + "=" * 80)
print("CONFIGURATION REFERENCE")
print("=" * 80)

config_example = """
.env file:

# Hybrid mode (recommended)
HYBRID_LLM_MODE=true

# Ollama configuration (local LLM)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral

# OpenAI configuration (fallback)
OPENAI_API_KEY=sk-...

# Or force retrieval-only mode
RETRIEVAL_ONLY_MODE=false
"""

print(config_example)

print("\n" + "=" * 80)
print("QUICK START")
print("=" * 80)

quickstart = """
1. Use retrieval-only (instant, free):
   code-sensei ask "question" --no-llm

2. Use local Ollama (free):
   ollama pull mistral
   ollama serve
   code-sensei ask "question" -p .

3. Use OpenAI (paid, high quality):
   export OPENAI_API_KEY=sk-...
   code-sensei ask "question" -p .

4. Interactive chat with toggle:
   code-sensei chat -p .
   # Type: /llm-off (retrieval-only)
   # Type: /llm-on (LLM mode)
"""

print(quickstart)

print("\n✓ Demo complete! See HYBRID_LLM_GUIDE.md for full documentation.")
