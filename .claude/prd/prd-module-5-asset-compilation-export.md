# PRD: Module 5 — Asset Compilation & Export

> Part of the SpecForge detailed business-requirements PRD set. Sources: `.claude/prd/01-system-overview-and-business-context.md`, `.claude/prd/business-requirements-by-module.md`.

## 1. Introduction / Overview

Module 5 governs how SpecForge content leaves the workbench as external artefacts. Throughout the SDLC lifecycle, SpecForge treats documents as connected, versioned, traceable objects whose claims are backed by source spans, app-brain facts, or explicit assumptions. Export is the point where that governed content must cross the boundary into stakeholder reviews, approval workflows, records systems, offline QA, regulator evidence packages, and downstream integrations — without losing its meaning or its controls.

This module covers source corpus compilation, full-document export, section export, traceability-matrix export, app-brain export, assumption-ledger export, version snapshot preview and compare, non-destructive restore, standalone HTML packaging, JSON schema export, and background export job management. Because SpecForge content includes citations, assumptions, review state, AI provenance, source-security classifications, trace links, and version history, an export is never a flat "dump." A BRD export must not lose requirement-card structure. A trace export must not lose gap status. An assumption-ledger export must not hide low-confidence assumptions. An app-brain export must not leak restricted source text to an unauthorized recipient.

Module 5 is therefore as much a governance and security module as it is a formatting module. Every export must preserve provenance, version identity, citations, trace links, and assumption status; must enforce access controls and redaction policy at generation time and at download time; and must produce an immutable audit record. Long-running exports run as background jobs with status, secure expiring download links, and retry behavior.

This is a brand-new system with no existing codebase. This document specifies requirements (not code) covering every Module 5 business requirement (BR-M5-001 through BR-M5-010) plus the backend/production capabilities implied by the system overview's enterprise controls (section 8) and production-implied services (section 9).

## 2. Goals

- Let authorized users export any governed SpecForge artefact (whole documents, sections, trace matrices, assumption ledgers, app brains, version snapshots, JSON schemas, and standalone packages) in approved enterprise formats.
- Guarantee that every export preserves provenance: version identity, citations and source spans, trace links and gap status, assumption status and confidence, review state, and AI generation metadata.
- Enforce role-based access control and redaction policy on every export, both at generation time and at download time, so restricted source text and secrets never leak to unauthorized recipients.
- Make exports auditable: every export request and download produces an immutable audit record tied to actor, project, document/app, version, scope, and policy applied.
- Provide reliable handling of large or slow exports through background jobs with queued/running/completed/failed status, secure expiring download links, actionable failures, and parameter-preserving retries.
- Support machine-readable, versioned JSON schema exports so downstream enterprise systems can integrate against stable, validatable contracts.
- Enable safe version governance: read-only snapshot preview, side-by-side compare with diff, immutable snapshots, and non-destructive restore that creates a new current version while preserving history and re-running staleness checks.

## 3. Scope

### In scope (with priority)

- BR-M5-001 — Document Export — Must
- BR-M5-002 — Section Export — Should
- BR-M5-003 — Trace Matrix Export — Must
- BR-M5-004 — App Brain Export — Should
- BR-M5-005 — Assumption Ledger Export — Must
- BR-M5-006 — Version Snapshot Preview and Compare — Must
- BR-M5-007 — Non-Destructive Restore — Must
- BR-M5-008 — Standalone HTML Packaging — Could
- BR-M5-009 — JSON Schema Export — Should
- BR-M5-010 — Export Job Management — Should

### Priorities covered

- Must: BR-M5-001, BR-M5-003, BR-M5-005, BR-M5-006, BR-M5-007
- Should: BR-M5-002, BR-M5-004, BR-M5-009, BR-M5-010
- Could: BR-M5-008

### Cross-module dependencies (consumed, not redefined here)

- Module 0: global version history infrastructure and version chip (BR-M0-006), immutable audit logging (BR-M0-007), role-based access control (BR-M0-008), and design tokens for status semantics (BR-M0-005).
- Module 2: document/section content, requirement cards, citations, assumptions (assumption ledger BR-M2-007), open questions, traceability matrix (BR-M2-013), trace gaps (BR-M2-014), stale impact (BR-M2-011), section toolbar export entry point (BR-M2-002).
- Module 4: app-brain content and facts (BR-M4-003), data security and PII governance / export redaction (BR-M4-011), provider/skill version metadata (BR-M4-010).

## 4. Users & Roles

SpecForge defines seven roles. Their relationship to Module 5:

- **Business Analyst** — Primary export operator. Exports BRDs, sections, trace matrices, and assumption ledgers for stakeholders, review, and records. Previews/compares versions and restores prior versions within authorization.
- **Product Owner / Business Sponsor** — Exports BRD and section content for offline business review and to attach to approval workflows.
- **Solution Architect** — Exports FS, NFR, design artefacts, trace matrices, and version snapshots to validate downstream consistency and architecture readiness; performs non-destructive restore on design artefacts within authorization.
- **App Owner** — Authorized exporter of app-brain data (BR-M5-004), governing whether restricted source text is included.
- **QA Lead** — Exports the traceability matrix and assumption ledger (spreadsheet/JSON) to confirm coverage offline and feed test management tools.
- **Compliance / Risk Reviewer** — Heavy consumer of assumption-ledger exports, trace exports, app-brain exports, and version snapshots as audit evidence; relies on retained provenance, redaction enforcement, and audit records.
- **Platform Administrator / AI Engineer** — Configures export policy: allowed formats, redaction rules, download-link expiry, retention, JSON schema registry/versioning, export queue/worker capacity, and access scoping. Reviews export audit logs.

Authorization principle: a user may only export content they are authorized to view, and any source span, app-brain fact, or section the user cannot access is redacted or excluded from the resulting artefact (consumes BR-M0-008, BR-M4-011).

