# E4c · Part 4 — Ambient, Non-Blocking FRS Generation · Plan

> Companion to `E4c-frs-generation-ux.md`. That plan added live progress and the
> stage action bar. This plan fixes the **blocking, laggy, no-feedback** behavior
> that remained, and makes generation an *ambient* experience the builder never
> leaves.

---

## 1. Problems (observed)

1. **Click "Regenerate Specs" → blink then nothing.** The button spins during the
   API call (~1–2s), then `regenLoadingKey` clears in `finally`. But Celery hasn't
   set `_current_unit` yet (it picks up + the next SWR poll lands 2–6s later). In
   that gap nothing shows → looks broken. Then seconds later the screen suddenly
   flips to the full-screen generation view.

2. **Generation takes over the whole screen and blocks navigation.** Two render
   gates in `FrsBuilderView` short-circuit the entire builder into the full-screen
   `FrsTwoPhaseGenerationViz`:
   - `if (stageBMode !== null)` (client-driven)
   - `if (status === 'generating' && hasGenerationProgress && stageAApproved)` (server-driven)
   While either is true, the rail, the other modules, the header — everything is
   gone. The user cannot click another module or do anything else.

3. **Multi-second delay before any progress appears**, because the only feedback
   path is: API round-trip → Celery pickup → DB write → SWR poll (2s). Nothing is
   optimistic.

## 2. Root-cause summary

| Symptom | Cause |
|---|---|
| Blink then nothing | `regenLoadingKey` cleared on API return, before `_current_unit` appears |
| Full-screen block | `FrsBuilderView` *returns* the viz instead of *overlaying* it |
| Lag | No optimistic state; everything waits on the poll |

Key backend fact (already true): `_set_current_unit` only writes
`unit_status._current_unit`. It never sets `doc.status`. A **single-module regen
leaves `status='in_interview'`**; only a **bulk run sets `status='generating'`**.
That gives a clean, free signal to distinguish the two contexts — no backend
change needed.

## 3. Design principles

1. **Generation is ambient, never modal.** The builder stays fully interactive at
   all times. Progress is shown *in place* (rail + module panel overlay + a slim
   top banner), not by replacing the screen.
2. **Optimistic first paint.** The instant the user clicks, progress shows — the
   module-panel overlay mounts and a toast confirms, before any round-trip.
3. **The full two-phase viz is opt-in.** It becomes a "watch the whole run"
   overlay the user can open and *close at will* (generation keeps running
   underneath). It is never force-shown for Stage B.
4. **Two contexts, two treatments:**
   - **Bulk run** (`status==='generating'`): slim ambient banner + per-module rail
     progress; optional viz overlay.
   - **Single regen** (`status==='in_interview'` + pending/`_current_unit`):
     overlay on just that module; no banner takeover; free navigation.
5. **Stage-A first run keeps its full-screen theater** only while there is no
   builder yet (`modules.length === 0`). Once modules exist, everything is ambient.

## 4. State model (frontend, `FrsBuilderView`)

```ts
// Modules the user just triggered — bridges the optimistic gap until the poll
// confirms the run started, then confirms it finished. Single-regen only.
const [pendingRegens, setPendingRegens] = useState<Set<string>>(new Set())
const confirmedRunning = useRef<Set<string>>(new Set())
const regenTriggeredAt = useRef<Map<string, number>>(new Map())

// Whether the optional full "watch" overlay is open (user choice, NOT forced)
const [vizOpen, setVizOpen] = useState(false)

// Derived
const bulkActive = status === 'generating' && stageAApproved
```

### 4.1 Per-module generation state (robust derivation)

```ts
type ModuleGenState = 'done' | 'running' | 'queued' | 'idle'

function moduleGenState(key: string): ModuleGenState {
  const prog = doc?.unit_status?.[`design_mod_${key}`] as FrsModuleDesignProgress | undefined
  const isCurrentUnit = doc?.unit_status?.['_current_unit'] === `design_mod_${key}`
  // "live, not finished": specs_total present but the final completeness not yet written
  const liveRunning = prog?.specs_total != null && !(prog?.completeness)
  if (pendingRegens.has(key) || isCurrentUnit || liveRunning) return 'running'
  if ((prog?.completeness ?? 0) > 0) return 'done'
  if (bulkActive) return 'queued'
  return 'idle'
}
```

