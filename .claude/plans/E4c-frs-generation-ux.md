# E4c · Part 3 — FRS Stage B Generation UX · Implementation Plan

> **Companion to** `.claude/plans/E4c-frs-functional-design.md` (Stage B plan).
> This plan fixes three UX problems discovered after Stage B shipped:
> (1) blank screen during generation with no live feedback,
> (2) no one-click "design all modules" flow after Stage A,
> (3) the Regenerate button is buried and hard to find.

---

## 1. Problem statement (exact symptoms)

### Problem 1 — Blank screen after "Regenerate"

When the user clicks any module-level regenerate action, the API dispatches a
Celery task and returns immediately. The frontend shows a toast ("Module design
queued") and then **nothing changes visually** until Celery finishes — which can
be 2–10 minutes for a real module. The user has no idea whether the system is
working or stuck.

Root cause: `unit_status` for a module (`design_mod_<key>`) is only written
**after all specs for that module are done** (frs_orchestrator.py:1372-1387).
During the run, the only signal available is `_current_unit` being set, which
makes the module rail show a spinner — but the main content panel (the big area
on the right) has zero progress state.

### Problem 2 — No one-click "design all" after Stage A

After Stage A validates, the user sees `FrsContinueStageBBanner` — a floating
bottom banner. It dispatches one Celery task per module from the frontend loop
(`handleContinueStageB`). Problems:
- The banner is dismissible and doesn't come back (sessionStorage)
- It dispatches N independent Celery tasks, not the coordinated
  `asyncio.Semaphore(3)` pattern from `generate_frs_all`
- If the user dismisses the banner or navigates away, there's no recovery CTA
- After partial completion, there's no "design remaining" affordance

### Problem 3 — Regenerate button is buried

The regenerate action is inside `FrsModuleIdentityCard`, which is inside
`FrsModulePanel`, which is scrolled. There is no top-of-panel affordance and no
rail-level quick action.

---

## 2. What's already built (reuse inventory)

| Existing piece | Reuse strategy |
|---|---|
| `generate_frs_all(run_stage_b=True)` in orchestrator | Already has Semaphore(3) parallel pattern + context gathered once — just needs a backend endpoint to expose it cleanly |
| `regenerate_frs_module` Celery task | Already exists and works — reused for single-module regen |
| `unit_status._current_unit` | Already set at start of each module design — SWR already polls every 2s when set |
| `FrsTwoPhaseGenerationViz` | Already shows per-module bars — extend to support sequential pause points |
| `FrsModuleRail` hover pattern | Already has hover state per module row — add a regen icon button |
| `_set_current_unit` helper | Already exists in orchestrator — pattern to copy for per-spec progress |

**Net new backend**: 1 endpoint, 1 Celery task, 1 small helper for per-spec progress.
**Net new frontend**: 2 new components (`FrsStageActionBar`, `FrsModuleGeneratingOverlay`),
extensions to `FrsBuilderView`, `FrsModuleRail`, `FrsTwoPhaseGenerationViz`.

---

## 3. Architecture decisions

### Decision A — Context gathering per "design all" call

**Chosen**: `POST /frs/design-all-modules` calls a new Celery task
`design_all_frs_modules` that calls `generate_frs_all(run_stage_b=True,
skip_designed=True)`. Context is gathered **once** inside that task, then shared
across all module coroutines via the `bundle` object — exactly as the existing
`generate_frs_all` works.

**Why not dispatch N individual tasks from the frontend** (the current
`handleContinueStageB` approach): Each individual task re-gathers the full
context bundle independently (~1–2s of DB queries per task). With 5 modules that's
5 redundant bundle builds. The `generate_frs_all` pattern gathers it once and
passes the same in-memory object to all coroutines — cheaper and consistent.

**Why not just set `run_stage_b=True` on the existing `/generate` endpoint**:
That endpoint re-runs Stage A (full modularize pass) before Stage B. We need a
path that runs Stage B only, optionally skipping already-designed modules.

### Decision B — Per-spec progress signal

**Chosen**: Write an intermediate `unit_status` patch after each spec completes
within a module's loop. The patch key is `design_mod_<module_key>` and adds
`current_spec_key`, `specs_done`, `specs_total`. This piggybacks on the existing
atomic JSONB merge pattern — no schema change.

**Why not track section-level progress** (§1 UI, §2 Backend, etc.): DSPy returns
the full spec in one shot — there's no per-section streaming. The per-spec
granularity (spec N of M) is the finest real signal available.

### Decision C — Sequential mode lives entirely in the frontend

**Chosen**: Sequential mode dispatches one module at a time from the frontend
state machine. It polls `unit_status.design_mod_<key>` until `specs_done ===
specs_total` (or `completeness > 0`), then dispatches the next module and shows
a pause card. No backend change needed.

**Why not a backend sequential mode**: The frontend can achieve the same effect
by gating each dispatch on the previous module completing. This gives the user
the natural pause point to review — which is the whole point of sequential mode.

### Decision D — "Design remaining" skips already-designed modules

`generate_frs_all` gains a `skip_designed: bool = False` parameter. When True,
modules where `unit_status` already contains a `design_mod_<key>` entry with
`completeness > 0` are skipped. This makes the "design all" endpoint idempotent
and safe to re-invoke after partial completion.

---

## 4. Backend implementation

### 4.1 Per-spec progress signal — `frs_orchestrator.py` (EXTEND)

**File**: `backend/app/services/artifacts/frs_orchestrator.py`

Inside `generate_frs_design_module`, the per-spec for-loop currently:
```
for sk in stub_keys:
    LLM call → spec_out
    _persist_design_module_result(...)
    db.commit()
```

After each `db.commit()`, add an intermediate `unit_status` merge:

```python
# After commit of each spec — write live progress so frontend can show "spec N of M"
specs_done_count = len(designed_specs)
await db.execute(sa_text(
    "UPDATE artifact_documents "
    "SET unit_status = COALESCE(unit_status, '{}'::jsonb) || CAST(:patch AS jsonb), "
    "    updated_at = NOW() "
    "WHERE id = :doc_id"
), {
    "patch": json.dumps({
        f"design_mod_{module_row_key}": {
            "current_spec_key": sk,
            "specs_done": specs_done_count,
            "specs_total": len(stub_keys),
            # completeness stays 0 until all done — set at the end (unchanged)
        },
    }),
    "doc_id": str(doc.id),
})
await db.commit()
```

This merge is additive (JSONB `||` operator). It does not overwrite the final
`completeness`/`confidence` keys written at the end of the loop — those are a
superset and will overwrite this intermediate entry when the module finishes.

> **Location in file**: Insert after the existing `await db.commit()` on line
> 1342, before the `continue` guard. The pattern is the same JSONB merge already
> used on lines 1372-1387.

### 4.2 `skip_designed` parameter — `generate_frs_all` (EXTEND)

**File**: `backend/app/services/artifacts/frs_orchestrator.py`

```python
async def generate_frs_all(
    project: Project,
    db: AsyncSession,
    *,
    brief: str | None = None,
    run_stage_b: bool = False,
    skip_designed: bool = False,     # NEW
    max_parallel_modules: int = 3,
) -> dict:
```

In the Stage B section (currently lines 1722-1757):

```python
if run_stage_b:
    modules = (await db.execute(
        select(FrsModule).where(
            FrsModule.document_id == doc.id,
            FrsModule.is_current.is_(True),
            FrsModule.status == "active",
        )
    )).scalars().all()

    if skip_designed:
        current_us = (doc.unit_status or {})
        module_keys = [
            m.row_key for m in modules
            if not (current_us.get(f"design_mod_{m.row_key}") or {}).get("completeness")
        ]
    else:
        module_keys = [m.row_key for m in modules]

    # ... rest unchanged (asyncio.gather + Semaphore)
```

### 4.3 New orchestrator function — `run_frs_stage_b` (NEW)

**File**: `backend/app/services/artifacts/frs_orchestrator.py`

A dedicated entry point for "design all modules, optionally skipping designed ones",
without re-running Stage A:

```python
async def run_frs_stage_b(
    project: Project,
    db: AsyncSession,
    *,
    skip_designed: bool = True,
    max_parallel_modules: int = 3,
) -> dict:
    """Run Stage B per-module design without re-running Stage A.

    skip_designed=True (default): modules with completeness > 0 are skipped,
    making this safe to call after partial completion.
    """
    doc = await _ensure_frs_document(project.id, db)

    bundle = await gather_project_context(
        project.id, db,
        artifact_document_id=doc.id,
        artifact_type="frs",
    )

    if not bundle.readiness.can_generate:
        raise RuntimeError(
            f"FRS generation blocked: {bundle.readiness.blocking_reason}"
        )

    # Mark generating
    current_us = doc.unit_status or {}
    await db.execute(sa_text(
        "UPDATE artifact_documents "
        "SET status = 'generating', unit_status = CAST(:us AS jsonb), updated_at = NOW() "
        "WHERE id = :doc_id"
    ), {"us": json.dumps(current_us), "doc_id": str(doc.id)})
    await db.commit()

    # Load modules
    modules = (await db.execute(
        select(FrsModule).where(
            FrsModule.document_id == doc.id,
            FrsModule.is_current.is_(True),
            FrsModule.status == "active",
        )
    )).scalars().all()

    if skip_designed:
        module_keys = [
            m.row_key for m in modules
            if not (current_us.get(f"design_mod_{m.row_key}") or {}).get("completeness")
        ]
    else:
        module_keys = [m.row_key for m in modules]

    if not module_keys:
        # All already designed — just flip status back
        async with AsyncSessionLocal() as fin_db:
            fin_doc = await fin_db.get(ArtifactDocument, doc.id)
            fin_doc.status = "in_interview"
            await fin_db.commit()
        return await get_frs_detail(project.id, db)

    sem = asyncio.Semaphore(max_parallel_modules)

    async def _design_one(mod_row_key: str) -> None:
        async with sem:
            async with AsyncSessionLocal() as unit_db:
                unit_doc = await unit_db.get(ArtifactDocument, doc.id)
                if unit_doc is None:
                    return
                try:
                    await generate_frs_design_module(
                        project, mod_row_key, unit_doc, bundle, unit_db,
                    )
                    await unit_db.commit()
                except Exception:
                    log.exception(
                        "run_frs_stage_b.module_failed",
                        extra={"doc_id": str(doc.id), "module_row_key": mod_row_key},
                    )
                    await unit_db.rollback()

    await asyncio.gather(*[_design_one(mk) for mk in module_keys])

    # Finalize
    async with AsyncSessionLocal() as fin_db:
        fin_doc = await fin_db.get(ArtifactDocument, doc.id)
        if fin_doc:
            fin_doc.status = "in_interview"
            await fin_db.commit()

    return await get_frs_detail(project.id, db)
```

### 4.4 New Celery task — `design_all_frs_modules` (NEW)

**File**: `backend/workers/tasks.py`

```python
@celery_app.task(
    name="workers.tasks.design_all_frs_modules",
    bind=True,
    max_retries=1,
    default_retry_delay=30,
    time_limit=3600,  # up to 1 hour for a large project
)
def design_all_frs_modules(
    self, project_id: str, skip_designed: bool = True,
) -> dict:
    """Design all (or remaining) FRS modules in parallel (Semaphore=3).

    skip_designed=True: modules with completeness > 0 are skipped.
    Used by the "Design All Specs" and "Design Remaining" CTAs.
    """
    return _run_async(_design_all_frs_modules(project_id, skip_designed))


async def _design_all_frs_modules(
    project_id: str, skip_designed: bool,
) -> dict:
    from app.db import AsyncSessionLocal
    from app.models.project import Project
    from app.services.artifacts.frs_orchestrator import run_frs_stage_b

    async with AsyncSessionLocal() as db:
        project = await db.get(Project, UUID(project_id))
        if project is None:
            log.error("design_all_frs_modules project_id=%s not found", project_id)
            return {"ok": False, "error": "project_not_found"}
        try:
            result = await run_frs_stage_b(project, db, skip_designed=skip_designed)
            return {"ok": True, **result}
        except Exception:
            log.exception(
                "design_all_frs_modules failed project_id=%s", project_id,
            )
            # Reset status so the UI doesn't get stuck
            from sqlalchemy import select
            from app.models.artifact import ArtifactDocument
            doc = (await db.execute(
                select(ArtifactDocument).where(
                    ArtifactDocument.project_id == UUID(project_id),
                    ArtifactDocument.artifact_type == "frs",
                )
            )).scalar_one_or_none()
            if doc:
                doc.status = "in_interview"
                await db.commit()
            return {"ok": False, "error": "design_all_failed"}
```

Also register in `workers/dispatch.py` — add `design_all_frs_modules` to the import list.

### 4.5 New API endpoint — `POST /frs/design-all-modules` (NEW)

**File**: `backend/app/api/frs.py`

```python
class _FrsDesignAllIn(BaseModel):
    skip_designed: bool = True


@router.post("/projects/{project_id}/artifacts/frs/design-all-modules")
async def design_all_frs_modules_endpoint(
    project_id: UUID,
    body: _FrsDesignAllIn = Body(default_factory=_FrsDesignAllIn),
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger Stage B design for all (or remaining) modules.

    skip_designed=True (default): modules with completeness > 0 are left alone.
    In mock mode runs in-process. In production dispatches to Celery.
    """
    from app.config import get_settings
    from app.services.artifacts.frs_orchestrator import (
        run_frs_stage_b, get_frs_detail, _ensure_frs_document,
    )

    settings = get_settings()
    if settings.llm_provider == "mock":
        doc = await _ensure_frs_document(project_id, db)
        result = await run_frs_stage_b(project, db, skip_designed=body.skip_designed)
        return ok(result)

    # Production: mark generating, dispatch Celery task
    doc = await _ensure_frs_document(project_id, db)
    # Preserve current unit_status (don't reset it — skip_designed reads it)
    doc.status = "generating"
    await db.commit()

    from workers.dispatch import dispatch
    from workers.tasks import design_all_frs_modules
    dispatch(design_all_frs_modules, str(project_id), body.skip_designed)

    return ok(await get_frs_detail(project_id, db))
```

### 4.6 Backend summary

| File | Change | Description |
|---|---|---|
| `frs_orchestrator.py` | extend | Per-spec progress patch in `generate_frs_design_module` loop |
| `frs_orchestrator.py` | extend | `skip_designed` param on `generate_frs_all` |
| `frs_orchestrator.py` | new function | `run_frs_stage_b` — Stage B only, no Stage A re-run |
| `workers/tasks.py` | new task | `design_all_frs_modules` + `_design_all_frs_modules` |
| `workers/dispatch.py` | extend | Register `design_all_frs_modules` |
| `app/api/frs.py` | new route | `POST /frs/design-all-modules` |

**No new models. No new migrations. No schema changes.**

---

## 5. Frontend implementation

### 5.1 API client — `frontend/lib/api.ts` (EXTEND)

Add one new method on `api.frs`:

```ts
api.frs.designAllModules = (
  projectId: string,
  skipDesigned = true,
) =>
  apiFetch(`/api/projects/${projectId}/artifacts/frs/design-all-modules`, {
    method: 'POST',
    body: JSON.stringify({ skip_designed: skipDesigned }),
  })
```

### 5.2 Types — `frontend/lib/types.ts` (EXTEND)

Extend the `unit_status` shape for the per-spec progress key:

```ts
// Already exists implicitly via Record<string, unknown>.
// Add explicit helper type for design_mod_<key> values:
export interface FrsModuleDesignProgress {
  completeness?: number        // 0 until all specs done, then final score
  confidence?: string
  spec_count?: number          // final: how many specs were designed
  current_spec_key?: string    // live: which spec is being designed right now
  specs_done?: number          // live: how many specs completed so far
  specs_total?: number         // live: total stubs in this module
}
```

### 5.3 `FrsStageActionBar` — NEW component

**File**: `frontend/app/components/frs/FrsStageActionBar.tsx`

This replaces `FrsContinueStageBBanner` (which was a floating bottom element,
easy to dismiss, doesn't return). `FrsStageActionBar` is an **inline** strip
rendered at the top of the content area — always visible while specs are pending.

Three states:

**State 1 — All modules undesigned (fresh Stage A approval)**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ✦ Stage 2 ready · 5 modules · 18 specs to design                           │
│                                                                             │
│  [⚡ Design All — parallel]   [▶ Design one by one]                          │
│                                                                             │
│  Parallel: all 5 modules at once (fastest, ~5–12 min)                      │
│  Sequential: design one module, review it, then continue                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

**State 2 — Partial completion (some modules done, some not)**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ◐ 3 of 5 modules designed · 2 still pending                                │
│  [Design Remaining]   [Design All from scratch]                   [×]       │
└─────────────────────────────────────────────────────────────────────────────┘
```

**State 3 — All designed (show nothing; component unmounts)**

```tsx
'use client'
import { useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { Layers, Play, Zap, X } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import type { FrsModuleHydrated } from '@/lib/types'

interface Props {
  projectId: string
  modules: FrsModuleHydrated[]
  unitStatus: Record<string, unknown> | null | undefined
  stageAApproved: boolean
  docStatus: string | null
  onDesignAll: (sequential: boolean) => void   // triggers FrsTwoPhaseGenerationViz
  onMutate: () => void
}

export function FrsStageActionBar({
  projectId, modules, unitStatus, stageAApproved, docStatus, onDesignAll, onMutate,
}: Props) {
  // ...
}
```

**Dismissibility**: The bar is never permanently dismissible. It disappears
naturally when all modules have `completeness > 0` in `unit_status`. The `×`
dismiss on the partial-state variant hides it for the current session only
(sessionStorage key `frs-action-bar-dismissed-{projectId}`), but it reappears
on next page load.

**Props logic**:

```ts
const moduleDesignKeys = modules.map(m => `design_mod_${m.row_key}`)
const designedCount = moduleDesignKeys.filter(k =>
  ((unitStatus?.[k] as any)?.completeness ?? 0) > 0
).length
const totalCount = modules.length
const pendingCount = totalCount - designedCount
const allDesigned = pendingCount === 0
const noneDesigned = designedCount === 0
```

If `allDesigned` or `!stageAApproved` or `docStatus === 'validated'` → return null.

**Actions**:

```ts
async function handleDesignAll(skipDesigned: boolean) {
  try {
    await api.frs.designAllModules(projectId, skipDesigned)
    // switch to FrsTwoPhaseGenerationViz via onDesignAll(false)
    onDesignAll(false)
  } catch (e) {
    toast.error(e instanceof Error ? e.message : 'Failed to start generation')
  }
}

function handleSequential() {
  onDesignAll(true)  // parent switches to sequential state machine
}
```

### 5.4 `FrsModuleGeneratingOverlay` — NEW component

**File**: `frontend/app/components/frs/FrsModuleGeneratingOverlay.tsx`

Shown **inside the module panel content area** when `_current_unit ===
design_mod_<activeModuleKey>`. Replaces the blank wait.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Designing specs for MOD-001 · User Onboarding                              │
│                                                                             │
│  ▰▰▰▰▰▱▱▱▱▱  1 of 3 specs complete                                          │
│                                                                             │
│  Currently writing                                                          │
│  M001-FRS002 · Login & Session Management                                   │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────────  │
│  ✓  M001-FRS001  User Registration            complete                      │
│  ◐  M001-FRS002  Login & Session Management   designing…      ← pulsing     │
│  ○  M001-FRS003  Registration Wizard          queued                        │
│                                                                             │
│  This can take 1–3 min per spec. The page updates as each spec completes.  │
└─────────────────────────────────────────────────────────────────────────────┘
```

Data sources:
- `progress.current_spec_key` → highlight the active row
- `progress.specs_done` / `progress.specs_total` → progress bar + counter
- `module.backlog` → the spec list (known upfront from Stage A stubs)
- `spec.completeness > 0` → which stubs are already done (survive refresh)

```tsx
interface Props {
  module: FrsModuleHydrated
  progress: FrsModuleDesignProgress  // from unit_status[design_mod_<key>]
  onCancel?: () => void
}
```

The spec list shows each stub row with one of three states:
- `completeness > 0` → `<CheckCircle2>` green (fetched from fresh SWR data)
- `row_key === current_spec_key` → `<Loader2 className="animate-spin">` blue + row highlighted
- otherwise → `<Circle>` gray "queued"

The progress bar uses the segmented `▰▱` pattern from `FrsTwoPhaseGenerationViz`
(10 segments, width = `specs_done / specs_total * 10` filled).

**Animation**: The active row pulses with a subtle amber background every 2s
(CSS `@keyframes frs-spec-pulse`). All animations gated by `useReducedMotion()`.

### 5.5 `FrsBuilderView.tsx` — EXTEND (state machine + wiring)

**File**: `frontend/app/components/frs/FrsBuilderView.tsx`

#### New state variables

```ts
const [stageBMode, setStageBMode] = useState<'parallel' | 'sequential' | null>(null)
const [sequentialIndex, setSequentialIndex] = useState(0)   // which module we're on
const [seqPaused, setSeqPaused] = useState(false)           // paused between modules
```

#### Remove `stageBRunning` boolean → replace with `stageBMode`

Old: `stageBRunning: boolean` → shows `FrsTwoPhaseGenerationViz` while true.
New: `stageBMode: 'parallel' | 'sequential' | null` → same guard but richer.

#### New `handleDesignAll` (replaces `handleContinueStageB`)

```ts
async function handleDesignAll(sequential: boolean) {
  setBannerDismissed(true)
  if (sequential) {
    // Sequential mode: set up state machine, dispatch first module
    setStageBMode('sequential')
    setSequentialIndex(0)
    setSeqPaused(false)
    const firstUndesigned = modules.find(m =>
      !((doc?.unit_status?.[`design_mod_${m.row_key}`] as any)?.completeness)
    )
    if (!firstUndesigned) return
    try {
      await api.frs.designModule(projectId, firstUndesigned.row_key)
      await mutate()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to start generation')
      setStageBMode(null)
    }
  } else {
    // Parallel mode: single backend call, Semaphore(3) handles concurrency
    setStageBMode('parallel')
    try {
      await api.frs.designAllModules(projectId, true)
      await mutate()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to start generation')
      setStageBMode(null)
    }
  }
}
```

#### Sequential mode state machine

```ts
// Watch unit_status to detect when current sequential module finishes
useEffect(() => {
  if (stageBMode !== 'sequential' || seqPaused) return

  const undesigned = modules.filter(m =>
    !((doc?.unit_status?.[`design_mod_${m.row_key}`] as any)?.completeness)
  )
  const currentUnit = doc?.unit_status?.['_current_unit'] as string | undefined

  // The module we dispatched has finished (no longer _current_unit) AND
  // the undesigned count decreased → advance state
  if (!currentUnit && undesigned.length < modules.length - sequentialIndex) {
    // One more module done — pause and let user review
    setSeqPaused(true)
  }
}, [doc?.unit_status, stageBMode, seqPaused, sequentialIndex, modules])
```

In render: when `stageBMode === 'sequential'`:
- If `seqPaused` → show `FrsTwoPhaseGenerationViz` with a pause-point banner
- If not paused → show `FrsTwoPhaseGenerationViz` normally (module bar spinning)

#### Module panel — inject generating overlay

In the builder body section where `FrsModulePanel` renders:

```tsx
// Inside the activeModule branch
const modProgress = doc?.unit_status?.[`design_mod_${activeModule.row_key}`] as
  FrsModuleDesignProgress | undefined
const modDesigning =
  (doc?.unit_status?.['_current_unit'] as string | undefined) ===
  `design_mod_${activeModule.row_key}`

return activeSpec ? (
  <FrsSpecPanel ... />
) : activeModule ? (
  <>
    {modDesigning && (
      <FrsModuleGeneratingOverlay
        module={activeModule}
        progress={modProgress ?? {}}
      />
    )}
    {!modDesigning && (
      <FrsModulePanel ... />
    )}
  </>
) : ...
```

When `modDesigning` is true, the overlay completely replaces the module panel.
When generation finishes (SWR poll sees `_current_unit` cleared), the overlay
unmounts and the module panel appears with the freshly-designed specs. The
transition uses a 220ms fade via `motion.div` `AnimatePresence`.

#### Replace `FrsContinueStageBBanner` → `FrsStageActionBar`

Remove the `FrsContinueStageBBanner` import and fixed-position bottom element.
Add `FrsStageActionBar` as an inline element at the top of the right-column
content area, before `SourceStrip`:

```tsx
{/* Stage B action bar — inline, always visible while specs are pending */}
<FrsStageActionBar
  projectId={projectId}
  modules={modules}
  unitStatus={doc?.unit_status ?? null}
  stageAApproved={stageAApproved}
  docStatus={status}
  onDesignAll={handleDesignAll}
  onMutate={() => mutate()}
/>
```

### 5.6 `FrsModuleRail.tsx` — EXTEND (per-module regen quick action)

**File**: `frontend/app/components/frs/FrsModuleRail.tsx`

In `FrsModuleRailItem`, the module row already has hover state (`hover`
boolean). Add a "Design Specs" / "Regenerate" icon button that appears on hover,
to the right of the stub count badge:

```tsx
{/* Regen quick action — only on hover, only when not currently designing */}
{hover && !moduleDesigning && onRegenModule && (
  <button
    onClick={(e) => { e.stopPropagation(); onRegenModule(m.row_key) }}
    title="Regenerate specs for this module"
    className={cn(
      'shrink-0 rounded p-0.5 transition-colors',
      'text-[var(--text-tertiary)] hover:text-[var(--accent)]',
      'hover:bg-[var(--accent-subtle)]',
    )}
    aria-label={`Regenerate specs for ${m.name}`}
  >
    <RotateCcw size={11} />
  </button>
)}
```

Add `onRegenModule?: (moduleRowKey: string) => void` to `FrsModuleRail` props.

Wire in `FrsBuilderView`:

```tsx
<FrsModuleRail
  ...
  onRegenModule={async (rowKey) => {
    try {
      await api.frs.designModule(projectId, rowKey)
      toast.success(`Regenerating ${rowKey}…`)
      await mutate()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Regeneration failed')
    }
  }}
/>
```

### 5.7 `FrsTwoPhaseGenerationViz.tsx` — EXTEND (sequential pause point)

**File**: `frontend/app/components/frs/FrsTwoPhaseGenerationViz.tsx`

Add optional props for sequential mode:

```ts
interface Props {
  // ... existing props
  sequential?: boolean           // true = sequential mode
  pausedAfterModule?: string | null  // row_key of the module just completed
  onReviewAndContinue?: () => void   // user clicks "Design next module"
  onDesignAllRemaining?: () => void  // skip sequential, run all remaining at once
}
```

When `sequential && pausedAfterModule`:

Render a pause card below the completed module bar:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ✓ MOD-001 designed — 3 specs, 92% completeness                             │
│  Review the specs in the panel, then continue when ready.                   │
│                                                                             │
│  [← Review specs]   [▶ Design MOD-002 next]   [⚡ Design all remaining]     │
└─────────────────────────────────────────────────────────────────────────────┘
```

The "← Review specs" button calls `onCancel()` which exits the theater back to
the builder body (the module panel is still there with the completed specs).

### 5.8 Prominent Regenerate button in module panel

**File**: `frontend/app/components/frs/FrsModuleIdentityCard.tsx` (EXTEND)

The `onRegenerateModule` prop is already wired into the identity card. Currently
it renders as a small ghost button among other actions. Change it to a
**distinctly-styled primary button**:

```tsx
{onRegenerateModule && (
  <button
    onClick={onRegenerateModule}
    className={cn(
      'inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold',
      'bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)]',
      'transition-colors shadow-[var(--shadow-sm)]',
    )}
  >
    <RotateCcw size={12} />
    Regenerate Specs
  </button>
)}
```

This is the same accent-fill style used for the primary CTA across the app (same
as the "Continue to Stage 2" button in `FrsContinueStageBBanner`). It will be
immediately visible without hunting for it.

### 5.9 `globals.css` — small addition (pulse animation)

**File**: `frontend/app/globals.css`

```css
@keyframes frs-spec-pulse {
  0%, 100% { background-color: transparent; }
  50%       { background-color: var(--accent-subtle); }
}
.frs-spec-pulse {
  animation: frs-spec-pulse 2s ease-in-out infinite;
}
```

Used by `FrsModuleGeneratingOverlay` for the currently-designing spec row.
Gated by `useReducedMotion()` — static amber background used as fallback.

### 5.10 Frontend summary

| File | Change | Purpose |
|---|---|---|
| `frontend/lib/api.ts` | extend | `api.frs.designAllModules(projectId, skipDesigned)` |
| `frontend/lib/types.ts` | extend | `FrsModuleDesignProgress` interface |
| `frontend/app/globals.css` | extend | `frs-spec-pulse` keyframe |
| `frontend/app/components/frs/FrsStageActionBar.tsx` | **new** | Inline persistent CTA replacing bottom banner |
| `frontend/app/components/frs/FrsModuleGeneratingOverlay.tsx` | **new** | Live progress inside module panel during generation |
| `frontend/app/components/frs/FrsBuilderView.tsx` | extend | New state machine (`stageBMode`, sequential logic, overlay wiring, bar replacement) |
| `frontend/app/components/frs/FrsModuleRail.tsx` | extend | Per-module `↻` hover quick action |
| `frontend/app/components/frs/FrsTwoPhaseGenerationViz.tsx` | extend | Sequential pause-point card |
| `frontend/app/components/frs/FrsModuleIdentityCard.tsx` | extend | Prominent filled Regenerate button |

**`FrsContinueStageBBanner.tsx`** — keep the file (other imports may reference
it) but stop mounting it in `FrsBuilderView`. Its functionality is fully
superseded by `FrsStageActionBar`.

---

## 6. Data flow — end-to-end trace

### Parallel mode ("Design All — parallel")

```
User clicks "Design All — parallel" in FrsStageActionBar
│
├─ handleDesignAll(sequential=false)
│   ├─ setStageBMode('parallel')
│   └─ api.frs.designAllModules(projectId, true)
│       └─ POST /frs/design-all-modules  {skip_designed: true}
│           ├─ mock mode: run_frs_stage_b() in-process → returns full detail
│           └─ prod mode:
│               ├─ doc.status = 'generating'
│               ├─ dispatch(design_all_frs_modules, project_id, true)
│               └─ return current detail
│
Celery worker (prod):
  _design_all_frs_modules(project_id, skip_designed=True)
  └─ run_frs_stage_b(project, db, skip_designed=True)
      ├─ gather_project_context() ONCE ← full BRD + CB + apps + docs
      ├─ doc.status = 'generating'
      ├─ asyncio.gather([MOD-001, MOD-002, MOD-003, MOD-004, MOD-005])
      │   └─ Semaphore(3): MOD-001, MOD-002, MOD-003 start simultaneously
      │       Each module's loop:
      │         for spec in stubs:
      │           LLM call (30–120s)
      │           _persist_design_module_result()
      │           db.commit()  ← SWR sees new spec appear
      │           JSONB patch: {current_spec_key, specs_done, specs_total}  ← NEW
      │         JSONB patch: {completeness, confidence, spec_count}  ← end of module
      └─ doc.status = 'in_interview'

SWR polling (frontend, every 2s):
  ├─ _current_unit set → SWR active
  ├─ unit_status.design_mod_MOD-001.current_spec_key updated
  │   → FrsModuleGeneratingOverlay re-renders: spec 2 of 3 highlighted
  ├─ new spec row appears in module.backlog
  │   → FrsModuleGeneratingOverlay marks that spec ✓
  └─ _current_unit cleared (module done)
      → FrsModuleGeneratingOverlay unmounts → FrsModulePanel appears with specs
```

### Sequential mode ("Design one by one")

```
User clicks "Design one by one" in FrsStageActionBar
│
├─ handleDesignAll(sequential=true)
│   ├─ setStageBMode('sequential'), setSequentialIndex(0), setSeqPaused(false)
│   └─ api.frs.designModule(projectId, firstUndesignedModuleKey)
│       └─ POST /modules/MOD-001/design
│           └─ dispatch(regenerate_frs_module, project_id, 'MOD-001')
│
FrsTwoPhaseGenerationViz renders (sequential=true):
  Shows MOD-001 bar running, MOD-002…005 queued
│
[MOD-001 completes — _current_unit cleared, design_mod_MOD-001.completeness > 0]
│
useEffect fires → seqPaused = true
│
FrsTwoPhaseGenerationViz shows pause card:
  "✓ MOD-001 designed — review specs or continue"
  [← Review specs]  [▶ Design MOD-002 next]  [⚡ Design all remaining]
│
User clicks "← Review specs":
  setStageBMode(null) → back to builder body
  Module panel shows MOD-001's specs (just designed)
  FrsStageActionBar shows "4 modules pending" with [Design Remaining]
│
User clicks "▶ Design MOD-002 next":
  setSeqPaused(false), setSequentialIndex(1)
  api.frs.designModule(projectId, 'MOD-002')
  FrsTwoPhaseGenerationViz resumes with MOD-002 bar running
│
User clicks "⚡ Design all remaining":
  setStageBMode('parallel')
  api.frs.designAllModules(projectId, true)  ← skip MOD-001 (already done)
  FrsTwoPhaseGenerationViz shows parallel bars for MOD-002…005
```

### Single module regen (from rail hover button or identity card)

```
User clicks ↻ on MOD-003 row in rail
│
onRegenModule('MOD-003')
└─ api.frs.designModule(projectId, 'MOD-003')
    └─ POST /modules/MOD-003/design
        └─ dispatch(regenerate_frs_module, project_id, 'MOD-003')

SWR sees _current_unit = 'design_mod_MOD-003'
→ if activeModuleKey === 'MOD-003':
    FrsModuleGeneratingOverlay mounts (replaces blank panel)
→ if activeModuleKey !== 'MOD-003':
    Module rail shows spinner on MOD-003 row
    User can click MOD-003 to navigate in and see the overlay
```

---

## 7. Implementation phases

### Phase 1 — Backend signal (1 day)

1. Add per-spec `unit_status` intermediate patch in `generate_frs_design_module`
2. Add `skip_designed` param to `generate_frs_all`
3. Add `run_frs_stage_b` function in orchestrator
4. Add `design_all_frs_modules` Celery task + `_design_all_frs_modules` helper
5. Register in `dispatch.py`
6. Add `POST /frs/design-all-modules` endpoint
7. Add `api.frs.designAllModules` to frontend API client

### Phase 2 — Live progress overlay (1.5 days)

8. Add `FrsModuleDesignProgress` type
9. Add `frs-spec-pulse` keyframe to globals.css
10. Build `FrsModuleGeneratingOverlay` component
11. Wire into `FrsBuilderView` content area (show overlay when `modDesigning`)
12. Test with mock provider — click regen on a module → overlay appears immediately

### Phase 3 — Stage action bar (1 day)

13. Build `FrsStageActionBar` (all three states)
14. Replace `FrsContinueStageBBanner` mounting in `FrsBuilderView` with `FrsStageActionBar`
15. Wire `handleDesignAll` (parallel path only first)
16. Test: Stage A approved → bar shows; design all → viz appears; all done → bar hides

### Phase 4 — Sequential mode (1 day)

17. Add `stageBMode`, `sequentialIndex`, `seqPaused` state to `FrsBuilderView`
18. Wire sequential path in `handleDesignAll`
19. Add `useEffect` for sequential module completion detection
20. Extend `FrsTwoPhaseGenerationViz` with `sequential`, `pausedAfterModule`, `onReviewAndContinue`, `onDesignAllRemaining` props
21. Test: sequential mode → each module designs → pause card → user reviews → continues

### Phase 5 — Rail & panel prominence (0.5 days)

22. Add `onRegenModule` prop to `FrsModuleRail` + per-row `↻` hover button
23. Update `FrsModuleIdentityCard` to use filled accent button for Regenerate
24. Wire `onRegenModule` in `FrsBuilderView`

### Phase 6 — Verification (1 day)

25. Mock-mode E2E walkthrough (§8 below)
26. TypeScript clean (`make typecheck`)
27. Lint clean (`make lint`)
28. Visual regression: dev-browser skill, check all 3 trigger surfaces

**Total**: ~5.5 days

---

## 8. Verification

### Mock-mode E2E — the key flows

**Flow A — Parallel mode from fresh Stage A**

1. Stage A approved. `FrsStageActionBar` visible at top of content area.
2. Click "Design All — parallel".
3. `FrsTwoPhaseGenerationViz` mounts showing all module bars.
4. SWR polls: bars fill as each module completes.
5. Navigate to a module mid-design → `FrsModuleGeneratingOverlay` shows, spec
   checklist updates as specs complete.
6. All bars complete → overlay exits → module panels show full specs.
7. `FrsStageActionBar` disappears (all completeness > 0).

**Flow B — Sequential mode**

1. Stage A approved. Click "Design one by one".
2. Viz shows MOD-001 bar spinning. MOD-002–005 queued.
3. MOD-001 completes → pause card appears.
4. Click "← Review specs" → back to builder, MOD-001's specs visible.
5. `FrsStageActionBar` shows "4 pending". Click "Design Remaining" → parallel
   mode for remaining 4.

**Flow C — Rail hover regen**

1. All modules designed. Hover MOD-003 in rail → `↻` icon appears.
2. Click `↻` → toast "Regenerating MOD-003…"
3. Navigate to MOD-003 → overlay shows (spec checklist, progress bar).
4. Generation completes → overlay exits → updated specs visible.

**Flow D — Partial completion recovery**

1. Kill the Celery worker mid-generation (2 of 5 modules done).
2. Page reload: `_current_unit` may be stale. SWR detects `status='generating'`
   but no progress change after 10s → `StalledGenerationBanner` shows.
3. Click "Clear stuck state" → `reset_frs_generating` called → status = 'in_interview'.
4. `FrsStageActionBar` shows "3 modules pending" (2 already done, skip_designed=True).
5. Click "Design Remaining" → only the 3 undesigned modules are queued.

### Critical assertions

| Assertion | How to verify |
|---|---|
| `current_spec_key` appears in `unit_status` during generation | `make test-be::test_design_module_smoke` — inspect unit_status mid-run |
| `skip_designed=True` skips modules with completeness > 0 | New test `test_design_all_skips_designed` |
| Overlay unmounts when `_current_unit` clears | Browser: watch overlay → panel transition |
| Sequential pause card blocks next dispatch | Browser: click pause → confirm no new Celery tasks dispatched |
| Regenerate from rail dispatches exactly one Celery task | Check broker queue in Redis |
| `FrsStageActionBar` hides when all modules designed | Browser: all completeness > 0 → bar gone |

---

## 9. Backend tests to add

**File**: `backend/tests/test_frs_design_module.py` (extend existing)

```python
async def test_per_spec_progress_written_to_unit_status():
    """After each spec in a module, unit_status.design_mod_<key>.current_spec_key
    is written. After the full module, completeness + spec_count are written."""

async def test_skip_designed_excludes_complete_modules():
    """run_frs_stage_b with skip_designed=True skips modules where
    unit_status.design_mod_<key>.completeness > 0."""

async def test_design_all_endpoint_mock_mode():
    """POST /frs/design-all-modules runs in-process in mock mode,
    returns full detail with all modules designed."""

async def test_design_all_endpoint_sets_status_generating_in_prod_mode():
    """POST /frs/design-all-modules in non-mock mode sets doc.status='generating'
    and dispatches the Celery task."""
```

---

## 10. Risks & mitigations

| Risk | Mitigation |
|---|---|
| `_current_unit` stays set after Celery worker dies | Existing `StalledGenerationBanner` + reset endpoint already handle this |
| Sequential mode useEffect fires prematurely (detects wrong module) | Guard: check `_current_unit === null` AND `design_mod_<dispatched_key>.completeness > 0` |
| `design_all_frs_modules` Celery task runs when doc already validated | Guard in `run_frs_stage_b`: if `doc.status === 'validated'`, raise error before marking generating |
| Two simultaneous "Design All" calls → double-generation | Guard in endpoint: if `doc.status === 'generating'`, return 409 with current detail |
| Per-spec intermediate JSONB patch overwrites module's final completeness | JSONB `||` is additive; the intermediate patch only sets `current_spec_key/specs_done/specs_total`. The final patch (end of loop) sets `completeness/confidence/spec_count` and overwrites the whole key — which is correct |
| Old `FrsContinueStageBBanner` still mounted somewhere | Remove mount point in `FrsBuilderView`; file stays for reference but is a dead component |
