# SpecForge — Detailed Business Requirements PRD (Index)

This is the master index for the SpecForge detailed Product Requirements Document (PRD) set. SpecForge is an AI-assisted SDLC documentation platform for enterprise delivery teams: it takes a business change request plus source documents, prior project knowledge, and organisation application knowledge, then guides teams through a governed documentation lifecycle (Requirement Understanding → BRD → FS → NFR → design → test artefacts → review → traceability → approval), treating SDLC documents as connected, versioned, traceable artefacts.

## Sources of truth
- `01-system-overview-and-business-context.md` — product vision, business problem, objectives, the 7 user roles, end-to-end lifecycle, core concepts, enterprise production controls (§8), and implied production capabilities (§9).
- `business-requirements-by-module.md` — the reverse-engineered business requirement catalogue (BR-M0-001 … BR-M5-010).

The PRD files below convert that catalogue into implementation-ready requirements: every business requirement is decomposed into user stories with verifiable acceptance criteria, numbered functional requirements, and the backend/production requirements needed to build it for real.

## Scope of this PRD set
- **Coverage:** all 67 source business requirements across 6 modules — every priority (Must / Should / Could) — **plus 4 added security requirements** (BR-M0-009…012: Authentication & Login, Session & Token Management, Password & Credential Security, API Security & Backend Integrity), for a total of **71** requirements.
- **Depth:** full user-story decomposition per BR.
- **Production scope:** includes backend/production requirements (persistence, auth/RBAC, real LLM + RAG, ingestion pipelines, export jobs, immutable audit) drawn from overview §8 and §9 — not just prototype UI behavior.
- **Status:** brand-new build (no existing codebase). These are requirements, not code; tech-stack specifics live under each module's "Technical Considerations".

## Module PRDs

| Module | File | BRs | Must / Should / Could | User stories | FRs | Backend reqs |
|---|---|---|---|---|---|---|
| 0 — Global System Architecture | [prd-module-0-global-architecture.md](prd-module-0-global-architecture.md) | BR-M0-001…012 (12) | 11 / 1 / 0 | 44 | 61 | 41 |
| 1 — Dashboard & Project Hub | [prd-module-1-dashboard-project-hub.md](prd-module-1-dashboard-project-hub.md) | BR-M1-001…012 (12) | 10 / 2 / 0 | 34 | 58 | 36 |
| 2 — SDLC Document Workbench | [prd-module-2-sdlc-document-workbench.md](prd-module-2-sdlc-document-workbench.md) | BR-M2-001…017 (17) | 17 / 0 / 0 | 37 | 87 | 56 |
| 3 — Template & Prompt Engineer Workspace | [prd-module-3-template-prompt-workspace.md](prd-module-3-template-prompt-workspace.md) | BR-M3-001…009 (9) | 5 / 3 / 1 | 32 | 43 | 33 |
| 4 — Integrations, Configurations & AI Brains | [prd-module-4-integrations-ai-brains.md](prd-module-4-integrations-ai-brains.md) | BR-M4-001…011 (11) | 10 / 1 / 0 | 39 | 51 | 46 |
| 5 — Asset Compilation & Export | [prd-module-5-asset-compilation-export.md](prd-module-5-asset-compilation-export.md) | BR-M5-001…010 (10) | 6 / 3 / 1 | 29 | 48 | 32 |
| **Total** | | **71** | **59 / 10 / 2** | **215** | **348** | **244** |

## ID conventions
- **Business requirement:** `BR-M{module}-{nnn}` (carried over from the source catalogue).
- **User story:** `US-M{module}-{BRnum}-{idx}` (e.g., `US-M2-011-2`).
- **Functional requirement:** `FR-M{module}-{BRnum}-{idx}`.
- **Backend / production requirement:** `BE-M{module}-{BRnum}-{idx}`.

Each module file ends with a Traceability Map (BR → user stories → FRs → backend reqs) so coverage can be audited at a glance.

## User roles (referenced throughout)
Business Analyst · Product Owner / Business Sponsor · Solution Architect · App Owner · QA Lead · Compliance / Risk Reviewer · Platform Administrator / AI Engineer.

## Full business requirement catalogue

### Module 0 — Global System Architecture
| BR | Title | Priority |
|---|---|---|
| BR-M0-001 | Single-Page Workbench Shell | Must |
| BR-M0-002 | Global Project and Document Context | Must |
| BR-M0-003 | Persistent Navigation Chrome | Must |
| BR-M0-004 | Responsive Design Scaling | Should |
| BR-M0-005 | Design Token Governance | Must |
| BR-M0-006 | Global Version History Access | Must |
| BR-M0-007 | Global Auditability | Must |
| BR-M0-008 | Role-Based Access Control | Must |
| BR-M0-009 | User Authentication & Login | Must |
| BR-M0-010 | Session & Token Management (JWT) | Must |
| BR-M0-011 | Password & Credential Security | Must |
| BR-M0-012 | API Security & Backend Integrity | Must |

> BR-M0-009–012 are security requirements added beyond the source catalogue, aligned to the binding SPEC FORGE security standard (`.claude/skills/spec-forge-security/SKILL.md`).

