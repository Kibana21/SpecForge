"""Project-level embedding upsert for similar-project discovery + app suggestion.

Kept on pgvector (embeddings) deliberately — PageIndex covers source retrieval,
embeddings cover short project/app similarity. Recomputed on create + RU validate.
"""
import logging
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.understanding import RequirementUnderstanding
from app.services.embeddings import get_embedding_provider

log = logging.getLogger(__name__)


def _project_text(project: Project, ru_objective: str | None) -> str:
    parts = [
        project.name,
        project.description or "",
        project.business_unit or "",
        project.app_scope or "",
        ru_objective or "",
    ]
    return "\n".join(p for p in parts if p).strip()


async def upsert_project_embedding(project_id: uuid.UUID, db: AsyncSession) -> bool:
    """Embed a project's identity text and upsert into project_embeddings.

    Returns True if an embedding was written. Best-effort: never raises into the
    caller's request path (logs and returns False on failure)."""
    project = await db.get(Project, project_id)
    if project is None:
        return False

    ru_objective = (
        await db.execute(
            select(RequirementUnderstanding.objective).where(
                RequirementUnderstanding.project_id == project_id
            )
        )
    ).scalar_one_or_none()

    body = _project_text(project, ru_objective)
    if not body:
        return False

    try:
        vec = await get_embedding_provider().embed(body)
    except Exception as exc:  # noqa: BLE001
        log.warning("project_embedding embed failed project_id=%s error=%s", project_id, exc)
        return False

    vec_str = "[" + ",".join(str(v) for v in vec) + "]"
    await db.execute(
        text(
            """
            INSERT INTO project_embeddings (project_id, embedding, updated_at)
            VALUES (:pid, CAST(:vec AS vector(768)), now())
            ON CONFLICT (project_id)
            DO UPDATE SET embedding = EXCLUDED.embedding, updated_at = now()
            """
        ),
        {"pid": str(project_id), "vec": vec_str},
    )
    await db.commit()
    return True
