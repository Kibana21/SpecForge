# PRD: Module 2 — SDLC Document Workbench

> Part of the SpecForge detailed business-requirements PRD set. Sources: `.claude/prd/01-system-overview-and-business-context.md`, `.claude/prd/business-requirements-by-module.md`.

## 1. Introduction / Overview

Module 2 is the core production engine of SpecForge. It turns a validated Requirement Understanding (produced and approved in Module 1) into structured SDLC artefacts and then keeps those artefacts consistent with one another over the life of the project. It covers the BRD editor and its right-side intelligence panels, AI-assisted section actions, document quality scoring, the assumption ledger, open-question management, gated submission for approval, targeted review queues, stale-impact analysis, section-scoped regeneration, the traceability matrix and trace-gap resolution, Functional Specification (FS) and Non-Functional Specification (NFR) generation, and the pending-gate screens for downstream documents (ADR, TBP, SDD, TS, TC).

The business need is not simply "generate a BRD." Enterprise delivery requires a chain of artefacts that must stay aligned. A BRD describes business intent; a Functional Specification turns that intent into system behavior; an NFR document defines measurable quality targets; architecture and build permits depend on approved upstream artefacts; and test scenarios and test cases must prove the requirements. SpecForge models this lifecycle as a dependency graph so that changes can be controlled instead of silently drifting across documents. When an upstream section changes (for example a BRD scope or limit clause), SpecForge identifies exactly which downstream FS/NFR/design/test sections become stale, why, what text needs to change, and which sections can be regenerated safely while preserving unrelated manual edits.

This module also defines SpecForge's human-in-the-loop governance model. The AI may draft, regenerate, improve, expand, simplify, strengthen citations, check for contradictions, and suggest — but the human validates understanding, accepts or rejects AI suggestions, accepts or rejects assumptions, resolves targeted review items, resolves trace gaps, and submits documents for approval. AI assistance must be visible and auditable rather than invisible prose generation: every generated claim should be backed by a source span, an app-brain fact, or an explicit assumption, and every material AI or human action that affects generated content, review status, assumptions, traceability, or approval must be recorded.

Because this is a real system to be built (not just a prototype), this PRD also specifies the backend and production capabilities Module 2 depends on, drawn from overview §8 (enterprise controls) and §9 (implied production capabilities): real LLM provider integration and model routing; permission-filtered RAG over indexed sources and app-brain facts; section-scoped regeneration jobs with streaming progress; a staleness/dependency-graph computation service; a traceability graph store; version-snapshot and immutable audit persistence; contradiction, citation, and quality scoring services; and human-approval gates with signatures — all subject to RBAC, source/PII security, and prompt/model/skill version governance.

## 2. Goals

- Turn a validated Requirement Understanding into a structured, citation-backed BRD whose AI-generated content is visibly distinct from human edits and always traceable to a source span, an app-brain fact, or an explicit assumption.
- Give every BRD section a consistent set of authoring and AI-assist controls (edit, regenerate, improve, expand, simplify, strengthen citations, find contradictions, comment, history, metadata, approve, lock) that preserve manual edits outside the targeted scope.
- Make provenance inspectable in place: any citation, assumption marker, or trace chip can be clicked to reveal its source, reference, or forward trace chain.
- Continuously score document quality across completeness, clarity, traceability, risk coverage, consistency, and NFR coverage, including cross-document consistency checks, so issues are surfaced before approval.
- Track every AI-introduced or inferred assumption in an exportable ledger with an accept/reject/ask-owner workflow, and track every open question with an assignable, resolvable workflow that merges back into document sections with provenance.
- Enforce governed approval: documents cannot be submitted for approval while required review items remain unresolved, and stale downstream documents cannot be finalized until invalidation is resolved or explicitly accepted.
- Focus reviewer effort on changed, new, low-confidence, contradictory, and open-question content via targeted review queues instead of full-document rereads.
- Detect upstream changes and compute downstream stale impact at section level, then allow regeneration of only affected sections while preserving unrelated manual edits and updating trace links, versions, and audit records.
- Maintain a living traceability matrix from BRs to FRs, design sections, test cases, and NFRs, make coverage gaps visible and actionable, and require a governed reason for ignored gaps.
- Generate downstream FS and NFR artefacts that are traceable to upstream BRs, detect contradictions and stale sizing against current upstream values, and propagate missing coverage to the traceability matrix.
- Gate downstream document generation (ADR, TBP, SDD, TS, TC) on required upstream approvals, clearly showing what is required and allowing users to subscribe for notification when dependencies are approved.
- Enforce enterprise controls (RBAC, source/PII security, immutable audit, prompt/model/skill version governance, approval signatures) on every Module 2 generation, edit, review, regeneration, and approval action.

## 3. Scope

In scope (with priority):

- BR-M2-001 — BRD Document Editing — Must
- BR-M2-002 — BRD Section Toolbar — Must
- BR-M2-003 — Citation Source Popover — Must
- BR-M2-004 — Trace Path Popover — Must
- BR-M2-005 — AI-Assisted Section Actions — Must
- BR-M2-006 — Document Quality Panel — Must
- BR-M2-007 — Assumption Ledger — Must
- BR-M2-008 — Open Question Management — Must
- BR-M2-009 — Gated Submission for Approval — Must
- BR-M2-010 — Targeted Review — Must
- BR-M2-011 — Stale Impact Analysis — Must
- BR-M2-012 — Section-Scoped Regeneration — Must
- BR-M2-013 — Traceability Matrix — Must
- BR-M2-014 — Trace Gap Resolution — Must
- BR-M2-015 — Functional Specification Generation — Must
- BR-M2-016 — Non-Functional Specification Generation — Must
- BR-M2-017 — Downstream Pending Gates — Must

Priorities covered: Must (all of BR-M2-001 through BR-M2-017). No Should- or Could-priority requirements exist in Module 2; all 17 requirements are launch-critical "Must" requirements.

## 4. Users & Roles

All seven SpecForge roles interact with Module 2, with access enforced by RBAC:

- **Business Analyst (BA)** — Primary operator of the workbench. Edits BRD sections; runs AI section actions (regenerate, improve, expand, simplify, strengthen citations, find contradictions); inspects citations and trace chains; manages the assumption ledger and open questions; resolves targeted review items; runs section-scoped regeneration to resolve stale impact; resolves trace gaps; generates FS and NFR; and submits documents for approval.
- **Product Owner / Business Sponsor** — Reviews BRD content and requirement cards; participates in targeted review for business-facing items; confirms scope and trade-offs; provides business approval at the gate.
- **Solution Architect** — Reviews functional/non-functional consistency, application constraints, integrations, and downstream stale impact; reviews FS and NFR for design readiness; resolves architecture-related contradictions and stale sizing; approves FS/NFR where authorized; consumes downstream pending gates.
- **App Owner** — Provides the governed app-brain facts that ground BRD/FS/NFR sections; sees app-brain grounding surfaced on sections; is a target for "ask the owner" on assumptions and for open questions about app facts (governance of the brain itself lives in Module 4).
- **QA Lead** — Uses the traceability matrix to confirm BR/FR coverage by design and test cases; reviews and resolves trace gaps; consumes FS/NFR missing-test-coverage signals propagated to the matrix; reviews boundary/exception coverage.
- **Compliance / Risk Reviewer** — Relies on citations, assumption provenance, the assumption ledger, the quality panel's consistency/risk findings, and NFR privacy/security/auditability targets; uses targeted review for low-confidence and contradictory items; depends on immutable audit of generation and approval.
- **Platform Administrator / AI Engineer** — Governs the providers, model routing, skills, prompt-template versions, and confidence thresholds that Module 2's AI actions consume; ensures regeneration jobs, RAG, contradiction/quality services, audit, and approval signatures operate within policy.

## 5. Key Business Objects