## 5. Key Business Objects

- **Source document** — An ingested project or app-brain source file with extraction state, indexing state, page count, and PII/data classification. Cited by exported content.
- **Export request** — The user-initiated specification of an export: artefact target, scope (full/section/filtered), format(s), options (include/exclude provenance, redaction profile), and requesting actor/role.
- **Export job** — The background execution of an export request: status (queued, running, completed, failed), progress, worker, timestamps, output artefact reference, error detail, retry lineage, and audit linkage.
- **Export artefact** — The produced output file(s) (e.g., DOCX/PDF/CSV/XLSX/JSON/HTML), stored with checksum, size, format, content classification, and the redaction profile applied.
- **Version snapshot** — An immutable point-in-time capture of a document/version including content, sections, metadata, provenance, and change note. Used for preview, compare, restore, and snapshot export.
- **Trace export row** — A flattened traceability record: BR, statement, linked FRs, linked design sections, linked test cases, NFRs, status, gap notes, and rebuild metadata.
- **Ledger export row** — A flattened assumption record: ID, text, confidence, source, section, status, owner/question link, and decision history.
- **App-brain export package** — A bundle of app-brain overview, glossary, capabilities, limitations, constraints, integrations, corpus summary, open questions, skills, projects touching, proposed updates, and per-fact metadata, with restricted source text governed by authorization.
- **Redaction policy** — Tenant- and classification-driven rules determining what content is excluded, masked, or watermarked in an export for a given recipient/role and data classification.
- **Secure download link** — A short-lived, access-controlled URL granting a specific authorized recipient time-limited access to a completed export artefact; expires per tenant policy.
- **JSON schema (registry entry)** — A published, versioned schema describing the structure of a machine-readable export type, used by consumers to validate exported payloads.
- **Audit record** — An immutable log entry capturing actor, timestamp, project, document/app, action (export requested/generated/downloaded/restored), source/target version, scope, format, and redaction profile.

## 6. Detailed Business Requirements

### BR-M5-001 — Document Export
**Priority:** Must

**Requirement:** SpecForge shall allow authorized users to export managed documents in approved enterprise formats, producing a complete artefact that preserves document identity, structure, provenance, and governance state, while enforcing the requesting user's permissions and the applicable redaction policy, and recording an immutable audit entry.

**User Stories:**

#### US-M5-001-1: Export a full document
**As a** Business Analyst, **I want** to export a complete managed document (e.g., BRD) in an approved enterprise format **so that** I can share an authoritative copy with stakeholders and attach it to approval workflows.

**Acceptance Criteria:**
- [ ] Export can be initiated for the full-document scope from the document workbench.
- [ ] Only approved enterprise formats are offered (e.g., DOCX, PDF), per administrator policy.
- [ ] The exported artefact includes document title, project metadata, and the document version identity.
- [ ] The exported artefact includes all sections in correct order with their rendered kind (prose, bulleted, table, requirement cards, process flow) preserved.
- [ ] The exported artefact includes requirement cards with ID, title, description, acceptance criteria, rationale, priority, owner, and source citation.
- [ ] The exported artefact includes citations/source spans and assumption markers tied to the content they support.
- [ ] The exported artefact includes per-section approval/status state (approved, edited, AI-generated, stale) and AI confidence where applicable.
- [ ] Verify in browser using dev-browser skill.

#### US-M5-001-2: Export respects permissions and redaction
**As a** Compliance / Risk Reviewer, **I want** document exports to honor my access permissions and the redaction policy **so that** restricted source text is never disclosed to unauthorized recipients.

**Acceptance Criteria:**
- [ ] The export only includes content the requesting user is authorized to view.
- [ ] Source spans, citations, or sections the user cannot access are redacted or excluded, never silently leaked.
- [ ] The applied redaction profile is recorded with the export artefact.
- [ ] If redaction would remove material content, the export indicates that redaction was applied (e.g., a redaction notice/summary) without revealing the redacted text.
- [ ] Verify in browser using dev-browser skill.

#### US-M5-001-3: Document export is audited
**As a** Platform Administrator, **I want** every document export to create an immutable audit record **so that** I can reconstruct who exported what, when, at which version, and under which policy.

**Acceptance Criteria:**
- [ ] An audit record is created for each document export including actor, timestamp, project, document key, version, scope, format, and redaction profile.
- [ ] The audit record is immutable to non-admin users.
- [ ] The audit record links to the resulting export job and artefact reference.

**Functional Requirements:**
- FR-M5-001-1: The system must offer a full-document export entry point from the document workbench and section "more" menu (export action).
- FR-M5-001-2: The system must restrict offered export formats to the administrator-configured approved set per document type and tenant.
- FR-M5-001-3: The system must compile into the artefact: document title, project metadata, version identity, ordered sections with preserved rendering kind, requirement cards (full fields), citations/source spans, assumption markers with status, and per-section approval/status and confidence.
- FR-M5-001-4: The system must evaluate the requesting user's permissions and the redaction policy before compiling, and exclude or mask unauthorized/restricted content.
- FR-M5-001-5: The system must create an immutable audit record for each document export request and link it to the export job and artefact.

**Backend / Production Requirements:**
- BE-M5-001-1: Document exports must be produced by the background export job pipeline (see BR-M5-010), with secure expiring download links for completed artefacts.
- BE-M5-001-2: The redaction policy engine must evaluate recipient role, user clearance, and content data classification at generation time, applying tenant redaction rules consistently (consumes BR-M4-011).
- BE-M5-001-3: Export rendering must read from the immutable version snapshot for the requested version so the artefact is reproducible and consistent with the recorded version.
- BE-M5-001-4: Generated artefacts must be stored with checksum, size, format, content classification, and the applied redaction profile; access to stored artefacts must be permission-filtered.

