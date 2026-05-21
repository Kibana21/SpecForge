import asyncio
import math
import pytest
from app.services.embeddings.mock_embedding_provider import MockEmbeddingProvider


@pytest.fixture
def provider():
    return MockEmbeddingProvider()


def test_returns_768_floats(provider):
    result = asyncio.run(provider.embed("test text"))
    assert len(result) == 768
    assert all(isinstance(v, float) for v in result)


def test_deterministic(provider):
    a = asyncio.run(provider.embed("same input"))
    b = asyncio.run(provider.embed("same input"))
    assert a == b


def test_different_inputs_differ(provider):
    a = asyncio.run(provider.embed("input A"))
    b = asyncio.run(provider.embed("input B"))
    assert a != b


def test_unit_length_normalized(provider):
    vec = asyncio.run(provider.embed("some text"))
    norm = math.sqrt(sum(v * v for v in vec))
    assert abs(norm - 1.0) < 1e-5


def test_batch_returns_correct_count(provider):
    texts = ["a", "b", "c", "d"]
    result = asyncio.run(provider.embed_batch(texts))
    assert len(result) == 4
    assert all(len(v) == 768 for v in result)