Note ordering: `running` is checked before `done` so a regen of an
already-designed module (completeness already > 0) still shows as running while
in flight.

### 4.2 pendingRegens lifecycle (the gap-bridge)

`_current_unit` is reliable for **single** regen (one Celery task at a time):

```ts
useEffect(() => {
  if (pendingRegens.size === 0) return
  const cu = doc?.unit_status?.['_current_unit'] as string | undefined
  const next = new Set(pendingRegens)
  let changed = false
  for (const key of pendingRegens) {
    const unitKey = `design_mod_${key}`
    if (cu === unitKey) {
      confirmedRunning.current.add(key)            // Celery picked it up
    } else if (confirmedRunning.current.has(key)) {
      confirmedRunning.current.delete(key)          // was running, now isn't → done
      regenTriggeredAt.current.delete(key)
      next.delete(key); changed = true
    } else {
      // never confirmed yet — stale-guard so a dead worker can't pin forever
      const t = regenTriggeredAt.current.get(key) ?? 0
      if (Date.now() - t > 90_000) {
        regenTriggeredAt.current.delete(key)
        next.delete(key); changed = true
        toast.error(`Generation didn't start for ${key} — is the worker running?`)
      }
    }
  }
  if (changed) setPendingRegens(next)
}, [doc?.unit_status, pendingRegens])
```

(`Date.now()` is fine here — this is a React client component, not a workflow script.)

## 5. Render-gate restructure (`FrsBuilderView`)

**Delete** both Stage-B full-screen gates:
- Remove `if (stageBMode !== null) return <FrsTwoPhaseGenerationViz/>`.
- Remove the `stageAApproved` branch inside `if (status === 'generating' && hasGenerationProgress)`.

**Keep** Stage-A first-run theater, but only when there is genuinely no builder:

```ts
if (status === 'generating' && !stageAApproved && modules.length === 0
    && (modularizeStatus?.completeness ?? 0) >= 0) {
  return <FrsConstructionTheater .../>
}
```

Everything else falls through to the **always-interactive builder**, which now
renders (in addition to what it has):
- `FrsGenerationBanner` (new) at the top when `bulkActive || pendingRegens.size`.
- The module-panel overlay when `moduleGenState(activeModule) === 'running'`.
- An optional full-screen `FrsTwoPhaseGenerationViz` overlay when `vizOpen`.

## 6. New component — `FrsGenerationBanner.tsx`

Slim, fixed-height (h-9) strip below the builder header. Non-blocking.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ◐ Designing 3 of 7 modules · MOD-003 Claims Intake   ▰▰▰▱▱▱▱  [View details ›] ✕│
└──────────────────────────────────────────────────────────────────────────────┘
```

Props:
```ts
interface Props {
  modules: FrsModuleHydrated[]
  unitStatus: Record<string, unknown> | null | undefined
  bulkActive: boolean
  pendingCount: number
  onOpenDetails: () => void   // sets vizOpen = true
}
```
- Aggregate: `done = modules with completeness>0`, `total`, `running label`.
- Thin progress bar = done/total.
- "View details ›" → opens the viz overlay.
- Renders `null` when nothing is generating.
- Subtle animated left-border in the accent color; respects `useReducedMotion()`.

## 7. `FrsTwoPhaseGenerationViz` → dismissible overlay

Add `onMinimize?: () => void`. When present:
- Render the existing top-left "Back" affordance as **"Continue in builder →"**
  calling `onMinimize` (just closes the overlay; does NOT reset generation).
- Keep "Resume from here" (reset) as the recovery action, separate.

In `FrsBuilderView`, mount it as a fixed overlay:
```tsx
{vizOpen && (
  <div className="fixed inset-0 z-50 bg-[var(--bg-base)]">
    <FrsTwoPhaseGenerationViz
      …
      onMinimize={() => setVizOpen(false)}
      sequential={stageBMode === 'sequential'}
      pausedAfterModule={…}
      onReviewAndContinue={() => { setVizOpen(false); setStageBMode(null); setSeqPaused(false); mutate() }}
      onDesignNext={handleDesignNext}
      onDesignAllRemaining={handleDesignAllRemaining}
    />
  </div>
)}
```

## 8. Handler changes

### 8.1 `handleRegenerateModule` — optimistic, fire-and-forget