- **Document module** — A structured SDLC artefact (BRD, FS, NFR, and the pending ADR/TBP/SDD/TS/TC) with dependencies, sections, version history, review queues, and quality expectations.
- **Document section** — A unit of a document with status (approved, edited, AI-generated, stale), content, rendering kind, confidence (for AI content), section version, edit time, citations, assumptions, trace links, and app-brain grounding.
- **Requirement card** — A structured requirement object with ID, priority, title, description, acceptance criteria, rationale, owner, source, and trace links, embedded in a section and expandable/collapsible.
- **Citation / source span** — A reference from generated content to a specific location in a source document (source name, location, quote, reference ID) or to an app-brain fact.
- **AI assumption** — A claim used in generated content that is not fully proven by sources, with ID, text, confidence, source/inference reason, section, and accept/reject/ask-owner status.
- **Open question** — An assignable unresolved decision/missing fact with ID, text, section, assignee, due date, and status that merges back into a section with provenance when resolved.
- **Review item** — A targeted-review entry classified by kind (changed, new, low-confidence, open-question, contradiction) with section, title, source, severity, supporting text/diff, and resolution state.
- **Stale impact item** — A downstream invalidation caused by an upstream change, computed at section level, with affected document, section, severity, stale reason, current text, and proposed regenerated text.
- **Trace row / trace link** — A row in the traceability matrix linking a BR to FRs, design sections, test cases, and NFRs, with status and gap notes; missing links are gaps.
- **Functional requirement (FR)** — A traceable FS requirement with ID, upstream BR, description, preconditions, behavior, outputs, errors, acceptance criteria, dependencies, and NFR coupling.
- **Non-functional requirement (NFR)** — A measurable quality requirement with ID, category, description, targets, measurement method, constrained FRs, and release gate.
- **Version snapshot** — An immutable record of a document/section at a point in time, with actor, timestamp, change note, changed sections, change count, and generation type.
- **AI action** — A discrete AI operation (regenerate, improve, expand, simplify, strengthen citations, find contradictions, generate FS/NFR) recording skill version, model, prompt template version, source references, and output decision state.

## 6. Detailed Business Requirements

### BR-M2-001 — BRD Document Editing
**Priority:** Must

**Requirement:** SpecForge shall provide a BRD editor that renders structured sections, generated content, human edits, requirement cards, citations, assumptions, traceability links, and app-brain grounding, with each section showing its status (approved, edited, AI-generated, stale), AI-generated sections showing confidence, edited sections showing section version and edit time, expandable/collapsible requirement cards, clickable citation and assumption chips, and visible app-brain grounding where app facts were used.

**User Stories:**

#### US-M2-001-1: Read a structured BRD with clear status and provenance
**As a** Business Analyst, **I want** the BRD to render structured sections with status, confidence, and edit metadata **so that** I can tell at a glance what is AI-generated, edited, approved, or stale and how trustworthy each section is.

**Acceptance Criteria:**
- [ ] Each section displays a status of approved, edited, AI-generated, or stale.
- [ ] AI-generated sections display a confidence percentage.
- [ ] Edited sections display their section version and the time of the last edit.
- [ ] AI-generated content is visually distinct from human-edited content.
- [ ] App-brain grounding is visibly indicated on sections that used app facts.
- [ ] Verify in browser using dev-browser skill.

#### US-M2-001-2: Expand requirement cards and inspect inline chips
**As a** Business Analyst, **I want** to expand/collapse requirement cards and click citation and assumption chips **so that** I can drill into requirement detail and provenance without leaving the section.

**Acceptance Criteria:**
- [ ] Requirement cards embedded in sections can be expanded and collapsed.
- [ ] Citation chips are clickable (opening the citation source popover, see BR-M2-003).
- [ ] Assumption chips are clickable (opening the source/assumption popover, see BR-M2-003).
- [ ] Trace links/chips are present on sections/cards where requirements have downstream coverage (see BR-M2-004).
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M2-001-1: The system must render the BRD as ordered, structured sections containing generated content, human edits, requirement cards, citations, assumptions, trace links, and app-brain grounding.
- FR-M2-001-2: The system must display each section's status as approved, edited, AI-generated, or stale.
- FR-M2-001-3: The system must display a confidence percentage on AI-generated sections.
- FR-M2-001-4: The system must display section version and edit time on edited sections.
- FR-M2-001-5: The system must render requirement cards as expandable/collapsible elements.
- FR-M2-001-6: The system must render citation and assumption chips as clickable controls.
- FR-M2-001-7: The system must visually distinguish AI-generated content from human-edited content and surface app-brain grounding on sections that used app facts.

**Backend / Production Requirements:**
- BE-M2-001-1: A persistent document store must hold the BRD as structured sections with status, confidence, section version, edit time, rendering kind, requirement cards, citations, assumptions, trace links, and app-brain grounding references (overview §9 persistent database).
- BE-M2-001-2: The BRD must be generated from the validated Requirement Understanding via the LLM orchestration service using permission-filtered RAG over indexed sources and selected app-brain facts, attaching citations/assumptions/grounding to each generated claim (overview §9 LLM integration, RAG; §8 access controls).
- BE-M2-001-3: Generation and each subsequent change must create a version snapshot and AI/human audit record (skill version, model, prompt template version, source references, decision state) (overview §8 audit, version governance).
- BE-M2-001-4: Section reads must be RBAC-filtered so restricted source content underlying citations is not exposed to unauthorized users (overview §8).

### BR-M2-002 — BRD Section Toolbar
**Priority:** Must

**Requirement:** Each BRD section shall expose controls for edit, regenerate, improve wording, comment, section history, and a "more" menu, where edit opens the shared Section Editor with current content, regenerate starts section-specific generation, improve wording creates an inline AI suggestion, comment opens a section comment composer, section history opens version history scoped to the document/section, and the more menu includes edit metadata, mark approved, lock, copy link, export, and delete actions.

**User Stories:**

#### US-M2-002-1: Use the core section controls
**As a** Business Analyst, **I want** edit, regenerate, improve wording, comment, and history controls on each section **so that** I can author and govern that section in place.

**Acceptance Criteria:**
- [ ] Edit opens the shared Section Editor (Module 3) pre-loaded with the section's current content.
- [ ] Regenerate starts section-specific (section-scoped) generation for that section.
- [ ] Improve wording produces an inline AI suggestion for that section.
- [ ] Comment opens a section comment composer.
- [ ] Section history opens version history scoped to that document/section.
- [ ] Verify in browser using dev-browser skill.

#### US-M2-002-2: Use the section "more" menu actions
**As a** Business Analyst, **I want** a more menu with edit metadata, mark approved, lock, copy link, export, and delete **so that** I can govern the section's lifecycle and sharing.

**Acceptance Criteria:**
- [ ] The more menu includes: edit metadata, mark approved, lock, copy link, export, and delete actions.
- [ ] Edit metadata opens section metadata management (Module 3).
- [ ] Mark approved sets the section status to approved (subject to authorization).
- [ ] Lock prevents AI modification while still allowing authorized manual edits.
- [ ] Copy link copies a deep link to the section; export triggers section export (Module 5); delete removes the section (with confirmation).
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M2-002-1: The system must expose per-section controls for edit, regenerate, improve wording, comment, and section history.
- FR-M2-002-2: Edit must open the shared Section Editor with the section's current content.
- FR-M2-002-3: Regenerate must initiate section-scoped generation for the targeted section only.
- FR-M2-002-4: Improve wording must create an inline AI suggestion for the section.
- FR-M2-002-5: Comment must open a section comment composer; section history must open version history scoped to the document/section.
- FR-M2-002-6: The more menu must include edit metadata, mark approved, lock, copy link, export, and delete.
- FR-M2-002-7: Lock must prevent AI modification of the section while permitting authorized manual edits.

**Backend / Production Requirements:**
- BE-M2-002-1: Mark approved, lock, delete, and metadata changes must be authorized by RBAC and recorded as immutable audit events with actor, timestamp, and affected section (overview §8 audit, RBAC).
- BE-M2-002-2: Lock state must be enforced server-side so AI actions (regenerate/improve/expand/etc.) cannot modify a locked section (overview §8).
- BE-M2-002-3: Comments must be persisted against the section with author and timestamp; copy link must resolve to an access-controlled deep link; export must invoke the Module 5 section-export service with redaction/permission enforcement.
- BE-M2-002-4: Each toolbar action that changes content or status must create a version snapshot (overview §6 version infra).

### BR-M2-003 — Citation Source Popover
**Priority:** Must

**Requirement:** SpecForge shall allow users to inspect the source behind every citation or AI assumption marker via a popover opened near the clicked chip, displaying source name, location, quote or assumption text, and reference ID, providing actions to open the source and copy the reference, and closing on outside click.

**User Stories:**

#### US-M2-003-1: Inspect the source behind a citation or assumption
**As a** Compliance Reviewer, **I want** clicking a citation or assumption marker to open a popover with its source detail **so that** I can verify provenance without leaving the document.

**Acceptance Criteria:**
- [ ] Clicking a citation chip opens a popover positioned near the clicked chip.
- [ ] Clicking an AI assumption marker opens the same popover behavior for that assumption.
- [ ] The popover displays source name, location, the quote (for citations) or the assumption text (for assumptions), and the reference ID.
- [ ] Verify in browser using dev-browser skill.

