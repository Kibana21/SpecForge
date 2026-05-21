import asyncio
import logging

from app.services.embeddings.base import EmbeddingProvider

log = logging.getLogger(__name__)

_BATCH_SIZE = 250
_EXPECTED_DIMS = 768
_MAX_RETRIES = 3


class VertexEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        from app.config import get_settings
        from app.core.google_credentials import get_google_credentials
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        settings = get_settings()
        creds = get_google_credentials()
        self._model = GoogleGenerativeAIEmbeddings(
            model=settings.embedding_model,
            credentials=creds,
        )
        self._validated = False

    async def embed(self, text: str) -> list[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i: i + _BATCH_SIZE]
            embeddings = await self._embed_with_retry(batch)
            if not self._validated and embeddings:
                assert len(embeddings[0]) == _EXPECTED_DIMS, (
                    f"Expected {_EXPECTED_DIMS} dims, got {len(embeddings[0])}"
                )
                self._validated = True
            all_embeddings.extend(embeddings)
        return all_embeddings

    async def _embed_with_retry(self, texts: list[str]) -> list[list[float]]:
        import google.api_core.exceptions as gexc

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                return await asyncio.get_event_loop().run_in_executor(
                    None, self._model.embed_documents, texts
                )
            except gexc.GoogleAPICallError as exc:
                log.warning("vertex_embed attempt=%d error=%s", attempt, str(exc))
                if attempt == _MAX_RETRIES:
                    raise
                await asyncio.sleep(2**attempt)
        raise RuntimeError("Unreachable")
