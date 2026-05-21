import math

from app.services.embeddings.base import EmbeddingProvider

_DIMS = 768


def _unit_vector(seed: int) -> list[float]:
    """Deterministic pseudo-random unit-length 768-dim vector seeded from hash."""
    # Simple LCG to generate reproducible floats from seed
    values: list[float] = []
    state = seed & 0xFFFFFFFF
    for _ in range(_DIMS):
        state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
        values.append((state / 0xFFFFFFFF) * 2.0 - 1.0)
    # Normalize to unit length
    norm = math.sqrt(sum(v * v for v in values))
    if norm == 0:
        values[0] = 1.0
        norm = 1.0
    return [v / norm for v in values]


class MockEmbeddingProvider(EmbeddingProvider):
    """Returns deterministic unit-normalized 768-dim vectors. Zero cost, no API calls."""

    async def embed(self, text: str) -> list[float]:
        return _unit_vector(hash(text) % (2**32))

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [_unit_vector(hash(t) % (2**32)) for t in texts]