#### US-M2-003-2: Act on and dismiss the popover
**As a** Business Analyst, **I want** open-source and copy-reference actions and an easy dismiss **so that** I can navigate to evidence or capture the reference quickly.

**Acceptance Criteria:**
- [ ] The popover provides an "open source" action that navigates to the underlying source.
- [ ] The popover provides a "copy reference" action that copies the reference ID.
- [ ] The popover closes on outside click.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M2-003-1: The system must open a popover anchored near the clicked citation or assumption chip.
- FR-M2-003-2: The popover must display source name, location, quote-or-assumption text, and reference ID.
- FR-M2-003-3: The popover must provide open-source and copy-reference actions.
- FR-M2-003-4: The popover must close on outside click.

**Backend / Production Requirements:**
- BE-M2-003-1: The citation service must resolve a citation/assumption marker to its source span (document, location, quote) or app-brain fact and reference ID from the persistent provenance store (overview §9 persistent database).
- BE-M2-003-2: Open-source navigation and quote display must enforce the user's clearance; restricted source text must not be revealed in the popover to unauthorized users (overview §8 source security, RBAC).

### BR-M2-004 — Trace Path Popover
**Priority:** Must

**Requirement:** SpecForge shall show the forward trace chain for business and functional requirements inline from document chips, where trace chips display counts for FR, design, and test coverage, missing links are marked as gaps, clicking a trace chip opens a popover showing BR → FR → Design → Test, and popover actions allow opening the traceability matrix and related documents.

**User Stories:**

#### US-M2-004-1: See forward trace coverage inline
**As a** QA Lead, **I want** trace chips on requirements showing FR/design/test counts and gaps **so that** I can spot coverage problems while reading the document.

**Acceptance Criteria:**
- [ ] Trace chips display counts for FR coverage, design coverage, and test coverage.
- [ ] Missing links are marked as gaps on the chip/popover.
- [ ] Verify in browser using dev-browser skill.

#### US-M2-004-2: Open the trace chain and navigate
**As a** Solution Architect, **I want** to click a trace chip to see the BR → FR → Design → Test chain and jump to the matrix or related docs **so that** I can follow a requirement across the lifecycle.

**Acceptance Criteria:**
- [ ] Clicking a trace chip opens a popover showing the forward chain BR → FR → Design → Test.
- [ ] The popover provides an action to open the traceability matrix.
- [ ] The popover provides actions to open related documents in the chain.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M2-004-1: The system must render trace chips showing FR, design, and test coverage counts for business/functional requirements.
- FR-M2-004-2: The system must mark missing links as gaps.
- FR-M2-004-3: The system must open a popover showing the forward trace chain BR → FR → Design → Test when a trace chip is clicked.
- FR-M2-004-4: The popover must provide actions to open the traceability matrix and related documents.

**Backend / Production Requirements:**
- BE-M2-004-1: A traceability graph store must maintain forward links from BRs to FRs, design sections, and test cases, and compute coverage counts and gaps per requirement (overview §9 persistent database; traceability as a living graph, overview §1).
- BE-M2-004-2: Trace chip data and popover navigation must be RBAC-filtered so links to documents the user cannot access are not exposed (overview §8).

### BR-M2-005 — AI-Assisted Section Actions
**Priority:** Must

**Requirement:** SpecForge shall support AI-assisted actions for regenerating, improving, expanding, simplifying, strengthening citations, and finding contradictions for focused sections, where regeneration streams progress and preserves manual edits outside the target section, inline suggestions show running and ready states, users can accept replacement / insert alongside / reject suggestions, citation checks identify missing or weak citations, and contradiction checks can route users to targeted review.

**User Stories:**

#### US-M2-005-1: Run focused AI actions on a section
**As a** Business Analyst, **I want** AI actions to regenerate, improve, expand, simplify, strengthen citations, and find contradictions on a focused section **so that** I can refine that section without affecting the rest of the document.

**Acceptance Criteria:**
- [ ] AI actions are available for: regenerate, improve, expand, simplify, strengthen citations, and find contradictions, scoped to the focused section.
- [ ] Regeneration streams progress while running.
- [ ] Regeneration preserves manual edits outside the target section.
- [ ] Verify in browser using dev-browser skill.

#### US-M2-005-2: Review and act on inline suggestions
**As a** Business Analyst, **I want** inline suggestions to show running/ready states and let me accept, insert alongside, or reject **so that** I stay in control of what becomes authoritative.

**Acceptance Criteria:**
- [ ] Inline suggestions display a running state while generating and a ready state when complete.
- [ ] The user can accept the suggestion as a replacement.
- [ ] The user can insert the suggestion alongside the existing content.
- [ ] The user can reject the suggestion.
- [ ] No AI suggestion becomes authoritative until the user accepts/inserts it.
- [ ] Verify in browser using dev-browser skill.

#### US-M2-005-3: Check citations and contradictions
**As a** Compliance Reviewer, **I want** citation checks to flag missing/weak citations and contradiction checks to route me to targeted review **so that** unsupported and conflicting content is caught.

**Acceptance Criteria:**
- [ ] Citation checks identify missing or weak citations in the focused section.
- [ ] Contradiction checks can route the user to the targeted review queue with the relevant item(s).
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M2-005-1: The system must provide section-scoped AI actions: regenerate, improve, expand, simplify, strengthen citations, and find contradictions.
- FR-M2-005-2: The system must stream regeneration progress and preserve manual edits outside the target section.
- FR-M2-005-3: The system must display running and ready states for inline suggestions.
- FR-M2-005-4: The system must allow accept-as-replacement, insert-alongside, and reject for suggestions, and treat content as authoritative only after user acceptance.
- FR-M2-005-5: The system must identify missing or weak citations via citation checks.
- FR-M2-005-6: The system must allow contradiction checks to create/route targeted review items.

**Backend / Production Requirements:**
- BE-M2-005-1: AI section actions must call the LLM provider via model routing with permission-filtered RAG over indexed sources and app-brain facts, scoped to the target section's content and context (overview §9 LLM integration, RAG; §8).
- BE-M2-005-2: Section-scoped operations must not modify content outside the target section; locked sections must be rejected (overview §8, BR-M2-002).
- BE-M2-005-3: A citation-scoring service must evaluate citation presence/strength; a contradiction service must compare the section against current BRD/FS/NFR values and app-brain facts and emit targeted review items (overview §9).
- BE-M2-005-4: Each AI action must record skill version, model, prompt template version, source references, and decision state, and create version/audit records on acceptance (overview §8 audit, version governance).
- BE-M2-005-5: The confidence threshold configured for drafting (Module 3) must govern these actions and be stored in AI audit metadata (overview §8 version governance).

### BR-M2-006 — Document Quality Panel
**Priority:** Must

**Requirement:** SpecForge shall calculate and display document quality across completeness, clarity, traceability, risk coverage, consistency, and NFR coverage, showing an overall score out of 100, each subscore with a progress bar, findings grouped by severity, and cross-document checks for BRD/FS, FS/test, BRD/NFR, and glossary consistency.

**User Stories:**

#### US-M2-006-1: See document quality scores
**As a** Business Analyst, **I want** an overall quality score and per-dimension subscores **so that** I can judge document health before submitting for approval.

**Acceptance Criteria:**
- [ ] An overall quality score is displayed out of 100.
- [ ] Subscores are displayed for completeness, clarity, traceability, risk coverage, consistency, and NFR coverage.
- [ ] Each subscore is displayed with a progress bar.
- [ ] Verify in browser using dev-browser skill.

#### US-M2-006-2: Review findings and cross-document checks
**As a** Compliance Reviewer, **I want** findings grouped by severity and cross-document consistency results **so that** I can prioritize fixes and catch inconsistencies between documents.

**Acceptance Criteria:**
- [ ] Findings are grouped by severity.
- [ ] Cross-document checks identify BRD/FS consistency results.
- [ ] Cross-document checks identify FS/test consistency results.
- [ ] Cross-document checks identify BRD/NFR consistency results.
- [ ] Cross-document checks identify glossary consistency results.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M2-006-1: The system must calculate document quality across completeness, clarity, traceability, risk coverage, consistency, and NFR coverage.
- FR-M2-006-2: The system must display an overall score out of 100 and each subscore with a progress bar.
- FR-M2-006-3: The system must group findings by severity.
- FR-M2-006-4: The system must perform and display cross-document checks for BRD/FS, FS/test, BRD/NFR, and glossary consistency.

