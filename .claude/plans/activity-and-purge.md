# Per-Artifact Activity + Test-Data Purge (Workstream 2)

## Context

Every action in SpecForge is audited, and the admin **Audit Log** (`/audit`) exists — but it's locked to `platform_admin` + `compliance_reviewer` (it exposes IPs/security events). Project owners and app owners have **no scoped activity view** of their own artifacts. `recent_activity` is already computed in `get_project` but is **never rendered**. This workstream adds member-accessible activity views, and cleans up leftover test apps.

**Confirmed decision:** use **new member-accessible scoped endpoints**, NOT the admin audit API.

## Verified facts to reuse
- Audit serialization is reusable: `app/services/audit/catalog.py::classify` (event → label/category/severity) + `app/api/audit.py` actor-resolution (`_resolve_actors`, `_actor_name`). Extract to a shared helper.
- App audit events store the app id in **`ai_meta["app_id"]`** (no `app_key` column populated) → app activity filters on JSONB.
- Access deps exist: `require_project_access` (404-safe) in `app/api/deps.py`; `require_app_access` in `app/api/apps.py`.
- Frontend: `ActivityItem` type exists; `lib/audit.SEVERITY_VARIANT` for badges; app detail `SECTIONS` list in `app/apps/[id]/page.tsx`.

## 2A. Shared serialization (backend)
Extract into `app/services/audit/serialize.py`: `resolve_actors(db, rows)` + `serialize_event(row, actors)` (label/category/severity via `catalog.classify`). Reuse in `audit.py` + the new activity endpoints (DRY).

## 2B. Scoped activity endpoints (member-accessible)
- `GET /api/projects/{project_id}/activity` — `Depends(require_project_access)`, `AuditEvent.project_id == id`, ts-desc, paginated `ok(items, meta={total,limit,offset})`, serialized.
- `GET /api/apps/{app_id}/activity` — `Depends(require_app_access)`, filter `AuditEvent.ai_meta["app_id"].astext == str(app_id)`, serialized + paginated.

## 2C. Activity UI (frontend)
- `lib/hooks/useActivity.ts` (`useProjectActivity(id)`, `useAppActivity(id)`); `api.projects.activity` / `api.apps.activity`.
- `app/components/ActivityFeed.tsx` — compact event rows (severity badge + actor + ts), paginated.
- **Project:** add an "Activity" view to the workspace (a stage-rail entry / tab). **App:** add `{key:'activity', label:'Activity', icon: History}` to `SECTIONS` + a render branch in `app/apps/[id]/page.tsx`.

## 2D. Purge leftover test apps
Re-run `backend/scripts/purge_test_data.py --apply` (deletes hex-suffixed test apps `^(hyb|prc|pay|clm|sg)[0-9a-f]{8}$`; keeps PRJ-0001 + clean-named apps; idempotent, dry-run by default). **Destructive → confirm with user at execution time.**

## 2E. Tests (backend)
`tests/test_activity_api.py`: project member sees their project's activity (200, paginated, serialized); non-member → 404; app owner sees app activity (filtered by `ai_meta.app_id`).

## Files
**Create:** `app/services/audit/serialize.py`, `frontend/lib/hooks/useActivity.ts`, `frontend/app/components/ActivityFeed.tsx`, `tests/test_activity_api.py`.
**Modify:** `app/api/{audit,projects,apps}.py`, `frontend/lib/api.ts`, `frontend/app/apps/[id]/page.tsx`, `frontend/app/projects/[id]/page.tsx`.

## Verification
1. `cd backend && ./.venv/bin/python -m pytest tests/test_activity_api.py -q` then full suite.
2. UI: open a project → **Activity** lists real events (actor + badge); open an app → **Activity** section lists app events. Confirm a non-member gets 404 on `/projects/{id}/activity`.
3. Run the purge (confirmed) → registry shows only real apps.
