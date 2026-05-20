# SpecForge — Master Roadmap (Tier 2)

Dependency-ordered milestones for building SpecForge as **foundation + vertical slices**. Each milestone delivers a usable end-to-end slice and lays groundwork the next one consumes. Decisions/standards live in [`00-foundations-and-decisions.md`](00-foundations-and-decisions.md); requirements in [`../prd/`](../prd/prd-00-index.md).

**How to use:** Build milestones in order. Before starting each, write its **Tier-3 deep plan** (template at the bottom) — just-in-time, so it reflects what you actually learned in the prior slice.

---

## Why this order
Auth, RBAC, audit, storage, and AI grounding are **cross-cutting** — building any feature module "fully" before they exist forces rework. So: stand up the foundation and the AI substrate first, then slice features that each go UI→API→worker→DB end-to-end. Module 2 (the core engine) is split into **generation/editing** (E3) and the **consistency engine** (E4) because the latter depends on FS/NFR/trace existing.

```
E0 Foundation ──► E1 AI Infra ──► E2 Intake ──► E3 BRD + Section Engine ──► E4 Consistency Engine
                       │                              │                          │
                       └──────────────► E5 Knowledge Loop ◄─────────────────────┘
                                                                                 └──► E6 Export ──► E7 Polish
```

---

## Milestones

### E0 — Foundation / Walking Skeleton
**Goal:** Log in → land in the shell (sidebar/topbar, design tokens) → RBAC enforced → every action audited → version infra ready. No features yet, but the spine is real.
**BRs:** BR-M0-001…012 (all of Module 0).
**Backend:** FastAPI skeleton; auth (login/refresh/logout, JWT, bcrypt); RBAC service + `require_role`; audit store + `audit.emit`; version-snapshot service; `StorageBackend` (postgres impl); Celery + Redis wired; API security middleware (CORS, rate limit, headers); route/permission resolution; global context; Alembic; seed users.
**Frontend:** App shell, persistent nav chrome, breadcrumbs, global context store, design-token system, login, access-denied/fallback routes, version-history panel shell, responsive canvas scaling.
**Depends on:** nothing.
**Exit / demo:** Log in as seeded users of different roles; unauthorized routes → access-denied; an audited no-op action appears in the audit log; health check; CI + security checklist green.

### E1 — AI Infrastructure & App Brain Core
**Goal:** The generation substrate — store app knowledge, configure a provider, ingest a doc, extract facts, answer "ask the app brain" with citations.
**BRs:** BR-M4-010 (provider/skill config), BR-M4-011 (PII/security), BR-M4-001 (registry), BR-M4-003 (app-brain detail), BR-M4-004 (pipeline transparency), BR-M4-005 (corpus management), BR-M4-006 (ask the app brain).
**Backend:** LLM provider abstraction + secret mgmt + model routing; RAG retrieval over **pgvector**; ingestion pipeline (Celery: parse → extract facts → embed); app-brain + fact data model; PII detection/classification; permission-filtered retrieval.
**Frontend:** App registry, app-brain detail (facts, pipeline steps), corpus management, streaming Ask panel with citations.
**Depends on:** E0 (storage, jobs, auth, audit).
**Exit / demo:** Configure provider; ingest a PDF into the PayHub brain; see extracted facts w/ confidence; ask a question → cited answer; restricted content filtered for unauthorized users.

### E2 — Project Intake & Requirement Understanding
**Goal:** Create a project from sources, pick apps in scope, run the adaptive interview, validate the Requirement Understanding (the gate to generation).
**BRs:** BR-M1-001…012 (all of Module 1).
**Backend:** Project store; portfolio search/saved-views/grouping; triage analytics (Celery recompute); project-creation intake; similar-project discovery (embeddings); apps-in-scope loading; source intake (upload → DB storage → ingestion pipeline → PII); requirement-understanding generation + validation gate.
**Frontend:** Dashboard (table/board, saved views, triage), project wizard, source intake UI, project workspace (stage map + operational panels), adaptive interview UI.
**Depends on:** E0, E1.
**Exit / demo:** Create a project from uploaded sources + apps in scope → adaptive interview → validated Requirement Understanding; portfolio triage shows real signals.

### E3 — BRD Generation, Editing & Section Engine
**Goal:** Generate a BRD from the validated understanding and edit it with the shared Section Editor — citations, assumptions, app-brain grounding, AI actions, quality, ledgers.
**BRs:** BR-M2-001, 002, 003, 005, 006, 007, 008; BR-M3-001…008; BR-M4-009 (app-brain grounding in documents).
**Backend:** BRD generation (Celery + LLM + RAG + provenance); section model + rendering kinds; shared Section Editor service (content/metadata/linkages); requirement cards; citation/assumption inspection + ledger; open questions; quality scoring; AI section actions (regenerate/improve/expand/simplify/strengthen-citations/find-contradictions); templates; confidence threshold.
**Frontend:** BRD editor, section toolbar, citation/assumption popovers, Section Editor (3 tabs), card editor, assumption ledger, open-questions panel, quality panel, app-brain grounding footer.
**Depends on:** E0, E1, E2.
**Exit / demo:** Generate a BRD with citations/assumptions/grounding; edit a section; accept an AI suggestion; manage assumptions + open questions; see quality score.