---

### BR-M5-002 — Section Export
**Priority:** Should

**Requirement:** SpecForge shall allow authorized users to export an individual document section, preserving its number, title, content, citations, linked requirements, version, and status, warning when the section is stale or has unresolved review items, and recording an immutable audit entry.

**User Stories:**

#### US-M5-002-1: Export a single section
**As a** Business Analyst, **I want** to export one section from the section "more" menu **so that** I can share or reuse a specific part of a document without exporting the whole document.

**Acceptance Criteria:**
- [ ] Section export is accessible from the section "more" menu.
- [ ] The exported section includes section number, title, and content with the rendered kind preserved.
- [ ] The exported section includes citations/source spans and linked requirement references (BR/FR/NFR).
- [ ] The exported section includes the section version and status.
- [ ] Verify in browser using dev-browser skill.

#### US-M5-002-2: Warned about stale or unresolved sections
**As a** Solution Architect, **I want** to be warned when the section I am exporting is stale or has unresolved review items **so that** I do not distribute content that is known to be invalid or under review.

**Acceptance Criteria:**
- [ ] If the section is stale, the export flow displays a warning before producing the artefact.
- [ ] If the section has unresolved review items, the export flow displays a warning before producing the artefact.
- [ ] The user can proceed or cancel after acknowledging the warning.
- [ ] If the user proceeds, the staleness/review state is reflected in the exported artefact (e.g., a status banner) so recipients are aware.
- [ ] Verify in browser using dev-browser skill.

#### US-M5-002-3: Section export is audited
**As a** Compliance / Risk Reviewer, **I want** section exports to be audit logged **so that** partial-document disclosures are traceable.

**Acceptance Criteria:**
- [ ] An audit record is created for each section export including actor, timestamp, project, document key, section identifier, section version, and format.
- [ ] The audit record records whether the section was stale or had unresolved review items at export time.

**Functional Requirements:**
- FR-M5-002-1: The system must expose a section-scoped export action in the section "more" menu (consumes BR-M2-002).
- FR-M5-002-2: The system must compile into the section artefact: section number, title, content with preserved rendering kind, citations, linked BR/FR/NFR references, section version, and status.
- FR-M5-002-3: The system must detect stale state and unresolved review-item count for the target section and warn the user before producing the artefact.
- FR-M5-002-4: The system must reflect stale/unresolved-review state in the exported section artefact when the user proceeds.
- FR-M5-002-5: The system must create an immutable audit record for each section export, capturing stale/review state at export time.

**Backend / Production Requirements:**
- BE-M5-002-1: Section exports must apply the same permission and redaction evaluation as full-document exports (consumes BR-M5-001 redaction engine).
- BE-M5-002-2: Section exports must be produced via the background job pipeline when large or when the requested format requires heavy rendering; small synchronous exports may complete inline but must still produce audit records and secure-access artefacts.

---

### BR-M5-003 — Trace Matrix Export
**Priority:** Must

**Requirement:** SpecForge shall allow authorized users to export the Traceability Matrix to spreadsheet-compatible and machine-readable formats, including all trace columns, gap notes, and rebuild metadata; supporting export of all rows or current filter results; preserving gap highlighting in spreadsheet output; and reflecting the latest trace rebuild.

**User Stories:**

#### US-M5-003-1: Export the traceability matrix to spreadsheet
**As a** QA Lead, **I want** to export the traceability matrix to a spreadsheet-compatible format **so that** I can analyze coverage offline and feed test-management tooling.

**Acceptance Criteria:**
- [ ] The export includes BR, statement, linked FRs, linked design sections, linked test cases, NFRs, status, gap notes, and rebuild metadata for each row.
- [ ] Spreadsheet (Excel) export preserves gap highlighting so gaps are visually identifiable.
- [ ] The exported data is consistent with the latest trace rebuild.
- [ ] Verify in browser using dev-browser skill.

#### US-M5-003-2: Export all rows or current filter
**As a** QA Lead, **I want** to choose between exporting all rows or only my current filter results (e.g., gaps only) **so that** I can produce focused coverage reports.

**Acceptance Criteria:**
- [ ] The user can export all matrix rows.
- [ ] The user can export only the rows matching the current filter (all / gaps / complete).
- [ ] The exported file indicates which scope (all vs filtered) was applied.
- [ ] Verify in browser using dev-browser skill.

#### US-M5-003-3: Machine-readable trace export
**As a** Solution Architect, **I want** a machine-readable trace export **so that** downstream integration tools can consume trace relationships programmatically.

**Acceptance Criteria:**
- [ ] A machine-readable format (e.g., JSON/CSV) is available for the trace matrix.
- [ ] The machine-readable export preserves BR→FR→design→test→NFR relationships and IDs.
- [ ] Gap status is explicitly represented (not only visual) in the machine-readable export.

**Functional Requirements:**
- FR-M5-003-1: The system must export the traceability matrix to at least one spreadsheet-compatible format and at least one machine-readable format.
- FR-M5-003-2: The system must include per row: BR, statement, linked FRs, linked design sections, linked test cases, NFRs, status, gap notes, and rebuild metadata.
- FR-M5-003-3: The system must support exporting all rows or only the current filter results, and record which scope was used.
- FR-M5-003-4: The system must preserve gap highlighting in Excel output and represent gap status explicitly in machine-readable output.
- FR-M5-003-5: The system must base the export on the latest trace rebuild and include rebuild metadata (e.g., rebuild timestamp/version).

**Backend / Production Requirements:**
- BE-M5-003-1: Trace exports must read from the current materialized traceability graph (consumes BR-M2-013/BR-M2-014) to guarantee consistency with the latest rebuild.
- BE-M5-003-2: Trace exports must apply permission filtering so BRs/FRs/design/test rows the user cannot access are excluded.
- BE-M5-003-3: Trace exports must be produced through the background export job pipeline for large matrices and produce an immutable audit record.