**Backend / Production Requirements:**
- BE-M2-006-1: A quality-scoring service must compute the six subscores and overall score from document content, citations, trace coverage, risk content, and NFR coverage (overview §9 analytics computation).
- BE-M2-006-2: A cross-document consistency service must compare BRD/FS, FS/test, BRD/NFR, and glossary terms and emit findings with severity (overview §9; consistency objective, overview §3).
- BE-M2-006-3: Quality results must be persisted and recomputed on relevant content changes; findings should be linkable to targeted review where applicable (overview §9).

### BR-M2-007 — Assumption Ledger
**Priority:** Must

**Requirement:** SpecForge shall maintain an assumption ledger for every AI-introduced or inferred assumption, where each assumption includes ID, text, confidence, source, section, and status; users can filter all/open/accepted assumptions; users can accept, reject, or ask the owner about open assumptions; accepted assumptions are visibly distinguished; and the ledger can be exported.

**User Stories:**

#### US-M2-007-1: Review the assumption ledger
**As a** Compliance Reviewer, **I want** a ledger of every AI-introduced/inferred assumption with full attributes and filtering **so that** I can audit what the system assumed and where.

**Acceptance Criteria:**
- [ ] Each assumption displays ID, text, confidence, source, section, and status.
- [ ] The ledger captures every AI-introduced or inferred assumption.
- [ ] Users can filter the ledger by all, open, and accepted assumptions.
- [ ] Accepted assumptions are visibly distinguished from others.
- [ ] Verify in browser using dev-browser skill.

#### US-M2-007-2: Resolve and export assumptions
**As a** Business Analyst, **I want** to accept, reject, or ask the owner about open assumptions and export the ledger **so that** I can resolve them and provide an audit/compliance record.

**Acceptance Criteria:**
- [ ] Users can accept an open assumption.
- [ ] Users can reject an open assumption.
- [ ] Users can ask the owner about an open assumption (creating an inquiry/open question to the relevant owner).
- [ ] The ledger can be exported.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M2-007-1: The system must record every AI-introduced or inferred assumption with ID, text, confidence, source, section, and status.
- FR-M2-007-2: The system must allow filtering by all, open, and accepted assumptions.
- FR-M2-007-3: The system must allow accept, reject, and ask-the-owner actions on open assumptions.
- FR-M2-007-4: The system must visibly distinguish accepted assumptions.
- FR-M2-007-5: The system must allow exporting the ledger.

**Backend / Production Requirements:**
- BE-M2-007-1: An assumption store must persist assumptions with ID, text, confidence, source/inference reason, section, status, and decision history; assumptions are created automatically when AI introduces unproven claims (overview §6 Assumption; §9 persistent database).
- BE-M2-007-2: Accept/reject/ask-owner decisions must be authorized and recorded as immutable audit events; ask-owner must create a routed inquiry/open question to the relevant owner (overview §8 audit; §9 notification/inbox).
- BE-M2-007-3: Ledger export must invoke the Module 5 export service preserving status distinctions and respecting data classification and access controls (overview §8; BR-M5-005 alignment).

### BR-M2-008 — Open Question Management
**Priority:** Must

**Requirement:** SpecForge shall maintain assignable open questions that merge back into relevant document sections with provenance when resolved, where each question includes ID, text, section, assignee, due date, and status; users can reassign, resolve, and add questions; assigned and open statuses are visually distinct; and resolved questions produce traceable document updates.

**User Stories:**

#### US-M2-008-1: Manage assignable open questions
**As a** Business Analyst, **I want** to add, reassign, and track open questions with due dates and status **so that** unresolved decisions are owned and visible.

**Acceptance Criteria:**
- [ ] Each open question displays ID, text, section, assignee, due date, and status.
- [ ] Users can add a new open question.
- [ ] Users can reassign an open question to a different assignee.
- [ ] Assigned and open statuses are visually distinct.
- [ ] Verify in browser using dev-browser skill.

#### US-M2-008-2: Resolve a question into the document with provenance
**As a** Business Analyst, **I want** resolving a question to merge the answer back into the relevant section with provenance **so that** the document reflects the decision and the change is traceable.

**Acceptance Criteria:**
- [ ] Users can resolve an open question.
- [ ] A resolved question produces a traceable update in the relevant document section.
- [ ] The merged update retains provenance to the originating question.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M2-008-1: The system must record open questions with ID, text, section, assignee, due date, and status.
- FR-M2-008-2: The system must allow adding, reassigning, and resolving open questions.
- FR-M2-008-3: The system must visually distinguish assigned and open statuses.
- FR-M2-008-4: The system must merge resolved questions back into the relevant section as a traceable document update with provenance.

**Backend / Production Requirements:**
- BE-M2-008-1: An open-question store must persist questions with full attributes, assignment, due date, status, and resolution history (overview §6 Open Question; §9 persistent database).
- BE-M2-008-2: Resolution must apply the answer to the target section, create a version snapshot, and persist a provenance link from the section update to the originating question (overview §6; §8 version infra).
- BE-M2-008-3: Assignment/reassignment must notify the assignee via the inbox/notification workflow and be audit logged (overview §9 notification; §8 audit).

### BR-M2-009 — Gated Submission for Approval
**Priority:** Must

**Requirement:** SpecForge shall prevent document submission for approval while required review items remain unresolved, where submit-for-approval is disabled when the open review-item count is greater than zero, the review button displays the unresolved count, a tooltip explains why submission is disabled, and once required review items are resolved submission becomes available for authorized users.

**User Stories:**

#### US-M2-009-1: Be blocked from submitting with open review items
**As a** Business Analyst, **I want** submission disabled while required review items are unresolved, with the count and an explanation **so that** I cannot submit an incomplete document and I know what is blocking me.

**Acceptance Criteria:**
- [ ] Submit-for-approval is disabled when the open review-item count is greater than zero.
- [ ] The review button displays the count of unresolved review items.
- [ ] A tooltip on the disabled submit control explains why submission is disabled.
- [ ] Verify in browser using dev-browser skill.

#### US-M2-009-2: Submit once review items are resolved
**As an** authorized approver/submitter, **I want** submission to become available once required review items are resolved **so that** I can advance the document through the gate.

**Acceptance Criteria:**
- [ ] When the open required review-item count reaches zero, submit-for-approval becomes available.
- [ ] Submission is available only to authorized users.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M2-009-1: The system must disable submit-for-approval while the open required review-item count is greater than zero.
- FR-M2-009-2: The system must display the unresolved review-item count on the review button.
- FR-M2-009-3: The system must provide a tooltip explaining why submission is disabled.
- FR-M2-009-4: The system must enable submission for authorized users once required review items are resolved.

**Backend / Production Requirements:**
- BE-M2-009-1: The system must compute open required review-item count server-side and enforce the submission gate regardless of client state (overview §8 approval gates, traceability/stale enforcement before finalization).
- BE-M2-009-2: Submission for approval must be RBAC-restricted to authorized submitters/approvers and recorded as an immutable audit event with an approval signature where applicable (overview §8 RBAC, audit, approval signatures).

### BR-M2-010 — Targeted Review
**Priority:** Must

**Requirement:** SpecForge shall provide document-specific targeted review queues for changed, new, low-confidence, open-question, and contradiction items, where queues can be filtered by item kind, each item shows section/title/source/severity and supporting text/diff, users can resolve individual items, the center pane shows focused before/after or recommendation detail, and the right rail shows reviewers, statuses, comments, and a reply input.

**User Stories:**

#### US-M2-010-1: Triage targeted review items by kind
**As a** reviewer, **I want** review queues filtered by changed, new, low-confidence, open-question, and contradiction kinds with key item attributes **so that** I review only what needs attention instead of the whole document.

**Acceptance Criteria:**
- [ ] Review queues can be filtered by item kind: changed, new, low-confidence, open-question, and contradiction.
- [ ] Each review item shows section, title, source, severity, and supporting text/diff.
- [ ] Verify in browser using dev-browser skill.

#### US-M2-010-2: Inspect and resolve an item
**As a** reviewer, **I want** the center pane to show a focused before/after or recommendation and let me resolve the item **so that** I can act on each issue with full context.

**Acceptance Criteria:**
- [ ] Selecting an item shows focused before/after (diff) or recommendation detail in the center pane.
- [ ] Users can resolve individual review items.
- [ ] Resolving an item updates the open review-item count used by the submission gate (BR-M2-009).
- [ ] Verify in browser using dev-browser skill.

