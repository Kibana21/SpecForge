# E4b — BRD Builder · Complete Implementation Plan

> **Self-contained build plan** covering every aspect of the BRD Builder — backend wiring,
> data model, DSPy units, validators, transport, frontend UX, components, animations, verification.
> Built as a companion to the design doc `E4b-brd-builder.md`, but readable end-to-end on its own.
>
> Engineers: open this file and execute. Companion design doc only needed for "why" questions.

---

## 0 · Context

The BRD Builder is the second SDLC artifact module after the Concept Brief (E4a) and the first
heavy-weight one — **21 typed row tables**, **24 generation units**, mandatory **outward
traceability**, a strict validation gate, and a hard **full-corpus context coverage** requirement.

E4b's design introduces:

1. A **standalone, cross-module Project Context Bundle subsystem** in `services/context/` that every
   future artifact module (FRS, NFR, Architecture, …) will reuse.
2. A **mandatory outward-traceability table** (`brd_traceability`) capturing how every BR / KPI /
   objective / risk row links back to its source (CB row · app fact · doc section · discover Q&A).
3. A **wonderful UI/UX** — calm under density, provenance is the product, the AI is a colleague not
   a magic wand — turning the BRD builder into the most polished surface in the product.

This plan sequences the build so backend phases unblock the frontend as early as possible, and
component-level FE work can run in parallel with corresponding BE phases once type contracts are
stubbed.

---

## 1 · North-star principles

### Product (UX)

1. **Calm under density.** 14 sections × 21 row tables is a lot. Default to collapsed; progressively
   disclose; anchor on a sticky rail. No tabs, no horizontal scroll. Whitespace is the primary tool.
2. **Provenance is the product.** Every AI claim earns its place by showing where it came from.
   Trace chips, source pop-outs, the three-layer context strip are not decorations — they're why a
   non-technical BA can defend the BRD to a reviewer.
3. **The AI is a colleague, not a magic wand.** Always show what the AI is doing, what it grounded
   on, where the user can intervene. No black-box "regenerate" buttons.
4. **Friction in the right places.** Validation findings, broken traces, stale corpora — **visible**
   (not buried in toasts). Edits, regenerations, acceptance — **frictionless** (autosaved,
   undoable).
5. **Crib from `InterviewPanel.tsx`.** It's the most polished surface in the codebase: two-column
   live thread + structured panel, citation chips, confidence badges, soft accent bubbles. BRD
   inherits its DNA and extends it.

### Engineering

6. **Full-corpus context is a hard invariant.** Generation blocks until every included project doc
   is indexed + every in-scope app fact + the validated CB is in the bundle. Memory:
   [[full-corpus-context-rule]].
7. **Build infrastructure once, reuse forever.** Context Bundle, discover-table generalisation,
   traceability table, generic API router — all graduate cleanly to FRS.
8. **Per-sub-artifact granularity, never one-shot.** One focused DSPy unit per table; row-level
   versioning; typed columns; no JSONB blobs. Memory: [[artifact-generation-granularity]].

---

## 2 · Cross-cutting architecture decisions

Pulled into one place for fast reference.

| Decision | Why |
|----------|-----|
| `services/context/` is a **standalone, artifact-agnostic** subsystem | Build it BEFORE BRD-specific work; everything downstream depends on its types and readiness gate |
| Bundle composes **3 layers — App Brain · Project Documents · Concept Brief** — with full-coverage guarantees | A reviewer asking "what fed this BR?" must always have a real, non-empty answer |
| Full-corpus **readiness gate** blocks generation when any included doc is still indexing | Bounded wait cost (minutes); unbounded cost of missing a documented constraint |
| **`brd_traceability` table** captures outward links per row (target_table, target_row_key, source_kind, source_ref, relation, excerpt, confidence) | Per-row provenance, queryable, versioned; future-rename to `artifact_traceability` for FRS |
| Generalise **`cb_discover_*` → `artifact_discover_*`** + per-type catalog | One rename, eliminates duplication per new artifact |
| **Async generation** via Celery + dispatcher; bundle built inside the task | ~24 units × Vertex latency exceeds a request budget; bundles can be large |
| **CB → BRD is one-way snapshot read**, not a live link | Editing CB after BRD generation doesn't mutate BRD rows; FE surfaces "regenerate to incorporate" hint |
| **Trace integrity** is a validate-gate finding, not a write-time block | Orphan refs surface in FindingsDrawer for user fixing; auditable |
| `BR.objective_ids` / `.stakeholder_ids` are **within-BRD soft refs**; `brd_traceability` is **outward** | Two distinct concepts; FE renders separately |
| Markdown export gains **Appendix A** (traceability matrix) + **Appendix B** (snapshot refs) | Auto-generated from `brd_traceability` + `snapshot_refs`; no new persistence |
| **Legacy E3 `brd` SpecType** stays alive through E4b, removed in E4c | Deprecation header + hide UI when new artifact exists |
| **FRS gate factory** wired now behind a 501 stub | Pre-wired to prevent regression when E4c lands |
| **PII out of scope** project-wide | Memory: [[pii-out-of-scope]] |

---

## 3 · UI/UX deep dive (every surface, in full)

### 3.1 Information architecture

