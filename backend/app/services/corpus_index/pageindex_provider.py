"""Self-hosted PageIndex corpus index, LLM calls via our Vertex/Gemini.

- build_index: PageIndex OSS builds a reasoning tree (LiteLLM → Vertex Gemini).
  PDF uses the native page path; other formats are bridged through our parser
  to Markdown. Per-page text is extracted with PyMuPDF for node-text fetching.
- tree_search: our Gemini (via the DSPy `dspy_tree_search` module) reasons over
  the in-scope trees' outline to select relevant node_ids, then we fetch their text.

NOTE: PageIndex + Vertex has no official example — validate via the T6 live spike
(`tests/test_pageindex_vertex.py`, opt-in). All heavy imports are lazy so this
module loads even when the package isn't installed (mock path stays usable).
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from app.config import get_settings
from app.services.corpus_index.base import (
    CorpusIndexProvider,
    DocTree,
    IndexedDoc,
    RetrievedSection,
    count_nodes,
    find_node,
    flatten_outline,
    node_text,
)

log = logging.getLogger(__name__)

_PDF_MIME = "application/pdf"
_PAGE_CHARS = 1500


def _configure_litellm() -> str:
    """Point LiteLLM (used internally by PageIndex) at our Vertex project/creds.

    Verified in the T6 spike: setting these module globals + GOOGLE_APPLICATION_CREDENTIALS
    is sufficient for PageIndex's `litellm.completion(model="vertex_ai/...")` calls.
    Returns the model id.
    """
    import os

    import litellm

    settings = get_settings()
    litellm.drop_params = True  # tolerate Gemini not supporting some OpenAI params
    litellm.vertex_project = settings.gemini_project_id
    litellm.vertex_location = settings.gemini_location
    if settings.google_service_account_path and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_service_account_path
    return settings.pageindex_model


def _normalize_tree(raw) -> dict:
    """Coerce PageIndex output into the canonical {"nodes": [...]} shape."""
    if isinstance(raw, list):
        return {"nodes": raw}
    if isinstance(raw, dict):
        if "nodes" in raw:
            return raw
        if "structure" in raw:
            return {"nodes": raw["structure"]}
        # a single root node
        return {"nodes": [raw]}
    return {"nodes": []}


def _pdf_page_texts(data: bytes) -> dict:
    import fitz  # PyMuPDF (already a dependency)

    out: dict[str, str] = {}
    doc = fitz.open(stream=data, filetype="pdf")
    try:
        for i, page in enumerate(doc):
            out[str(i + 1)] = page.get_text()
    finally:
        doc.close()
    return out


def _paginate(text: str) -> dict:
    pages = [text[i : i + _PAGE_CHARS] for i in range(0, len(text), _PAGE_CHARS)] or [text]
    return {str(i + 1): p for i, p in enumerate(pages)}


def _fallback_tree(page_texts: dict, filename: str) -> dict:
    """One node per page when PageIndex detects no structure (heading-less text)."""
    nodes = []
    for i, page in enumerate(sorted(page_texts.keys(), key=int), start=1):
        body = (page_texts[page] or "").strip()
        if not body:
            continue
        nodes.append({
            "node_id": f"{i:04d}",
            "title": f"{filename} — part {i}",
            "summary": body[:160].replace("\n", " ").strip(),
            "start_index": int(page),
            "end_index": int(page),
            "nodes": [],
        })
    return {"nodes": nodes}


def _run_pageindex(file_path: str, *, is_markdown: bool, model: str) -> dict:
    """Invoke the vendored PageIndex OSS tree builder (verified API).

    PDF  → page_index_main(path, opt)  (sync)
    MD   → md_to_tree(...)             (async)
    Both return a dict with a "structure" list of nodes (title, node_id,
    start_index, end_index, summary, [nodes]).
    """
    try:
        from vendor.pageindex.page_index import page_index_main
        from vendor.pageindex.utils import ConfigLoader
    except ImportError as exc:  # pragma: no cover - install/vendor issue
        raise RuntimeError(
            "Vendored PageIndex not importable. Ensure backend/vendor/pageindex exists and "
            "litellm + PyPDF2 + pyyaml are installed (or set CORPUS_INDEX_PROVIDER=mock)."
        ) from exc

    if is_markdown:
        import asyncio

        from vendor.pageindex.page_index_md import md_to_tree

        return asyncio.run(
            md_to_tree(
                md_path=file_path,
                if_add_node_summary=True,
                model=model,
                if_add_node_text=False,
                if_add_node_id=True,
            )
        )

    opt = ConfigLoader().load(
        {"model": model, "if_add_node_summary": "yes", "if_add_node_text": "no", "if_add_node_id": "yes"}
    )
    return page_index_main(file_path, opt)


class PageIndexProvider(CorpusIndexProvider):
    async def build_index(self, *, data: bytes, content_type: str, filename: str) -> DocTree:
        import asyncio

        model = _configure_litellm()
        is_pdf = content_type == _PDF_MIME or filename.lower().endswith(".pdf")

        if is_pdf:
            page_texts = _pdf_page_texts(data)
            suffix = ".pdf"
            payload = data
            is_md = False
        else:
            # Bridge non-PDF → Markdown via our existing parser.
            from app.services.documents.parser import parse

            text = parse(data, content_type) or ""
            page_texts = _paginate(text)
            payload = text.encode("utf-8")
            suffix = ".md"
            is_md = True

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(payload)
            tmp_path = tmp.name
        try:
            raw = await asyncio.get_event_loop().run_in_executor(
                None, lambda: _run_pageindex(tmp_path, is_markdown=is_md, model=model)
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        tree = _normalize_tree(raw)
        # PageIndex builds nodes from document STRUCTURE: a PDF's table-of-contents /
        # section page-ranges, or a markdown file's `#` headings. Heading-less plain
        # text yields 0 nodes — synthesize page-spanning nodes so the doc stays
        # retrievable (important for E2 sources, which have no vector fallback).
        if count_nodes(tree) == 0 and page_texts:
            tree = _fallback_tree(page_texts, filename)
            log.info("pageindex_fallback filename=%s nodes=%d (no structure detected)", filename, count_nodes(tree))

        log.info("pageindex_built filename=%s pdf=%s nodes=%d", filename, is_pdf, count_nodes(tree))
        return DocTree(tree=tree, page_texts=page_texts, node_count=count_nodes(tree), model=model)

    async def tree_search(
        self, *, query: str, docs: list[IndexedDoc], top_k: int
    ) -> list[RetrievedSection]:
        if not docs:
            return []

        from app.services.corpus_index.dspy_tree_search import run_tree_search

        outline = flatten_outline(docs)
        doc_index = {f"D{i}": d for i, d in enumerate(docs)}

        result = await run_tree_search(query, outline, top_k)
        selections = result.get("selections", []) if isinstance(result, dict) else []

        out: list[RetrievedSection] = []
        for sel in selections[:top_k]:
            doc = _resolve_doc(sel, doc_index, docs)
            if doc is None:
                continue
            node = find_node(doc.tree, str(sel.get("node_id")))
            if node is None:
                continue
            out.append(
                RetrievedSection(
                    document_id=doc.document_id,
                    doc_name=doc.doc_name,
                    node_id=str(node.get("node_id")),
                    title=node.get("title", ""),
                    page_start=int(node.get("start_index", 1)),
                    page_end=int(node.get("end_index", 1)),
                    text=node_text(node, doc.page_texts),
                    reason=str(sel.get("reason", "")),
                )
            )
        return out


def _resolve_doc(sel: dict, doc_index: dict, docs: list[IndexedDoc]) -> IndexedDoc | None:
    # The skill may return either a doc alias (D0) or a document_id.
    alias = sel.get("doc")
    if alias and alias in doc_index:
        return doc_index[alias]
    did = sel.get("document_id")
    if did:
        for d in docs:
            if str(d.document_id) == str(did):
                return d
    return None