---

### BR-M5-004 — App Brain Export
**Priority:** Should

**Requirement:** SpecForge shall allow authorized users to export app-brain data, including overview, glossary, capabilities, limitations, constraints, integrations, corpus summary, open questions, skills, projects touching, and proposed updates, with per-fact metadata; excluding restricted source text unless explicitly authorized; and recording an immutable audit entry.

**User Stories:**

#### US-M5-004-1: Export an app brain
**As an** App Owner, **I want** to export an app brain's governed knowledge **so that** I can share or archive system knowledge outside the workbench.

**Acceptance Criteria:**
- [ ] The export includes overview, glossary, capabilities, limitations, constraints, integrations, corpus summary, open questions, skills, projects touching, and proposed updates.
- [ ] The export includes per-fact metadata: fact IDs, sources, confidence, proposed/merged status, and owner validation.
- [ ] The export is initiated from the app-brain toolbar export action.
- [ ] Verify in browser using dev-browser skill.

#### US-M5-004-2: Restricted source text protection
**As a** Compliance / Risk Reviewer, **I want** restricted source text excluded from app-brain exports unless explicitly authorized **so that** sensitive source material does not leak through app-brain artefacts.

**Acceptance Criteria:**
- [ ] Restricted source text is excluded from the export by default.
- [ ] Restricted source text is only included when the requesting user holds explicit authorization for that classification.
- [ ] The export records whether restricted source text was included and under whose authorization.
- [ ] Fact metadata (ID, confidence, status) is preserved even when the underlying restricted source text is excluded.
- [ ] Verify in browser using dev-browser skill.

#### US-M5-004-3: App-brain export is audited
**As a** Platform Administrator, **I want** app-brain exports audit logged **so that** disclosure of organisational knowledge is traceable.

**Acceptance Criteria:**
- [ ] An audit record is created for each app-brain export including actor, timestamp, app key, app-brain version, scope, format, and whether restricted source text was included.
- [ ] The audit record is immutable to non-admin users.

**Functional Requirements:**
- FR-M5-004-1: The system must expose an app-brain export action from the app-brain toolbar (consumes BR-M4-003).
- FR-M5-004-2: The system must compile into the app-brain export package: overview, glossary, capabilities, limitations, constraints, integrations, corpus summary, open questions, skills, projects touching, proposed updates, and per-fact metadata (ID, sources, confidence, proposed/merged status, owner validation).
- FR-M5-004-3: The system must exclude restricted source text by default and include it only with explicit authorization for that classification.
- FR-M5-004-4: The system must record in the artefact and audit log whether restricted source text was included and the authorizing basis.
- FR-M5-004-5: The system must create an immutable audit record for each app-brain export.

**Backend / Production Requirements:**
- BE-M5-004-1: App-brain exports must enforce app-owner / delegated-maintainer or authorized-export permissions before generation (consumes BR-M0-008).
- BE-M5-004-2: The redaction policy engine must distinguish fact metadata (always exportable to authorized app viewers) from restricted source text (gated by explicit clearance) (consumes BR-M4-011).
- BE-M5-004-3: App-brain exports must run through the background job pipeline and produce a secure expiring download link.

---

### BR-M5-005 — Assumption Ledger Export
**Priority:** Must

**Requirement:** SpecForge shall allow authorized users to export the assumption ledger for compliance and review, including each assumption's ID, text, confidence, source, section, status, owner/question link, and decision history; supporting CSV/XLSX/JSON formats; keeping accepted, rejected, and open assumptions distinguishable; and respecting data classification and access controls.

**User Stories:**

#### US-M5-005-1: Export the assumption ledger
**As a** Compliance / Risk Reviewer, **I want** to export the full assumption ledger **so that** I have a compliance-ready record of every AI-introduced or inferred assumption and its disposition.

**Acceptance Criteria:**
- [ ] The export includes for each assumption: ID, text, confidence, source, section, status, owner/question link, and decision history.
- [ ] Accepted, rejected, and open assumptions are distinguishable in the export.
- [ ] Low-confidence assumptions are not hidden or omitted from the export.
- [ ] Verify in browser using dev-browser skill.

#### US-M5-005-2: Choose ledger export format
**As a** QA Lead, **I want** to export the ledger as CSV, XLSX, or JSON **so that** I can use it in spreadsheets or feed it to downstream tools.

**Acceptance Criteria:**
- [ ] CSV export is available.
- [ ] XLSX export is available.
- [ ] JSON export is available.
- [ ] The JSON export preserves status, confidence, and decision-history structure for machine consumption.
- [ ] Verify in browser using dev-browser skill.

#### US-M5-005-3: Ledger export honors classification and access
**As a** Compliance / Risk Reviewer, **I want** ledger exports to respect data classification and access controls **so that** sensitive assumptions or restricted sources are not disclosed improperly.

**Acceptance Criteria:**
- [ ] The export excludes or redacts assumptions whose source/section the user is not authorized to view.
- [ ] Restricted source references are masked according to data classification.
- [ ] An audit record is created for each ledger export.

**Functional Requirements:**
- FR-M5-005-1: The system must export the assumption ledger from the ledger view (consumes BR-M2-007) in CSV, XLSX, and JSON.
- FR-M5-005-2: The system must include per assumption: ID, text, confidence, source, section, status, owner/question link, and decision history.
- FR-M5-005-3: The system must keep accepted, rejected, and open assumptions distinguishable, and must never omit low-confidence assumptions.
- FR-M5-005-4: The system must apply data-classification and access-control filtering/redaction to ledger exports.
- FR-M5-005-5: The system must create an immutable audit record for each ledger export.

