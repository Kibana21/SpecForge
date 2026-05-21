from app.services.embeddings.base import EmbeddingProvider
from app.services.embeddings.mock_embedding_provider import MockEmbeddingProvider
from app.services.embeddings.vertex_embedding_provider import VertexEmbeddingProvider


def get_embedding_provider() -> EmbeddingProvider:
    from app.config import get_settings
    settings = get_settings()
    if settings.llm_provider == "mock":
        return MockEmbeddingProvider()
    return VertexEmbeddingProvider()


__all__ = ["EmbeddingProvider", "MockEmbeddingProvider", "VertexEmbeddingProvider", "get_embedding_provider"]