| Route | Purpose | Status |
|-------|---------|--------|
| `/projects/[id]` | Workspace — left rail surfaces the BRD chip in the SDLC pipeline | exists; extend |
| `/projects/[id]/artifacts/brd` | The BRD Builder (this plan's main subject) | new; reuses `ArtifactBuilderPanel` shell |
| `/projects/[id]/artifacts/concept-brief` | Sibling — viewable read-only from BRD via "Open CB →" | exists |

### 3.2 Workspace card (entry point)

`frontend/app/projects/[id]/page.tsx` already has a BRD chip at lines ~305–315 (currently gated by
`ruValidated`). Re-purpose:

- **Gate logic** flips: `cb.status === "validated"` instead of `ruValidated`.
- **Tooltip:** "BRD locked until Concept Brief is validated".
- **Status chip** mirrors `artifact.status`:

  | Status | Chip |
  |--------|------|
  | `null` (not started) | grey "Not started" |
  | `in_discover` | violet pulse — "Discover" |
  | `in_interview` | amber "In progress" |
  | `generating` | blue pulse — "Generating…" |
  | `validated` | emerald — "Validated ✓" |

- **FRS chip** sits below BRD: greyed "coming soon"; once BRD is validated → "disabled — BRD
  validated ✓" (telegraphs the next gate; no live FRS builder yet).

### 3.3 Builder shell layout

Reuses `ArtifactBuilderPanel.tsx`. Right column has a new sub-layout for BRD:

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ HEADER (sticky, h-12)                                                                    │
│ ← CB    BRD · In progress    ⚙ Sources  ✦ Coverage 14/14  ✓ Validate  ⤓ Export          │
├──────────────────────────────────┬──────────────────────────────────────────────────────┤
│ LEFT — Q&A thread + composer     │ RIGHT — Document surface                              │
│ (lg:max-w-[420px])               │                                                       │
│                                  │ ┌──────────────────────────────────────────────────┐ │
│ • Active clarification card      │ │ THREE-SOURCE CONTEXT STRIP (sticky, collapsible)  │ │
│   (question + trace seed)        │ │ ▾ App Brain · 2 apps · 47 facts          ✓ ready  │ │
│                                  │ │ ▾ Documents  · 5 of 5 indexed            ✓ ready  │ │
│ • Up next · 3 (collapsed list)   │ │ ▾ Concept Brief · validated v2           ✓ ready  │ │
│                                  │ └──────────────────────────────────────────────────┘ │
│ • Thread (synthesis + Q's        │ ┌──────────────────────────────────────────────────┐ │
│   + user replies + citations)    │ │ CB ECHO STRIP (collapsible, opt-in 2nd row)       │ │
│                                  │ │   Problem · 3 outcomes · 5 capabilities (inline)  │ │
│                                  │ └──────────────────────────────────────────────────┘ │
│                                  │ ┌────┐ ┌───────────────────────────────────────────┐ │
│                                  │ │ §  │ │ SECTION CONTENT (scrollable, anchored)    │ │
│                                  │ │RAIL│ │                                            │ │
│                                  │ │ 1 ●│ │  1. Business Context …                    │ │
│                                  │ │ 2 ●│ │  2. Problem Statement …                   │ │
│                                  │ │ 3 ●│ │  3. Objectives                             │ │
│                                  │ │ 4 ◐│ │     [grid of objective cards]              │ │
│                                  │ │ 5 ○│ │  ...                                       │ │
│                                  │ │ 7 ★│ │  7. Business Requirements ★ keystone      │ │
│                                  │ │…   │ │     [grid of BR cards]                     │ │
│                                  │ │14 ○│ │                                            │ │
│                                  │ └────┘ └───────────────────────────────────────────┘ │
│ ┌──────────────────────────────┐ │                                                       │
│ │ Composer (⌘+Enter)           │ │                                                       │
│ └──────────────────────────────┘ │                                                       │
└──────────────────────────────────┴──────────────────────────────────────────────────────┘
```

Mobile (`<md`): single-column with bottom-sheet composer + tab switcher (`thread | sections |
sources`). Reuses `ThreePanel.tsx`'s segmented-tab approach.

### 3.4 The 7 stages of the BRD journey

#### Stage 0 — Workspace card (entry)

Covered in §3.2. State machine in `useArtifact(projectId, "brd").detail.document.status`.

#### Stage 1 — Empty state (CB just validated, BRD not started)

```
                        ┌──────────────────────────────────┐
                        │  ✦                                │
                        │  (w-16 h-16 accent-subtle circle) │
                        └──────────────────────────────────┘

                          Build the Business Requirements
                        (text-lg font-semibold text-primary)

           Derive a complete BRD from your validated Concept Brief,
           every in-scope app's facts, and your indexed project docs.
           (text-sm text-secondary, max-w-md)

           ┌───────────────────────────────────────────────────┐
           │  ⚡ Grounded in 2 apps · 5 docs · CB v2            │
           └───────────────────────────────────────────────────┘

           ┌───────────────────────────────────────────────────┐
           │  Briefly restate the initiative for the BRD       │
           │  (optional)                          [✦ AI Enhance]│
           │                                                   │
           │  textarea, rows=4                                 │
           └───────────────────────────────────────────────────┘

           ┌─ DocReadinessPanel (only when blocked) ───────────┐
           │  ⏳ 2 of 5 documents still indexing                │
           │  • 151012-Press-Release.pdf · running (47% · 30s) │
           │  • Settlement-Manual.docx   · pending              │
           │  Generation will run automatically when ready      │
           └───────────────────────────────────────────────────┘

                    [  Discover & Continue →  ]
                    (Button size="lg"; disabled while indexing pending)
```

**Differences from CB empty state:**
- "Discover & Continue" instead of "Analyze & Continue".
- Three-layer grounding badge (apps · docs · CB).
- **Inline `DocReadinessPanel`** animates in when any doc is still indexing — replaces a hostile
  409 dialog. Per-doc progress polls every 3 s via `useBrdReadiness`; when all flip to `done`, CTA
  un-greys with a 200 ms fade and one-line toast "All sources ready".

**Edge cases:**
- Zero docs uploaded → neutral note + inline `UploadPanel`.
- Doc failed indexing → red row with "Re-upload" + "Re-index" actions.
- `platform_admin` "Generate without doc N" escape hatch → confirm dialog: "Skipping `<doc>`. The
  BRD may miss requirements documented there." (audited)

#### Stage 2 — The Discover phase

Reuses E5 `DiscoverPhase` shell. BRD-specific tweaks:

- **18 questions across 7 categories** (vs CB's 14 / 5). Category emoji set extends with
  `⚠ Risks` and `🚀 Delivery`:

  🎯 Initiative · 📊 Objectives · 👥 Stakeholders · 🔄 Processes · 📦 Scope · ⚠ Risks · 🚀 Delivery

- **Per-category progress segments** — 7 mini-bars filling independently. Finishing a category
  feels like a milestone:

  ```
  🎯 Initiative   ▰▰▰▰
  📊 Objectives   ▰▰▰▱
  👥 Stakeholders ▰▰▱▱
  🔄 Processes    ▰▱▱▱
  📦 Scope        ▱▱▱
  ⚠  Risks       ▱
  🚀 Delivery     ▱▱
  ```

- **"Why this matters" tooltip** per question — clicking a small `i` icon next to a question
  reveals one sentence about which BRD section uses the answer.

- **Per-question grounding hints** — hovering a source badge → side popover with the source
  excerpt (200-char snippet). Same Radix Popover pattern as the trace chip.

The full BRD discover catalog is in §5.7.

#### Stage 3 — Generation theater

This is one of the **hero moments**. Naive impl = spinner. Wonderful impl = live unit-by-unit DAG
showing topological parallelism. Earns trust at a glance.

```
                          Building your BRD…
                  (text-2xl font-semibold)  est. 60–90 s

  ┌─────────────────────────────────────────────────────────────────────────┐
  │  DEPENDENCY MAP — live                                                   │
  │                                                                          │
  │  ✓ business_context  ✓ problem  ◐ objectives    ◐ stakeholders         │
  │       │                  │             │              │                   │
  │       └────────┬─────────┘             │              │                   │
  │                ▼                       ▼              ▼                   │
  │              actors                  scope    asis_process              │
  │                │                       │              │                   │
  │                ▼                       ▼              ▼                   │
  │              (parallel branches running…)                                 │
  │                                                                          │
  │  Legend:  ✓ done   ◐ in progress   ○ queued   ⚠ error                   │
  └─────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────────┐
  │ ◐ Right now: writing 5 objectives (grounded in CB outcomes)             │
  │    text-sm with subtitle "[CB#3] [CB#5] · 1 app fact"                   │
  └─────────────────────────────────────────────────────────────────────────┘
```

**Implementation:**
- Polls `GET /api/projects/[id]/artifacts/brd` every 2 s during `status === "generating"`.
- Response includes `unit_status: {unit_key: {state, completeness, confidence, current_grounding?}}`.
- DAG rendered from the static BRD manifest in `lib/brd-manifest.ts`.
- Animations: `framer-motion` `AnimatePresence` + `motion.span` for ○ → ◐ → ✓ transitions
  (300 ms ease-out per step).
- On error: dot turns ⚠ red; clicking opens drawer with error + "Retry from here" → calls
  `POST units/{unit_key}/regenerate`.
- **Reduced motion:** plain ordered list with `[✓ / ◐ / ○]` icons updating in place.

#### Stage 4 — The Builder (main surface)

The 80% of the experience. State: `doc?.status === "in_interview"`. Layout per §3.3.

##### 3.4.4.a · Three-Source Context Strip (sticky top of right column)

Three rows, each collapsible to a 32-px line. Each row's chevron expands an **inline** detail panel
(NOT a drawer — keeps the user oriented). Uses shadcn `Collapsible`.

```
▾  App Brain · 2 apps · 47 facts                              ✓ ready    [edit scope →]
   ├─ PayHub Core   (tier 1, ops)  · 32 facts  · "add SMS settlement channel"
   ├─ NotifyService (tier 2, ops)  · 15 facts  · —
   └─ (expanded — fact list grouped by kind on click)

▾  Documents · 5 of 5 indexed                                ✓ ready    [manage sources →]
   ├─ 151012-Press-Release.pdf · 47 pages · ✓ indexed
   ├─ Settlement-Manual.docx   · 23 pages · ✓ indexed
   ├─ FX-Rates-Q3.xlsx        · 12 pages · ✓ indexed
   ├─ Customer-Survey.pdf      ·  8 pages · ✓ indexed
   └─ Compliance-Checklist.md  ·  3 pages · ✓ indexed
   (expanded — per-doc PageIndex outline preview; click row → markdown viewer modal)

▾  Concept Brief · validated v2 · 2 days ago                 ✓ ready    [open CB →]
   Problem: Manual reconciliation across premium collections and refunds…
   Outcomes (3): Reduce reconciliation 70% · Fewer exceptions · Faster refund SLA
   Capabilities (5): Automated reconciliation · Exception handling · Audit ledger · …
   ⚠ CB has changed since BRD generated — [regenerate to incorporate]
   (this banner shows only when bundle.snapshot_refs.cb < project's current cb VersionSnapshot)
```

**Visual touches:**
- Left 2-px border tint per layer: App Brain `--app-brain` (#0369A1), Docs `--status-info`
  (#2C5A7A), CB `--accent` (#2F6B4C).
- Status pill on the right: `✓ ready` emerald, `⏳ N pending` amber, `⚠ stale` warning.
- Counts auto-update via SWR; subtle pulse animation on the count number when it changes (scale
  1 → 1.15 → 1, 240 ms).
- Hover any source line → side popover (same component as Trace Hover Pop-out).

##### 3.4.4.b · CB Echo Strip (collapsed by default, below Source Strip)

A single-row, expandable band that distils the validated CB into one glance. Separate from the
Source Strip because users routinely need to re-read CB while writing BRD; a second, smaller,
always-collapsible row beats forcing a drawer trip.

```
▸ Concept Brief essence · "Reduce settlement time across PayHub" · 3 outcomes · 5 capabilities
```

Expanded: full CB problem statement (prose) + outcomes (one line each) + capabilities (one line
each) in a compressed read-only view. "Open CB →" link in the corner.

##### 3.4.4.c · Section Rail (sticky vertical left of right column)

56-px wide rail with one row per section. Each row:

```
┌────┐
│ 1 ●│  Business Context        (text-[10px] section number, status dot)
│ 2 ●│  Problem Statement
│ 3 ●│  Objectives
│ 4 ◐│  Stakeholders & Actors    ← currently in view (filled + accent-subtle bg)
│ 5 ○│  Scope
│ 6 ○│  Processes (as-is + to-be)
│ 7 ★│  Business Requirements    ← keystone
│ 8 ○│  Data & Reporting
│ 9 ○│  Assumptions / Deps / Constraints
│10 ○│  Risks & Issues
│11 ○│  Implementation & Phasing
│12 ○│  KPIs
│13 ○│  Open Questions / Decisions
│14 ○│  References / Glossary
└────┘
```

**Status dots:**
- ● filled accent = `unit_status[unit].completeness ≥ 90`
- ◐ half-filled = 60–89
- ○ outline = <60 or never generated
- ⚠ red = validate finding on this unit
- 🔒 small lock = section has ≥ 1 locked row

**Interactions:**
- Click row → smooth-scroll content area to that section; section title pulses for 600 ms.
- Sticky position with `top-[var(--header-h)]`; rail scrolls if it overflows.
- Reduced-motion: instant jump, no pulse.
- Right-click → context menu: "Collapse all but this", "Regenerate this section", "Copy section
  link" (anchor URL).
- Active section detected via `IntersectionObserver` on section anchors.

##### 3.4.4.d · Section panels (the document content)

Each numbered section is a `SectionPanel` (reuse + extend existing from CB builder). Example for
the keystone §7:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ § 7 · Business Requirements                      completeness 94% · confidence high     │
│  ────────────────────────────────────────────────────────────────────────────────────  │
│  AI-generated · 1 row edited · 0 locked                       [✦ Regenerate this section]│
│                                                                                          │
│  ┌─── BR card ──────────────────────────────────────────────────────────────────────┐  │
│  │ BR-001 · must                       [edit] [history] [regenerate] [⋮]            │  │
│  │  Reconcile premium collections within 7 days of receipt                          │  │
│  │  ──────────────────────────────────────────────────────────────────────────────  │  │
│  │  ▾ Description       …text…                                                       │  │
│  │  ▾ Acceptance criteria                                                            │  │
│  │     • Given a premium received   When ≥ 7 days have passed   Then it appears in…│  │
│  │     • Given a discrepancy of > $10   When reconciliation runs   Then …          │  │
│  │  ▾ Traces (3 outward, 4 within-BRD)                                              │  │
│  │     [← CB · capability: Automated reconciliation]                               │  │
│  │     [← PayHub · capability: Multi-rail settlement]                              │  │
│  │     [← Press-Release.pdf §Problem Overview (p.2)]                               │  │
│  │     Within-BRD: [→ OBJ-1] [→ OBJ-2] [→ STK-1] [→ STK-3]                        │  │
│  │  ▾ Quality            AI-generated · confidence high · completeness 96%          │  │
│  └───────────────────────────────────────────────────────────────────────────────┘   │
│  (more BR cards…)                                                                       │
│  [+ Add BR manually]                                                                    │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

##### 3.4.4.e · Refine composer (left column bottom)

Same shape as `InterviewPanel.tsx`'s composer. Two-row textarea, ⌘+Enter to send. Above the textarea:
the **active question card** (with its trace_seeds shown as ghost chips) + a **collapsed list of
pending questions**. New for BRD: a small **active-scope chip** above the textarea showing which
unit will re-run on submit:

```
[⤴ §7 Business Requirements + dependents]   ← affected scope chip, hover to expand
┌──────────────────────────────────────────────────────┐
│  Answer "Who owns the reconciliation SLA?"           │
│                                                      │
│                                 ⌘+Enter to send  ▶  │
└──────────────────────────────────────────────────────┘
```

#### Stage 5 — Validation theater

Click header `✓ Validate` → opens **FindingsDrawer** (right-slide, 480 px). NOT a toast-pass /
toast-fail.

```
┌─ Validate BRD ─────────────────────────────────────────────────── ✕ ─┐
│  3 findings to resolve before this BRD can be approved                │
│                                                                       │
│  ▸ Critical (1)                                                       │
│  ▾ Major (2)                                                          │
│     □ BR-007 has no objective trace                                   │
│        Suggested fix: link to one of [OBJ-1, OBJ-2, OBJ-3]            │
│        [accept fix] [jump to BR →] [edit manually]                    │
│     □ KPI-2 missing baseline                                          │
│        Suggested fix: AI inferred "0.4% currently"                    │
│        [accept fix] [edit manually]                                   │
│  ▸ Minor (0)                                                          │
│  ▸ Coverage / context (0) — every CB element is mapped ✓              │
│  ▸ Warnings (1) — not blocking                                        │
│     • App "NotifyService" is in scope but no BR traces back to it     │
│       [review →] [remove from scope]                                  │
│                                                                       │
│  ─────────────────────────────────────────────────────────────────    │
│             [  Validate (1 finding remaining)  ]                       │
│             (button disables when critical/major > 0)                  │
└───────────────────────────────────────────────────────────────────────┘
```

**Findings groups** (cross-ref §5.9 backend validators):

| Group | What goes here |
|-------|----------------|
| **Critical** | required-section missing entirely (e.g. zero objectives, zero BRs) |
| **Major** | BR/KPI/risk fails its per-row contract (no trace, no AC, no baseline, etc.) |
| **Minor** | per-unit completeness < 90 (soft heuristic) |
| **Coverage / context** | uncovered CB rows, stale source set, orphan trace refs |
| **Warnings** | non-blocking advisories (in-scope app with no traces, etc.) |

**Interactions per finding:**
- `[jump to row →]` smooth-scrolls content + section-rail dot pulses red; finding row stays
  visible.
- `[accept fix]` → `api.artifacts.acceptFix(projectId, "brd", finding)` server-side via the
  row-edit endpoint; finding collapses with "✓ Fixed" inline label; header count decrements.
- `[edit manually]` → opens existing `RowEditModal` pre-filtered to the offending field.

**Success state:** when 0 findings remain, button label changes to `✓ Validate BRD`. Click →
transitions to validated state with `BrdConfettiBurst` (6 particles, 600 ms, accent palette).

**Override (platform_admin only):** tiny `[override blocking findings]` link bottom-left of drawer
opens a confirm dialog requiring a typed reason; logged as `brd.validate.override` audit event.

#### Stage 6 — Validated state (post-validate)

Same shell, but:
- Header status badge: `Validated ✓` (emerald) + version tag `v1 · 2 mins ago`.
- All rows locked-by-default (rail lock icons light up). Editing requires "Edit validated BRD"
  confirm → switches artifact back to `in_interview` (audited).
- Header `⤓ Export` becomes primary action — menu: `Markdown` (live), `DOCX` (coming soon),
  `Copy public link` (coming soon).
- Workspace card BRD chip flips to `Validated ✓`; FRS chip flips to "disabled — BRD validated ✓".

### 3.5 Cross-cutting components (build once, reuse everywhere)

#### 3.5.1 `BrCard` — the centerpiece object

File: `frontend/app/components/brd/BrCard.tsx`. Renders one `brd_business_requirements` row.
Variants (same component, prop override): `br | objective | risk | kpi`.

**Anatomy:**

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ BR-001                       ┌─ MoSCoW pill ┐    [edit] [⤴ history] [✦] [⋮]            │
│ ★ Reconcile premium collections within 7 days of receipt                                 │
│ ──────────────────────────────────────────────────────────────────────────────────────  │
│ ▾ Description       …text…                                                              │
│ ▾ Acceptance criteria                                                                    │
│   • Given a premium received   When ≥ 7 days have passed   Then …                       │
│ ▾ Traces (3 outward, 4 within-BRD)                                                       │
│   [← CB · capability: Automated reconciliation]                                          │
│   [← PayHub · capability: Multi-rail settlement]                                         │
│   [← Press-Release.pdf §Problem Overview (p.2)]                                          │
│   Within-BRD: [→ OBJ-1] [→ OBJ-2] [→ STK-1] [→ STK-3]                                  │
│ ▾ Quality           AI-generated · confidence high · completeness 96%                    │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

**States (border / bg-tinted left-bar):**

| State | Left bar | Treatment |
|-------|----------|-----------|
| AI-generated (default) | none / neutral | `bg-[var(--bg-surface)]` + neutral border |
| Human-edited | `--human-edited` teal | subtle `--human-edited-bg` tint |
| Locked | `--status-warning` amber | amber Lock chip in header |
| Validation-flagged | `--status-danger` red | small "1 finding" chip linking to drawer |
| Stale (broken trace) | `--status-danger` red | strike-through trace chip |

**Priority pill (MoSCoW):**

| Priority | Classes |
|----------|---------|
| `must` | `bg-danger-bg text-danger border-danger-border` |
| `should` | `bg-warning-bg text-warning border-warning-border` |
| `could` | `bg-info-bg text-info border-info-border` |
| `wont` | `bg-elevated text-tertiary border-default` (struck-through) |

**Interactions:**
- Whole card click expands/collapses; sub-sections (`Description`, `Acceptance`, `Traces`,
  `Quality`) toggle independently.
- Action bar appears on hover only (`opacity-0 group-hover:opacity-100`).
- Drag-and-drop reorder within section (`@dnd-kit/sortable` — see §10 open Q's; or skip for v1).
- Double-click BR-ID → rename (validation: matches `^BR-\d{3,}$`; collision check).

**Variants:**
- `<BrCard variant="objective">` renders `brd_objectives` (statement / category / priority / owner)
- `<BrCard variant="risk">` adds severity × likelihood matrix mini-viz in the header
- `<BrCard variant="kpi">` splits the body into Baseline / Target / Timeframe / Data source

#### 3.5.2 `TraceChip` + Trace Hover Pop-out

File: `frontend/app/components/brd/TraceChip.tsx`.

**Chip variants** (colour-coded by source kind via 2-px left border):

| Source kind | Visual |
|-------------|--------|
| `cb_row` | `bg-accent-subtle text-accent-deep border-l-2 border-accent` |
| `app_fact` | `bg-app-brain-bg text-app-brain border-l-2 border-app-brain` |
| `doc_section` | `bg-status-info-bg text-status-info border-l-2 border-status-info` |
| `discover_qa` | `bg-ai-generated-bg text-ai-generated border-l-2 border-ai-generated` |
| stale (any kind) | `text-danger line-through` overlay |
| `confidence: "low"` | tiny dotted underline; tooltip "AI inferred — verify" |

**Hover popover** (Radix Popover, 300 ms delay):

```
┌─────────────────────────────────────────────────────┐
│ From Concept Brief                                   │
│ ───────────────────────────────────────────────────  │
│ Capability · "Automated reconciliation"              │
│                                                      │
│  Reconcile premium collections, agent commissions,  │
│  and refunds via an audit-tracked ledger; flag       │
│  exceptions for manual review.                       │
│                                                      │
│ [open in Concept Brief →]   [unlink trace]          │
└─────────────────────────────────────────────────────┘
```

Click chip → pins source in `TraceDrawer` (right side, stacks multiple pinned sources).

#### 3.5.3 `SourceStrip` + `SourceStripRow`

Files: `frontend/app/components/brd/SourceStrip.tsx`, `SourceStripRow.tsx`. Specced visually in
§3.4.4.a. Props for `SourceStripRow`:

```typescript
interface Props {
  layer: 'apps' | 'docs' | 'cb'
  state: 'ready' | 'pending' | 'stale'
  count: number
  subtitle: string
  onExpand: () => void
  children: React.ReactNode  // collapsible body content
}
```

#### 3.5.4 `CbEchoStrip`

File: `frontend/app/components/brd/CbEchoStrip.tsx`. Single-row collapsible band; specced
§3.4.4.b. Pulls from `useArtifact(projectId, "concept-brief").detail.sections` (CB current rows).

#### 3.5.5 `SectionRail`

File: `frontend/app/components/brd/SectionRail.tsx`. Sticky vertical nav; specced §3.4.4.c.
Status dots driven by `unit_status[unit].completeness` + findings count + locked-rows count.

#### 3.5.6 `FindingsDrawer`

File: `frontend/app/components/brd/FindingsDrawer.tsx`. Right-slide drawer; specced §3.4.5. Internal
state: `expandedGroups: Set<FindingGroup>`. SWR-mutates `useArtifact` on accept-fix.

#### 3.5.7 `UnitDagViz`

File: `frontend/app/components/brd/UnitDagViz.tsx`. Static-layout SVG DAG; specced §3.4.3. Inputs:
the BRD manifest (units + depends_on from `lib/brd-manifest.ts`) + a `unit_state` map. Hand-laid
node positions (manifest is small, 24 units; no graphviz needed). Animations via framer-motion.

#### 3.5.8 `DocReadinessPanel`

File: `frontend/app/components/brd/DocReadinessPanel.tsx`. Shared by:
- Stage 1 empty-state blocker panel.
- Builder header alert when source set changes post-generation.

Polls `useBrdReadiness(projectId)` every 3 s; stops when all done or after 10 minutes (safety
fuse).

#### 3.5.9 `CoverageGalaxy`

File: `frontend/app/components/brd/CoverageGalaxy.tsx`. SVG ribbon diagram CB column ↔ BRD column.
~120 LOC. Iterates `BRD_CONTEXT_PROJECTION` from `lib/brd-manifest.ts`.

```
┌─ CB → BRD Coverage Map ──────────────────────────────────────────── ✕ ─┐
│                                                                          │
│   CONCEPT BRIEF                              BUSINESS REQUIREMENTS       │
│   ─────────────────                          ────────────────────        │
│   ● business_context        ─────────────►   §1 Business Context  ✓     │
│   ● problem_statement       ─────────────►   §2 Problem  ✓              │
│   ● value_hypothesis_if/then ──────╮         §3 Objectives  ✓           │
│   ● outcomes (3)            ──────┼────►     §3 Objectives  ✓           │
│   ● outcomes (3)            ──────┴────►     §12 KPIs  ✓                │
│   ● metrics (2)             ─────────────►   §12 KPIs  ✓                │
│   ● capabilities (5)        ──────╮          §7 BR  ✓                   │
│   ● capabilities (5)        ──────┴────►     §5 Scope  ✓                │
│   ● scope_items.in_scope    ─────────────►   §5 Scope  ✓                │
│   ● scope_items.out_of_scope ────────────►   §10 Risks  ✓               │
│   ● scope_items.assumption  ─────────────►   §9 Assumptions  ✓          │
│   ● milestones              ─────────────►   §11 Phasing  ✓             │
│   ● context_map (6 fixed)   ─────────────►   §1–§4 (various)  ✓         │
│   ● discover_qa (14)        ─────────────►   §13 Open Q's + others  ✓   │
│                                                                          │
│   All 14 CB elements covered — every populated CB row maps to ≥ 1 BR    │
│   unit. (Uncovered CB rows would appear in red on the left.)             │
└─────────────────────────────────────────────────────────────────────────┘
```

**Failure state:** uncovered CB row glows `--status-danger`; right column shows `?` placeholder
with `[suggest a target section]` (manual override → adds a soft mapping to user's chosen unit,
audited).

#### 3.5.10 `BrdEmptyState`

File: `frontend/app/components/brd/BrdEmptyState.tsx`. Specced §3.4.Stage 1. Composes grounding
badge + AI-Enhance composer + `DocReadinessPanel` + CTA.

#### 3.5.11 `BrdConfettiBurst`

File: `frontend/app/components/brd/BrdConfettiBurst.tsx`. 6-particle CSS-only burst on successful
validate. Honours `useReducedMotion()`. No new deps.

#### 3.5.12 `TraceDrawer`

File: `frontend/app/components/brd/TraceDrawer.tsx`. Right-side pinned drawer stacking multiple
pinned sources (from clicking trace chips). Each pinned card has `[unpin]` and `[open in source →]`.

### 3.6 Animations + micro-interactions

All animations respect `useReducedMotion()` (per `frontend/CLAUDE.md`).

| Where | Animation | Duration / curve |
|-------|-----------|------------------|
| Section rail dot ○ → ◐ → ● | morph + colour | 280 ms ease-out |
| Section anchor scroll | smooth-scroll + title pulse | 600 ms ease-in-out |
| Trace chip hover popover | scale 0.96 → 1, fade 0 → 1 | 180 ms ease-out (Radix default) |
| BR card expand/collapse | height auto + content fade | 220 ms ease-out (accordion-down keyframe) |
| Generation theater ○ → ◐ → ✓ | colour + scale 1 → 1.08 → 1 | 300 ms ease-out per step |
| Validate-success confetti | 6 particles | 600 ms; reduced-motion skip |
| Source-strip count pulse on change | scale 1 → 1.15 → 1 | 240 ms ease-out |
| Findings drawer slide-in | translate-x-full → 0 | 280 ms ease-out |
| Toast notifications | sonner defaults | (existing) |

**Hover micro-interactions:**
- BR card hover lifts shadow `--shadow-card` → `--shadow-md`; action bar fades in
  (`opacity-0 group-hover:opacity-100`).
- Trace chip hover tints background 1 stop deeper.
- Section rail row hover → tooltip with section name (Radix Tooltip, 200 ms delay).

### 3.7 Edge cases (designed, not afterthought)

| Scenario | UX |
|----------|----|
| Generation Celery task crashes mid-way | Theater pops `⚠ Generation interrupted` overlay with "Resume from §K" + "Restart". Orchestrator can resume because rows are persisted per-unit. |
| Validate finds 0 findings on first try | Confetti + "Wow, BRD is clean on first run" inline note. (Surprise & delight; honest because it's rare.) |
| User opens BRD before CB validated | Friendly redirect screen: "BRD is locked while the Concept Brief is still in interview. Open Concept Brief →" with button. |
| All docs failed indexing | CTA stays disabled; doc rows red with "Re-upload" and one-line hint per doc. |
| Trace chip's source deleted post-generation | Chip renders red strike-through; hover popover shows "Source no longer exists. [remove trace] [re-link to another source]". Validate surfaces as finding. |
| User regenerates a unit while another regen running | Active scope chip in composer shows both targets stacked; orchestrator queues them. UI shows two pulsing dots on rail. |
| Network drops mid-typing in composer | Composer textarea persists in local state; sonner toast "Reconnecting…"; auto-retries on `online` event. |
| Large BR row (1000-char desc, 20 AC bullets) | Card body `max-h-[40vh] overflow-y-auto` with gradient at bottom edge. "Open full" → `RowEditModal`. |
| Empty `acceptance_criteria` | Card shows red "AC missing" chip + CTA "AI suggest from description". Validate surfaces. |
| Same `objective_id` referenced by 30 BRs | Within-BRD chip on BR card just shows `[→ OBJ-3 +29 more]`; click → side panel listing every BR tracing to OBJ-3. |
| Bundle build fails (rare DB issue) | Toast + offer "Retry" / "Open support ticket". Stays in current state. |
| Source list changes during builder session | SWR refreshes Source Strip; banner "Source set changed — last gen out of sync" + regenerate CTA. |

### 3.8 Responsive breakpoints

- **`lg+` (1024 px+):** two-column layout per §3.3.
- **`md` (768–1023 px):** Section Rail collapses to a fly-out hamburger; Three-Source Strip stays
  full-width but inline bodies become drawers.
- **`< md`:** single-column with tab switcher (`Thread · Document · Sources`); composer = bottom
  sheet (slide-up). Section Rail = sticky chip carousel at top of Document tab. Mirrors
  `ThreePanel.tsx`'s existing mobile fallback.

### 3.9 Accessibility

- All interactive chips are real `<button>`s with discernible names; trace chips read out
  "Trace to Concept Brief capability Automated reconciliation, press Enter to expand".
- Section rail uses `aria-current="location"` on the active row.
- Keyboard shortcuts (discoverable via `?` → command palette using shadcn `Command`):
  - `g s` → Section Rail focus
  - `g t` → thread focus
  - `/` → composer focus
  - `Esc` → close any drawer/popover
- Focus rings use `--accent-ring` (`rgba(47,107,76,0.30)`) — already in tokens.
- Reduced-motion paths defined per §3.6.

### 3.10 Visual style — verbatim tokens to use

All in `app/globals.css`; no new tokens to add.

| Use | Token / utility |
|-----|-----------------|
| Card base | `.card` (`rounded-xl border border-default bg-surface shadow-card`) |
| Primary CTA | `<Button variant="default">` (charcoal `--primary`) |
| Accent CTA / chip | `bg-accent-subtle text-accent border-accent-subtle` |
| BR-ID badge | `bg-elevated text-text-secondary border-border-default text-[10px] font-semibold rounded` |
| Status dots | `--status-success` / `--status-warning` / `--status-danger` |
| Trace chip — CB | `bg-accent-subtle text-accent-deep border-l-2 border-accent` |
| Trace chip — App | `bg-app-brain-bg text-app-brain border-l-2 border-app-brain` |
| Trace chip — Doc | `bg-status-info-bg text-status-info border-l-2 border-status-info` |
| Trace chip — Discover | `bg-ai-generated-bg text-ai-generated border-l-2 border-ai-generated` |
| Section-rail active | `bg-accent-subtle` + `border-l-2 border-accent` (mirrors AppShell nav) |
| Locked indicator | `<Lock size={11}>` + `text-warning` |
| Confidence | `<Badge variant={CONF_VARIANT[c]}>` (reused from `ArtifactBuilderPanel`) |
| Completeness % | `completenessColor(pct)` helper (reused) |
| Source-strip rules | 2-px left borders: `--app-brain` / `--status-info` / `--accent` |
| Confetti | CSS-only 6-span burst (transform + opacity); no new dep |

**Typography:**
- Section title: `text-base font-semibold text-text-primary`
- Card title: `text-sm font-semibold text-text-primary`
- Body: `text-sm text-text-primary` / `text-xs text-text-secondary`
- Metadata: `text-[10px] uppercase tracking-wider text-text-tertiary`
- BR-ID: `text-[11px] font-semibold`

---

## 4 · Backend deep dive — Project Context Bundle (cross-module foundation)

### 4.1 Module layout

```
backend/app/services/context/
├── __init__.py
├── project_context.py   # gather_project_context() entry-point, ProjectContextBundle, BundleReadiness
├── app_layer.py         # AppLayer: wraps app_context + wiki_grounding into typed shape
├── docs_layer.py        # DocsLayer: breadth (inventory) + depth (tree_search)
├── cb_layer.py          # CbLayer: full Concept Brief extraction
├── projection.py        # project_for_unit() per-unit narrowing
└── coverage.py          # CoverageReport + static contract check
```

### 4.2 `ProjectContextBundle` dataclass

```python
@dataclass
class AppFactBlock:
    app_id: UUID; app_name: str; tier: str | None
    impact_note: str | None
    facts_by_kind: dict[str, list[AppFactRow]]   # capability / constraint / limitation / integration / gotcha
    wiki_concepts: list[AppWikiConceptRow]       # ALL — budgeted only at render time

@dataclass
class AppLayer:
    apps: list[AppFactBlock]      # one per ProjectApp.included
    formatted: str                # [A#] tagged: per-app block + grouped facts + concepts

@dataclass
class DocOutlineNode:
    node_id: str; title: str; summary: str
    page_start: int; page_end: int
    children: list["DocOutlineNode"]

@dataclass
class DocInventoryEntry:
    document_id: UUID; doc_name: str; mime: str; page_count: int
    indexing_status: str          # must be "done" to be in the bundle
    outline: list[DocOutlineNode] # full PageIndex tree (root + summarised nodes) — every doc
    included: bool                # mirror of artifact_sources.included for the requesting brief

@dataclass
class DocsLayer:
    docs: list[DocInventoryEntry]      # EVERY included, indexed project doc — breadth
    sections: list[RetrievedSection]   # per-unit tree_search hits — depth
    formatted_inventory: str           # [DOC#] tagged: one block per doc with outline
    formatted_sections: str            # [D#] tagged: doc + section + page range
    pending_docs: list[DocPendingEntry] # any included doc whose indexing_status != "done"

@dataclass
class CbLayer:
    text_blocks: dict[str, str]
    context_map: list[CbContextMapRow]
    outcomes: list[CbOutcomeRow]
    metrics: list[CbMetricRow]
    capabilities: list[CbCapabilityRow]
    scope_items: list[CbScopeItemRow]
    milestones: list[CbMilestoneRow]
    enhanced_brief: str | None
    original_brief: str | None
    discover_qa: list[CbDiscoverQuestionRead]
    cb_snapshot_key: str
    formatted: str                # [CB#] tagged

@dataclass
class BundleReadiness:
    ok: bool
    pending_docs: list[DocPendingEntry]
    failed_docs:  list[DocPendingEntry]
    missing_apps: list[UUID]
    cb_validated: bool

@dataclass
class ProjectContextBundle:
    project: ProjectRead
    apps: AppLayer
    docs: DocsLayer
    cb: CbLayer | None
    generated_at: datetime
    snapshot_refs: dict[str, Any]    # {"cb": <key>, "doc_tree_shas": {...}, "app_fact_ids": [...]}
    coverage: CoverageReport
    readiness: BundleReadiness
```

### 4.3 Entry point

```python
async def gather_project_context(
    project_id: UUID,
    *,
    db: AsyncSession,
    include_cb: bool = True,
    include_apps: bool = True,
    include_docs: bool = True,
    docs_query: str | None = None,
    docs_top_k: int | None = None,
    artifact_document_id: UUID | None = None,
    require_full_corpus: bool = True,
) -> ProjectContextBundle: ...
```

### 4.4 Coverage contract

```python
@dataclass
class CoverageReport:
    cb_rows_total: int
    cb_rows_projected: int
    cb_uncovered: list[tuple[str, str]]       # (cb_table, row_key) not projected
    app_facts_total: int
    app_facts_projected: int
    doc_sections_total: int
    doc_sections_projected: int
    discover_qa_total: int
    discover_qa_projected: int
```

`coverage.py` exposes:
- `compute_coverage(bundle, projection_map) → CoverageReport`
- `validate_coverage_contract_static(projection_map, cb_schema) → None | RaisesAssertion` (called
  by CI test)

### 4.5 Per-unit projection

```python
@dataclass
class UnitContext:
    apps_context: str
    docs_inventory: str
    docs_sections: str
    cb_context: str
    discover_qa: list[DiscoverQuestionRead]
    traceability_seeds: list[TraceRef]

def project_for_unit(
    bundle: ProjectContextBundle,
    *,
    artifact_type: str,
    unit_key: str,
) -> UnitContext: ...
```

---

## 5 · Backend deep dive — BRD specifics

### 5.1 Data model — every BRD table

Add to `backend/app/models/artifact.py`. All tables include `VersionedRowMixin` (from E4a).

| Table | Typed columns | `row_key` |
|-------|---------------|-----------|
| `brd_text_blocks` | `field_key TEXT, text TEXT` | `field_key` (business_overview, strategic_alignment, current_situation, problem_statement, scope_boundaries, asis_summary, tobe_summary, business_rules, implementation_approach, qualitative_success) |
| `brd_drivers` | `text TEXT, kind TEXT` (regulatory\|competitive\|cost\|growth\|other) | ordinal `drv-1…` |
| `brd_problem_impact` | `area TEXT, description TEXT, magnitude TEXT, evidence TEXT` | ordinal `pi-1…` |
| `brd_objectives` | `statement TEXT, category TEXT, priority TEXT, owner TEXT` | natural `OBJ-1, OBJ-2…` (LLM-stable) |
| `brd_benefits` | `benefit TEXT, kind TEXT (financial\|operational\|customer\|strategic\|other), magnitude TEXT, timing TEXT, confidence TEXT` | ordinal `ben-1…` |
| `brd_stakeholders` | `group_name TEXT, role TEXT, responsibilities TEXT, influence TEXT (low\|medium\|high), engagement TEXT` | natural `STK-1…` |
| `brd_actors` | `persona TEXT, description TEXT, goals TEXT, pain_points TEXT, impact_of_change TEXT` | natural `ACT-1…` |
| `brd_scope_items` | `kind TEXT (in_scope\|out_of_scope), text TEXT` | `{kind}-{n}` |
| `brd_asis_steps` | `step_no INT, actor TEXT, description TEXT, inputs TEXT, outputs TEXT, pain_points TEXT` | `asis-{n}` |
| `brd_tobe_steps` | `step_no INT, actor TEXT, description TEXT, inputs TEXT, outputs TEXT, business_benefit TEXT` | `tobe-{n}` |
| `brd_business_requirements` | `title TEXT, description TEXT, objective_ids TEXT[], stakeholder_ids TEXT[], priority TEXT (must\|should\|could\|wont), acceptance_criteria TEXT` | natural `BR-001, BR-002…` |
| `brd_data_needs` | `domain TEXT, description TEXT, source_systems TEXT, consumers TEXT, quality_expectations TEXT` | ordinal `dn-1…` |
| `brd_reporting` | `name TEXT, purpose TEXT, audience TEXT, frequency TEXT, detail_level TEXT` | ordinal `rpt-1…` |
| `brd_assumptions` | `text TEXT, impact_if_false TEXT, owner TEXT` | natural `ASM-1…` |
| `brd_dependencies` | `name TEXT, kind TEXT (system\|team\|vendor\|external\|other), criticality TEXT, owner TEXT, notes TEXT` | natural `DEP-1…` |
| `brd_constraints` | `text TEXT, category TEXT, description TEXT, implication TEXT` | natural `CON-1…` |
| `brd_risks` | `description TEXT, cause TEXT, impact TEXT, likelihood TEXT, severity TEXT, mitigation TEXT, owner TEXT, status TEXT` | natural `RSK-1…` |
| `brd_issues` | `description TEXT, impact TEXT, workaround TEXT, owner TEXT, status TEXT` | natural `ISS-1…` |
| `brd_phasing` | `phase TEXT, description TEXT, target_dates TEXT, entry_criteria TEXT, exit_criteria TEXT` | natural `PH-1…` |
| `brd_change_mgmt` | `audience TEXT, change_impact TEXT, training_needs TEXT, channel TEXT, timing TEXT` | ordinal `cm-1…` |
| `brd_kpis` | `name TEXT, baseline TEXT, target TEXT, timeframe TEXT, data_source TEXT, notes TEXT` | natural `KPI-1…` |
| `brd_open_questions` | `text TEXT, owner TEXT, due_date DATE NULL, status TEXT` | natural `Q-1…` |
| `brd_decisions` | `decision TEXT, date DATE NULL, decision_makers TEXT, rationale TEXT, impact TEXT` | natural `DEC-1…` |
| `brd_references` | `kind TEXT, title TEXT, location TEXT, notes TEXT` | natural `REF-1…` |
| `brd_glossary` | `term TEXT, definition TEXT` | `term` slug (lowercased, kebab) |
| `brd_traceability` | `target_table TEXT, target_row_key TEXT, source_kind TEXT (cb_row\|app_fact\|doc_section\|discover_qa), source_ref TEXT, relation TEXT (derives_from\|constrained_by\|enabled_by\|informs\|annotates), excerpt TEXT, confidence TEXT (high\|medium\|low)` | composite slug `tr-{target_table}-{target_row_key}-{n}` |

**Notes:**
- `brd_business_requirements.objective_ids` / `.stakeholder_ids` use `ARRAY(String)`; soft within-BRD
  references validated by the orchestrator at write.
- `brd_traceability` is **outward** linkage (separate concept from within-BRD refs).

### 5.2 Migration `0018_brd_artifact.py`

`down_revision = "0017_cb_discover_questions"`. Mirror `0014_ask_sessions.py` / `0015_artifact_documents.py`
patterns.

**Block 1 — enum guards** (DO $$ … EXCEPTION WHEN duplicate_object):
- `brd_priority` (must|should|could|wont)
- `brd_risk_severity`, `brd_risk_likelihood` (low|medium|high)
- `brd_risk_status` (open|mitigated|accepted|closed)
- `brd_question_status` (open|answered|deferred)
- `brd_dependency_kind`, `brd_constraint_category`, `brd_driver_kind`
- `trace_source_kind` (cb_row|app_fact|doc_section|discover_qa)
- `trace_relation` (derives_from|constrained_by|enabled_by|informs|annotates)
- `trace_confidence` (high|medium|low)
- `ALTER TYPE artifact_type ADD VALUE IF NOT EXISTS 'brd'` (if not already present)

**Block 2 — discover-table rename:**
```sql
ALTER TABLE cb_discover_questions       RENAME TO artifact_discover_questions;
ALTER TABLE cb_discover_enhanced_briefs RENAME TO artifact_discover_enhanced_briefs;
-- rename indexes too
```

**Block 3 — DRY-loop create the 22 brd_* tables:**
```python
BRD_TABLES = [
    ("brd_text_blocks",         [("field_key", "TEXT NOT NULL"), ("text", "TEXT NOT NULL")]),
    ("brd_drivers",             [("text", "TEXT NOT NULL"), ("kind", "TEXT NOT NULL")]),
    # ... 19 more ...
    ("brd_traceability",        [
        ("target_table", "TEXT NOT NULL"),
        ("target_row_key", "TEXT NOT NULL"),
        ("source_kind", "trace_source_kind NOT NULL"),
        ("source_ref", "TEXT NOT NULL"),
        ("relation", "trace_relation NOT NULL"),
        ("excerpt", "TEXT"),
        ("confidence", "trace_confidence NOT NULL DEFAULT 'medium'"),
    ]),
]

for table_name, content_cols in BRD_TABLES:
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            row_key TEXT NOT NULL,
            version INT NOT NULL CHECK(version > 0),
            is_current BOOLEAN NOT NULL DEFAULT TRUE,
            is_locked BOOLEAN NOT NULL DEFAULT FALSE,
            status artifact_row_status NOT NULL DEFAULT 'active',
            source artifact_row_source NOT NULL,
            created_by UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            {", ".join(f"{n} {t}" for n, t in content_cols)}
        );
        CREATE UNIQUE INDEX IF NOT EXISTS ix_{table_name}_doc_rowkey_v ON {table_name} (document_id, row_key, version);
        CREATE UNIQUE INDEX IF NOT EXISTS ix_{table_name}_doc_current ON {table_name} (document_id, row_key) WHERE is_current;
        CREATE INDEX IF NOT EXISTS ix_{table_name}_doc ON {table_name} (document_id) WHERE is_current;
    """)
```

`downgrade()` drops in reverse + `DROP TYPE IF EXISTS …`.

### 5.3 Generation units + DAG

Manifest `backend/app/services/artifacts/manifest/brd.py`.

```
business_context      → []
problem               → [business_context]
objectives            → [problem]                            (consumes CB outcomes — §5.5)
stakeholders          → [problem, business_context]
actors                → [stakeholders]
scope                 → [objectives, problem]
asis_process          → [problem, actors]
tobe_process          → [asis_process, scope, objectives]
business_rules        → [tobe_process]
business_requirements → [objectives, stakeholders, tobe_process, scope]   ★ keystone
data_needs            → [business_requirements]
reporting             → [objectives, business_requirements]
benefits              → [objectives, scope]
assumptions           → [scope, business_requirements]
dependencies          → [scope, business_requirements]
constraints           → [scope]
risks                 → [objectives, scope, business_requirements]
issues                → [problem, asis_process]
implementation_approach → [scope, business_requirements]
phasing               → [implementation_approach, business_requirements]
change_management     → [stakeholders, tobe_process, phasing]
kpis                  → [objectives, benefits]
qualitative_success   → [objectives]
compendium            → [business_requirements, risks]    (suggests open Q's / refs / glossary)
```

`generate_all` topologically sorts; independent peers parallelise (asyncio gather with bounded
semaphore, `max_concurrency=4`).

### 5.4 Manifest entry shape

```python
@dataclass
class UnitSpec:
    unit_key: str
    label: str
    section_no: int            # 1..14
    section_title: str
    output_tables: list[str]   # tables this unit writes
    primary_table: str          # for trace target binding
    depends_on: list[str]
    unit_instruction: str       # short overlay (_BRD_SCAFFOLD added in dspy_artifacts.py)
    discover_keys: list[str]
    docs_query: str             # for per-unit tree_search
    validate_checks: list[str]  # named checks to apply (§5.9)

BRD_UNITS: list[UnitSpec] = [ ... 24 entries ... ]
```

### 5.5 `BRD_CONTEXT_PROJECTION` — full coverage map

Lives in `manifest/brd.py`. Every populated CB element must appear ≥ 1 time. Lint test
`test_brd_coverage_contract.py` enforces this.

| CB source | BRD consumer unit(s) | Relation |
|-----------|----------------------|----------|
| `cb_text_blocks.business_context` | `business_context` | derives_from |
| `cb_text_blocks.problem_statement` | `problem` | derives_from |
| `cb_text_blocks.value_hypothesis_if` / `_then` | `objectives`, `benefits` | informs |
| `cb_context_map.business_unit` | `stakeholders`, `business_context` | constraint |
| `cb_context_map.new_channel` | `scope`, `business_requirements` | informs |
| `cb_context_map.customer_segments` | `actors`, `stakeholders` | informs |
| `cb_context_map.current_gap` | `problem`, `asis_process` | informs |
| `cb_context_map.strategic_driver` | `business_context`, `objectives` | informs |
| `cb_context_map.engagement_goal` | `tobe_process`, `change_management` | informs |
| `cb_outcomes.*` | `objectives`, `benefits`, `kpis` | derives_from |
| `cb_metrics.*` | `kpis`, `qualitative_success` | derives_from |
| `cb_capabilities.*` | `business_requirements`, `scope` | derives_from |
| `cb_scope_items.in_scope` | `scope` | derives_from |
| `cb_scope_items.out_of_scope` | `scope` | derives_from |
| `cb_scope_items.assumption` | `assumptions` | derives_from |
| `cb_milestones.*` | `phasing`, `change_management` | derives_from |
| `cb_discover_questions.*` (answered) | `compendium`, `assumptions`, `dependencies` | annotates |
| `cb_discover_enhanced_briefs.enhanced_brief` | `business_context` | annotates |
| `cb_gate_criteria.*` | (not projected — metadata only) | — |

### 5.6 App Brain + document coverage (BRD-side)

- Every **app** in `ProjectApp.included` surfaced to at least: `business_context`, `scope`,
  `business_requirements`, `risks`, `dependencies`.
- Every app-fact **kind** has ≥ 1 consumer:
  - capability + integration → `business_requirements`, `scope`, `tobe_process`
  - constraint + limitation → `risks`, `constraints`, `assumptions`, `business_requirements`
  - gotcha → `risks`, `issues`
- Every BRD unit consuming docs receives both `formatted_inventory` (breadth) AND
  `formatted_sections` (per-unit depth).

### 5.7 DSPy units — `_BRD_SCAFFOLD` + per-unit overlays

File: `backend/app/services/skills/dspy_artifacts.py`.

#### 5.7.1 Shared scaffold — `_BRD_SCAFFOLD`

Prepended to every BRD unit Signature docstring:

```
You are generating one section of a Business Requirements Document (BRD). The BRD describes
**what** the business needs, never **how** it will be technically built — output stays
solution-agnostic (SKILL.md "Best Practices").

# Inputs the unit sees
- apps_context     — every fact of every kind for every in-scope app, [A#] tagged.
- docs_inventory   — outline (titles + summaries + page ranges) of every included project doc, [DOC#] tagged.
- docs_sections    — depth-retrieved sections relevant to THIS unit, [D#] tagged.
- cb_context       — the validated Concept Brief slice for THIS unit, [CB#] tagged. Treat the CB
                     as the BRD's **business intent** — the BRD operationalises it; it does not
                     contradict it without an explicit open_questions entry.
- discover_qa      — answered Q&A from the BRD Discover phase for THIS unit, [Q#] tagged.
- qa_pairs         — clarification Q&A appended after generation began.
- upstream         — current rows of the BRD units this one depends on (within the BRD).
- current_rows     — the current rows of THIS unit (with their stable row_keys).
- locked_rows      — rows the user has edited and locked; **reproduce them verbatim**.
- traceability_seeds — the set of source_ref values you are permitted to cite for this unit.

# Output rules (non-negotiable)
1. **Solution-agnostic.** Describe WHAT the business needs and the to-be state — not the technology.
2. **Cite explicitly.** Every claim worth tracing carries inline `[CB#…]` / `[A#…]` / `[D#…]` /
   `[Q#…]` markers.
3. **Conflict resolution (SKILL.md):** User statements > recent project documents > older
   references. SpecForge extension: app-brain facts sit lowest. On conflict, emit `open_questions`.
4. **Stable row keys.** For unchanged concepts, keep `row_key` from `current_rows`. Mint new keys
   only for genuinely new rows. Never reuse a `status='removed'` key.
5. **Reproduce `locked_rows` verbatim** — no rephrasing.
6. **Emit traces.** For every output row, populate `traces: list[TraceRef]` with source_refs from
   `traceability_seeds` — never invent. `traces=[]` only with an `open_questions` entry explaining.
7. **Don't fabricate.** Silent inputs → `open_questions` row tagged `field=<missing-field>`.
8. **Register.** Business prose; present tense for as-is, future-conditional for to-be;
   third-person; no hedging; no marketing.
9. **Build on upstream, don't restate it.** Reference by row_key.
```

#### 5.7.2 Per-unit overlays (5 representative; the remaining 19 follow the same shape)

**`business_context`** (§1):
> Compose: 2–4 paragraph business overview, 2–3 sentence strategic-alignment statement, ≥ 3 drivers
> categorised as regulatory|competitive|cost|growth|other. Seed from
> `cb_context.text_blocks[business_context]`; expand with framing from `docs_inventory` and
> `apps_context`. Each driver carries ≥ 1 trace.

**`objectives`** (§3.1):
> Generate 3–7 BRD objectives. Each row: single-sentence `statement`, `category` ∈
> {operational|financial|customer|compliance|strategic}, `priority` ∈ {must,should,could}, `owner`
> drawn from `cb_context.context_map.business_unit` or discover_qa. **Every objective traces to ≥ 1
> `cb_outcomes` row OR `cb_value_hypothesis_*` blocks** — this is how BRD inherits CB intent.
> (SKILL.md: "Trace every requirement to an objective.")

**`business_requirements`** (§7 — keystone):
> Generate the full BR table. Each row must satisfy SKILL.md's validate checklist by construction:
> - `row_key` matches `^BR-\d{3,}$` starting at `BR-001`.
> - `title` — concise noun phrase, ≤ 12 words.
> - `description` — one **testable** sentence using *must* / *shall* / *will* with a measurable
>   predicate (deadline, threshold, observable state).
> - `objective_ids` — ≥ 1 entry, each in `upstream.brd_objectives.row_key`.
> - `stakeholder_ids` — ≥ 1 entry, each in `upstream.brd_stakeholders.row_key`.
> - `priority` ∈ {must,should,could,wont} (MoSCoW).
> - `acceptance_criteria` — Given-When-Then bullet list, ≥ 1 line per BR.
> - `traces` — ≥ 1 outward trace per BR.
>
> Every populated `cb_capabilities` row yields ≥ 1 BR; if intentionally deferred, emit
> `open_questions` explaining (closes §5.4 CB-coverage loop).

**`risks`** (§10.1):
> Generate **business** risks (not technical — those belong to FRS). Each row: `description`,
> `cause`, `impact`, `likelihood`, `severity`, **non-empty `mitigation`**, `owner`. Anchor in:
> - `cb_scope_items.out_of_scope` (what we're NOT doing → risk)
> - app `constraint` / `limitation` / `gotcha` facts (technical reality → business risk)
> - `cb_metrics` (KPI thresholds → risk of missing them)

**`kpis`** (§12.1):
> Generate ≥ 1 KPI per measurable objective. Each row: `name`, `baseline` (quantified current),
> `target` (quantified desired), `timeframe` (e.g. '90 days post-launch'), `data_source`, `notes`.
> **Every KPI traces to ≥ 1 `cb_metrics` row** — if a quantifiable CB metric has no KPI, emit
> `open_questions`. (SKILL.md: "KPIs have baselines, targets, and timeframes.")

#### 5.7.3 SKILL.md → prompt mapping (auditable lineage)

| SKILL.md rule | Where it lands |
|---------------|-----------------|
| "Build iteratively" | Discover Q&A is **per-unit** via `UNIT_DISCOVER_MAP`; each unit sees only its answers |
| "Solution-agnostic — what not how" | Scaffold rule #1 + rule #8 (register); overlay restates where ambiguity likely |
| "Trace every requirement to an objective" | `objective_ids` (≥1) + `stakeholder_ids` (≥1) are typed fields; validate §5.9.B re-checks |
| "Document both current and future state" | Two distinct units `asis_process` + `tobe_process`; manifest forces ordering |
| "User > Recent docs > Older refs" | Scaffold rule #3; discover answers override docs/apps; conflict → `open_questions` |
| "BR-001 ID, testable, linked objective, stakeholders, AC, priority" | `business_requirements` overlay enumerates every field; validate §5.9.B re-checks |
| "KPIs have baselines, targets, timeframes" | `kpis` overlay names them required; validate §5.9.C re-checks |
| "Risks identified with mitigations" | `risks` overlay requires non-empty `mitigation`; validate §5.9.D re-checks |
| Question states ❓✅❌ + composite IDs | Lives in Discover UI (E5 pattern); not in DSPy prompts |
| Output modes (summary/section/full/diff) | Lives at API/FE layer; not in units |

#### 5.7.4 Row Pydantic models with `traces`

Every row model gains optional `traces: list[TraceRef]`:

```python
class TraceRef(BaseModel):
    source_kind: Literal["cb_row","app_fact","doc_section","discover_qa"]
    source_ref:  str
    relation:    Literal["derives_from","constrained_by","enabled_by","informs","annotates"]
    excerpt:     str = Field(max_length=240)
    confidence:  Literal["high","medium","low"] = "medium"

class BusinessRequirementRow(BaseModel):
    row_key: str = Field(pattern=r"^BR-\d{3,}$")
    title: str
    description: str
    objective_ids: list[str]
    stakeholder_ids: list[str]
    priority: Literal["must","should","could","wont"]
    acceptance_criteria: str
    traces: list[TraceRef] = []
```

### 5.8 BRD Discover catalog — full 18-question table

File: `backend/app/services/artifacts/discover_catalog.py`.

| Key | Category | Question | Primary sources |
|-----|----------|----------|-----------------|
| 1a | initiative | Initiative name (working title for the BRD)? | project + CB |
| 1b | initiative | Concise restatement of the business problem this BRD solves | CB.problem_statement + brief |
| 1c | initiative | Primary business driver — regulatory, competitive, cost, growth? | CB + brief + docs |
| 1d | initiative | Initiative type — process change, system implementation, organizational, mixed? | brief |
| 2a | objectives | Top 3–5 measurable objectives this BRD must deliver | CB.outcomes + brief + docs |
| 2b | objectives | Which existing KPIs are in scope as baselines? | CB.metrics + app_brain.KPIs |
| 2c | objectives | What benefits are expected (financial / operational / customer / strategic)? | brief + docs |
| 3a | stakeholders | Executive sponsor + accountable owner | project + brief |
| 3b | stakeholders | Most-impacted user groups / personas | app_brain users + docs |
| 3c | stakeholders | Stakeholder groups that must approve the BRD | brief + project members |
| 4a | processes | Briefly describe the current (as-is) process and its pain points | docs + app_brain.gotchas |
| 4b | processes | Briefly describe the desired (to-be) process | brief + CB.capabilities |
| 4c | processes | Material business rules / policies that constrain the to-be | docs + app_brain.constraints |
| 5a | scope | Items explicitly **out of scope** for this BRD | brief |
| 5b | scope | Major assumptions / dependencies / constraints | brief + docs + app_brain |
| 6a | risks | Top business risks if this initiative fails or is delayed | brief + docs |
| 7a | delivery | Known milestones / target dates / phasing constraints | brief + project.go_live_date |
| 7b | delivery | Change-management considerations (training, comms, rollout) | brief + app_brain |

**Per-unit map:**
```python
UNIT_DISCOVER_MAP_BRD = {
  "business_context":      ["1a","1b","1c","1d"],
  "problem":               ["1b","1c","4a"],
  "objectives":            ["2a","2c"],
  "stakeholders":          ["3a","3b","3c"],
  "actors":                ["3b"],
  "scope":                 ["5a","5b"],
  "asis_process":          ["4a"],
  "tobe_process":          ["4b","4c"],
  "business_rules":        ["4c"],
  "business_requirements": ["2a","4b","5a","5b"],
  "assumptions":           ["5b"],
  "dependencies":          ["5b"],
  "constraints":           ["5b"],
  "risks":                 ["6a","5b"],
  "kpis":                  ["2b","2c"],
  "benefits":              ["2c"],
  "phasing":               ["7a"],
  "change_management":     ["7b","3b"],
}

BRD_PROJECT_PREFILL = {
    "1a": lambda p: f"{p.name} — Business Requirements Document",
    "7a": lambda p: p.go_live_date.isoformat() if p.go_live_date else "",
}
```

### 5.9 Validators — §8.1 A–G full checklist

File: `backend/app/services/artifacts/validators/brd.py`. Each check returns
`(group, ok, finding, suggested_fix)`:

**A. Required sections complete (existence):**
- `brd_text_blocks` has non-trivial entries for `business_overview`, `problem_statement`,
  `current_situation` (≥ 200 chars combined per row).
- `brd_drivers ≥ 1`; `brd_objectives ≥ 1`; `brd_stakeholders ≥ 1`; `brd_actors ≥ 1`.
- `brd_scope_items` has both `in_scope ≥ 1` AND `out_of_scope ≥ 1`.
- `brd_business_requirements ≥ 1`.

**B. BR quality (per row):**
- `row_key` matches `^BR-\d{3,}$`.
- `title` non-empty; `description` ≥ 1 testable sentence (heuristic: presence of *must/shall/will* +
  measurable predicate).
- `objective_ids` ⊆ current `brd_objectives.row_key` AND ≥ 1.
- `stakeholder_ids` ⊆ current `brd_stakeholders.row_key` AND ≥ 1.
- `priority ∈ {must, should, could, wont}`.
- `acceptance_criteria` non-empty AND looks like a list / GWT (≥ 1 line starting `-`, `*`, `1.`,
  `Given`).

**C. KPIs:**
- If any rows exist → each row has `baseline`, `target`, `timeframe` non-empty.
- Soft gate (warning): `brd_objectives ≥ 1` AND `brd_kpis = 0` → "BRD validated with no KPIs".

**D. Risks:**
- For every row: `mitigation` non-empty; `severity, likelihood ∈ {low,medium,high}`.

**E. Within-BRD trace integrity:**
- No `brd_business_requirements.objective_ids` entry points at a `status='removed'` objective.
- No `brd_kpis` references an objective by name that no current `brd_objectives.row_key` row
  matches.

**F. Per-unit completeness:**
- Every unit has `unit_status[unit_key].completeness ≥ 90`.

**G. Coverage + outward traceability:**
- `bundle.coverage.cb_uncovered == []`.
- Bundle readiness at the time of last generation matched the **current** `artifact_sources` set.
- **Every `brd_business_requirements` row has ≥ 1 `brd_traceability` link** (mandatory).
- **Every `brd_kpis` row has ≥ 1 trace** (typically to `cb_metrics`).
- **Every `brd_objectives` row has ≥ 1 trace** (typically to `cb_outcomes`).
- **Every `brd_risks` row has ≥ 1 trace** (CB out_of_scope / app constraint|limitation|gotcha).
- For every `brd_traceability` row, `source_ref` resolves in pinned bundle (orphan ref → finding).
- Soft check (warning): every `ProjectApp.included` app has ≥ 1 contributing trace.

### 5.10 Orchestrator wiring

`backend/app/services/artifacts/orchestrator.py` — extensions:

```python
async def generate_all(project, artifact_type, db):
    if artifact_type == "brd":
        # 1. Build bundle once
        bundle = await gather_project_context(project.id, db=db, require_full_corpus=True)
        if not bundle.readiness.ok:
            raise BundleReadinessError(bundle.readiness)  # → 409 at API edge

        # 2. Pin snapshot_refs onto the artifact document for later validate diff
        await _ensure_document("brd", project.id, db).update(
            snapshot_refs=bundle.snapshot_refs,
        )

    # 3. Topo-walk DAG; run independents concurrently
    manifest = get_manifest(artifact_type)
    sem = asyncio.Semaphore(4)
    for layer in topological_layers(manifest):
        await asyncio.gather(*[
            _bounded_unit(sem, generate_unit(u.unit_key, bundle, db))
            for u in layer
        ])

async def generate_unit(unit_key, bundle, db):
    unit_ctx = project_for_unit(bundle, artifact_type="brd", unit_key=unit_key)
    output = await run_unit(unit_key, **unit_ctx.as_inputs())   # DSPy call

    # Primary rows
    await upsert_rows(unit.primary_table, output.rows, source="ai")

    # Trace rows: drop any source_ref not in traceability_seeds
    valid_seeds = {(s.source_kind, s.source_ref) for s in unit_ctx.traceability_seeds}
    trace_rows = []
    for row in output.rows:
        for t in (row.traces or []):
            if (t.source_kind, t.source_ref) in valid_seeds:
                trace_rows.append(BrdTraceabilityRow(
                    target_table=unit.primary_table,
                    target_row_key=row.row_key,
                    **t.dict(),
                ))
    await upsert_rows("brd_traceability", trace_rows, source="ai")

    # Open questions, synthesis, status
    await _append_messages(unit_key, output.open_questions, db)
    await _update_unit_status(unit_key, output, db)
```

### 5.11 API surface — `backend/app/api/artifacts.py`

| Method + path | Purpose |
|---------------|---------|
| `GET /api/projects/{id}/artifacts/brd` | Bundle: artifact doc + current rows by section + open questions + unit_status + `traceability_by_target` |
| `POST .../artifacts/brd/generate` | Ensure doc + enqueue `generate_brd` Celery task. 409 with readiness payload if bundle not ready |
| `POST .../artifacts/brd/units/{unit_key}/generate` | Generate one unit (sync ok; one Vertex call) |
| `POST .../artifacts/brd/units/{unit_key}/regenerate` | `{directive?}` — re-run one unit, no auto-lock |
| `POST .../artifacts/brd/answer` | `{answer, seq?, unit_key?}` — append user msg + re-run answered unit + downstream |
| `GET .../artifacts/brd/units/{unit_key}/rows/{row_key}/history` | Row version history |
| `PATCH .../artifacts/brd/rows/{table}/{row_id}` | `{fields, lock?}` — edit one row → new version |
| `POST .../artifacts/brd/rows/{table}/{row_id}/restore` | `{version}` — restore historical version |
| `POST .../artifacts/brd/rows/{table}/{row_id}/unlock` | Unlock human-edited row |
| `GET .../artifacts/brd/coverage` | `CoverageReport` for CoverageGalaxy |
| `GET .../artifacts/brd/readiness` | `BundleReadiness` for DocReadinessPanel polling |
| `GET .../artifacts/brd/findings` | Read-only validator run (no side effects) |
| `POST .../artifacts/brd/validate` | Run validators; 409 with findings; on pass → `status=validated` + pin VersionSnapshot |
| `GET .../artifacts/brd/export/markdown` | Markdown attachment with Appendix A + B |

**Gating:** every route except `GET …/readiness` and `GET …/coverage` gated by
`Depends(require_artifact_validated("concept_brief"))`.

**Findings shape:**
```python
class FindingItem(BaseModel):
    group: Literal["critical","major","minor","coverage","warnings"]
    target: str | None              # e.g. "brd_business_requirements:BR-007"
    message: str
    suggested_fix: dict | None      # {kind: "set_field", field: "objective_ids", value: ["OBJ-1"]}
```

### 5.12 Markdown export

`backend/app/services/export/artifact_markdown.py` extensions:

1. Register BRD manifest with the existing manifest-driven exporter.
2. Render YAML frontmatter:
   ```yaml
   title: "{project.name} — Business Requirements Document"
   description: "Business requirements for {project.business_unit}"
   artefactId: "brd-{project.human_id.lower()}"
   artefactType: "brd"
   generatorAgent: "spec-forge"
   generatorSkill: "brd-builder"
   generatedAt: "{utcnow}"
   ```
3. **Document Control** table — rows from `VersionSnapshot` history of `brd:{project_id}`.
4. Render 14 sections in template order. Prose blocks from `brd_text_blocks`, pipe tables from each
   `brd_*` row table in template column order.
5. **Appendix A — Traceability Matrix:** one row per `brd_traceability` link. Columns: BRD Row ·
   Source Kind · Source Ref (human-readable: "CB outcomes / o-3: Reduce reconciliation time 70%",
   "PayHub / capability: Multi-rail settlement", "151012-Press-Release.pdf §Problem Overview
   (p.2)") · Relation · Excerpt · Confidence.
6. **Appendix B — Context Sources Snapshot:** pinned CB version, included doc ids + tree_shas +
   filenames, included app ids + names.

### 5.13 Celery task

`backend/workers/tasks.py::generate_brd(project_id)`:
- Wraps `orchestrator.generate_all(project, "brd", db)` via `dispatch._run_async`.
- Per-unit progress writes to `artifact_documents.unit_status[unit_key]` so the FE generation
  theater can poll.
- On terminal unit failure: sets `unit_status[unit_key].state = 'error'` with exception message;
  theater renders ⚠ and offers retry via `POST units/{unit_key}/regenerate`.

---

## 6 · Build phases — 10 phases

### Phase 0 — Discover-table generalisation + Project Context Bundle foundation
*(backend; ~1 day; pre-everything)*

- **P0.1** Build `services/context/` per §4 (entry point, all layers, projection, coverage).
- **P0.2** Generalise discover tables — rename in migration 0018 Block 2; update model class names.
- **P0.3** Per-type discover catalog in `services/artifacts/discover_catalog.py`.
- **P0.4** Tests: `tests/test_project_context_bundle.py`, `tests/test_discover_generalisation.py`.

### Phase 1 — BRD data model + migration
*(backend; ~0.5 day)*

- **P1.1** `models/artifact.py` — 22 model classes (21 brd_* + `BrdTraceability`). Register in
  `models/__init__.py`.
- **P1.2** Migration `0018_brd_artifact.py` per §5.2 (Block 1 enums + Block 2 rename + Block 3
  DRY-loop).
- **P1.3** Confirm `artifact_type` enum has `'brd'`; add ALTER if not.
- **P1.4** Test: `tests/test_migration_0018.py` round-trip.

### Phase 2 — BRD manifest + DSPy units + mock fixtures
*(backend; ~1.5 days)*

- **P2.1** `manifest/brd.py` per §5.3, §5.4, §5.5 — 24 `UnitSpec` entries + DAG +
  `BRD_CONTEXT_PROJECTION` + `BRD_VALIDATE_CHECKS`.
- **P2.2** `manifest/__init__.py::get_manifest(artifact_type)` lookup.
- **P2.3** `dspy_artifacts.py` extensions per §5.7 — `_BRD_SCAFFOLD` + 24 Signatures/Modules + row
  Pydantic models with `traces`.
- **P2.4** 24 mock fixtures `services/llm/fixtures/artifact_<unit>.json` (PayHub-themed; coherent
  end-to-end).
- **P2.5** BRD discover catalog per §5.8.
- **P2.6** Tests: `test_brd_manifest.py`, `test_brd_coverage_contract.py`, `test_dspy_artifacts_brd.py`.

### Phase 3 — Orchestrator + validators + traceability persistence
*(backend; ~1.5 days; **FE Phase 5 can start in parallel** after P3.1 schemas exported)*

- **P3.1** Orchestrator extensions per §5.10 — bundle plumbing, trace persistence, BRD validate
  selector, gate re-check.
- **P3.2** Validators `validators/brd.py` per §5.9 — checks A–G.
- **P3.3** Wire `validate("brd", …)` end-to-end (manifest validate_checks + VersionSnapshot pin +
  audit emit).
- **P3.4** Gate factory verified; FRS stub endpoint returns 501.
- **P3.5** Tests: `test_brd_orchestrator.py`, `test_brd_validators.py`, `test_brd_readiness.py`.

### Phase 4 — API + transport + export
*(backend; ~1 day; FE Phase 6 parallelises)*

- **P4.1** API extensions per §5.11.
- **P4.2** Schema extensions per §5.11 (factory for `BrdRowRead` × 22 + `BrdTraceabilityRead`,
  `BundleReadiness`, `CoverageReport`, `FindingItem`; extend `ArtifactDetailResponse.traceability_by_target`).
- **P4.3** Celery task `generate_brd` per §5.13.
- **P4.4** Markdown export with Appendix A + B per §5.12.
- **P4.5** Tests: `test_brd_api.py` + `brd_golden.md` export golden file.

### Phase 5 — Frontend foundations + atomic components
*(frontend; ~2 days; parallel with BE 3 once types exported)*

- **P5.1** `lib/types.ts` — BRD row types, traceability, readiness, findings, coverage, status enum.
- **P5.2** `lib/brd-manifest.ts` — FE mirror of `manifest/brd.py` (BRD_SECTIONS, BRD_UNITS,
  BRD_CONTEXT_PROJECTION, BRD_FINDINGS_GROUPS).
- **P5.3** `lib/api.ts` — wrappers (`coverage`, `findings`, `readiness`, `exportMarkdown`,
  `acceptFix`).
- **P5.4** `lib/hooks/useBrdReadiness.ts` — SWR polling.
- **P5.5** Atomic components under `app/components/brd/` per §3.5 (13 files: BrCard, TraceChip,
  TraceDrawer, SourceStrip, SourceStripRow, CbEchoStrip, SectionRail, FindingsDrawer, UnitDagViz,
  DocReadinessPanel, CoverageGalaxy, BrdEmptyState, BrdConfettiBurst).
- **P5.6** Dev-only visual sandbox `app/(dev)/brd-sandbox/page.tsx`.

### Phase 6 — Frontend hero surfaces
*(frontend; ~3 days; sequential after P5)*

- **P6.1** Workspace card update (§3.2): BRD chip gate `cb.status === "validated"`; FRS chip below.
- **P6.2** Stage 1 — Empty state: mount `BrdEmptyState`; full-corpus blocker via
  `DocReadinessPanel`.
- **P6.3** Stage 2 — Discover (extend `DiscoverPhase`): 18 questions / 7 categories / segmented
  progress / "why this matters" tooltip.
- **P6.4** Stage 3 — Generation theater: mount `UnitDagViz`; 2-s poll; live unit transitions.
- **P6.5** Stage 4 — Builder shell wired in Phase 7.
- **P6.6** Stage 5 — Validation theater: mount `FindingsDrawer`; inline `[accept fix]`,
  `[jump to row]`, `[edit manually]`; override flow.
- **P6.7** Stage 6 — Validated state: header transitions, lock-by-default, export menu.

### Phase 7 — Frontend builder wiring (integration milestone)
*(frontend; ~2 days; after P6)*

- **P7.1** Branch `ArtifactBuilderPanel.tsx` on `artifactType`. Refactor SECTION_LABELS,
  SECTION_ORDER, UNIT_FOR_TABLE, TABLE_COLS to per-type config.
- **P7.2** Mount BRD layout: `<SourceStrip />` + `<CbEchoStrip />` + `<SectionRail />` + section
  content (14 `SectionPanel`s).
- **P7.3** Header actions (Sources / Coverage / Validate / Export).
- **P7.4** Refine composer with active-scope chip.
- **P7.5** Trace chip wiring: each BR card reads
  `detail.traceability_by_target[<table>:<row_key>]`. Hover popover, click to pin in TraceDrawer.
- **P7.6** Section rail wired via `IntersectionObserver`.
- **P7.7** Keyboard shortcuts + command palette (`?`).

### Phase 8 — Polish + verification
*(both; ~1 day)*

- **P8.1** Reduced-motion audit per §3.6 table.
- **P8.2** Responsive breakpoints per §3.8.
- **P8.3** A11y per §3.9.
- **P8.4** Performance: TTI ≤ 1.5 s; section scroll ≤ 16 ms/frame.
- **P8.5** Full end-to-end manual walk-through per §8 Verification.

### Phase 9 — Legacy retirement
*(backend; ~0.5 day)*

- **P9.1** Legacy `POST /api/projects/{id}/specs/brd` adds `Deprecation: true` header;
  `services/specs/registry.py` flag `legacy_only=True`.
- **P9.2** Hide legacy "Generate BRD" button in `OutputTabs.tsx` / `GenerateSpecsButton.tsx` when
  `detail.artifacts.brd != null`.
- **P9.3** CHANGELOG note: removal in E4c.

---

## 7 · Critical files manifest

### New backend files

| File | Purpose |
|------|---------|
| `backend/app/services/context/__init__.py` | Module init |
| `backend/app/services/context/project_context.py` | Entry-point + dataclasses |
| `backend/app/services/context/app_layer.py` | App Brain layer |
| `backend/app/services/context/docs_layer.py` | Doc breadth + depth |
| `backend/app/services/context/cb_layer.py` | Full CB extraction |
| `backend/app/services/context/projection.py` | Per-unit narrowing |
| `backend/app/services/context/coverage.py` | CoverageReport + static contract |
| `backend/app/services/artifacts/manifest/__init__.py` | get_manifest() |
| `backend/app/services/artifacts/manifest/brd.py` | 24 units + DAG + projection |
| `backend/app/services/artifacts/validators/__init__.py` | Module init |
| `backend/app/services/artifacts/validators/brd.py` | §5.9 A–G |
| `backend/app/services/llm/fixtures/artifact_<24 unit keys>.json` | Mock outputs |
| `backend/alembic/versions/0018_brd_artifact.py` | 22 tables + enums + rename |
| `backend/tests/test_project_context_bundle.py` | Bundle tests |
| `backend/tests/test_brd_manifest.py` | Manifest self-test |
| `backend/tests/test_brd_coverage_contract.py` | Static coverage lint |
| `backend/tests/test_brd_orchestrator.py` | Generation + versioning |
| `backend/tests/test_brd_validators.py` | Findings A–G |
| `backend/tests/test_brd_readiness.py` | Pending/failed-doc gate |
| `backend/tests/test_brd_api.py` | End-to-end API |
| `backend/tests/fixtures/exports/brd_golden.md` | Markdown export golden |

### Modified backend files

| File | What changes |
|------|--------------|
| `backend/app/models/artifact.py` | +22 model classes; rename CB discover model class names |
| `backend/app/models/__init__.py` | Register new models |
| `backend/app/schemas/artifact.py` | Per-table BrdRowRead factory; BrdTraceabilityRead; BundleReadiness; CoverageReport; FindingItem; extend ArtifactDetailResponse.traceability_by_target |
| `backend/app/services/artifacts/orchestrator.py` | Bundle plumbing; trace persistence; BRD validate selector |
| `backend/app/services/artifacts/discover_catalog.py` | Per-type registry (CB + BRD) |
| `backend/app/services/skills/dspy_artifacts.py` | `_BRD_SCAFFOLD` + 24 Signatures/Modules + row models with `traces` |
| `backend/app/services/skills/dspy_discover.py` | Accept `artifact_type` param |
| `backend/app/services/export/artifact_markdown.py` | BRD manifest registration + Appendix A + B |
| `backend/app/api/artifacts.py` | Whitelist brd_* tables; add generate/validate/findings/coverage/readiness/export routes |
| `backend/app/api/deps.py` | Confirm `require_artifact_validated("brd")`; FRS stub |
| `backend/workers/tasks.py` | `generate_brd` Celery task |

### New frontend files

| File | Purpose |
|------|---------|
| `frontend/app/projects/[id]/artifacts/brd/page.tsx` | Thin route → `ArtifactBuilderPanel artifactType="brd"` |
| `frontend/lib/brd-manifest.ts` | FE mirror of backend manifest |
| `frontend/lib/hooks/useBrdReadiness.ts` | SWR polling |
| `frontend/app/components/brd/BrCard.tsx` | Centerpiece row card (4 variants) |
| `frontend/app/components/brd/TraceChip.tsx` | Source-attribution chip + popover |
| `frontend/app/components/brd/TraceDrawer.tsx` | Pinned multi-source drawer |
| `frontend/app/components/brd/SourceStrip.tsx` | Three-layer context strip |
| `frontend/app/components/brd/SourceStripRow.tsx` | One row of the strip |
| `frontend/app/components/brd/CbEchoStrip.tsx` | Distilled CB essence band |
| `frontend/app/components/brd/SectionRail.tsx` | Sticky 14-section nav |
| `frontend/app/components/brd/FindingsDrawer.tsx` | Validation findings with inline fix |
| `frontend/app/components/brd/UnitDagViz.tsx` | Generation theater DAG |
| `frontend/app/components/brd/DocReadinessPanel.tsx` | Per-doc indexing progress |
| `frontend/app/components/brd/CoverageGalaxy.tsx` | CB↔BRD ribbon diagram |
| `frontend/app/components/brd/BrdEmptyState.tsx` | Stage 1 surface |
| `frontend/app/components/brd/BrdConfettiBurst.tsx` | 6-particle CSS burst |
| `frontend/app/(dev)/brd-sandbox/page.tsx` | Dev-only visual sandbox |

### Modified frontend files

| File | What changes |
|------|--------------|
| `frontend/lib/types.ts` | BRD row types, traceability, readiness, findings, coverage |
| `frontend/lib/api.ts` | `api.artifacts.{coverage,findings,readiness,exportMarkdown,acceptFix}` |
| `frontend/lib/hooks/useArtifact.ts` | Propagate `traceability_by_target` |
| `frontend/app/components/ArtifactBuilderPanel.tsx` | Branch on `artifactType`; per-type config; mount BRD layout |
| `frontend/app/projects/[id]/page.tsx` | BRD chip gate (`cb.status === "validated"`); FRS chip |
| `frontend/app/components/OutputTabs.tsx` & `GenerateSpecsButton.tsx` | Hide legacy BRD generate when new artifact exists |

---

## 8 · Reuse map (don't reinvent)

| Need | Reuse |
|------|-------|
| DSPy config | `services/skills/fact_extractor/dspy_extractor.py::_configure_dspy` |
| Source-doc retrieval | `services/understanding/orchestrator.py::_retrieve_project_sections(..., document_ids=…)` |
| App-fact loading | `services/projects/app_context.py::load_app_facts_for_project` |
| App-wiki grounding | `services/rag/wiki_grounding.py::gather_app_brain_context` |
| Version snapshot pinning | `services/version_service.py::create_snapshot` + `VersionSnapshot` model |
| Audit emission | `core/audit.py::emit` |
| Response envelope | `schemas/envelope.py::ok` / `err` |
| Mock provider | `services/skills/mock_fixtures.py::mock_fixture` |
| Discover enhancer + analyser | `services/skills/dspy_discover.py::BriefEnhancerModule` / `DiscoverAnalysisModule` (artifact-agnostic) |
| Builder shell | `app/components/ArtifactBuilderPanel.tsx` (extend with `artifactType` branching) |
| Q&A thread visual DNA | `app/components/InterviewPanel.tsx` (crib bubble + citation chip styling) |
| Row edit modal + history drawer | existing in `ArtifactBuilderPanel.tsx` (`RowEditModal`, `HistoryDrawer`) |
| Discover phase + drawer | existing `DiscoverPhase` / `DiscoverQADrawer` |
| Confidence + completeness chips | existing `CONF_VARIANT`, `completenessColor`, `UnitScoreChip` |
| Source badges | existing `SOURCE_BADGE_MAP` — extend with `cb_row` kind |
| Version history pattern | existing `VersionHistoryPanel.tsx` |
| Status badge palette | existing `Badge` variants |
| Provenance lifecycle colours | `globals.css` `--ai-generated` / `--human-edited` / `--app-brain` / `--approved` / `--stale` |
| Card / shadow / radius tokens | `globals.css` `.card` / `--shadow-card` / `--radius-*` |
| Empty-state pattern | existing `EmptyState.tsx` |
| Toast | sonner via `app/components/ui/sonner.tsx` |
| Animations | framer-motion (dep) + `tailwindcss-animate` (accordion) |
| Icons | lucide-react (dep) |

---

## 9 · Verification — full-stack walk-through

### Migration round-trip
```bash
make migrate
( cd backend && ./.venv/bin/alembic downgrade -1 && ./.venv/bin/alembic upgrade head )
```
All 22 BRD tables present; CB rows survive discover rename.

### Backend pytest (`LLM_PROVIDER=mock`)
```bash
make test-be
```
- `test_project_context_bundle.py` — bundle composition + readiness gate (pending → 409; all done →
  ok; zero docs → ok).
- `test_brd_coverage_contract.py` — static CB-coverage lint passes.
- `test_brd_manifest.py` — DAG acyclic, every writes/depends_on resolves.
- `test_brd_orchestrator.py`:
  - `generate_all('brd')` → version-1 rows in every brd_* table in dependency order.
  - Every BR / KPI / objective / risk has ≥ 1 `brd_traceability` row populated by orchestrator.
  - Re-run unit with no change → 0 new primary versions AND 0 new trace versions.
  - Edit BR → version 2, locked; re-run unit does not overwrite.
  - Drop a row across regen → `status='removed'`; history kept.
- `test_brd_validators.py` — drive every finding group:
  - BR with 0 outward traces → Major (G).
  - Missing KPI baseline → Major (C).
  - Orphan objective_id → Major (B).
  - Stale source set → Coverage (G).
  - Uncovered CB row (mutate manifest in test) → Coverage (G).
  - In-scope app with 0 traces → Warning (G).
- `test_brd_readiness.py` — pending doc → 409 with readiness payload; failed doc → 409; zero docs → ok.
- `test_brd_api.py` — gate, generate, validate, findings, coverage, readiness, export endpoints.
- `make typecheck && make lint && make test-be` green.

### Frontend smoke (manual, in-browser)
```bash
make dev-be     # Postgres + Redis
make dev-fe     # Next.js on :3000
make worker     # Celery worker
```
Login `admin@specforge.test` / `SpecForge#Test2026!`. Use seeded `PRJ-0001` (PayHub).

1. **Stage 0** — workspace. BRD chip disabled with tooltip "BRD locked until Concept Brief is
   validated".
2. Validate the Concept Brief (existing CB flow). BRD chip enables; status = "Not started".
3. **Stage 1** — click BRD chip. Empty state:
   - Grounding badge "2 apps · 5 docs · CB v2".
   - AI-Enhance composer.
   - Force pending doc (re-upload PDF) → `DocReadinessPanel` appears with progress; CTA disabled.
   - When all flip to `done`, CTA un-greys; toast "All sources ready".
4. **Stage 2** — "Discover & Continue". 18 questions across 7 categories. Per-category progress
   segments fill independently. Source badges work (hover → popover). "Why this matters" tooltips.
5. **Stage 3** — "Generate BRD". Generation theater opens with `UnitDagViz`:
   - Multiple ◐ at once (topological parallelism).
   - "Right now" subtitle updates.
   - 2 s polls.
   - Closes on `in_interview`.
6. **Stage 4 — Builder.** Layout shows:
   - Header: status badge, Sources, Coverage 14/14, Validate, Export.
   - Three-Source Strip (apps · docs · CB) — each row expandable inline.
   - CB Echo Strip — collapsed; expand to read CB essence.
   - Section Rail (sticky left) — 14 rows with completion dots.
   - Section content — 14 panels, §7 renders as `BrCard`s.
   - Hover trace chip → side popover with excerpt. Click → pin in `TraceDrawer`.
   - `✦ Coverage 14/14` → `CoverageGalaxy` modal. All 14 covered.
   - Edit a BR (human-edited bar + lock chip + v2 in history).
   - Drag-reorder two BRs within §7 (if v1 ships drag-reorder).
7. **Stage 5** — `✓ Validate`. `FindingsDrawer` opens:
   - Remove a BR's traces → "BR-N has no source trace" under Major.
   - Clear a KPI baseline → "KPI-N missing baseline" under Major.
   - `[jump to row]` → smooth-scroll + rail dot pulse red.
   - `[accept fix]` → finding clears; count decrements.
   - Fix all critical + major → `✓ Validate BRD` enables.
8. **Stage 6** — click `✓ Validate BRD` → confetti → header "Validated ✓ · v1 · 2 mins ago". Rows
   lock-by-default. `Export → Markdown` downloads with Appendix A + B.
9. Workspace card: BRD chip "Validated ✓"; FRS chip "disabled — BRD validated ✓".

### A11y + reduced-motion
- Toggle macOS "Reduce motion" → re-run steps 5, 7, 8. All animations degrade gracefully.
- Tab-through builder; every element reachable; focus rings visible.
- Voiceover reads BR card correctly.

### Responsive
- 768 px → Section Rail fly-out; Source Strip bodies → drawers.
- 375 px → tab switcher; composer = bottom sheet.

### Performance
- Builder TTI ≤ 1.5 s on 30 BRs / 5 risks / 5 KPIs.
- Section anchor scroll ≤ 16 ms / frame.

### Live (opt-in, `@pytest.mark.slow`)
- End-to-end against real Vertex on small seeded project.

---

## 10 · Risks + mitigations

| Risk | Mitigation |
|------|-----------|
| Bundle build cost (10–100s KB, 50+ DB rows) | Build once per `generate_all`; lazy formatted strings per layer; tree-search capped by `top_k`; wiki budgeter trims at prompt-render time only |
| Full-corpus readiness blocks generation when docs slow | Indexing async + visible; platform_admin override available; copy supportive not punitive |
| LLM trace fabrication | `traceability_seeds` enumerate allowed refs; orchestrator drops invalid refs; validate orphan-trace check |
| CB coverage map drift | `tests/test_brd_coverage_contract.py` fails CI immediately |
| Generation theater feels performative | Theater closes the instant generation completes; no artificial holds |
| Trace chips dominate dense BR cards | Collapsed by default in card body; summary count in header |
| BR card density at 50+ BRs | Header toggle `[expand all in §7]`; per-user state remembered |
| Coverage Galaxy at scale | Auto-bucket by cb_table when totals exceed 25 |
| Discover-table rename touches CB data | `ALTER TABLE … RENAME TO` atomic in PG; idempotency guards; downgrade reverses |
| Manifest regression breaks generation silently | `test_brd_manifest.py` + `test_brd_coverage_contract.py` |
| Vertex latency on `generate_all` (~24 units) | Topological parallelism (asyncio.gather, max_concurrency=4); aim ≤ 90 s p50 |
| Legacy E3 `brd` SpecType coexistence | Hide legacy UI when new artifact exists; CHANGELOG note |
| FRS deferred | Gate factory wired + tested via 501 stub |

---

## 11 · Open questions (confirm before kickoff)

1. **Bundle size on the wire** — `?include=apps,docs,cb` query param on
   `GET /api/projects/{id}/artifacts/brd`, or always full? Default: always full.
2. **Coverage Galaxy auto-bucket threshold** — start at 25 CB rows? Tune after real project.
3. **Theater poll cadence** — 2 s vs 1 s. Default 2 s.
4. **Findings drawer override** — platform_admin only, or project_owner too? Default platform_admin.
5. **Section drag-and-drop reorder** — `@dnd-kit/sortable` in v1, or sort-by-priority only?
   Default: skip drag for v1; add in v1.5.
6. **Confetti library** — `tsparticles` (~100 KB) vs CSS-only. Default: CSS-only 6-particle burst.

---

## 12 · Out of scope (deferred)

- **DOCX / public-link export** — Module 5; menu items present but disabled.
- **Real-time multi-user editing / cursor presence** — no backend support.
- **Dark theme** — project non-goal per `frontend/CLAUDE.md`.
- **Inline AI-rewrite of a single sentence** ("improve wording" per PRD §BR-M2-005) — separate
  skill arc.
- **Slack / Teams "share BRD finding"** integrations.
- **FRS module** — gate factory wired but no builder route yet (E4c).
- **Removal of legacy E3 `brd` SpecType** — happens with E4c.

---

## 13 · Appendix · Section-by-section mapping to E4b-brd-builder.md

| This plan §  | E4b §  |
|-------------|--------|
| §2 Cross-cutting decisions | E4b §5.8, §13 |
| §3 UI/UX deep dive | E4b §11 (extended) |
| §4 Project Context Bundle | E4b §5.1–§5.8 |
| §5.1 Data model | E4b §3 |
| §5.2 Migration | E4b §3.2 |
| §5.3 Generation units + DAG | E4b §4 |
| §5.5 BRD_CONTEXT_PROJECTION | E4b §5.5 |
| §5.6 App + doc coverage | E4b §5.6 |
| §5.7 DSPy units + scaffold | E4b §5.9 |
| §5.8 BRD Discover catalog | E4b §6.1 |
| §5.9 Validators A–G | E4b §8.1 |
| §5.10 Orchestrator | E4b §7 |
| §5.11 API | E4b §9 |
| §5.12 Markdown export | E4b §10 |
| §5.13 Celery task | E4b §7 |
| §6 Build phases 0–9 | E4b §12 (extended) |
| §10 Risks | E4b §15 |