**Backend / Production Requirements:**
- BE-M5-005-1: Decision history must be sourced from the immutable audit/decision store so the exported ledger reflects the authoritative disposition trail (consumes BR-M0-007).
- BE-M5-005-2: Ledger exports must apply the redaction policy engine to source references based on classification and clearance (consumes BR-M4-011).
- BE-M5-005-3: Large ledger exports must run through the background job pipeline with secure expiring download links.

---

### BR-M5-006 — Version Snapshot Preview and Compare
**Priority:** Must

**Requirement:** SpecForge shall allow authorized users to preview a historical document version read-only and compare a selected version against the current version side-by-side with diff additions and deletions visually marked, before export or restore; snapshot versions shall be marked immutable.

**User Stories:**

#### US-M5-006-1: Preview a historical version
**As a** Business Analyst, **I want** to open a read-only preview of a historical document version **so that** I can inspect prior content before deciding to export or restore it.

**Acceptance Criteria:**
- [ ] Preview shows a read-only snapshot of the selected version.
- [ ] No edits can be made within preview.
- [ ] Preview is reachable from version history (consumes BR-M0-006) for any managed document.
- [ ] Verify in browser using dev-browser skill.

#### US-M5-006-2: Compare a version against current
**As a** Solution Architect, **I want** to compare a selected version against the current version side-by-side **so that** I can see exactly what changed between versions.

**Acceptance Criteria:**
- [ ] Compare displays the selected version and the current version side-by-side.
- [ ] Diff additions are visually marked.
- [ ] Diff deletions are visually marked.
- [ ] The comparison identifies which version is selected and which is current.
- [ ] Verify in browser using dev-browser skill.

#### US-M5-006-3: Immutable snapshots
**As a** Compliance / Risk Reviewer, **I want** snapshot versions to be marked immutable **so that** archived/finalized versions cannot be altered and remain trustworthy as evidence.

**Acceptance Criteria:**
- [ ] Snapshot versions are visibly marked immutable.
- [ ] Immutable snapshots cannot be restored or edited (consumes BR-M0-006).
- [ ] Immutable snapshots can still be previewed, compared, and exported.

**Functional Requirements:**
- FR-M5-006-1: The system must provide a read-only preview of any non-current version snapshot.
- FR-M5-006-2: The system must provide a side-by-side compare of a selected version against the current version with additions and deletions visually marked.
- FR-M5-006-3: The system must label snapshot versions as immutable and prevent restore/edit of immutable snapshots.
- FR-M5-006-4: The system must allow preview, compare, and export of immutable snapshots.

**Backend / Production Requirements:**
- BE-M5-006-1: Version snapshots must be stored in an immutable, content-addressed snapshot store capturing content, sections, metadata, provenance, actor, timestamp, and change note (consumes BR-M0-006/BR-M0-007).
- BE-M5-006-2: The diff computation must operate at section granularity so additions/deletions map to specific sections, and must run server-side over snapshot content.
- BE-M5-006-3: Snapshot access must be permission-filtered; restricted sections within a snapshot are redacted in preview/compare/export for unauthorized users.

---

### BR-M5-007 — Non-Destructive Restore
**Priority:** Must

**Requirement:** SpecForge shall allow authorized users to restore a prior non-snapshot version non-destructively by creating a new current version with the restored content, preserving the prior current version in history, running downstream staleness checks after restore, and recording an immutable audit entry.

**User Stories:**

#### US-M5-007-1: Restore a prior version non-destructively
**As a** Solution Architect, **I want** to restore a prior non-snapshot version as a new current version **so that** I can roll back content without losing any version history.

**Acceptance Criteria:**
- [ ] The restore confirmation explains the selected version, the current version, and the new-version behavior before the user commits.
- [ ] The prior current version is preserved in version history after restore.
- [ ] Restore creates a new version containing the restored content and marks it current.
- [ ] Immutable snapshot versions cannot be restored (consumes BR-M5-006/BR-M0-006).
- [ ] Verify in browser using dev-browser skill.

#### US-M5-007-2: Staleness re-evaluation after restore
**As a** Business Analyst, **I want** downstream staleness checks to run after a restore **so that** the system flags any downstream documents invalidated by the rolled-back content.

**Acceptance Criteria:**
- [ ] Downstream staleness checks run automatically after restore completes.
- [ ] Newly stale downstream sections/documents are flagged per stale-impact behavior (consumes BR-M2-011).
- [ ] Verify in browser using dev-browser skill.

#### US-M5-007-3: Restore is audited and authorized
**As a** Platform Administrator, **I want** restores to be authorization-gated and audit logged **so that** only permitted users can roll back content and every restore is traceable.

**Acceptance Criteria:**
- [ ] Only authorized users can perform a restore.
- [ ] An audit record is created for each restore including actor, timestamp, document key, source version (restored from), and target (new) version.
- [ ] The audit record is immutable to non-admin users.

**Functional Requirements:**
- FR-M5-007-1: The system must present a restore confirmation describing the selected version, current version, and resulting new-version behavior.
- FR-M5-007-2: The system must create a new current version with the restored content while preserving the prior current version in history (non-destructive).
- FR-M5-007-3: The system must prevent restore of immutable snapshot versions.
- FR-M5-007-4: The system must trigger downstream staleness checks after a restore and surface results via stale-impact behavior.
- FR-M5-007-5: The system must enforce restore authorization and create an immutable audit record for each restore.

**Backend / Production Requirements:**
- BE-M5-007-1: Restore must be transactional: the new version is committed atomically and the prior version chain remains intact (consumes BR-M0-006).
- BE-M5-007-2: Restore must enqueue downstream staleness recomputation across the dependency graph (consumes BR-M2-011) and update trace annotations where restored content changes links.
- BE-M5-007-3: Restore authorization must be enforced server-side per role (consumes BR-M0-008), and the audit record must capture source/target versions and affected downstream sections (consumes BR-M0-007).

