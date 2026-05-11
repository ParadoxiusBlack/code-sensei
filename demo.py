"""
Demonstration of CodeSensei capabilities.

This script showcases:
1. Indexing a codebase
2. Performing Q&A queries
3. Generating tests
4. Analyzing code for refactoring
5. Generating documentation
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

# Setup paths
DEMO_PROJECT = Path(__file__).parent
print(f"📁 Demo project: {DEMO_PROJECT}\n")

# Import CodeSensei components
from code_sensei.indexer.file_loader import FileLoader
from code_sensei.indexer.chunker import Chunker
from code_sensei.indexer.embedder import Embedder
from code_sensei.retrieval.vector_store import VectorStore
from code_sensei.retrieval.retriever import Retriever
from code_sensei.assistant.qa import CodeQA
from code_sensei.assistant.test_generator import TestGenerator
from code_sensei.assistant.refactor import RefactorAdvisor
from code_sensei.assistant.doc_generator import DocGenerator, DocStyle
from code_sensei.memory.conversation import ConversationMemory
from code_sensei.cache.sqlite_cache import SqliteCache

print("=" * 80)
print("STEP 1: INDEX THE CODEBASE")
print("=" * 80)

# Load and chunk files
loader = FileLoader(root=DEMO_PROJECT / "src")
chunker = Chunker()
embedder = Embedder()

files_loaded = 0
total_chunks = 0

for source_file in loader.load():
    files_loaded += 1
    print(f"  ✓ Loaded: {source_file.path.name} ({len(source_file.content)} chars)")
    chunks = chunker.chunk_file(source_file)
    total_chunks += len(chunks)
    print(f"    → Chunked into {len(chunks)} pieces")

print(f"\n📊 Summary: {files_loaded} files, {total_chunks} chunks indexed\n")

print("=" * 80)
print("STEP 2: QUERY THE INDEXED CODE")
print("=" * 80)

# Build a mock retriever with real chunks
vector_store = VectorStore(collection_name="demo")
vector_store.connect()
retriever = Retriever(vector_store=vector_store, embedder=embedder)

# Create assistants with mocked LLM (no API key needed)
def mock_invoke(self, prompt):
    """Mock LLM response based on the prompt content."""
    if "Question" in prompt:
        return "The TokenManager class manages JWT tokens for authenticated users. It provides methods to issue tokens with expiry times and validate existing tokens. See src/auth.py for implementation details."
    elif "Generate comprehensive tests" in prompt:
        return """def test_token_manager_issue_token():
    manager = TokenManager()
    token = manager.issue_token("user123", expiry_hours=24)
    assert token.startswith("token_user123_")
    assert manager.validate_token(token)

def test_token_manager_expired_token():
    manager = TokenManager()
    token = manager.issue_token("user456", expiry_hours=-1)  # Already expired
    assert not manager.validate_token(token)"""
    elif "refactoring" in prompt.lower():
        return """## Critical Issues
- **Location**: src/auth.py - TokenManager.issue_token()
- **Problem**: Placeholder token implementation using string concatenation instead of proper JWT
- **Suggested Fix**: Use PyJWT library to create proper JWT tokens with cryptographic signing

## Major Issues  
- **Location**: src/auth.py - User.verify_password()
- **Problem**: Using Python's hash() which is not secure for password hashing
- **Suggested Fix**: Use bcrypt.hashpw() for proper password hashing"""
    elif "docstrings" in prompt:
        return """# TokenManager

Manages JWT tokens for authenticated users.

## Methods

### issue_token(user_id: str, expiry_hours: int = 24) -> str
Issue a JWT token for the specified user.

**Parameters:**
- user_id: Unique user identifier
- expiry_hours: Token validity period in hours (default: 24)

**Returns:** JWT token string

### validate_token(token: str) -> bool
Check if a token is still valid and not expired.

**Parameters:**
- token: JWT token to validate

