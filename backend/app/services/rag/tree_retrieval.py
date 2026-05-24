"""Reasoning (PageIndex) retrieval over an app's corpus trees — the hybrid
counterpart to the pgvector RAGRetrievalService."""
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.corpus import AppCorpusDoc, AppDocTree
from app.services.corpus_index import IndexedDoc, RetrievedSection, get_corpus_index_provider
from app.services.corpus_index.base import find_node, node_text

log = logging.getLogger(__name__)


async def get_sections_by_refs(
    app_id: uuid.UUID, refs: list[dict], db: AsyncSession
) -> list[RetrievedSection]:
    """Resolve [{doc_id, node_id}] refs into RetrievedSections by drilling the
    app's PageIndex trees — the 'get_tree_sections' tool for Deep Search.

    Loads each referenced doc's tree once, finds the node, and reconstructs its
    text from page_texts. Skips refs whose doc/node no longer exist.
    """
    wanted_doc_ids = {str(r.get("doc_id")) for r in refs if r.get("doc_id")}
    if not wanted_doc_ids:
        return []

    rows = (await db.execute(
        select(AppDocTree, AppCorpusDoc.name)
        .join(AppCorpusDoc, AppCorpusDoc.id == AppDocTree.corpus_doc_id)
        .where(AppDocTree.app_id == app_id)
    )).all()
    trees = {
        str(tree.corpus_doc_id): (tree.tree_json, tree.page_texts, name)
        for tree, name in rows
    }

    sections: list[RetrievedSection] = []
    seen: set[tuple[str, str]] = set()
    for ref in refs:
        doc_id = str(ref.get("doc_id"))
        node_id = str(ref.get("node_id"))
        key = (doc_id, node_id)
        if key in seen or doc_id not in trees:
            continue
        seen.add(key)
        tree_json, page_texts, doc_name = trees[doc_id]
        node = find_node(tree_json, node_id)
        if node is None:
            continue
        text = node_text(node, page_texts)
        if not text:
            continue
        sections.append(RetrievedSection(
            document_id=uuid.UUID(doc_id),
            doc_name=doc_name,
            node_id=node_id,
            title=(node.get("title") or "").strip(),
            page_start=int(node.get("start_index") or 0),
            page_end=int(node.get("end_index") or 0),
            text=text,
            reason="",
        ))
    return sections


async def retrieve_app_sections(
    app_id: uuid.UUID, question: str, top_k: int, db: AsyncSession
) -> list[RetrievedSection]:
    """LLM tree-search over the app's PageIndex trees. Returns [] if the app has
    no trees (e.g. ingested before hybrid was enabled)."""
    rows = (
        await db.execute(
            select(AppDocTree, AppCorpusDoc.name)
            .join(AppCorpusDoc, AppCorpusDoc.id == AppDocTree.corpus_doc_id)
            .where(AppDocTree.app_id == app_id)
        )
    ).all()
    if not rows:
        return []

    docs = [
        IndexedDoc(
            document_id=tree.corpus_doc_id,
            doc_name=name,
            tree=tree.tree_json,
            page_texts=tree.page_texts,
        )
        for tree, name in rows
    ]
    sections = await get_corpus_index_provider().tree_search(
        query=question, docs=docs, top_k=top_k
    )
    log.info("tree_retrieve app_id=%s docs=%d sections=%d", app_id, len(docs), len(sections))
    return sections
