from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from click.testing import CliRunner

from code_sensei.assistant.qa import QAResponse
from code_sensei.cli import main
from code_sensei.retrieval.retriever import RetrievalResult


def test_ask_command_prints_metrics(monkeypatch, tmp_path: Path):
    runner = CliRunner()

    retrieval_results = [
        RetrievalResult(
            chunk_id="chunk-1",
            content="def load(): pass",
            source_path="src/code_sensei/indexer/file_loader.py",
            language="python",
            score=0.9,
            metadata={},
        )
    ]

    class DummyRetriever:
        def __init__(self):
            self.last_metrics = SimpleNamespace(embed_ms=1.5, vector_query_ms=2.5, avg_score=0.9)

    dummy_retriever = DummyRetriever()

    class DummyQA:
        def __init__(self, retriever, top_k=8, **kwargs):
            self.retriever = retriever
            self.top_k = top_k
            self.llm_init_error = None
            self.last_query_metrics = SimpleNamespace(
                total_ms=12.0,
                retrieval_ms=4.0,
                generation_ms=8.0,
                result_count=1,
                source_count=1,
            )

        def ask(self, question, language_filter=None, path_prefix=None, use_llm=True):
            return QAResponse(
                question=question,
                answer="Found it.",
                sources=["src/code_sensei/indexer/file_loader.py"],
                retrieval_results=retrieval_results,
            )

    monkeypatch.setattr("code_sensei.assistant.qa.CodeQA", DummyQA)
    monkeypatch.setattr("code_sensei.cli._load_pipeline", lambda project_dir: (object(), object(), dummy_retriever))

    result = runner.invoke(
        main,
        ["ask", "Where is file loading?", "--project-dir", str(tmp_path), "--no-stream"],
    )

    assert result.exit_code == 0
    assert "Ask Metrics" in result.output
    assert "Retrieval (ms)" in result.output
    assert "Embed (ms)" in result.output


def test_index_command_prints_metrics(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    sample_file = tmp_path / "main.py"
    sample_file.write_text("print('ok')", encoding="utf-8")

    class DummySourceFile:
        def __init__(self, path: Path):
            self.path = path
            self.content = path.read_text(encoding="utf-8")
            self.language = "python"

    class DummyLoader:
        def __init__(self, root, extensions=None):
            self.root = root

        def load(self):
            yield DummySourceFile(sample_file)

    class DummyChunker:
        def chunk_file(self, source_file):
            return [SimpleNamespace(content=source_file.content)]

    class DummyEmbedder:
        embed_init_error = None

        def embed_chunks(self, chunks):
            return chunks

    class DummyVectorStore:
        def __init__(self, collection_name):
            self.collection_name = collection_name

        def connect(self):
            return None

        def upsert(self, embedded):
            return None

    monkeypatch.setattr("code_sensei.indexer.file_loader.FileLoader", DummyLoader)
    monkeypatch.setattr("code_sensei.indexer.chunker.Chunker", DummyChunker)
    monkeypatch.setattr("code_sensei.indexer.embedder.Embedder", DummyEmbedder)
    monkeypatch.setattr("code_sensei.retrieval.vector_store.VectorStore", DummyVectorStore)

    result = runner.invoke(main, ["index", str(tmp_path)])

    assert result.exit_code == 0
    assert "Index Metrics" in result.output
    assert "Files/sec" in result.output
    assert "Chunks/sec" in result.output


def test_benchmark_command_writes_json(monkeypatch, tmp_path: Path):
    runner = CliRunner()
    dataset = tmp_path / "dataset.json"
    output_json = tmp_path / "summary.json"
    dataset.write_text(
        json.dumps([
            {
                "query": "Where is file loading implemented?",
                "expected_sources": ["src/code_sensei/indexer/file_loader.py"],
                "top_k": 3,
            }
        ]),
        encoding="utf-8",
    )

    class DummyRetriever:
        def search(self, query, top_k=None, language_filter=None, path_prefix=None):
            return [
                RetrievalResult(
                    chunk_id="chunk-1",
                    content="def load(): pass",
                    source_path="src/code_sensei/indexer/file_loader.py",
                    language="python",
                    score=0.95,
                    metadata={},
                )
            ]

    monkeypatch.setattr("code_sensei.cli._load_pipeline", lambda project_dir: (object(), object(), DummyRetriever()))

    result = runner.invoke(
        main,
        [
            "benchmark-retrieval",
            "--project-dir",
            str(tmp_path),
            "--dataset",
            str(dataset),
            "--output-json",
            str(output_json),
        ],
    )

    assert result.exit_code == 0
    summary = json.loads(output_json.read_text(encoding="utf-8"))
    assert summary["total_queries"] == 1
    assert summary["recall_at_k"] == 1.0
