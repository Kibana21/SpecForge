import logging

from app.config import get_settings
from app.services.corpus_index.base import (
    CorpusIndexProvider,
    DocTree,
    IndexedDoc,
    RetrievedSection,
)

log = logging.getLogger(__name__)


def get_corpus_index_provider() -> CorpusIndexProvider:
    settings = get_settings()
    choice = settings.corpus_index_provider.lower()
    if choice == "auto":
        choice = "mock" if settings.llm_provider.lower() == "mock" else "pageindex"

    if choice == "mock":
        from app.services.corpus_index.mock_provider import MockCorpusIndexProvider
        return MockCorpusIndexProvider()
    if choice == "pageindex":
        from app.services.corpus_index.pageindex_provider import PageIndexProvider
        return PageIndexProvider()

    raise ValueError(f"Unknown CORPUS_INDEX_PROVIDER: {choice!r}. Valid: auto, mock, pageindex")


__all__ = [
    "CorpusIndexProvider",
    "DocTree",
    "IndexedDoc",
    "RetrievedSection",
    "get_corpus_index_provider",
]