#### US-M2-010-3: Collaborate on review items
**As a** Solution Architect, **I want** the right rail to show reviewers, statuses, comments, and a reply input **so that** I can collaborate on resolving an item.

**Acceptance Criteria:**
- [ ] The right rail shows reviewers and their statuses.
- [ ] The right rail shows comments and provides a reply input.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M2-010-1: The system must provide document-specific review queues for changed, new, low-confidence, open-question, and contradiction items, filterable by kind.
- FR-M2-010-2: The system must display section, title, source, severity, and supporting text/diff per item.
- FR-M2-010-3: The system must allow resolving individual review items.
- FR-M2-010-4: The system must show focused before/after or recommendation detail in the center pane.
- FR-M2-010-5: The system must show reviewers, statuses, comments, and a reply input in the right rail.

**Backend / Production Requirements:**
- BE-M2-010-1: A review service must generate and persist targeted review items from change detection (vs. prior version), new content, low-confidence content, open questions, and contradiction checks, each classified by kind and severity (overview §5.5; §9 persistent database).
- BE-M2-010-2: Item resolution must be RBAC-restricted to assigned reviewers/authorized approvers, decrement the open required-item count, and be audit logged (overview §8 RBAC, audit).
- BE-M2-010-3: Review comments/replies must be persisted with author, timestamp, and item reference, and reviewers must be notified via the inbox/notification workflow (overview §9 notification).

### BR-M2-011 — Stale Impact Analysis
**Priority:** Must

**Requirement:** SpecForge shall detect upstream document changes and identify downstream documents and sections invalidated by the change, where the stale-impact view shows the upstream change/changed section/actor/timestamp, a dependency graph shows affected documents and pending downstream stages, impact cards show affected document/section/severity/stale reason/current text/proposed regenerated text, users can regenerate only affected sections, and finalization of stale downstream documents is blocked until invalidation is resolved or explicitly accepted.

**User Stories:**

#### US-M2-011-1: See what an upstream change invalidated
**As a** Solution Architect, **I want** the stale-impact view to show the upstream change and a dependency graph of affected documents/sections **so that** I understand the full blast radius of a change.

**Acceptance Criteria:**
- [ ] The stale-impact view shows the upstream change, the changed section, the actor, and the timestamp.
- [ ] A dependency graph shows affected downstream documents and pending downstream stages.
- [ ] Verify in browser using dev-browser skill.

#### US-M2-011-2: Inspect impact cards and regenerate affected sections
**As a** Business Analyst, **I want** impact cards detailing why each downstream section is stale and a way to regenerate only affected sections **so that** I can fix the impact precisely.

**Acceptance Criteria:**
- [ ] Each impact card shows the affected document, affected section, severity, stale reason, current text, and proposed regenerated text.
- [ ] Users can regenerate only the affected sections (not the whole document).
- [ ] Verify in browser using dev-browser skill.

#### US-M2-011-3: Be blocked from finalizing stale documents
**As a** Solution Architect, **I want** finalization of stale downstream documents blocked until invalidation is resolved or explicitly accepted **so that** work cannot progress on invalidated assumptions.

**Acceptance Criteria:**
- [ ] Finalization of a stale downstream document is blocked while invalidation is unresolved.
- [ ] The block is cleared when invalidation is resolved (e.g., via regeneration) or explicitly accepted with governance.
- [ ] Explicit acceptance of stale impact is recorded.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M2-011-1: The system must detect upstream document changes and identify invalidated downstream documents and sections at section level.
- FR-M2-011-2: The system must show the upstream change, changed section, actor, and timestamp.
- FR-M2-011-3: The system must show a dependency graph of affected documents and pending downstream stages.
- FR-M2-011-4: The system must show impact cards with affected document, section, severity, stale reason, current text, and proposed regenerated text.
- FR-M2-011-5: The system must allow regenerating only affected sections.
- FR-M2-011-6: The system must block finalization of stale downstream documents until invalidation is resolved or explicitly accepted.

**Backend / Production Requirements:**
- BE-M2-011-1: A staleness/dependency-graph computation service must maintain section-level dependency links across documents and, on an upstream change, compute the set of invalidated downstream sections with stale reasons (overview §5.8; §9 persistent database).
- BE-M2-011-2: The service must produce proposed regenerated text per impacted section for preview without committing it until the user regenerates (overview §9 LLM integration).
- BE-M2-011-3: Finalization gating must be enforced server-side; explicit acceptance of stale impact must require authorization, capture a reason, and be audit logged (overview §8 stale-impact enforcement, audit).
- BE-M2-011-4: Upstream-change detection must run on version commits and update downstream stale state and the dashboard/triage signals (overview §9 analytics; Module 1 triage alignment).

### BR-M2-012 — Section-Scoped Regeneration
**Priority:** Must

**Requirement:** SpecForge shall regenerate only impacted sections when resolving stale downstream impact and preserve unrelated manual edits, where regeneration progress is displayed, completed regeneration marks affected impact cards as regenerated, manual edits outside affected sections are preserved, trace annotations are updated when regenerated text changes links, and regeneration creates version and audit records.

**User Stories:**

#### US-M2-012-1: Regenerate only impacted sections with visible progress
**As a** Business Analyst, **I want** to regenerate only the impacted sections with visible progress and have impact cards marked regenerated **so that** I can clear stale impact safely and track completion.

**Acceptance Criteria:**
- [ ] Regeneration progress is displayed while running.
- [ ] On completion, the affected impact card(s) are marked as regenerated.
- [ ] Manual edits outside the affected sections are preserved (not overwritten).
- [ ] Verify in browser using dev-browser skill.

#### US-M2-012-2: Keep trace links and history consistent after regeneration
**As a** QA Lead, **I want** trace annotations updated when regenerated text changes links and regeneration recorded in version/audit history **so that** traceability and audit stay correct.

**Acceptance Criteria:**
- [ ] Trace annotations are updated when regenerated text changes the section's trace links.
- [ ] Regeneration creates a version record.
- [ ] Regeneration creates an audit record.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M2-012-1: The system must regenerate only the impacted sections when resolving stale impact.
- FR-M2-012-2: The system must display regeneration progress and mark affected impact cards as regenerated on completion.
- FR-M2-012-3: The system must preserve manual edits outside affected sections.
- FR-M2-012-4: The system must update trace annotations when regenerated text changes trace links.
- FR-M2-012-5: The system must create version and audit records for regeneration.

**Backend / Production Requirements:**
- BE-M2-012-1: A section-scoped regeneration job service must regenerate only targeted sections via the LLM provider with permission-filtered RAG, streaming progress and never modifying content outside the target sections (overview §9 LLM integration, RAG; §5.8 preserve manual edits).
- BE-M2-012-2: Regeneration must recompute and update the section's trace links in the traceability graph store when content changes references (overview §9; BR-M2-013 alignment).
- BE-M2-012-3: Each regeneration must create a version snapshot and an AI audit record (skill version, model, prompt template version, source references, decision state) and clear the corresponding stale state (overview §8 audit, version governance).
- BE-M2-012-4: Locked sections must not be regenerated; regeneration must respect the user's clearance for the sources/app facts used (overview §8).

### BR-M2-013 — Traceability Matrix
**Priority:** Must

**Requirement:** SpecForge shall maintain an auto-generated traceability matrix from BRs to FRs, design sections, test cases, and NFRs, where the matrix displays BR/statement/linked FRs/linked design sections/linked test cases/status, a coverage strip displays counts and gaps for BRs/FRs/design sections/test cases, users can filter all/gaps/complete rows, selecting a BR updates the detail card and gap rail context, and matrix rebuild metadata is displayed.

**User Stories:**

#### US-M2-013-1: View the traceability matrix and coverage
**As a** QA Lead, **I want** an auto-generated matrix of BRs to FRs/design/test/NFRs with a coverage strip **so that** I can see overall traceability and where coverage is missing.

**Acceptance Criteria:**
- [ ] The matrix displays, per row: BR, statement, linked FRs, linked design sections, linked test cases, and status.
- [ ] The matrix includes NFR linkage for requirements.
- [ ] A coverage strip displays counts and gaps for BRs, FRs, design sections, and test cases.
- [ ] Matrix rebuild metadata (e.g., last rebuild time) is displayed.
- [ ] Verify in browser using dev-browser skill.

#### US-M2-013-2: Filter rows and inspect a BR
**As a** QA Lead, **I want** to filter all/gaps/complete rows and select a BR to see its detail and gaps **so that** I can focus on incomplete requirements.