**Returns:** True if valid, False if expired or not found"""
    else:
        return "[Mock LLM Response] For demo purposes, this would call the actual LLM."

# Apply mocks
with patch.object(CodeQA, '_build_llm', return_value=None), \
     patch.object(TestGenerator, '_build_llm', return_value=None), \
     patch.object(RefactorAdvisor, '_build_llm', return_value=None), \
     patch.object(DocGenerator, '_build_llm', return_value=None), \
     patch.object(CodeQA, '_invoke', mock_invoke), \
     patch.object(TestGenerator, '_invoke', mock_invoke), \
     patch.object(RefactorAdvisor, '_invoke', mock_invoke), \
     patch.object(DocGenerator, '_invoke', mock_invoke):
    
    print("\n2A) CODE Q&A\n" + "-" * 80)
    qa = CodeQA(retriever=retriever, top_k=3)
    response = qa.ask("What does TokenManager do?")
    print(f"❓ Question: What does TokenManager do?\n")
    print(f"💭 Answer:\n{response.answer}\n")
    if response.sources:
        print(f"📄 Sources: {', '.join(response.sources)}\n")
    
    print("\n2B) TEST GENERATION\n" + "-" * 80)
    test_gen = TestGenerator(retriever=retriever, top_k=3)
    test_result = test_gen.generate(
        target="TokenManager",
        framework="pytest",
        test_types="unit"
    )
    print(f"🧪 Generating tests for: {test_result.source_path}\n")
    print(f"Framework: {test_result.framework}\n")
    print("Generated test code:")
    print(f"{test_result.test_code}\n")
    
    print("\n2C) REFACTORING ANALYSIS\n" + "-" * 80)
    advisor = RefactorAdvisor(retriever=retriever, top_k=5)
    refactor_report = advisor.analyse("token and password handling")
    print(f"🔍 Analysis of: {refactor_report.target}\n")
    print("Refactoring Report:")
    print(refactor_report.raw_response)
    print(f"\nFound: {refactor_report.critical_count} critical, {refactor_report.major_count} major issues\n")
    
    print("\n2D) DOCUMENTATION GENERATION\n" + "-" * 80)
    doc_gen = DocGenerator(retriever=retriever, top_k=3)
    doc_result = doc_gen.generate(
        target="TokenManager",
        doc_type="docstrings",
        style=DocStyle.GOOGLE
    )
    print(f"📚 Generating {doc_result.doc_type} in {doc_result.style} style\n")
    print("Generated documentation:")
    print(doc_result.content + "\n")

print("=" * 80)
print("STEP 3: CONVERSATION MEMORY")
print("=" * 80)

cache = SqliteCache()
memory = ConversationMemory(session_id="demo_session", cache=cache)

print(f"\n💬 Starting multi-turn conversation...\n")
memory.add_user_message("What's the main authentication module?")
print(f"You: What's the main authentication module?")
memory.add_assistant_message("The auth.py module contains the authentication logic with User and TokenManager classes.")
print(f"CodeSensei: The auth.py module contains the authentication logic with User and TokenManager classes.\n")

memory.add_user_message("Should I use bcrypt for password hashing?")
print(f"You: Should I use bcrypt for password hashing?")
memory.add_assistant_message("Yes, absolutely! The current hash() implementation is insecure. Use bcrypt.hashpw() instead.")
print(f"CodeSensei: Yes, absolutely! The current hash() implementation is insecure. Use bcrypt.hashpw() instead.\n")

print(f"📊 Conversation Stats:")
print(f"  - Total messages: {memory.message_count}")
print(f"  - Last user message: {memory.last_user_message}")
print(f"  - Session persisted to cache: ✓\n")

print("=" * 80)
print("DEMO COMPLETE ✨")
print("=" * 80)
print(f"""
CodeSensei successfully demonstrated:

1. ✓ Indexing Python files (3 files → {total_chunks} chunks)
2. ✓ Q&A about the codebase
3. ✓ Automated test generation
4. ✓ Refactoring analysis with severity levels
5. ✓ Multi-style documentation generation
6. ✓ Persistent conversation memory

Try these commands in your actual project:

  code-sensei index ./demo_project/src
  code-sensei ask "What security issues exist?" -p ./demo_project
  code-sensei tests TokenManager -p ./demo_project
  code-sensei refactor "authentication" -p ./demo_project
  code-sensei docs TokenManager --type docstrings -p ./demo_project
  code-sensei chat -p ./demo_project
""")
