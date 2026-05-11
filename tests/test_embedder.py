from __future__ import annotations

from unittest.mock import MagicMock

from code_sensei.indexer.chunker import Chunk
from code_sensei.indexer.embedder import Embedder


def _make_chunk(content: str = "def foo():\n    return 1\n") -> Chunk:
    return Chunk(
        chunk_id="chunk-1",
        content=content,
        source_path="/tmp/sample.py",
        language="python",
        start_char=0,
        end_char=len(content),
        metadata={"chunk_index": 0, "language": "python"},
    )


def test_embed_query_returns_model_vector_when_available():
    emb = Embedder(provider="ollama")
    emb._embedding_model = MagicMock()
    emb._embedding_model.embed_documents.return_value = [[0.1, 0.2, 0.3]]

    result = emb.embed_query("hello")

    assert result == [0.1, 0.2, 0.3]


def test_embed_chunks_returns_embedded_chunk_objects():
    emb = Embedder(provider="ollama")
    emb._embedding_model = MagicMock()
    emb._embedding_model.embed_documents.return_value = [[0.9, 0.8, 0.7]]
    chunks = [_make_chunk()]

    result = emb.embed_chunks(chunks)

    assert len(result) == 1
    assert result[0].chunk.chunk_id == "chunk-1"
    assert result[0].embedding == [0.9, 0.8, 0.7]


def test_embed_query_returns_zero_vector_when_model_unavailable():
    emb = Embedder(provider="ollama")
    emb._embedding_model = None

    result = emb.embed_query("hello")

    assert len(result) == 1536
    assert set(result) == {0.0}