---

### BR-M5-008 — Standalone HTML Packaging
**Priority:** Could

**Requirement:** SpecForge shall support a standalone HTML prototype/package export for offline stakeholder review, bundling required CSS, data, scripts, and assets; preserving the runtime behavior of the source shell; pinning or embedding external dependencies per enterprise policy; and excluding unauthorized source data and secrets.

**User Stories:**

#### US-M5-008-1: Export a standalone offline package
**As a** Product Owner, **I want** to export a standalone HTML package **so that** stakeholders can review the content offline without access to the live workbench.

**Acceptance Criteria:**
- [ ] The standalone file includes the required CSS, data, scripts, and assets needed to render and operate offline.
- [ ] The package preserves the runtime behavior of the source shell (navigation/interaction works offline as designed).
- [ ] External dependencies are pinned or embedded according to enterprise policy (no reliance on uncontrolled remote resources).
- [ ] Verify in browser using dev-browser skill.

#### US-M5-008-2: Standalone package excludes unauthorized data and secrets
**As a** Compliance / Risk Reviewer, **I want** standalone packages to exclude unauthorized source data and secrets **so that** offline distribution does not leak restricted content or credentials.

**Acceptance Criteria:**
- [ ] The exported package excludes source data the recipient/requester is not authorized to view.
- [ ] The exported package contains no secrets (e.g., API keys, credentials, provider endpoints).
- [ ] Redaction policy is applied to the embedded data before packaging.
- [ ] The package export is audit logged.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M5-008-1: The system must produce a standalone HTML package bundling required CSS, data, scripts, and assets for offline use.
- FR-M5-008-2: The system must preserve the source shell's runtime behavior in the standalone package.
- FR-M5-008-3: The system must pin or embed external dependencies according to enterprise policy.
- FR-M5-008-4: The system must exclude unauthorized source data and any secrets from the package, applying the redaction policy to embedded data.
- FR-M5-008-5: The system must create an immutable audit record for each standalone package export.

**Backend / Production Requirements:**
- BE-M5-008-1: Standalone packaging must run through the background job pipeline due to bundling size/cost, producing a secure expiring download link.
- BE-M5-008-2: The packaging step must run a secret-scan and redaction pass on all embedded data before producing the artefact; packaging must fail closed if secrets are detected.
- BE-M5-008-3: Embedded data must be permission-filtered for the requesting user's authorization scope (consumes BR-M0-008, BR-M4-011).

---

### BR-M5-009 — JSON Schema Export
**Priority:** Should

**Requirement:** SpecForge shall provide JSON exports for generated documents, traceability, review queues, app-brain facts, and assumption ledgers using stable, published, versioned schemas that include IDs and relationships needed for downstream integration; consumers can validate exports against published schemas; and schema changes are versioned and backward-compatible where possible.

**User Stories:**

#### US-M5-009-1: Export structured JSON for integration
**As a** Solution Architect, **I want** JSON exports for documents, traceability, review queues, app-brain facts, and assumption ledgers **so that** downstream enterprise systems can integrate against structured SpecForge data.

**Acceptance Criteria:**
- [ ] JSON export is available for generated documents, traceability, review queues, app-brain facts, and assumption ledgers.
- [ ] Each JSON export declares the schema version it conforms to.
- [ ] Each JSON export includes the IDs and relationships needed for downstream integration (e.g., BR→FR→design→test→NFR links, assumption→section links, fact→source links).
- [ ] Verify in browser using dev-browser skill.

#### US-M5-009-2: Validate exports against published schemas
**As a** Platform Administrator, **I want** published JSON schemas for each export type **so that** consumers can validate exported payloads programmatically.

**Acceptance Criteria:**
- [ ] A published schema is available for each JSON export type.
- [ ] An export payload validates successfully against its declared schema version.
- [ ] The schema is retrievable/discoverable by consumers (schema registry).

#### US-M5-009-3: Versioned, backward-compatible schemas
**As a** Platform Administrator, **I want** schema changes to be versioned and backward-compatible where possible **so that** existing integrations do not break when schemas evolve.

**Acceptance Criteria:**
- [ ] Schemas use stable, explicit version identifiers.
- [ ] Schema changes increment the schema version.
- [ ] Backward-compatible changes are made where possible, and breaking changes are published as new major schema versions.
- [ ] Prior schema versions remain published for a defined deprecation window.

**Functional Requirements:**
- FR-M5-009-1: The system must provide JSON exports for documents, traceability, review queues, app-brain facts, and assumption ledgers.
- FR-M5-009-2: Each JSON export must declare its schema version and include the IDs and relationships required for downstream integration.
- FR-M5-009-3: The system must publish a validatable schema for each JSON export type and expose it via a discoverable registry.
- FR-M5-009-4: The system must version schemas explicitly, prefer backward-compatible changes, and publish breaking changes as new versions while retaining prior versions during a deprecation window.

**Backend / Production Requirements:**
- BE-M5-009-1: A JSON schema registry must store, version, and serve published schemas, recording schema version, status (active/deprecated), and compatibility class.
- BE-M5-009-2: The export pipeline must validate generated JSON against the declared schema version before producing the artefact, failing the job with an actionable error if validation fails.
- BE-M5-009-3: JSON exports must apply permission filtering and redaction consistently with other export types so unauthorized IDs/relationships/source text are excluded.

---

### BR-M5-010 — Export Job Management
**Priority:** Should

**Requirement:** SpecForge shall manage long-running exports as background jobs with status (queued, running, completed, failed), secure download links on completion, actionable error messages on failure, link expiry per tenant policy, and retries that preserve original request parameters and the audit chain.

