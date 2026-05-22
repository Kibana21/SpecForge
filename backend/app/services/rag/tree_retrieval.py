"""Reasoning (PageIndex) retrieval over an app's corpus trees — the hybrid
counterpart to the pgvector RAGRetrievalService."""
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.corpus import AppCorpusDoc, AppDocTree
from app.services.corpus_index import IndexedDoc, RetrievedSection, get_corpus_index_provider

log = logging.getLogger(__name__)


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