**Acceptance Criteria:**
- [ ] Users can filter the matrix by all, gaps, and complete rows.
- [ ] Selecting a BR updates the detail card with that BR's trace detail.
- [ ] Selecting a BR updates the gap rail context to that BR.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M2-013-1: The system must auto-generate a traceability matrix from BRs to FRs, design sections, test cases, and NFRs.
- FR-M2-013-2: The system must display BR, statement, linked FRs, linked design sections, linked test cases, and status per row.
- FR-M2-013-3: The system must display a coverage strip with counts and gaps for BRs, FRs, design sections, and test cases.
- FR-M2-013-4: The system must allow filtering all, gaps, and complete rows.
- FR-M2-013-5: The system must update the detail card and gap rail context when a BR is selected.
- FR-M2-013-6: The system must display matrix rebuild metadata.

**Backend / Production Requirements:**
- BE-M2-013-1: A traceability graph store must persist links from BRs to FRs, design sections, test cases, and NFRs, and a matrix-build service must auto-generate the matrix and coverage counts/gaps, recording rebuild metadata (overview §5.7; §9 persistent database).
- BE-M2-013-2: The matrix must be rebuilt on relevant content changes (BRD/FS/NFR/test updates, regeneration) so it stays consistent with the latest state (overview §9; BR-M5-003 export consistency).
- BE-M2-013-3: Matrix data must be RBAC-filtered so rows/links to inaccessible artefacts are not exposed (overview §8).

### BR-M2-014 — Trace Gap Resolution
**Priority:** Must

**Requirement:** SpecForge shall identify trace gaps and allow users to generate or ignore missing downstream artefacts, where gaps identify a missing FR, design section, or test case, gap cards show BR/statement/gap note, a "generate missing" action drafts the missing artefact from upstream content, ignored gaps require a reason in production, and gap decisions are audit logged.

**User Stories:**

#### US-M2-014-1: Identify and generate missing downstream artefacts
**As a** QA Lead, **I want** trace gaps identified with detail and a "generate missing" action **so that** I can fill coverage gaps from upstream content quickly.

**Acceptance Criteria:**
- [ ] Gaps identify a missing FR, design section, or test case.
- [ ] Each gap card shows the BR, the statement, and a gap note.
- [ ] A "generate missing" action drafts the missing artefact from upstream content.
- [ ] Generated artefacts are linked back into the traceability matrix.
- [ ] Verify in browser using dev-browser skill.

#### US-M2-014-2: Ignore a gap with a governed reason
**As a** QA Lead, **I want** to ignore a gap only with a reason and have it logged **so that** accepted gaps are governed and auditable.

**Acceptance Criteria:**
- [ ] Ignoring a gap requires a reason (in production).
- [ ] Gap decisions (generate and ignore) are audit logged.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M2-014-1: The system must identify trace gaps for missing FRs, design sections, and test cases.
- FR-M2-014-2: The system must show BR, statement, and gap note on gap cards.
- FR-M2-014-3: The system must provide a "generate missing" action that drafts the missing artefact from upstream content and links it into the matrix.
- FR-M2-014-4: The system must require a reason to ignore a gap (in production).
- FR-M2-014-5: The system must audit log gap decisions.

**Backend / Production Requirements:**
- BE-M2-014-1: A gap-detection service must derive gaps from the traceability graph store (BRs lacking FR/design/test coverage) (overview §5.7; §9).
- BE-M2-014-2: "Generate missing" must invoke the LLM orchestration service to draft the missing artefact from upstream content and create the trace link (overview §9 LLM integration).
- BE-M2-014-3: Ignore decisions must require an authorized actor and a captured reason, and both generate and ignore decisions must be immutable audit events (overview §8 audit, governance).

### BR-M2-015 — Functional Specification Generation
**Priority:** Must

**Requirement:** SpecForge shall generate a Functional Specification from the approved BRD with traceable functional requirements, roles, process behavior, data, integrations, exception handling, and audit behavior, where each FR has a unique ID, upstream BR, description, preconditions, behavior, outputs, errors, acceptance criteria, dependencies, and NFR coupling; FS detects contradictions with current BRD values; FR cards expose upstream trace chips; and missing test coverage is propagated to the traceability matrix.

**User Stories:**

#### US-M2-015-1: Generate a traceable Functional Specification
**As a** Business Analyst, **I want** to generate an FS from the approved BRD with fully attributed, traceable FRs **so that** business intent becomes specified system behavior without losing traceability.

**Acceptance Criteria:**
- [ ] The FS is generated from the approved BRD and covers functional requirements, roles, process behavior, data, integrations, exception handling, and audit behavior.
- [ ] Each FR has a unique ID, upstream BR, description, preconditions, behavior, outputs, errors, acceptance criteria, dependencies, and NFR coupling.
- [ ] FR cards expose upstream trace chips (to the originating BR).
- [ ] Verify in browser using dev-browser skill.

#### US-M2-015-2: Detect contradictions and propagate coverage
**As a** Solution Architect, **I want** the FS to detect contradictions with current BRD values and propagate missing test coverage to the matrix **so that** the FS stays consistent with the BRD and gaps are visible.

**Acceptance Criteria:**
- [ ] The FS detects contradictions with current BRD values.
- [ ] Missing test coverage for FRs is propagated to the traceability matrix.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M2-015-1: The system must generate an FS from the approved BRD covering FRs, roles, process behavior, data, integrations, exception handling, and audit behavior.
- FR-M2-015-2: The system must give each FR a unique ID, upstream BR, description, preconditions, behavior, outputs, errors, acceptance criteria, dependencies, and NFR coupling.
- FR-M2-015-3: The system must detect contradictions between the FS and current BRD values.
- FR-M2-015-4: The system must expose upstream trace chips on FR cards.
- FR-M2-015-5: The system must propagate missing test coverage to the traceability matrix.

**Backend / Production Requirements:**
- BE-M2-015-1: FS generation must be gated on BRD approval and produced by the LLM orchestration service from the approved BRD via permission-filtered RAG, attaching upstream BR trace links to each FR (overview §5.6; §8 approval gates; §9 RAG).
- BE-M2-015-2: A contradiction service must compare FS values against current BRD values and surface contradictions (e.g., to targeted review/quality) (overview §9; consistency objective).
- BE-M2-015-3: Generated FRs and their BR links must be written to the traceability graph store, and FRs lacking test coverage must create gaps in the matrix (overview §9; BR-M2-013/014 alignment).
- BE-M2-015-4: FS generation must create version and AI audit records and record skill/model/prompt versions (overview §8 audit, version governance).

### BR-M2-016 — Non-Functional Specification Generation
**Priority:** Must

**Requirement:** SpecForge shall generate measurable NFRs from BRD, FS, app-brain constraints, and group standards, where each NFR includes ID, category, description, targets, measurement method, constrained FRs, and release gate; performance, availability, throughput, auditability, privacy, security, observability, DR, and accessibility categories are supported; stale sizing is detected when upstream scope changes; and NFR failures can be marked release blockers.

**User Stories:**

#### US-M2-016-1: Generate measurable NFRs grounded in upstream and standards
**As a** Solution Architect, **I want** measurable NFRs generated from the BRD, FS, app-brain constraints, and group standards **so that** quality targets are explicit, attributable, and tied to the FRs they constrain.

**Acceptance Criteria:**
- [ ] Each NFR includes ID, category, description, targets, measurement method, constrained FRs, and release gate.
- [ ] The supported categories include performance, availability, throughput, auditability, privacy, security, observability, DR, and accessibility.
- [ ] NFRs are generated from BRD, FS, app-brain constraints, and group standards.
- [ ] Verify in browser using dev-browser skill.

#### US-M2-016-2: Detect stale sizing and flag release blockers
**As a** Solution Architect, **I want** stale sizing detected when upstream scope changes and the ability to mark NFR failures as release blockers **so that** NFR targets stay valid and critical failures gate release.

**Acceptance Criteria:**
- [ ] Stale sizing is detected when upstream scope changes.
- [ ] NFR failures can be marked as release blockers.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M2-016-1: The system must generate measurable NFRs from BRD, FS, app-brain constraints, and group standards.
- FR-M2-016-2: The system must include ID, category, description, targets, measurement method, constrained FRs, and release gate for each NFR.
- FR-M2-016-3: The system must support performance, availability, throughput, auditability, privacy, security, observability, DR, and accessibility categories.
- FR-M2-016-4: The system must detect stale sizing when upstream scope changes.
- FR-M2-016-5: The system must allow marking NFR failures as release blockers.