### Module 1 — Dashboard & Project Hub
| BR | Title | Priority |
|---|---|---|
| BR-M1-001 | Portfolio Project Search | Must |
| BR-M1-002 | Portfolio Saved Views | Must |
| BR-M1-003 | Table and Board Portfolio Modes | Should |
| BR-M1-004 | Grouped Portfolio Table | Should |
| BR-M1-005 | Portfolio Insights Triage | Must |
| BR-M1-006 | Project Creation Intake | Must |
| BR-M1-007 | Similar Project Discovery and Reuse | Must |
| BR-M1-008 | Apps in Scope Selection | Must |
| BR-M1-009 | Source Document Intake | Must |
| BR-M1-010 | Project Workspace Stage Map | Must |
| BR-M1-011 | Project Workspace Operational Panels | Must |
| BR-M1-012 | Adaptive Requirement Understanding | Must |

### Module 2 — SDLC Document Workbench
| BR | Title | Priority |
|---|---|---|
| BR-M2-001 | BRD Document Editing | Must |
| BR-M2-002 | BRD Section Toolbar | Must |
| BR-M2-003 | Citation Source Popover | Must |
| BR-M2-004 | Trace Path Popover | Must |
| BR-M2-005 | AI-Assisted Section Actions | Must |
| BR-M2-006 | Document Quality Panel | Must |
| BR-M2-007 | Assumption Ledger | Must |
| BR-M2-008 | Open Question Management | Must |
| BR-M2-009 | Gated Submission for Approval | Must |
| BR-M2-010 | Targeted Review | Must |
| BR-M2-011 | Stale Impact Analysis | Must |
| BR-M2-012 | Section-Scoped Regeneration | Must |
| BR-M2-013 | Traceability Matrix | Must |
| BR-M2-014 | Trace Gap Resolution | Must |
| BR-M2-015 | Functional Specification Generation | Must |
| BR-M2-016 | Non-Functional Specification Generation | Must |
| BR-M2-017 | Downstream Pending Gates | Must |

### Module 3 — Template & Prompt Engineer Workspace
| BR | Title | Priority |
|---|---|---|
| BR-M3-001 | Shared Section Editor | Must |
| BR-M3-002 | Section Rendering Mode Selection | Must |
| BR-M3-003 | Section Metadata Management | Must |
| BR-M3-004 | Section Linkage Management | Must |
| BR-M3-005 | Card-Level Editing | Must |
| BR-M3-006 | Card AI Assistance | Should |
| BR-M3-007 | Template Application | Should |
| BR-M3-008 | Prompt Confidence Threshold | Should |
| BR-M3-009 | Global Tweak and Demo Controls | Could |

### Module 4 — Integrations, Configurations & AI Brains
| BR | Title | Priority |
|---|---|---|
| BR-M4-001 | Application Registry | Must |
| BR-M4-002 | App Onboarding Queue | Should |
| BR-M4-003 | Application AI Brain Detail | Must |
| BR-M4-004 | App Brain Pipeline Transparency | Must |
| BR-M4-005 | App Brain Corpus Management | Must |
| BR-M4-006 | Ask the App Brain | Must |
| BR-M4-007 | App Brain Proposed Updates | Must |
| BR-M4-008 | Promote Learnings from Project | Must |
| BR-M4-009 | App-Brain Grounding in Documents | Must |
| BR-M4-010 | LLM Provider and Skill Configuration | Must |
| BR-M4-011 | Data Security and PII Governance | Must |

### Module 5 — Asset Compilation & Export
| BR | Title | Priority |
|---|---|---|
| BR-M5-001 | Document Export | Must |
| BR-M5-002 | Section Export | Should |
| BR-M5-003 | Trace Matrix Export | Must |
| BR-M5-004 | App Brain Export | Should |
| BR-M5-005 | Assumption Ledger Export | Must |
| BR-M5-006 | Version Snapshot Preview and Compare | Must |
| BR-M5-007 | Non-Destructive Restore | Must |
| BR-M5-008 | Standalone HTML Packaging | Could |
| BR-M5-009 | JSON Schema Export | Should |
| BR-M5-010 | Export Job Management | Should |

## Cross-cutting production themes
These span every module and are detailed where they apply:
- **Authentication, sessions & RBAC** — JWT-based login, session/token management with refresh rotation, credential security, and an API security baseline (BR-M0-009…012, per `.claude/skills/spec-forge-security/SKILL.md`), plus role- and resource-level access to projects, documents, sources, app brains, settings, exports (Module 0 owns the foundation; enforced server-side everywhere — frontend checks are UX-only).
- **Provenance everywhere** — every generated claim is backed by a source span, an app-brain fact, or an explicit tracked assumption.
- **Immutable audit** — all material AI/human actions (generation, regeneration, approval, rejection, restore, export, app-brain merges) are audit-logged with actor, version deltas, and AI metadata (skill/model/prompt versions).
- **Human-in-the-loop gates** — AI drafts; humans validate understanding, accept/reject assumptions, resolve review items, and approve before content becomes authoritative.
- **Traceability & stale-impact enforcement** — dependency graph from BR → FR → design → test → NFR; finalization is blocked on unresolved gaps or unaddressed stale impact.
- **Data security & PII governance** — PII detection at ingestion; permission-filtered retrieval; redaction on export; restricted source text never leaks.

## Open questions (consolidated)
Each module file carries its own Open Questions section. Recurring organisation-level decisions to resolve before/at build time include: supported viewport/zoom range; audit retention and tamper-evidence approach; similar-project match algorithm and thresholds; file-size/type limits and malware-scan policy; confidence-threshold scope (global vs per-skill vs per-section); template approval workflow; secret-rotation policy; export link expiry and tenant retention; and JSON schema deprecation/versioning windows.
