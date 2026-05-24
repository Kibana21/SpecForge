import asyncio

import pytest

from app.services.corpus_index import get_corpus_index_provider
from app.services.corpus_index.base import IndexedDoc
from app.services.corpus_index.mock_provider import MockCorpusIndexProvider
import uuid


def test_factory_returns_mock_when_llm_mock():
    # conftest sets LLM_PROVIDER=mock; corpus_index_provider defaults to "auto"
    provider = get_corpus_index_provider()
    assert isinstance(provider, MockCorpusIndexProvider)


def test_mock_build_index_produces_tree():
    provider = MockCorpusIndexProvider()
    data = ("Section one talks about payments. " * 80).encode("utf-8")
    tree = asyncio.run(provider.build_index(data=data, content_type="text/plain", filename="doc.txt"))
    assert tree.node_count >= 1
    assert tree.tree["nodes"], "expected at least one root node"
    assert tree.page_texts, "expected page text map"
    assert tree.model == "mock"


def test_mock_tree_search_returns_sections():
    provider = MockCorpusIndexProvider()
    data = ("alpha beta gamma " * 300).encode("utf-8")
    built = asyncio.run(provider.build_index(data=data, content_type="text/plain", filename="d.txt"))
    doc = IndexedDoc(document_id=uuid.uuid4(), doc_name="d.txt", tree=built.tree, page_texts=built.page_texts)
    sections = asyncio.run(provider.tree_search(query="what about beta?", docs=[doc], top_k=3))
    assert 1 <= len(sections) <= 3
    s = sections[0]
    assert s.node_id != "0000"  # synthetic root excluded
    assert s.text
    assert s.document_id == doc.document_id


def test_source_tree_search_returns_selections():
    from app.services.corpus_index.dspy_tree_search import run_tree_search

    result = asyncio.run(
        run_tree_search("payments", "[D0] 0001 · Intro — about payments", 3)
    )
    assert "selections" in result
    assert isinstance(result["selections"], list)
    for sel in result["selections"]:
        assert "doc" in sel and "node_id" in sel