**Backend / Production Requirements:**
- BE-M2-016-1: NFR generation must use the LLM orchestration service over BRD, FS, app-brain constraints, and group-standard sources via permission-filtered RAG, linking each NFR to the FRs it constrains (overview §9 RAG; app-brain grounding, §1).
- BE-M2-016-2: The staleness service must flag NFR sizing as stale when upstream scope (BRD/FS) changes, integrating with the stale-impact view (overview §5.8; BR-M2-011 alignment).
- BE-M2-016-3: Release-blocker flags must be persisted and enforceable at release/finalization gates and audit logged (overview §8 approval gates, audit).
- BE-M2-016-4: NFR generation must create version and AI audit records with skill/model/prompt versions (overview §8).

### BR-M2-017 — Downstream Pending Gates
**Priority:** Must

**Requirement:** SpecForge shall block ADR, TBP, SDD, TS, and TC generation until required upstream documents are approved, where pending screens show required upstream documents, display planned sections/purpose/validators/estimated generation time, allow opening upstream documents from the pending state, and allow subscribing for notification when upstream dependencies are approved.

**User Stories:**

#### US-M2-017-1: See why a downstream document is pending
**As a** Solution Architect, **I want** pending screens for ADR/TBP/SDD/TS/TC that show required upstream documents and what will be generated **so that** I understand the dependency gate and what to expect.

**Acceptance Criteria:**
- [ ] Generation of ADR, TBP, SDD, TS, and TC is blocked until required upstream documents are approved.
- [ ] Each pending screen shows the required upstream documents.
- [ ] Each pending screen displays planned sections, purpose, validators, and estimated generation time.
- [ ] Verify in browser using dev-browser skill.

#### US-M2-017-2: Navigate to upstream and subscribe for notification
**As a** Solution Architect, **I want** to open upstream documents from the pending state and subscribe for notification when dependencies are approved **so that** I can unblock the work and be alerted when ready.

**Acceptance Criteria:**
- [ ] Users can open the required upstream documents directly from the pending state.
- [ ] Users can subscribe to be notified when upstream dependencies are approved.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M2-017-1: The system must block generation of ADR, TBP, SDD, TS, and TC until required upstream documents are approved.
- FR-M2-017-2: The system must show required upstream documents on each pending screen.
- FR-M2-017-3: The system must display planned sections, purpose, validators, and estimated generation time on pending screens.
- FR-M2-017-4: The system must allow opening upstream documents from the pending state.
- FR-M2-017-5: The system must allow subscribing for notification when upstream dependencies are approved.

**Backend / Production Requirements:**
- BE-M2-017-1: A dependency-gate service must encode required upstream-approval dependencies for ADR/TBP/SDD/TS/TC and enforce the generation block server-side based on upstream approval state (overview §5.6; §8 approval gates, dependency gates).
- BE-M2-017-2: Subscriptions must be persisted and trigger notification via the inbox/notification workflow when upstream dependencies are approved (overview §9 notification/inbox).
- BE-M2-017-3: Estimated generation time and planned sections/validators must be derived from document-type/template definitions (Module 3) so pending screens reflect governed configuration.

## 7. Non-Goals / Out of Scope

- The global shell, routing, sidebar/breadcrumb chrome, design tokens, global version-history infrastructure, RBAC, and audit foundation themselves (Module 0); Module 2 operates within and relies on them.
- Portfolio/dashboard, project-creation wizard, source ingestion, apps-in-scope selection, and the adaptive Requirement Understanding interview/validation (Module 1); Module 2 consumes the validated understanding as its generation precondition.
- The shared Section Editor internals, section rendering-kind selection, section metadata/linkage management, requirement-card editing, template application, prompt action controls, and confidence-threshold configuration (Module 3); Module 2 invokes these (e.g., Edit opens the shared Section Editor) but does not define them.
- App AI Brain detail authoring, app onboarding, fact extraction governance, proposed-update merge, LLM provider/skill configuration, and PII-governance configuration (Module 4); Module 2 consumes app-brain grounding/facts and the configured providers/skills and surfaces grounding, but does not govern them.
- Export job generation, redaction-policy execution, version preview/compare/restore UIs, and packaging (Module 5); Module 2 triggers exports (ledger, section) and relies on version snapshots but does not implement export jobs.
- Building the actual LLM models, embedding models, RAG retrieval engine, OCR/parsing engine, and notification transport; Module 2 integrates with these as services.
- Generation of the full ADR, TBP, SDD, TS, and TC document content (only their pending-gate screens and the upstream-approval gating are in Module 2 scope; their generation logic is downstream).

## 8. Technical Considerations

**Data model entities (Module 2 owned/primary):**
- DocumentModule (id, project, type [BRD/FS/NFR/ADR/TBP/SDD/TS/TC], dependencies, status, current version).
- DocumentSection (id, document, order, title, rendering kind, status [approved/edited/AI-generated/stale], content, confidence, section version, edit time, locked flag, owner/approvers).
- RequirementCard (id, section, priority, title, description, acceptance criteria, rationale, owner, source, trace links, expanded/collapsed default).
- Citation/SourceSpan (id, target [section/card], source name, location, quote, reference ID; or app-brain fact ref) and AppBrainGrounding (section, app key, fact IDs, fact text, fact kind, proposed status).
- Assumption (id, project, text, confidence, source/inference reason, section, status, decision history) — shared with Module 1.
- OpenQuestion (id, project, text, section, assignee, due date, status, resolution/provenance) — shared with Module 1.
- ReviewItem (id, document, kind [changed/new/low-confidence/open-question/contradiction], section, title, source, severity, supporting text/diff, status, reviewers, comments).
- StaleImpactItem (id, upstream change ref, affected document, affected section, severity, stale reason, current text, proposed regenerated text, state).
- DependencyLink (upstream section/document → downstream section/document, severity, reason) for staleness and gating.
- TraceRow/TraceLink (BR → FRs, design sections, test cases, NFRs; status; gap notes) in the traceability graph store; GapDecision (gap, decision [generate/ignore], reason, actor).
- FunctionalRequirement (id, upstream BR, description, preconditions, behavior, outputs, errors, acceptance criteria, dependencies, NFR coupling).
- NonFunctionalRequirement (id, category, description, targets, measurement method, constrained FRs, release gate, release-blocker flag, stale-sizing flag).
- VersionSnapshot (document/section, actor, timestamp, change note, changed sections, change count, generation type, immutable) and AIAction/AuditEvent (skill version, model, prompt template version, source references, decision state).
- DependencyGate (downstream type → required upstream approvals) and PendingSubscription (user, downstream type, project).

**API / service surface (illustrative, tech-agnostic):**
- Document/section service: render, edit, status (approve/lock), comment, copy-link, delete; version snapshots.
- AI action service: section-scoped regenerate/improve/expand/simplify/strengthen-citations/find-contradictions with streaming and accept/insert/reject.
- Citation service + traceability graph service: resolve provenance; compute forward chains, coverage, gaps.
- Quality service + cross-document consistency service: subscores, overall score, findings, BRD/FS, FS/test, BRD/NFR, glossary checks.
- Assumption ledger service + open-question service: CRUD, accept/reject/ask-owner, assign/resolve/merge-with-provenance.
- Review service: generate/filter/resolve targeted items; reviewers, comments, replies.
- Staleness/dependency service: upstream-change detection, section-level impact, proposed regenerated text, finalization gating.
- Section-scoped regeneration job service: regenerate only impacted sections, preserve manual edits, update trace links, version/audit.
- FS/NFR generation service: gated generation, contradiction/stale-sizing detection, trace propagation.
- Dependency-gate service + subscription/notification: block downstream generation, pending screens, notify on approval.

**Integration points:** Module 0 (shell, routing, RBAC, audit, version infrastructure, design tokens for AI/stale/approved/review states), Module 1 (validated Requirement Understanding as generation precondition; quality/assumption/open-question objects shared; triage/stale signals fed back), Module 3 (shared Section Editor, rendering kinds, metadata/linkage, card editing, templates, prompt action controls, confidence thresholds), Module 4 (app-brain facts/grounding, configured LLM providers/model routing/skills/prompt versions, PII governance), Module 5 (section/ledger/trace exports, version snapshot preview/compare/restore).

**Production capabilities (overview §9) relied upon:** real LLM provider integration + model routing; permission-filtered RAG over indexed sources and app-brain facts; persistent database for documents/sections/versions/reviews/questions/assumptions/trace links; real approval signatures; real notification/inbox workflows for reviews, ask-owner, and pending-gate subscriptions; analytics computation for quality and staleness.

