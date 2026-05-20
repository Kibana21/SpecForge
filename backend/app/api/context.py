from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.rbac import get_current_user
from app.models.user import User
from app.schemas.envelope import ok

router = APIRouter(prefix="/api/context", tags=["context"])

# Routes accessible per role — hierarchical prefix matching
_ROLE_ROUTE_PREFIXES: dict[str, list[str]] = {
    "platform_admin": ["/"],           # all routes
    "compliance_reviewer": ["/", "/audit"],
    "business_analyst": ["/", "/projects"],
    "product_owner": ["/", "/projects"],
    "solution_architect": ["/", "/projects"],
    "app_owner": ["/", "/projects"],
    "qa_lead": ["/", "/projects"],
}


def _is_allowed(role: str, route: str) -> bool:
    prefixes = _ROLE_ROUTE_PREFIXES.get(role, [])
    # platform_admin gets "/" which matches everything
    for prefix in prefixes:
        if prefix == "/" or route == prefix or route.startswith(prefix + "/"):
            return True
    return False


@router.get("/resolve")
async def resolve_context(
    route: str = Query(..., description="Frontend route path, e.g. /projects/abc"),
    project_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    allowed = _is_allowed(current_user.role, route)
    result = "allowed" if allowed else "access_denied"
    return ok({
        "result": result,
        "fallback_route": "/" if not allowed else None,
        "user": {
            "id": str(current_user.id),
            "role": current_user.role,
            "display_name": current_user.display_name,
        },
        "project_id": project_id,
    })