**User Stories:**

#### US-M5-010-1: Track export job status
**As a** Business Analyst, **I want** to see the status of my export jobs **so that** I know when an export is queued, running, completed, or failed.

**Acceptance Criteria:**
- [ ] Each export job displays status: queued, running, completed, or failed.
- [ ] Status updates are reflected to the user as the job progresses.
- [ ] The user can view their own export jobs and their statuses.
- [ ] Verify in browser using dev-browser skill.

#### US-M5-010-2: Download completed exports securely
**As a** Business Analyst, **I want** completed exports to provide a secure download link that expires **so that** artefacts are accessible only to authorized recipients for a limited time.

**Acceptance Criteria:**
- [ ] Completed exports provide a secure download link.
- [ ] The download link is access-controlled to authorized recipients.
- [ ] The link expires according to tenant policy.
- [ ] Expired links no longer grant access and indicate expiry to the user.
- [ ] Verify in browser using dev-browser skill.

#### US-M5-010-3: Understand and retry failures
**As a** Business Analyst, **I want** failed exports to show actionable error messages and to be retriable **so that** I can resolve issues and re-run the export without re-specifying everything.

**Acceptance Criteria:**
- [ ] Failed exports display an actionable error message.
- [ ] The user can retry a failed export.
- [ ] Retries preserve the original request parameters.
- [ ] Retries preserve the audit chain (the retry is linked to the original request).
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M5-010-1: The system must execute long-running exports as background jobs and expose status: queued, running, completed, failed.
- FR-M5-010-2: The system must provide a secure, access-controlled download link for each completed export.
- FR-M5-010-3: The system must expire download links according to tenant policy and indicate expiry to users.
- FR-M5-010-4: The system must surface actionable error messages for failed exports.
- FR-M5-010-5: The system must support retry of failed exports that preserves original request parameters and the audit chain.

**Backend / Production Requirements:**
- BE-M5-010-1: A durable export queue and worker pool must process export jobs asynchronously, persisting job state (status, progress, worker, timestamps, parameters, artefact reference, error detail).
- BE-M5-010-2: Secure download links must be short-lived, access-scoped tokens validated against recipient authorization at download time, and every download must be audit logged.
- BE-M5-010-3: Failed jobs must record a structured, user-safe error and a detailed internal diagnostic; retries must create a new job linked to the original request's audit chain and reuse the original parameters.
- BE-M5-010-4: Artefact storage and links must enforce retention/expiry per tenant policy; expired artefacts must be purged or made inaccessible per policy.
- BE-M5-010-5: The job pipeline must enforce per-tenant concurrency/rate limits and re-evaluate the requester's authorization at generation time to prevent stale-permission disclosure.

## 7. Non-Goals / Out of Scope

- Building or redefining the document/section content model, requirement cards, assumptions, traceability graph, stale-impact engine, or app-brain content — these are owned by Modules 2 and 4 and consumed here.
- Building the underlying version-history infrastructure, audit-log store, role-based access control, or design-token system — owned by Module 0 and consumed here.
- Defining LLM provider integration, model routing, or AI generation logic (Module 4); Module 5 only carries the resulting provenance/metadata into exports.
- Live collaborative co-editing of exported artefacts; exports are point-in-time outputs, not live documents.
- A general-purpose report designer or arbitrary custom-template authoring for exports; export formats follow administrator-approved templates.
- Inbound import/round-trip editing of exported files back into SpecForge.
- Real-time push delivery of exports to external systems (e.g., direct writes into records systems); Module 5 produces validatable artefacts and secure links that integrations consume.
- Digital signing / e-signature of approval (approval signatures are a separate production capability per overview section 9), beyond carrying approval state into exports.

## 8. Technical Considerations

- **Background job architecture:** Exports run via a durable queue and worker pool (e.g., message queue + worker service) with persisted job records. Synchronous inline export may be permitted only for small/cheap artefacts but must still produce audit records and access-controlled outputs. UI status reflects queued/running/completed/failed and progress.
- **Immutable snapshot store:** Version snapshots are stored content-addressed and immutable (consumes Module 0 version infrastructure). Export rendering and diff read from snapshots so artefacts are reproducible and consistent with the recorded version. Diff is computed server-side at section granularity.
- **Redaction policy engine:** A central policy engine evaluates recipient role, requester clearance, and content data classification (consumes BR-M4-011) at generation time. It applies exclusion, masking, and redaction-notice rules uniformly across all export types. Restricted source text and secrets must never appear in any artefact for an unauthorized recipient; standalone packaging additionally runs a secret-scan and fails closed.
- **Access-controlled, expiring downloads:** Completed artefacts are stored access-controlled; download links are short-lived signed/scoped tokens validated against recipient authorization at download time, with expiry per tenant policy. Re-authorization at generation and download prevents stale-permission disclosure.
- **JSON schema registry/versioning:** A schema registry stores and serves versioned, validatable schemas for each machine-readable export type (documents, traceability, review queues, app-brain facts, assumption ledgers). The pipeline validates payloads against the declared schema before producing artefacts. Backward-compatibility is preferred; breaking changes become new major versions; prior versions remain available for a deprecation window.
- **Format rendering:** Approved enterprise formats (e.g., DOCX, PDF, CSV, XLSX, JSON, standalone HTML) are produced by format-specific renderers that preserve section rendering kinds, requirement-card structure, citations/provenance, trace links/gap status, assumption status/confidence, and approval/status state. Excel renderers preserve gap highlighting.
- **Audit logging:** Every export request, generation, download, and restore writes an immutable audit record (consumes BR-M0-007) including actor, timestamp, project, document/app, version(s), scope, format, and redaction profile. Audit records are immutable to non-admin users and link request→job→artefact and retry lineage.
- **Provenance preservation:** All exports must carry version identity, citations/source spans, trace links (with explicit gap status), assumption status/confidence, and AI generation metadata (skill/model/prompt-template versions where available) so artefacts remain auditable and explainable outside the workbench.
- **Consistency with latest rebuilds:** Trace exports read the current materialized trace graph; restores re-run downstream staleness recomputation and update trace annotations.

