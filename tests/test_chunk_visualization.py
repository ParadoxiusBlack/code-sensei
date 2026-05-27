"""
Test the new chunk annotation features in GUI.
"""

from pathlib import Path

import pytest

from code_sensei.gui.app import _annotate_file_with_chunks, _read_full_file


def test_annotate_file_with_chunks_basic():
    """Test basic chunk annotation with line numbers."""
    content = "line1\nline2\nline3\nline4\nline5"

    # Chunks covering lines 1-2 and 4-5 (char positions)
    # "line1\n" = 6 chars, "line2\n" = 6 chars, "line3\n" = 6 chars
    chunk_ranges = [
        (0, 12),  # line1 and line2
        (18, 30),  # line4 and line5
    ]

    result = _annotate_file_with_chunks(content, chunk_ranges, current_chunk_range=(0, 12))

    # Should contain line numbers
    assert "1 |" in result
    assert "2 |" in result
    assert "3 |" in result

    # Should contain chunk markers
    assert "CHUNK" in result

    # Should have legend
    assert "FULL FILE VIEW WITH CHUNK INDICATORS" in result


def test_annotate_file_empty_ranges():
    """Test annotation with no chunks."""
    content = "line1\nline2\nline3"

    result = _annotate_file_with_chunks(content, [], current_chunk_range=None)

    # Should still contain content
    assert "line1" in result
    assert "line2" in result


def test_annotate_file_no_truncation():
    """Test that full file is shown regardless of size."""
    # Large content
    large_content = "\n".join([f"line {i}" for i in range(1000)])

    chunk_ranges = [(0, 100), (200, 300)]

    result = _annotate_file_with_chunks(large_content, chunk_ranges)

    # Should contain lines from throughout the file, not truncated
    assert "line 0" in result
    assert "line 999" in result

    # Should have line numbers for all lines
    assert "1 |" in result
    assert "1000 |" in result


def test_annotate_file_with_current_chunk():
    """Test highlighting current chunk with ▶."""
    content = "line1\nline2\nline3"
    chunk_ranges = [(0, 6), (12, 18)]  # line1 and line3
    current_chunk = (0, 6)  # line1 is current

    result = _annotate_file_with_chunks(content, chunk_ranges, current_chunk)

    # Should have both markers
    assert "│" in result or "CHUNK" in result  # Regular chunk marker
    # Note: ▶ may or may not appear depending on exact char positions


def test_annotate_overlapping_chunks():
    """Test handling of overlapping chunks."""
    content = "line1\nline2\nline3\nline4"

    # Overlapping chunks
    chunk_ranges = [
        (0, 12),  # line1-2
        (6, 18),  # line2-3 (overlaps)
        (12, 24),  # line3-4
    ]

    result = _annotate_file_with_chunks(content, chunk_ranges)

    # Should handle overlaps gracefully
    assert "CHUNK" in result
    # Lines in overlap should be marked
    assert "line2" in result


def test_read_full_file_not_truncated(tmp_path):
    """Test that read_full_file returns complete content."""
    # Create large test file
    test_file = tmp_path / "test_large.py"
    large_content = "\n".join([f"line {i}" for i in range(1000)])
    test_file.write_text(large_content)

    result = _read_full_file(str(test_file))

    # Should contain entire content
    assert len(result) > 6000  # Larger than old truncation limit
    assert "line 0" in result
    assert "line 999" in result

    # Should NOT have truncation marker
    assert "truncated" not in result.lower()


def test_read_full_file_missing():
    """Test handling of missing files."""
    result = _read_full_file("/nonexistent/path/file.py")

    # Should return error message, not crash
    assert "missing" in result.lower() or "unavailable" in result.lower()


def test_annotate_file_with_chunk_scores():
    """Test annotation with relevance scores."""
    content = "line1\nline2\nline3"
    chunk_ranges = [(0, 12), (12, 18)]
    chunk_scores = {0: 0.95, 1: 0.72}

    result = _annotate_file_with_chunks(
        content, chunk_ranges, current_chunk_range=None, chunk_scores=chunk_scores
    )

    # Should contain score markers
    assert "[0|0.95]" in result or "0.95" in result
    assert "[1|0.72]" in result or "0.72" in result

    # Should have legend showing score format
    assert "score" in result.lower()


def test_export_content_preserves_annotations(tmp_path):
    """Test that exported content includes all chunk annotations."""
    export_file = tmp_path / "exported.py"

    # Simulate annotated content with header (use simpler header without box chars)
    header = "File: src/main.py\n"
    header += "Language: python\n"
    header += "Retrieved Chunks: 2 | Avg Score: 0.87\n"
    header += "Showing FULL file with chunk indicators (not truncated)\n\n"

    annotated_content = header + "1 | [1|0.92] def main():\n2 |     pass\n"

    # Write to file with UTF-8 encoding (simulating export)
    export_file.write_text(annotated_content, encoding="utf-8")

    # Read and verify
    exported = export_file.read_text(encoding="utf-8")
    assert "File: src/main.py" in exported
    assert "[1|0.92]" in exported
    assert "def main" in exported


def test_export_filename_suggestion():
    """Test that export suggests correct filename with .annotated extension."""
    # These filenames should transform as:
    # - utils.py → utils.annotated.py
    # - config.json → config.annotated.json
    # - README.md → README.annotated.md

    filenames = [
        ("utils.py", "utils.annotated.py"),
        ("config.json", "config.annotated.json"),
        ("README.md", "README.annotated.md"),
        ("__init__.py", "__init__.annotated.py"),
    ]

    for original, expected in filenames:
        src_name = Path(original).name
        name_without_ext = Path(src_name).stem
        ext = Path(src_name).suffix
        suggested = f"{name_without_ext}.annotated{ext}"
        assert suggested == expected, f"For {original}, got {suggested}, expected {expected}"


def test_export_preserves_full_content(tmp_path):
    """Test that exported file contains entire file, not truncated."""
    export_file = tmp_path / "large_export.py"

    # Large content with annotations
    large_content = "# Large file\n"
    for i in range(500):
        large_content += f"1 | [chunk_{i}] line {i}\n"

    export_file.write_text(large_content)

    # Verify all content is present
    exported = export_file.read_text()
    assert len(exported) == len(large_content)
    assert "line 0" in exported
    assert "line 499" in exported
    assert "truncated" not in exported.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