**Performance:** AI section actions and regeneration run as asynchronous jobs with streaming progress so the editor is never blocked; regeneration is strictly section-scoped to bound cost and protect manual edits. The traceability graph and quality scores are recomputed incrementally on relevant changes and cached, with rebuild metadata displayed. Stale-impact computation runs on version commits, not synchronously per page load.

**Security (overview §8):** All reads/writes are RBAC-filtered; restricted source content underlying citations/quotes is never revealed to unauthorized users; AI calls never use restricted content when the user lacks clearance; locked sections cannot be modified by AI; mark-approved, lock, delete, gap-ignore, stale-accept, and submission-for-approval are authorization-gated and immutably audit logged with actor, timestamp, affected sections, and (for AI) skill/model/prompt versions and source references; submission for approval and release-blocker enforcement use approval signatures.

## 9. Success Metrics

- Provenance coverage: percentage of generated BRD/FS/NFR claims backed by a source span, app-brain fact, or explicit assumption — target ~100%.
- Reviewer focus: reduction in content reviewed per approval cycle versus full-document review (targeted-review coverage of changed/new/low-confidence/contradiction items).
- Edit preservation: zero incidents of section-scoped regeneration overwriting manual edits outside the target section.
- Traceability coverage: percentage of BRs with complete FR/design/test/NFR coverage; trend of open trace gaps over time.
- Stale enforcement: zero stale downstream documents finalized without resolution or governed explicit acceptance; median time from upstream change to resolved/accepted impact.
- Consistency: reduction in BRD/FS, FS/test, BRD/NFR, and glossary inconsistencies detected at approval (cross-document findings cleared before submission).
- Gate integrity: zero documents submitted for approval with open required review items; zero downstream documents generated before required upstream approvals.
- Assumption governance: percentage of AI-introduced assumptions resolved (accepted/rejected/asked) before document approval.
- Auditability: 100% of generation, regeneration, approval, lock, gap, and stale-acceptance actions captured in the immutable audit log with required AI metadata.

## 10. Open Questions

- What exactly defines a "required" review item versus an optional one for the submission gate, and is the policy configurable per tenant/document type?
- What thresholds define "low-confidence" content for review items and the AI confidence percentage shown on sections, and are they tied to the Module 3 confidence threshold?
- How are contradictions scored and prioritized, and what is the canonical source of truth when BRD and FS values disagree (which one is treated as authoritative)?
- What is the staleness propagation depth and granularity (section vs. clause), and how are dependency links seeded — automatically discovered, manually declared (Module 3 linkages), or both?
- What is the matrix rebuild cadence/trigger model (event-driven vs. scheduled vs. hybrid), and what is the acceptable freshness window?
- Who is authorized to mark a section approved, lock a section, accept stale impact, ignore a trace gap, and submit for approval — and how do these map to the seven roles per document type?
- For "ask the owner" on assumptions, who is the resolved owner (app owner, BA, sponsor) and how is routing determined?
- What are the supported export formats and redaction defaults for the assumption ledger and sections (delegated to Module 5), and what classifications block export?
- What governs estimated generation time and planned sections shown on pending gates (template definitions in Module 3), and how are validators assigned per downstream document type?
- How are NFR release-blocker flags reconciled with the overall release/finalization gate, and can a blocker be overridden with governance?

## 11. Traceability Map

| BR ID | User Stories | Functional Requirements | Backend Reqs |
|---|---|---|---|
| BR-M2-001 | US-M2-001-1, US-M2-001-2 | FR-M2-001-1, FR-M2-001-2, FR-M2-001-3, FR-M2-001-4, FR-M2-001-5, FR-M2-001-6, FR-M2-001-7 | BE-M2-001-1, BE-M2-001-2, BE-M2-001-3, BE-M2-001-4 |
| BR-M2-002 | US-M2-002-1, US-M2-002-2 | FR-M2-002-1, FR-M2-002-2, FR-M2-002-3, FR-M2-002-4, FR-M2-002-5, FR-M2-002-6, FR-M2-002-7 | BE-M2-002-1, BE-M2-002-2, BE-M2-002-3, BE-M2-002-4 |
| BR-M2-003 | US-M2-003-1, US-M2-003-2 | FR-M2-003-1, FR-M2-003-2, FR-M2-003-3, FR-M2-003-4 | BE-M2-003-1, BE-M2-003-2 |
| BR-M2-004 | US-M2-004-1, US-M2-004-2 | FR-M2-004-1, FR-M2-004-2, FR-M2-004-3, FR-M2-004-4 | BE-M2-004-1, BE-M2-004-2 |
| BR-M2-005 | US-M2-005-1, US-M2-005-2, US-M2-005-3 | FR-M2-005-1, FR-M2-005-2, FR-M2-005-3, FR-M2-005-4, FR-M2-005-5, FR-M2-005-6 | BE-M2-005-1, BE-M2-005-2, BE-M2-005-3, BE-M2-005-4, BE-M2-005-5 |
| BR-M2-006 | US-M2-006-1, US-M2-006-2 | FR-M2-006-1, FR-M2-006-2, FR-M2-006-3, FR-M2-006-4 | BE-M2-006-1, BE-M2-006-2, BE-M2-006-3 |
| BR-M2-007 | US-M2-007-1, US-M2-007-2 | FR-M2-007-1, FR-M2-007-2, FR-M2-007-3, FR-M2-007-4, FR-M2-007-5 | BE-M2-007-1, BE-M2-007-2, BE-M2-007-3 |
| BR-M2-008 | US-M2-008-1, US-M2-008-2 | FR-M2-008-1, FR-M2-008-2, FR-M2-008-3, FR-M2-008-4 | BE-M2-008-1, BE-M2-008-2, BE-M2-008-3 |
| BR-M2-009 | US-M2-009-1, US-M2-009-2 | FR-M2-009-1, FR-M2-009-2, FR-M2-009-3, FR-M2-009-4 | BE-M2-009-1, BE-M2-009-2 |
| BR-M2-010 | US-M2-010-1, US-M2-010-2, US-M2-010-3 | FR-M2-010-1, FR-M2-010-2, FR-M2-010-3, FR-M2-010-4, FR-M2-010-5 | BE-M2-010-1, BE-M2-010-2, BE-M2-010-3 |
| BR-M2-011 | US-M2-011-1, US-M2-011-2, US-M2-011-3 | FR-M2-011-1, FR-M2-011-2, FR-M2-011-3, FR-M2-011-4, FR-M2-011-5, FR-M2-011-6 | BE-M2-011-1, BE-M2-011-2, BE-M2-011-3, BE-M2-011-4 |
| BR-M2-012 | US-M2-012-1, US-M2-012-2 | FR-M2-012-1, FR-M2-012-2, FR-M2-012-3, FR-M2-012-4, FR-M2-012-5 | BE-M2-012-1, BE-M2-012-2, BE-M2-012-3, BE-M2-012-4 |
| BR-M2-013 | US-M2-013-1, US-M2-013-2 | FR-M2-013-1, FR-M2-013-2, FR-M2-013-3, FR-M2-013-4, FR-M2-013-5, FR-M2-013-6 | BE-M2-013-1, BE-M2-013-2, BE-M2-013-3 |
| BR-M2-014 | US-M2-014-1, US-M2-014-2 | FR-M2-014-1, FR-M2-014-2, FR-M2-014-3, FR-M2-014-4, FR-M2-014-5 | BE-M2-014-1, BE-M2-014-2, BE-M2-014-3 |
| BR-M2-015 | US-M2-015-1, US-M2-015-2 | FR-M2-015-1, FR-M2-015-2, FR-M2-015-3, FR-M2-015-4, FR-M2-015-5 | BE-M2-015-1, BE-M2-015-2, BE-M2-015-3, BE-M2-015-4 |
| BR-M2-016 | US-M2-016-1, US-M2-016-2 | FR-M2-016-1, FR-M2-016-2, FR-M2-016-3, FR-M2-016-4, FR-M2-016-5 | BE-M2-016-1, BE-M2-016-2, BE-M2-016-3, BE-M2-016-4 |
| BR-M2-017 | US-M2-017-1, US-M2-017-2 | FR-M2-017-1, FR-M2-017-2, FR-M2-017-3, FR-M2-017-4, FR-M2-017-5 | BE-M2-017-1, BE-M2-017-2, BE-M2-017-3 |