### E4 — Consistency Engine: Review, Traceability, Stale Impact, FS/NFR
**Goal:** Keep the artefact chain aligned — targeted review + gated submission, traceability + gaps, stale impact + section regen, FS and NFR generation, downstream gates.
**BRs:** BR-M2-004, 009, 010, 011, 012, 013, 014, 015, 016, 017.
**Backend:** Trace graph store + rebuild; coverage/gap queries; targeted review queues + submission gating; stale/dependency engine (Celery, section-level); section-scoped regeneration preserving manual edits; FS generator; NFR generator; downstream pending gates + subscribe.
**Frontend:** Trace matrix + coverage strip + gap rail, trace popover, targeted review UI, stale-impact view + regen, FS + NFR screens, pending-stage screens.
**Depends on:** E3.
**Exit / demo:** Generate FS + NFR from approved BRD; trace matrix shows coverage + gaps; change a BRD section → downstream flagged stale → regenerate only affected sections; submission blocked while review items open.

### E5 — Knowledge Loop: Proposed Updates & Promote Learnings
**Goal:** Close the org-memory loop so SpecForge gets better over time.
**BRs:** BR-M4-002 (onboarding queue), BR-M4-007 (proposed updates), BR-M4-008 (promote learnings).
**Backend:** App onboarding queue/skeletons; proposed-update review (merge/refine/dismiss) with owner governance + audit; promote-learnings flow; novelty scoring.
**Frontend:** Onboarding queue, proposed-updates inbox, promote-learnings modal.
**Depends on:** E1 (app brains), E3/E4 (documents to learn from).
**Exit / demo:** Lock a document → promote learnings → owner merges into app brain → a new project inherits the merged fact.

### E6 — Asset Compilation & Export
**Goal:** Get governed content out with provenance and redaction intact.
**BRs:** BR-M5-001…010.
**Backend:** Export service (Celery jobs, status, secure expiring links); document/section/trace/app-brain/ledger exporters; version preview/compare/restore; JSON-schema export + registry; standalone HTML packaging; redaction engine.
**Frontend:** Export dialogs + job status, version compare/restore UI.
**Depends on:** E3/E4 (content), E0 (versioning/audit).
**Exit / demo:** Export a BRD + trace matrix + assumption ledger with provenance/redaction; preview/compare/restore versions; background export job lifecycle visible.

### E7 — Demo Controls, Accessibility & Hardening
**Goal:** Could-priority and polish.
**BRs:** BR-M3-009 (tweak/demo controls, admin-gated); BR-M0-004 accessibility documentation; cross-cutting hardening, perf, a11y.
**Depends on:** all.

---

## Milestone → BR coverage matrix (all 71 accounted for)

| Milestone | BRs | Count |
|---|---|---|
| E0 | BR-M0-001 … BR-M0-012 | 12 |
| E1 | BR-M4-001, 003, 004, 005, 006, 010, 011 | 7 |
| E2 | BR-M1-001 … BR-M1-012 | 12 |
| E3 | BR-M2-001,002,003,005,006,007,008; BR-M3-001…008; BR-M4-009 | 16 |
| E4 | BR-M2-004,009,010,011,012,013,014,015,016,017 | 10 |
| E5 | BR-M4-002, 007, 008 | 3 |
| E6 | BR-M5-001 … BR-M5-010 | 10 |
| E7 | BR-M3-009 (+ BR-M0-004 docs, hardening) | 1 |
| **Total** | | **71** |

---

## Cross-cutting threads (span milestones)
- **Audit** every material action from E0 onward (BR-M0-007).
- **RBAC + permission-filtered retrieval** enforced in every slice (BR-M0-008, BR-M4-011).
- **Provenance** (source span / app-brain fact / assumption) on every generated claim from E3.
- **Versioning + staleness** participation whenever a document type is added (E3, E4, E6).

## Top risks
- **Staleness/trace engine** (E4) is the hardest piece — section-level dependency tracking; prototype the graph early.
- **RAG quality / pgvector scale** — validate retrieval quality in E1 before generation depends on it.
- **Storage migration** — keep the `StorageBackend` boundary clean so the Azure switch stays a config change.
- **LLM cost/latency** — generation is async (Celery) with streaming; budget tokens and cache where possible.

## Next step
Write the **E0 deep plan** (Tier 3) using the template below, then start building. Generate each subsequent deep plan just before its milestone.

---

## Tier-3 deep-plan template (copy per milestone)
```
# E{n} — {name} — Deep Plan
## BRs covered & acceptance mapping   (list BR/US IDs → tests)
## Dependencies (what must already exist)
## Data model & migrations
## API contracts (endpoints, auth, status codes, schemas)
## Background jobs (Celery tasks, triggers, status)
## Frontend (views, components, state, routes)
## Ordered work breakdown (tasks → BR/US IDs)
## Security checklist (from spec-forge-security skill)
## Test plan (unit / integration / e2e mapped to acceptance criteria)
## Done criteria + demo script
## Risks & open questions
```
