import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.embeddings import get_embedding_provider

log = logging.getLogger(__name__)

_SIMILARITY_THRESHOLD = 0.3


@dataclass
class RetrievedChunk:
    chunk_id: uuid.UUID
    doc_id: uuid.UUID
    doc_name: str
    chunk_no: int
    text: str
    similarity: float


_QUERY = text("""
    SELECT
        ac.id          AS chunk_id,
        ac.doc_id      AS doc_id,
        acd.name       AS doc_name,
        ac.chunk_no    AS chunk_no,
        ac.text        AS text,
        1 - (ac.embedding <=> CAST(:vec AS vector(768))) AS similarity
    FROM app_chunks ac
    JOIN app_corpus_docs acd ON acd.id = ac.doc_id
    WHERE acd.app_id = CAST(:app_id AS uuid)
      AND acd.index_status = 'done'
    ORDER BY ac.embedding <=> CAST(:vec AS vector(768))
    LIMIT :top_k
""")


class RAGRetrievalService:
    async def retrieve(
        self,
        app_id: uuid.UUID,
        question: str,
        top_k: int,
        db: AsyncSession,
    ) -> list[RetrievedChunk]:
        embedding = await get_embedding_provider().embed(question)
        vec_str = "[" + ",".join(str(v) for v in embedding) + "]"

        rows = await db.execute(
            _QUERY,
            {
                "vec": vec_str,
                "app_id": str(app_id),
                "top_k": top_k,
            },
        )
        results = rows.mappings().all()

        chunks = []
        for row in results:
            similarity = float(row["similarity"])
            if similarity < _SIMILARITY_THRESHOLD:
                continue
            chunks.append(
                RetrievedChunk(
                    chunk_id=row["chunk_id"],
                    doc_id=row["doc_id"],
                    doc_name=row["doc_name"],
                    chunk_no=row["chunk_no"],
                    text=row["text"],
                    similarity=similarity,
                )
            )

        log.info(
            "rag_retrieve app_id=%s question_len=%d top_k=%d returned=%d",
            app_id, len(question), top_k, len(chunks),
        )
        return chunks
