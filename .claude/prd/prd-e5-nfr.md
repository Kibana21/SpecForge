# E5 — NFR (Non-Functional Requirements) Module PRD

> **The quality spine of the SpecForge chain**: RU → CB → **BRD → NFR → FRS** → Test Cases.
> Conceptual seed: `reference_mds/skills/nfr-builder/{nfr-template.md, SKILL.md}`, elevated from a
> file-writing procedure into a first-class, versioned, **traceable** SpecForge artifact that
> mirrors the proven BRD/FRS/Test-Cases generation engine.
>
> **Goal**: from a human-validated **BRD**, generate comprehensive non-functional requirements across
> **seven quality categories** (Performance · Security · Availability · Usability · Scalability ·
> Maintainability · Portability), each row a **testable, solution-agnostic** statement with a
> **MoSCoW** priority and **traceability back to a BRD objective/requirement**, where every line item
> and property is **editable, deletable, lockable and version-tracked**, users can **add an NFR and
> link it to any BRD objective/business requirement**, and a signature **Quality Radar** proves the
> balance and priority mass of the quality landscape at a glance.
>
> **Standalone, gated on BRD** — NFR generation is blocked until the BRD `status='validated'`
> (reuses `require_artifact_validated("brd")`), exactly like FRS. NFR sits **parallel to FRS** in the
> left nav (both unlock on a validated BRD).
>
> **Feeds FRS, no hard gate** — when NFRs are validated, FRS generation **softly** consumes them as
> `nfr_driver` context + traceability (the FRS engine already has the `nfr_driver` trace kind and an
> "NFRs ⚡" discover category). FRS is **never blocked** if NFR is skipped.
>
> **Companion implementation plan**: `/Users/kartik/.claude/plans/next-check-the-nfr-template-md-recursive-codd.md`
> (full table DDL, manifest/orchestrator/DSPy file map, context-wiring, Quality-Radar spec, wireframes, verification).

---

## 1. Introduction / Overview

SpecForge turns messy requirements into a validated chain of artifacts. Today the chain captures *what* the system must do — Concept Brief → BRD (business requirements) → FRS (functional design) → Test Cases — but it has **no first-class home for the quality attributes the system must satisfy**: how fast, how secure, how available, how scalable, how maintainable, how portable, how usable. Those non-functional requirements (NFRs) are where real systems succeed or fail at go-live, and architects today smuggle them into the FRS discover Q&A or lose them entirely.

