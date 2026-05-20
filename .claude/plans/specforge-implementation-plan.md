# SpecForge — Implementation Plan (Index)

Planning is organized in three tiers so detail lands where it counts without rotting.

| Tier | Document | Purpose |
|---|---|---|
| 1 — Foundations | [`00-foundations-and-decisions.md`](00-foundations-and-decisions.md) | Locked tech stack, repo layout, and cross-cutting standards (auth, RBAC, audit, storage, jobs, versioning, provenance, testing). |
| 2 — Roadmap | [`01-master-roadmap.md`](01-master-roadmap.md) | Dependency-ordered milestones (E0–E7), what each delivers, exit criteria, and the BR-coverage matrix (all 71 BRs). |
| 3 — Deep plans | `E{n}-*.md` (written just-in-time) | One build-ready plan per milestone, mapping tasks to BR/US IDs. Template at the end of the roadmap. |

**Requirements source of truth:** [`../prd/prd-00-index.md`](../prd/prd-00-index.md) — 71 BRs across 6 modules.
**Binding security standard:** [`../skills/spec-forge-security/SKILL.md`](../skills/spec-forge-security/SKILL.md).

## Stack at a glance
FastAPI + Next.js (App Router, TS) + PostgreSQL · pgvector for RAG · **DB-first file storage behind a `StorageBackend` interface** (→ Azure Blob later) · **Celery + Redis** for background jobs · JWT/bcrypt auth per spec-forge-security skill · Railway/Vercel now (Azure later).

## Build order (foundation + vertical slices)
E0 Foundation → E1 AI Infra → E2 Intake → E3 BRD + Section Engine → E4 Consistency Engine → E5 Knowledge Loop → E6 Export → E7 Polish.

## Next step
Write the **E0 deep plan**, then start building. Generate each later deep plan just before its milestone.