## 9. Success Metrics

- 100% of exported artefacts retain version identity, citations, trace links (with gap status), and assumption status (verified by sampling/automated checks).
- 0 incidents of restricted source text or secrets appearing in exports delivered to unauthorized recipients.
- 100% of export requests, downloads, and restores produce an immutable audit record.
- ≥99% of export jobs complete successfully on first attempt; failed jobs surface an actionable error in 100% of cases.
- 100% of completed exports deliver via a secure link that enforces tenant expiry; 0 successful downloads via expired links.
- 100% of JSON exports validate against their declared published schema version.
- Non-destructive restore preserves prior versions in 100% of restores (0 history loss) and triggers downstream staleness recomputation in 100% of restores.
- Median time-to-download for standard document/trace/ledger exports within the agreed enterprise SLA (e.g., under a defined threshold for typical artefact sizes).

## 10. Open Questions

- Which exact enterprise formats are "approved" per document type (DOCX vs PDF vs both), and are signed/locked PDF variants required for approval workflows?
- What is the default download-link expiry per tenant, and can recipients request re-issuance of an expired link (and under what authorization)?
- What is the retention period for generated export artefacts before purge, and does it differ by classification (e.g., compliance evidence retained longer)?
- For app-brain exports, what is the explicit authorization mechanism (role, per-classification grant, owner approval) required to include restricted source text?
- What is the schema deprecation-window length, and how are consumers notified of schema version changes/deprecations?
- Should redaction produce a visible redaction summary/notice in human-readable exports, and at what granularity (per section vs per artefact)?
- For standalone HTML packaging, what is the enterprise policy on embedding vs pinning third-party dependencies, and is there an allowlist of permitted assets?
- Are exports ever delivered to external parties outside the tenant boundary, and if so what additional watermarking/DLP controls are required?
- What concurrency/rate limits and worker capacity are required to meet export SLAs at portfolio scale?
- Do JSON exports for "review queues" need to include reviewer identities/comments, and how are those redacted for non-authorized consumers?

## 11. Traceability Map

| BR ID | User Stories | Functional Requirements | Backend Reqs |
|-------|--------------|-------------------------|--------------|
| BR-M5-001 — Document Export | US-M5-001-1, US-M5-001-2, US-M5-001-3 | FR-M5-001-1, FR-M5-001-2, FR-M5-001-3, FR-M5-001-4, FR-M5-001-5 | BE-M5-001-1, BE-M5-001-2, BE-M5-001-3, BE-M5-001-4 |
| BR-M5-002 — Section Export | US-M5-002-1, US-M5-002-2, US-M5-002-3 | FR-M5-002-1, FR-M5-002-2, FR-M5-002-3, FR-M5-002-4, FR-M5-002-5 | BE-M5-002-1, BE-M5-002-2 |
| BR-M5-003 — Trace Matrix Export | US-M5-003-1, US-M5-003-2, US-M5-003-3 | FR-M5-003-1, FR-M5-003-2, FR-M5-003-3, FR-M5-003-4, FR-M5-003-5 | BE-M5-003-1, BE-M5-003-2, BE-M5-003-3 |
| BR-M5-004 — App Brain Export | US-M5-004-1, US-M5-004-2, US-M5-004-3 | FR-M5-004-1, FR-M5-004-2, FR-M5-004-3, FR-M5-004-4, FR-M5-004-5 | BE-M5-004-1, BE-M5-004-2, BE-M5-004-3 |
| BR-M5-005 — Assumption Ledger Export | US-M5-005-1, US-M5-005-2, US-M5-005-3 | FR-M5-005-1, FR-M5-005-2, FR-M5-005-3, FR-M5-005-4, FR-M5-005-5 | BE-M5-005-1, BE-M5-005-2, BE-M5-005-3 |
| BR-M5-006 — Version Snapshot Preview and Compare | US-M5-006-1, US-M5-006-2, US-M5-006-3 | FR-M5-006-1, FR-M5-006-2, FR-M5-006-3, FR-M5-006-4 | BE-M5-006-1, BE-M5-006-2, BE-M5-006-3 |
| BR-M5-007 — Non-Destructive Restore | US-M5-007-1, US-M5-007-2, US-M5-007-3 | FR-M5-007-1, FR-M5-007-2, FR-M5-007-3, FR-M5-007-4, FR-M5-007-5 | BE-M5-007-1, BE-M5-007-2, BE-M5-007-3 |
| BR-M5-008 — Standalone HTML Packaging | US-M5-008-1, US-M5-008-2 | FR-M5-008-1, FR-M5-008-2, FR-M5-008-3, FR-M5-008-4, FR-M5-008-5 | BE-M5-008-1, BE-M5-008-2, BE-M5-008-3 |
| BR-M5-009 — JSON Schema Export | US-M5-009-1, US-M5-009-2, US-M5-009-3 | FR-M5-009-1, FR-M5-009-2, FR-M5-009-3, FR-M5-009-4 | BE-M5-009-1, BE-M5-009-2, BE-M5-009-3 |
| BR-M5-010 — Export Job Management | US-M5-010-1, US-M5-010-2, US-M5-010-3 | FR-M5-010-1, FR-M5-010-2, FR-M5-010-3, FR-M5-010-4, FR-M5-010-5 | BE-M5-010-1, BE-M5-010-2, BE-M5-010-3, BE-M5-010-4, BE-M5-010-5 |
