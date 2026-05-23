"""DB-backed markdown conversion service.

Usage:
    svc = MarkdownConverterService(db, get_markdown_provider())
    md  = await svc.convert(raw_bytes, mime_type, filename, correlation_id=str(doc.id))

Cache strategy:
- First checks document_markdown by source_hash (content-level dedup — same PDF bytes
  uploaded to two different apps only hits the provider once).
- correlation_id is stored for traceability / per-entity lookup but is NOT the primary
  cache key, because the same entity can have its file replaced (new content, same id).
"""
import hashlib
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_markdown import DocumentMarkdown
from .base import MarkdownProvider

log = logging.getLogger(__name__)


class MarkdownConverterService:
    def __init__(self, db: AsyncSession, provider: MarkdownProvider) -> None:
        self._db = db
        self._provider = provider

    async def convert(
        self,
        content: bytes,
        mime_type: str,
        filename: str,
        correlation_id: str | None = None,
    ) -> str:
        source_hash = hashlib.sha256(content).hexdigest()

        # Content-level cache hit
        cached = await self._db.scalar(
            select(DocumentMarkdown)
            .where(DocumentMarkdown.source_hash == source_hash)
            .order_by(DocumentMarkdown.created_at.desc())
            .limit(1)
        )
        if cached:
            log.info(
                "markdown cache hit source_hash=%s correlation_id=%s",
                source_hash[:12], correlation_id,
            )
            return cached.markdown_text

        log.info(
            "markdown cache miss — calling provider=%s filename=%s",
            self._provider.name, filename,
        )
        markdown = await self._provider.convert(content, mime_type, filename)

        row = DocumentMarkdown(
            correlation_id=correlation_id,
            source_hash=source_hash,
            filename=filename,
            mime_type=mime_type,
            markdown_text=markdown,
            provider=self._provider.name,
        )
        self._db.add(row)
        await self._db.flush()
        log.info(
            "markdown stored id=%s provider=%s chars=%d",
            row.id, self._provider.name, len(markdown),
        )
        return markdown

    async def get_by_correlation_id(self, correlation_id: str) -> str | None:
        """Retrieve the most recent markdown for a given entity (corpus_doc.id, document.id, …)."""
        row = await self._db.scalar(
            select(DocumentMarkdown)
            .where(DocumentMarkdown.correlation_id == correlation_id)
            .order_by(DocumentMarkdown.created_at.desc())
            .limit(1)
        )
        return row.markdown_text if row else None
