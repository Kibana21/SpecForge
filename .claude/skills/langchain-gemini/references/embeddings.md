# GoogleGenerativeAIEmbeddings

## Instantiation (project pattern)

```python
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.core.google_credentials import get_google_credentials
from app.config import get_settings

settings = get_settings()
embedder = GoogleGenerativeAIEmbeddings(
    model=settings.embedding_model,          # "text-embedding-004"
    credentials=get_google_credentials(),
)
```

The project wraps this in `VertexEmbeddingProvider` at `app/services/embeddings/vertex_embedding_provider.py`. Access it via `get_embedding_provider()` rather than instantiating directly.

## Embed single text

```python
from app.services.embeddings import get_embedding_provider

provider = get_embedding_provider()
vector = await provider.embed("Some text to embed")  # list[float], 768 dims
```

## Embed batch

```python
vectors = await provider.embed_batch(["text A", "text B", "text C"])
# returns list[list[float]], one per input
```

## Raw LangChain call (if needed outside provider)

```python
# Sync (runs in executor for async contexts)
embeddings = embedder.embed_documents(["doc1", "doc2"])

# The provider wraps this in run_in_executor:
import asyncio
embeddings = await asyncio.get_event_loop().run_in_executor(
    None, embedder.embed_documents, texts
)
```

## Key facts

- Dimensions: **768** for `text-embedding-004` (hardcoded in pgvector column `vector(768)`)
- Batch limit: 250 texts per request (enforced in `VertexEmbeddingProvider`)
- Retry: 3 attempts with exponential back-off on `GoogleAPICallError`
- Mock: `MockEmbeddingProvider` returns deterministic unit-normalized 768-dim vectors — used automatically when `LLM_PROVIDER=mock`
