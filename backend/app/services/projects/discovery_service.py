"""App suggestion + similar-project discovery via pgvector cosine.

- suggest_apps: rank onboarded apps by best-matching app-brain chunk vs. the
  project's identity text (no avg() aggregate — uses MAX over per-chunk cosine,
  so it works on any pgvector version).
- find_similar_projects: cosine over project_embeddings, excluding self.
"""
import logging
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.app_scope import AppSuggestion, SimilarProject
from app.services.embeddings import get_embedding_provider

log = logging.getLogger(__name__)

_SUGGEST_THRESHOLD = 0.55
_SIMILAR_THRESHOLD = 0.50
_SIMILAR_LIMIT = 5


def _vec_str(vec: list[float]) -> str:
    return "[" + ",".join(str(v) for v in vec) + "]"


async def suggest_apps(query_text: str, db: AsyncSession) -> list[AppSuggestion]:
    """All onboarded apps, AI-suggestion flagged by similarity to query_text."""
    vec = await get_embedding_provider().embed(query_text)
    rows = (
        await db.execute(
            text(
                """
                SELECT a.id, a.name, a.short_name, a.description, a.tier,
                       a.domain_area, a.version, a.owner_id,
                       (SELECT count(*) FROM app_facts f
                          WHERE f.app_id = a.id AND f.status = 'active') AS fact_count,
                       (SELECT count(*) FROM app_corpus_docs d
                          WHERE d.app_id = a.id) AS corpus_doc_count,
                       sim.score
                FROM apps a
                LEFT JOIN (
                    SELECT cd.app_id,
                           MAX(1 - (ch.embedding <=> CAST(:vec AS vector(768)))) AS score
                    FROM app_chunks ch
                    JOIN app_corpus_docs cd ON cd.id = ch.doc_id
                    WHERE ch.embedding IS NOT NULL
                    GROUP BY cd.app_id
                ) sim ON sim.app_id = a.id
                WHERE a.is_onboarded = true
                ORDER BY sim.score DESC NULLS LAST, a.name ASC
                """
            ),
            {"vec": _vec_str(vec)},
        )
    ).mappings().all()

    out: list[AppSuggestion] = []
    for r in rows:
        score = r["score"]
        out.append(
            AppSuggestion(
                id=r["id"],
                name=r["name"],
                short_name=r["short_name"],
                description=r["description"],
                tier=r["tier"],
                domain_area=r["domain_area"],
                version=r["version"],
                owner_id=r["owner_id"],
                fact_count=r["fact_count"] or 0,
                corpus_doc_count=r["corpus_doc_count"] or 0,
                suggested=score is not None and score >= _SUGGEST_THRESHOLD,
                match_pct=round(score * 100) if score is not None else 0,
            )
        )
    return out


async def find_similar_projects(project_id: uuid.UUID, db: AsyncSession) -> list[SimilarProject]:
    """Top similar projects by project-embedding cosine (excludes self)."""
    rows = (
        await db.execute(
            text(
                """
                WITH self AS (
                    SELECT embedding FROM project_embeddings WHERE project_id = :pid
                )
                SELECT p.id, p.name, p.business_unit, p.status, p.updated_at,
                       1 - (pe.embedding <=> (SELECT embedding FROM self)) AS sim,
                       (SELECT array_agg(DISTINCT sv.spec_type)
                          FROM spec_versions sv WHERE sv.project_id = p.id) AS asset_tags
                FROM project_embeddings pe
                JOIN projects p ON p.id = pe.project_id
                WHERE pe.project_id != :pid
                  AND p.deleted_at IS NULL
                  AND EXISTS (SELECT 1 FROM self)
                ORDER BY sim DESC
                LIMIT :lim
                """
            ),
            {"pid": str(project_id), "lim": _SIMILAR_LIMIT},
        )
    ).mappings().all()

    out: list[SimilarProject] = []
    for r in rows:
        sim = r["sim"]
        if sim is None or sim < _SIMILAR_THRESHOLD:
            continue
        finalized_at = r["updated_at"] if r["status"] == "finalized" else None
        out.append(
            SimilarProject(
                source_project_id=r["id"],
                name=r["name"],
                business_unit=r["business_unit"],
                match_pct=round(sim * 100),
                finalized_at=finalized_at,
                asset_tags=[t for t in (r["asset_tags"] or []) if t],
            )
        )
    return out