```ts
function handleRegenerateModule(moduleRowKey?: string) {
  const key = (typeof moduleRowKey === 'string' ? moduleRowKey : null) ?? activeModuleKey
  if (!key) return
  // Optimistic: overlay + rail spinner mount immediately
  setPendingRegens(prev => new Set(prev).add(key))
  regenTriggeredAt.current.set(key, Date.now())
  toast.message(`Designing ${key}…`, { description: 'Specs will appear as they complete.' })
  // Fire without blocking the UI; do NOT clear pending in finally
  api.frs.designModule(projectId, key)
    .then(() => mutate())
    .catch((e) => {
      setPendingRegens(prev => { const n = new Set(prev); n.delete(key); return n })
      regenTriggeredAt.current.delete(key)
      toast.error(e instanceof Error ? e.message : 'Regeneration failed')
    })
}
```
Removes `regenLoadingKey` entirely — `moduleGenState(key) === 'running'` is now the
single source of truth for "this module is generating", and it stays true from
the optimistic click through completion.

### 8.2 `handleDesignAll(parallel)` — bulk, open viz by default

```ts
// parallel branch:
setVizOpen(true)                       // user explicitly asked to watch the whole run
await api.frs.designAllModules(projectId, true)
await mutate()
```
`status` becomes `generating` server-side → `bulkActive` true → banner shows too.
Closing the viz (`onMinimize`) drops them into the builder with the banner; the
run keeps going.

### 8.3 Sequential — uses pendingRegens + viz overlay

`handleDesignAll(true)` and `handleDesignNext` add the dispatched key to
`pendingRegens` (so the module overlay is correct) and `setVizOpen(true)` for the
sequential watch experience. The existing `seqPaused` logic stays, driven by the
reconcile effect.

## 9. Rail enhancement (`FrsModuleRail`)

Per-row, when `moduleGenState(key) === 'running'`, show a tiny inline progress
(`specs_done/specs_total`) next to the spinner. When `'queued'` (bulkActive),
show a faint "queued" dot. Drives off the same `unit_status` the rail already
receives — pass a `genState` resolver or compute inline from `unitStatus`.

## 10. Module panel overlay wiring

Replace the `regenLoadingKey`/`_current_unit` check with:
```ts
const activeGen = moduleGenState(activeModule.row_key) === 'running'
return activeGen
  ? <FrsModuleGeneratingOverlay module={activeModule} progress={…} />
  : <FrsModulePanel … />
```
Because `moduleGenState` is true from the optimistic click, the overlay mounts
instantly. The user can click any *other* module in the rail — that module's
panel renders normally (its own `moduleGenState` is `done`/`idle`), so navigation
is never blocked.

## 11. Poll cadence

Tighten the SWR `refreshInterval` during activity from 2000 → 1500ms while
`bulkActive || pendingRegens.size || _current_unit` so live progress feels snappy.

## 12. Files touched

| File | Change |
|---|---|
| `frontend/app/components/frs/FrsBuilderView.tsx` | Remove Stage-B full-screen gates; add `pendingRegens` lifecycle + `moduleGenState`; optimistic `handleRegenerateModule`; `vizOpen` overlay; mount `FrsGenerationBanner`; non-blocking module overlay; tighter poll |
| `frontend/app/components/frs/FrsGenerationBanner.tsx` | **New** — slim ambient progress strip |
| `frontend/app/components/frs/FrsTwoPhaseGenerationViz.tsx` | Add `onMinimize` → "Continue in builder"; render as overlay |
| `frontend/app/components/frs/FrsModuleRail.tsx` | Per-row running progress / queued hint; replace `regenLoadingKey` prop with `genStateOf` |
| Backend | **None** — single vs bulk already distinguished by `status` |

## 13. Verification

1. **Regenerate one module** → overlay + rail spinner appear *instantly*; toast
   shows; builder stays put. Navigate to another (done) module → see its specs.
   Navigate back → overlay still there until specs land, then panel with new specs.
2. **No worker running** → after 90s the optimistic state clears with an error
   toast (no infinite spinner).
3. **Design All** → viz overlay opens; click "Continue in builder →" → drops into
   builder with the slim banner; rail fills in parallel; can click around freely;
   "View details ›" reopens the viz.
4. **Sequential** → pause card still works; module overlay correct per step.
5. `make typecheck` + `make lint` clean.
```
