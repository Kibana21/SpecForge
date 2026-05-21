import pytest
from app.services.corpus.chunker import chunk_text


def test_empty_input():
    assert chunk_text("") == []


def test_single_chunk_short_text():
    result = chunk_text("Hello world")
    assert len(result) == 1
    assert "Hello world" in result[0]


def test_two_chunks_long_text():
    # Generate text that will produce multiple chunks (> 512 tokens)
    word = "specification " * 600  # ~600 tokens
    result = chunk_text(word)
    assert len(result) >= 2
    # Overlap: second chunk should partially overlap with first
    assert result[0][:20] != result[1][:20]


def test_trailing_sub_minimal_merged():
    # A very long text followed by a tiny bit shouldn't produce a tiny last chunk
    base = "word " * 480  # just under 512 tokens
    # Add another block that creates an overlap window
    full = base + "extra " * 20
    result = chunk_text(full)
    if len(result) > 1:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        # Last chunk should have at least 20 tokens (merged if sub-minimal)
        last_tokens = enc.encode(result[-1])
        assert len(last_tokens) >= 20