The **NFR module (E5)** gives them a dedicated, structured, traceable artifact. It reads the **validated BRD** (plus the same full-corpus context FRS uses — App Brain facts, the document corpus, and the validated Concept Brief) and generates, per the `nfr-builder` reference template, a set of **`NFR-nnn`** requirements organized into the **seven quality categories**. Each requirement is a **testable, solution-agnostic** statement (it states a measurable target, e.g. "p95 API latency < 300ms @ 200 concurrent users", and never prescribes a technology), carries a **MoSCoW** priority (Must/Should/Could/Won't), and **traces back to a BRD objective or business requirement**. The module also captures the template's governance sections: risks, trade-off decisions, open questions, pending decisions, references, and a glossary.

The defining experience is the **Quality Radar** — a seven-axis radar (one axis per category) whose magnitude is the **MoSCoW-weighted requirement mass** on that axis, so a user can see in one glance which quality dimensions are thin, which are over-indexed, and how priority is distributed. Click an axis to filter straight to that category's requirements.

NFR is **standalone and gated on the BRD** (it unlocks the moment the BRD is validated, parallel to FRS). When the user validates the NFRs, they **feed** the FRS engine: FRS generation softly receives the validated NFRs as `nfr_driver` context and emits `nfr_driver` traceability from the specs they shape — **but FRS is never blocked** if the team chooses to skip NFRs. This honors the "standalone" intent while unlocking real downstream value from the FRS scaffolding that already anticipates NFRs.

The module reuses the BRD/FRS engine wholesale — row-level versioning, locking, idempotent regeneration, Celery dispatch, the `unit_status` progress channel, the readiness gate, and the mock-provider path — so the hard infrastructure is proven, not reinvented.

---

## 2. Goals

- **G1 — Comprehensive, structured generation.** From a validated BRD, generate NFRs covering all **seven categories** (each populated or explicitly marked N/A), every requirement **testable and solution-agnostic** with a measurement and a MoSCoW priority, plus the governance sections (risks, trade-offs, open questions, decisions, references, glossary).
- **G2 — First-class traceability.** Every NFR links to ≥1 BRD objective/business requirement. The Project → BRD → NFR chain is queryable, and the BRD → NFR → FRS chain is realized through `nfr_driver` traces on FRS specs.
- **G3 — Quality you can see (the Quality Radar).** A seven-axis radar shows requirement count and MoSCoW-weighted mass per category, with priority-banded fills and click-to-filter — making the quality landscape legible and distinctive.
- **G4 — Full human control.** Every row and property is editable, deletable, lockable, restorable, and version-tracked. Users can add a brand-new NFR and link it to existing BRD elements. Locked/manual rows survive AI regeneration; a per-category re-gen never disturbs other categories.
- **G5 — Feeds FRS, no hard gate.** Validated NFRs softly enrich FRS generation (context + `nfr_driver` traces). FRS generates identically whether or not NFRs exist — no new blocking gate, no regression to the FRS flow.
- **G6 — Always-visible progress.** During generation the user sees exactly which step is running (overview → 7 categories → governance) via the live `unit_status` channel.
- **G7 — Rock-solid, mockable backend.** Mirror the FRS engine exactly; keep the `LLM_PROVIDER=mock` path green (zero Vertex/PageIndex calls) so CI and tests stay deterministic.

---

## 3. User Stories

> UI stories include browser verification (dev-browser skill) on a seeded validated-BRD project (`architect@specforge.test`, PayHub).

### US-001: NFR data model + migration
**Description:** As a developer, I need versioned tables for NFR requirements, governance rows, and traceability so authored content persists with full history.

**Acceptance Criteria:**
- [ ] Migration `0025_nfr_artifact.py` runs `ALTER TYPE artifact_type ADD VALUE IF NOT EXISTS 'nfr'` **first**, then creates 3 enums (`nfr_category`, `nfr_priority`, `nfr_trace_kind`) with `DO $$ … EXCEPTION WHEN duplicate_object` guards.
- [ ] Creates `nfr_requirements`, `nfr_risks`, `nfr_tradeoffs`, `nfr_open_questions`, `nfr_decisions`, `nfr_references`, `nfr_glossary`, `nfr_text_blocks` (row mixin + `UNIQUE(document_id,row_key,version)` + partial `is_current` index + `CHECK(version>0)`) and `nfr_traceability` (NOT versioned, 3 indexes).
- [ ] `"nfr"` added to the `ArtifactType` enum literal in `app/models/artifact.py`; all 9 models registered in `app/models/__init__.py`.
- [ ] `make migrate` applies cleanly; `make typecheck` passes.

### US-002: Context bundle exposes BRD/CB for NFR + readiness gate
**Description:** As the generation engine, I need the same full-corpus context FRS uses (apps + docs + validated CB + validated BRD), and a readiness check that blocks until the BRD is validated.

**Acceptance Criteria:**
- [ ] `gather_project_context(artifact_type="nfr")` loads the App, Docs, CB, and BRD layers (NFR is built from the same inputs as FRS).
- [ ] `_compute_readiness` sets `can_generate=False` + `blocking_reason` when the BRD is not validated; `can_generate=True` once it is.
- [ ] `projection.py` has an `nfr` branch giving full CB + BRD context to units.
- [ ] `make test-be` covers the readiness gate (BRD validated vs not).

### US-003: Overview + per-category generation
**Description:** As an architect, I want the system to draft a context overview and then author NFRs for each of the seven quality categories so I get a complete, organized baseline.

**Acceptance Criteria:**
- [ ] DSPy `overview` unit emits the §1 overview + objectives text blocks; the 7 category units each emit `nfr_requirements` scoped to their category.
- [ ] Every requirement is **testable** (non-empty `measurement`), **solution-agnostic** (no technology/product names), carries a MoSCoW `priority`, and has ≥1 `brd_refs` entry.
- [ ] Global sequential `NFR-nnn` numbering across all categories; existing keys preserved on regen; locked rows reproduced verbatim.
- [ ] A genuinely inapplicable category emits a single `na=true` row with a one-line rationale.
- [ ] Mock fixtures `nfr_overview.json` + 7 category fixtures registered; runs with zero Vertex calls under `LLM_PROVIDER=mock`.

### US-004: Governance + traceability generation
**Description:** As a reviewer, I want risks, trade-offs, open questions, decisions, references, a glossary, and a document-wide NFR→BRD traceability set so the artifact is governable.

**Acceptance Criteria:**
- [ ] DSPy `governance` unit (depends on all 7 categories) emits `nfr_risks`, `nfr_tradeoffs`, `nfr_open_questions`, `nfr_decisions`, `nfr_references`, `nfr_glossary`, and the replace-all `nfr_traceability` set.
- [ ] `_upsert_nfr_traceability` is delete-then-insert inside `begin_nested()` (mirrors `_upsert_frs_traceability`); no duplicate trace rows.
- [ ] Mock fixture `nfr_governance.json` registered; zero Vertex calls under mock.

### US-005: Generation endpoints + Celery + live progress
**Description:** As a user, I want to trigger generation and watch which step is running so long jobs feel transparent.

**Acceptance Criteria:**
- [ ] Endpoints `POST …/nfr/generate` (gated `require_artifact_validated("brd")`), `…/nfr/units/{unit_key}/regenerate`, `…/nfr/reset-generating`.
- [ ] Mock → in-process synchronous; real → set `status='generating'`, dispatch Celery (`_run_async` wrapper + `dispatch()`), return immediately; broker-down → reset + 503.
- [ ] `unit_status` JSONB carries `_current_unit`, per-unit `{completeness, confidence}`, and overall progress.

### US-006: Quality Radar (the signature view)
**Description:** As an architect, I want a seven-axis radar that shows the balance and priority mass of my NFRs so I instantly see thin or over-indexed quality dimensions.

**Acceptance Criteria:**
- [ ] `get_nfr_detail` returns a server-computed `radar: NfrRadarAxis[]` (7 axes) where each axis has `{category, count, weighted, byPriority}` and `weighted = Σ MoSCoW weights (must=4, should=3, could=2, wont=1)`.
- [ ] `NfrQualityRadar` renders 7 axes (SVG polar): magnitude = `weighted` normalized to the max axis; a dashed secondary ring = raw `count`; polygon fill stacked by MoSCoW composition (must=red→should=amber→could=blue→wont=gray).
- [ ] Hover an axis → tooltip (category, count, weighted, priority breakdown); click an axis → filters the rail + table to that category.
- [ ] Verify in browser using dev-browser skill.

### US-007: Edit / delete / lock / history on every row
**Description:** As a user, I want to edit, delete, lock, and view the history of any NFR/governance property.

**Acceptance Criteria:**
- [ ] `POST …/nfr/{table}/{row_id}/edit` (versioned, lock-aware, `expected_version` → 409 conflict), `/delete` (soft `status='removed'`), `/unlock`, `/restore`, `GET …/nfr/{table}/{row_id}/history`.
- [ ] `VALID_NFR_TABLES = set(NFR_TABLE_MAP)` guards generic routes; `nfr_traceability` is not editable via generic CRUD.
- [ ] A per-category regeneration **does not** soft-delete rows in other categories (scope_keys).
- [ ] Verify in browser using dev-browser skill (edit an NFR, delete it, restore from history).

### US-008: Add a new NFR and link it to a BRD requirement
**Description:** As an architect, I want to add my own NFR and link it to an existing BRD objective / business requirement.

**Acceptance Criteria:**
- [ ] `POST …/nfr/{table}/add` validates each link resolves to an active BRD row (422 otherwise), inserts with `source='human'`, version=1, next global `NFR-nnn`.
- [ ] Each link persisted as both a `brd_refs` entry and an `nfr_traceability` row.
- [ ] Manual NFRs survive AI regeneration (excluded from the category soft-delete scope).
- [ ] Verify in browser: add an NFR via dialog with a BRD link picker; it appears and counts on the radar.

### US-009: Validation checklist + validate gate
**Description:** As a reviewer, I want validation to block on real quality gaps so a weak NFR set can't be marked done.

**Acceptance Criteria:**
- [ ] `validators/nfr.py` produces tiered findings encoding the SKILL.md Phase-6 gate: CRITICAL (`brd_prerequisite`, `valid_moscow`), MAJOR (`all_categories_covered`, `sequential_numbering`, `traceability_present`), MINOR (`testable_statements`, `no_duplicate_overlap`), WARNING.
- [ ] `POST …/nfr/validate`: blocking (critical+major) > 0 → return findings uncommitted; else `status='validated'` + `validated_at/by/snapshot_key` + bulk-lock current rows.
- [ ] `GET …/nfr/findings` returns the read-only report.

### US-010: NFR workspace UI (Category → Requirement builder)
**Description:** As a user, I want a clear three-pane workspace to navigate categories, read requirements, and edit them inline.

**Acceptance Criteria:**
- [ ] Sidebar nav item (`Gauge`/`ShieldCheck`, **locked until BRD validated**, status badge) inserted **after BRD, before FRS**; `view==='nfr'` branch renders `NfrBuilderView`.
- [ ] Left rail: the 7 categories (with per-category counts); main panel: active-category requirement table (NFR# · Attribute · Requirement · Measurement · Priority pill · BRD trace chips); right: Q&A thread + findings drawer; header hosts the Quality Radar.
- [ ] Priority shown as colored MoSCoW badges (new `--nfr-*` CSS vars); row hover → Edit/History/Lock/Delete; edit opens a schema-driven dialog.
- [ ] Verify in browser using dev-browser skill.

### US-011: Feeds-FRS wiring (soft, no hard gate)
**Description:** As an architect, I want my validated NFRs to inform FRS design without ever blocking FRS.

**Acceptance Criteria:**
- [ ] `gather_project_context(artifact_type="frs"|"test_cases")` loads a (possibly empty) NFR layer; `projection.py` appends a `=== Validated NFR Drivers (optional) ===` block **only when** NFR exists, is validated, and has requirements.
- [ ] `dspy_frs.py` Stage-B docstring instructs: if the NFR-drivers block is present, emit `nfr_driver` traces for shaped specs; if absent, omit them (never fabricate). No FRS schema change (`nfr_driver` already exists).
- [ ] **FRS readiness stays `brd_ready` only** — no `nfr_ready` gate. Snapshot test: FRS output is identical with NFR absent / unvalidated / validated except for `nfr_driver` traces.
- [ ] NFR validated **after** FRS → a **minor** (non-blocking) FRS finding `nfr_drivers_missing`; deleted NFR ref → minor `nfr_drivers_stale`; neither blocks FRS validation; re-genning the FRS module clears them.

### US-012: Export
**Description:** As a user, I want to export the NFR document in the reference template's structure.

**Acceptance Criteria:**
- [ ] `GET …/nfr/export` produces markdown (or a zip) rendering `nfr-template.md` exactly: front-matter, §1 Document Control + Context (overview/objectives + the fixed Category-Framework table), §2–§8 one table per category (`| NFR Number | Attribute | Requirement | Priority |`, priority as `Must/Should/Could/Won't`), §9 Risks + Trade-offs, §10 Traceability to BRD, §11 Open Questions + Pending Decisions, §12 References + Glossary.

---

## 4. Functional Requirements

**Data & context**
- FR-1: Extend `artifact_type` enum with `nfr`; create `nfr_requirements`, `nfr_risks`, `nfr_tradeoffs`, `nfr_open_questions`, `nfr_decisions`, `nfr_references`, `nfr_glossary`, `nfr_text_blocks`, `nfr_traceability` (migration `0025`).
- FR-2: All versioned rows use the standard row mixin (version, is_current, is_locked, status, source, created_by) with `UNIQUE(document_id,row_key,version)`.
- FR-3: `nfr_traceability` is replace-all (not versioned), mirroring `frs_traceability`.
- FR-4: Add an `NfrLayer` to the context bundle; `artifact_type="nfr"` loads App+Docs+CB+BRD; readiness blocks until BRD validated. FRS/Test-Cases additionally load the (optional) NFR layer.
- FR-5: NFR row_keys are **global sequential** `NFR-nnn` across all categories; `category` is a column, not part of the key.

**Generation**
- FR-6: The `overview` unit produces the context/objectives text blocks; the 7 category units each produce `nfr_requirements` scoped to their category; the `governance` unit produces all governance rows + the replace-all traceability set.
- FR-7: Generation honors idempotency: existing row_keys preserved, locked + manual (`source='human'`) rows reproduced/preserved; a category re-gen's soft-delete scope is limited to that category (`scope_keys`).
- FR-8: All LLM calls route through the provider abstraction; `LLM_PROVIDER=mock` uses registered fixtures with zero Vertex/PageIndex calls.

**Quality & traceability**
- FR-9: Every non-`na` NFR must carry ≥1 `nfr_traceability` row to a BRD objective/business requirement; `brd_refs` mirrors those links on the requirement row.
- FR-10: `get_nfr_detail` returns a server-computed Quality Radar summary (per-category count, MoSCoW-weighted mass, priority breakdown).
- FR-11: Validated NFRs feed FRS generation as optional `nfr_driver` context + traceability, with **no hard gate** on FRS.

**Editing & control**
- FR-12: Every NFR/governance property is editable (versioned, lock-aware, 409 on version conflict), deletable (soft), lockable/unlockable, restorable, with history.
- FR-13: `POST …/nfr/{table}/add` adds a manual NFR and persists its BRD link(s) as traceability (rejecting links to nonexistent BRD rows).
- FR-14: Validation produces tiered findings; `POST …/nfr/validate` commits `status='validated'` + locks rows only when no blocking (critical/major) findings remain.

**UI/UX**
- FR-15: A locked-until-BRD-validated sidebar nav item (after BRD, before FRS) opens a three-pane Category → Requirement builder with a header Quality Radar.
- FR-16: Inline-editable requirement table with colored MoSCoW badges, per-row Edit/History/Lock/Delete, and a schema-driven edit dialog (attribute, requirement, measurement, priority, rationale).
- FR-17: An "Add NFR" dialog with a BRD-element link picker (search objectives / business requirements by row_key + label).
- FR-18: A live generation theater showing the running step (overview → 7 categories → governance).
- FR-19: The Quality Radar (7-axis) with priority-banded fills, hover tooltips, and click-to-filter.

---

## 5. Non-Goals (Out of Scope)

- **NG-1: No hard FRS gate on NFR.** FRS remains gated on the BRD only; NFR is a soft input. NFR is *standalone*.
- **NG-2: No PII handling** anywhere (project-wide non-goal — never reintroduce).
- **NG-3: No automated NFR verification / runtime monitoring.** Output is structured, human-readable, testable NFR statements — not SLO instrumentation, load tests, or compliance scanners.
- **NG-4: No generation from a draft/unvalidated BRD.** The BRD-validated gate is mandatory.
- **NG-5: No new artifact type beyond NFR**, and no BIA (Business Impact Assessment) artifact — the SKILL's optional BIA input is captured, if at all, as user-provided context, not a new module.
- **NG-6: No auto-mutation of a validated FRS** when NFRs change — only non-blocking advisory findings (`nfr_drivers_missing` / `nfr_drivers_stale`) and a manual re-gen affordance.

---

## 6. Design Considerations (UI/UX — first-class)

The UI mirrors the existing FRS frontend (SWR polling, dedicated builder, three-pane layout, modal edit, trace chips, sonner toasts, lucide icons, Tailwind CSS-var design language) so it feels native, with the **Quality Radar** as the signature differentiator.

**6.1 Workspace shell (three-pane, mirrors `FrsBuilderView`)**
```
┌──────────────────────────────────────────────────────────────────────────────┐
│ SpecForge  ▸ PayHub                                             [Export ▾] [⚙] │
├───────────────┬──────────────────────────────────────────────────────────────┤
│ NAV           │  NFR Builder            ⬡ Quality Radar          [Validate ✓]  │
│ ● Interview ✓ │ ┌─────────────┬──────────────────────────┬───────────────────┐│
│ ● Wiki        │ │ CATEGORY    │  Performance & Efficiency │  Q&A · Findings   ││
│ ● Ask         │ │ RAIL        │ ┌──────────────────────┐  │ ┌───────────────┐ ││
│ ● Concept Br. │ │ ⚡ Perf  (3)│ │NFR# Attr Req Meas Pri│  │ │ ❓ latency tgt│ ││
│ ● BRD      ✓  │ │ 🛡 Sec   (4)│ │001 Latency … p95 Must│  │ │ ✅ throughput │ ││
│ ▸ NFR [Draft] │ │ 🟢 Avail (2)│ │002 Thrupt … 1k/s Shld│  │ │ ⚠ 2 findings  │ ││
│ ○ FRS  (lock) │ │ 🎨 Usab  (3)│ │003 …                 │  │ └───────────────┘ ││
│ ○ Test (lock) │ │ 📈 Scale (2)│ │ [+ Add NFR]          │  │  Findings drawer  ││
│               │ │ 🔧 Maint (2)│ └──────────────────────┘  │  ▸ major: trace…  ││
│               │ │ 🔌 Port  (1)│   ◂ click rail / radar    │  ▸ minor: vague…  ││
│               │ └─────────────┴──────────────────────────┴───────────────────┘│
└───────────────┴──────────────────────────────────────────────────────────────┘
```

**6.2 Quality Radar (the signature).** A seven-axis SVG radar; axis = category; ring-1 magnitude = MoSCoW-weighted mass; dashed ring-2 = raw count; polygon fill stacked by MoSCoW composition.
```
                 Performance ⚡ (weighted 11)
        Portability 🔌 ╱╲ Security 🛡 (13)
   Maintainability 🔧 ╳──●──╳ Availability 🟢
        Scalability 📈 ╲╱ Usability 🎨
  Ring1 = MoSCoW-weighted mass · Ring2 (dashed) = raw count
  Fill bands: ▰must=red ▰should=amber ▰could=blue ▰wont=gray
  Hover axis → {category,count,weighted,priority breakdown} · Click → filter rail+table
```

**6.3 Inline editing & control.** Row hover reveals Edit (pencil) / History (clock) / Lock / Delete (trash). Edit opens `NfrRowEditDialog` (schema-driven: attribute, requirement textarea, measurement, `priority` MoSCoW select, rationale, lock toggle). Locked rows render at reduced opacity with a lock chip.

**6.4 Add + link.** `AddNfrDialog` includes a BRD-element **link picker** (typeahead over BRD objectives + business requirements, shown as row_key + label), enforcing ≥1 link before save; the link becomes both `brd_refs` and an `nfr_traceability` row.

**6.5 Live generation theater (mirrors `FrsConstructionTheater`).** A 9-step narrative — overview → Performance → Security → Availability → Usability → Scalability → Maintainability → Portability → Governance — with the currently-running step highlighted from `unit_status`.

**6.6 Trace chips.** Color-coded by `nfr_trace_kind` — `brd_objective` (OBJ), `brd_business_requirement` (BR), `brd_text_block` (CTX), `app_fact` (App), `doc_section` (Doc), `discover_qa` (Q&A), `within_nfr` (NFR). Hover → tooltip (label + confidence); click → jump to the BRD element.

**6.7 Components to create** (`frontend/app/components/nfr/`): `NfrBuilderView`, `NfrEmptyState`, `NfrGenerationTheater`, `NfrRequirementTable`, `NfrRowEditDialog`, `AddNfrDialog`, `NfrFindingsDrawer`, `NfrTraceChip`, `NfrQualityRadar`. Plus `lib/api.ts` (`api.nfr.*`), `lib/types.ts`, `lib/nfr-manifest.ts`, sidebar + view branch in `app/projects/[id]/page.tsx`, and `--nfr-*` tokens in `app/globals.css`.

---

## 7. Technical Considerations (rock-solid backend)

**7.1 Mirror the FRS engine verbatim.** Copy `upsert_frs_rows` → `upsert_nfr_rows`, `_upsert_frs_traceability` → `_upsert_nfr_traceability` (delete-then-insert per source in `begin_nested()`), `generate_frs_all` → `generate_nfr_all`. New files: `manifest/nfr.py`, `skills/dspy_nfr.py`, `artifacts/nfr_orchestrator.py`, `artifacts/validators/nfr.py`, `artifacts/exporters/nfr.py`, `context/nfr_layer.py`, `api/nfr.py`. Templates: `frs_orchestrator.py`, `dspy_frs.py`, `api/frs.py`, `validators/frs.py`, `context/frs_layer.py`.

**7.2 Single-phase generation, per-category scope.** Unlike FRS (Stage A/B), NFR is single-phase: `overview` → 7 category units (parallelizable) → `governance`. Each category unit passes `scope_keys` = its current NFR row_keys so a re-gen of one category never soft-deletes another's rows.

**7.3 Global NFR numbering.** Row_keys are global `NFR-001..NFR-n`; `_next_nfr_seq` reads the max across categories. This makes the SKILL gate's "sequential, no gaps, no cross-category dupes" checks trivial and lets a requirement change category without renumbering.

**7.4 Feeds-FRS is a single soft chokepoint.** All "feeds FRS" behavior lives in `projection.py` (inject the validated-NFR block into FRS/Test-Cases context only when present) + one sentence in the `dspy_frs.py` Stage-B docstring. **FRS readiness never references NFR.** The `nfr_driver` trace kind already exists on `FrsTraceabilityRow` — no FRS schema change.

**7.5 Stale-trace handling (no hard gate consequence).** Because FRS isn't gated on NFR, a user may validate FRS first. `validate_nfr` emits an advisory message + a **minor** FRS finding `nfr_drivers_missing`; deleted NFRs referenced by FRS traces surface as **minor** `nfr_drivers_stale`. Both are non-blocking; a manual FRS module re-gen (replace-all traceability) refreshes them. Validated FRS is never auto-mutated.

**7.6 Celery discipline.** Every async task wrapped in `_run_async()` (disposes the engine — prefork loop gotcha); dispatch via `workers/dispatch.py::dispatch()` (TCP pre-flight). Heavy LLM work never runs synchronously in the request path on the real provider.

**7.7 Gate reuse.** `require_artifact_validated("brd")` already exists (`deps.py:80`) — use it; do **not** write a new gate. Two-layer gating (deps decorator + bundle readiness) mirrors FRS-gates-on-BRD.

**7.8 Radar computed, never stored.** `get_nfr_detail` recomputes the radar summary from active rows each call, so manual additions/edits reflect immediately with no cache invalidation.

**7.9 Migration enum note.** `ALTER TYPE artifact_type ADD VALUE` uses the `IF NOT EXISTS` form; downgrade drops the new tables/enums but leaves the `'nfr'` value in place (matches FRS/BRD/Test-Cases migration practice).

---

## 8. Success Metrics

- **M1 — Category completeness:** after a single generation pass on a seeded validated-BRD project, all 7 categories are populated or explicitly N/A, with ≥3 testable requirements in each applicable category.
- **M2 — Traceable NFRs:** 100% of non-`na` NFRs are reachable through the BRD → NFR chain (untraced ones are explicitly flagged by validation, never silently missing).
- **M3 — Authoring speed:** a user can add a fully-linked manual NFR in <3 interactions (open dialog → fill → pick BRD link → save).
- **M4 — Radar legibility:** the Quality Radar correctly reflects MoSCoW weights (must=4…wont=1) and click-to-filter narrows the table to the chosen category.
- **M5 — Feeds-FRS without regression:** FRS output is byte-identical (modulo `nfr_driver` traces) whether NFR is absent, unvalidated, or validated — proven by snapshot test.
- **M6 — Deterministic CI:** the full module test suite passes under `LLM_PROVIDER=mock` with zero Vertex/PageIndex/network calls.
- **M7 — Regeneration safety:** 100% of locked and manual NFRs survive an AI regeneration of their category; a category re-gen never disturbs other categories.

---

## 9. Open Questions

- **OQ-1:** Should NFR numbering be global (`NFR-001..n` across all categories — current plan) or per-category (`PERF-001`, `SEC-001`)? Plan assumes global for gate simplicity and category-mobility.
- **OQ-2:** Should `na=true` categories count as "covered" for the `all_categories_covered` major check (current plan: yes, an explicit N/A satisfies the gate)?
- **OQ-3:** When NFRs are validated after FRS, do we want a one-click "re-gen affected FRS modules to capture nfr_driver traces", or leave it as a manual per-module action (current plan: manual + minor finding)?
- **OQ-4:** Should the SKILL's optional **BIA** (RTO/RPO) inputs be a structured sub-section of NFR (feeding Availability), or just free-text context? Plan: free-text context for now (no BIA artifact — NG-5).
- **OQ-5:** Should `export` produce a single markdown document, a zip (matching the FRS exporter), or both?
- **OQ-6:** Is uncovered-category or vague-measurement a MAJOR or MINOR finding? Plan: missing traceability/category = MAJOR; vague measurement / dup overlap = MINOR.

---

## 10. Implementation map (files)

**Create (backend):** `alembic/versions/0025_nfr_artifact.py` · `app/models/nfr.py` (+register in `__init__.py`) · `app/services/artifacts/manifest/nfr.py` · `app/services/skills/dspy_nfr.py` · `app/services/artifacts/nfr_orchestrator.py` · `app/services/artifacts/validators/nfr.py` · `app/services/artifacts/exporters/nfr.py` · `app/services/context/nfr_layer.py` · `app/api/nfr.py` · `app/services/llm/fixtures/nfr_overview.json` + 7 category fixtures + `nfr_governance.json`.

**Modify (backend):** `app/models/artifact.py` (ArtifactType += `nfr`) · `app/services/context/project_context.py` (NfrLayer, bundle field, BRD-load branch, readiness) · `app/services/context/projection.py` (`nfr` branch + soft feeds-FRS injection) · `app/services/skills/dspy_frs.py` (one-sentence `nfr_driver` instruction) · `app/services/artifacts/frs_orchestrator.py` (`nfr_drivers_missing`/`nfr_drivers_stale` minor findings + advisory hook) · `workers/tasks.py` · `app/main.py` · `app/services/llm/mock_provider.py`.

**Create/modify (frontend):** `lib/api.ts`, `lib/types.ts`, `lib/nfr-manifest.ts`, `app/projects/[id]/page.tsx`, `app/globals.css`, `app/components/nfr/*` (§6.7).

**Verification:** mock-first backend tests (generate → radar → add+link → edit/delete/history → validate → regenerate-survives-manual/locked → feeds-FRS soft-dependency snapshot); `make typecheck && make lint && make test-be`; live UI walkthrough via dev-browser on a seeded validated-BRD project; optional real-Vertex smoke. Full detail in the companion plan.
