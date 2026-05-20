# PRD: Module 3 — Template & Prompt Engineer Workspace

> Part of the SpecForge detailed business-requirements PRD set. Sources: `.claude/prd/01-system-overview-and-business-context.md`, `.claude/prd/business-requirements-by-module.md`.

## 1. Introduction / Overview

Module 3 is the reusable editing and prompt-control layer that sits underneath the SpecForge document workbench (Module 2). Where Module 2 delivers the end-user document experience (BRD/FS/NFR editing, review, traceability), Module 3 delivers the shared building blocks those screens depend on: a single Section Editor used across every managed document type, section metadata governance (numbering, status, locks, owners, approvers), upstream/downstream linkage management, requirement-card editing with AI assistance, reusable section templates, AI confidence-threshold controls, and restricted prototype/demo tweak controls.

The business value is structural consistency and configurability. Enterprise SDLC documents require standard section structures, consistent numbering, explicit ownership and approval, governed locks, traceable linkages, and uniform requirement-card schemas. Prompt engineers and platform administrators also need a governed place to control how AI drafting behaves — which templates are applied, what confidence threshold gates output, and how every AI-assisted edit is recorded for audit. By centralizing these capabilities, Module 3 turns SpecForge from a set of hard-coded screens into a configurable document-generation platform where new document types, section templates, and AI actions can be introduced without rebuilding the product.

This module is also the natural home for the production governance plumbing implied by the system overview (sections 8 and 9): section/template persistence and versioning, a prompt/skill/template version governance store, AI audit-metadata capture (skill version, model, prompt template version, confidence threshold used), and staleness-check scheduling triggered by linkage saves.

## 2. Goals

- Provide one shared Section Editor (Content / Metadata / Linkages) used consistently across all managed document types, in both edit and add modes.
- Make section structure governable: editable numbering with downstream renumbering preview, status lifecycle, AI locks, owners, and approvers.
- Allow users to select and persist a section rendering kind (prose, bulleted, table, requirement cards, process flow) that is honored consistently in editor, export, and version preview.
- Allow users to manage upstream linkages (source spans, BR/FR/NFR references) and downstream dependency links, and to trigger staleness checks when downstream links are saved.
- Provide structured requirement-card editing with acceptance-criteria management, ID suggestion, and AI assistance for criteria generation, wording improvement, and conflict detection.
- Allow application of approved, compatibility-validated section templates without silent content loss.
- Give users and administrators a governed AI confidence threshold that gates drafting aggressiveness and is recorded in AI audit metadata.
- Provide restricted design/demo tweak controls that are gated to prototype/demo/admin contexts in production.
- Capture full version and audit provenance (skill version, model, prompt template version, confidence threshold) for every AI-assisted section and card edit.

## 3. Scope

### In scope (with priority)

- BR-M3-001 — Shared Section Editor — Must
- BR-M3-002 — Section Rendering Mode Selection — Must
- BR-M3-003 — Section Metadata Management — Must
- BR-M3-004 — Section Linkage Management — Must
- BR-M3-005 — Card-Level Editing — Must
- BR-M3-006 — Card AI Assistance — Should
- BR-M3-007 — Template Application — Should
- BR-M3-008 — Prompt Confidence Threshold — Should
- BR-M3-009 — Global Tweak and Demo Controls — Could

### Priorities covered

- **Must:** BR-M3-001, BR-M3-002, BR-M3-003, BR-M3-004, BR-M3-005
- **Should:** BR-M3-006, BR-M3-007, BR-M3-008
- **Could:** BR-M3-009

## 4. Users & Roles

The following SpecForge roles (defined in overview section 4) interact with Module 3 capabilities:

- **Business Analyst** — Primary operator of the Section Editor and Card Editor. Adds/edits sections, sets rendering kind, manages metadata they own, links sources and requirements, edits requirement cards, applies templates, and uses card AI assistance.
- **Solution Architect** — Reviews and edits downstream-linked sections (FS/NFR design-bearing sections), declares downstream dependency links with severity/reason, and validates linkage-driven staleness impact.
- **QA Lead** — Consumes requirement cards and acceptance criteria; benefits from AI-generated, testable acceptance criteria and conflict checks against trace links.
- **Product Owner / Business Sponsor** — May be assigned as section owner or approver; participates in the section status lifecycle (In review, Approved).
- **Compliance / Risk Reviewer** — Relies on locked sections, recorded skill/model/template/threshold audit metadata, and provenance preserved through versioning and export.
- **Platform Administrator / AI Engineer** — Governs prompt/skill/template versions, configures the default and per-context confidence threshold, manages approved template catalogue, and controls access to restricted demo/tweak controls.
- **App Owner** — Indirect consumer: section linkages and grounding influence downstream app-brain proposals (handled in Module 4); included here as a stakeholder for linkage integrity.

Authorization note: section editing, locking, status promotion, approver assignment, template administration, threshold configuration, and demo-control access are all subject to Module 0 role-based access control (BR-M0-008).

## 5. Key Business Objects

- **Section Draft** — An in-progress editable representation of a document section, including content, rendering kind, metadata, and linkages, before save commits a new version.
- **Section Metadata** — Section number, status (Draft, AI draft, In review, Approved), lock state, owner, approvers, and AI skill/model attribution.
- **Section Template** — A reusable, approved, versioned section structure (e.g., group-standard scope, business rules, assumptions, open questions) with a target document type and section kind.
- **Rendering Kind** — The selected presentation style of a section: prose, bulleted, table, requirement cards, or process flow.
- **Linked Source Span** — An upstream citation linking a section to a specific location/quote in a source corpus document.
- **Linked Requirement** — An upstream/lateral reference to a BR, FR, or NFR.
- **Downstream Dependency** — A declared link from this section to a dependent downstream section, carrying severity and reason, used for staleness propagation.
- **Requirement Card** — A structured requirement object (ID, title, description, acceptance criteria, rationale, priority, owner, source citation) embedded in a requirement-card section.
- **Acceptance Criterion** — A single testable, objective condition belonging to a requirement card.
- **Prompt Action** — A configured AI action (e.g., generate acceptance criteria, improve wording, find conflicts) bound to a prompt template version, skill, and model.
- **Confidence Threshold** — A 0–100 setting that gates how aggressively AI drafting produces content and how outputs are confidence-marked.
- **AI Audit Metadata** — The recorded provenance of an AI-assisted edit: skill version, model, prompt template version, source references, confidence threshold used, and output decision state.

## 6. Detailed Business Requirements

### BR-M3-001 — Shared Section Editor
**Priority:** Must

**Requirement:** SpecForge shall provide a single shared Section Editor used for editing and adding sections across all managed document types, exposing Content, Metadata, and Linkages tabs, supporting both edit and add modes, incrementing section and document versions on save, and supporting append or insert-between placement with a downstream renumbering preview.

**User Stories:**

#### US-M3-001-1: Edit an existing section in the shared editor
**As a** Business Analyst, **I want** to open any document section in a shared editor with Content, Metadata, and Linkages tabs **so that** I can edit every aspect of a section consistently regardless of document type.

**Acceptance Criteria:**
- [ ] The Section Editor can be opened from any managed document (BRD, FS, NFR, and future modules) for an existing section.
- [ ] The editor exposes three tabs: Content, Metadata, and Linkages.
- [ ] Opening in edit mode preloads the section's current content, metadata, and linkages.
- [ ] The editor labels its current mode as edit.
- [ ] Verify in browser using dev-browser skill.

#### US-M3-001-2: Add a new section with append or insert placement
**As a** Business Analyst, **I want** to add a new section in either append or insert-between mode **so that** I can extend a document at the end or in the correct position within the existing structure.

**Acceptance Criteria:**
- [ ] The editor supports an add mode distinct from edit mode.
- [ ] Add mode offers append (place after the last section) and insert-between (place at a chosen position) placement options.
- [ ] When insert-between is chosen, a downstream renumbering preview shows how subsequent section numbers will change before save is confirmed.
- [ ] Cancelling add mode does not create a section or alter existing numbering.
- [ ] Verify in browser using dev-browser skill.

#### US-M3-001-3: Versioned save of section edits
**As a** Business Analyst, **I want** saving a section to create new section and document versions **so that** every edit is captured in version history with provenance.

**Acceptance Criteria:**
- [ ] Saving a section in edit mode increments the section version.
- [ ] Saving a section increments the parent document version.
- [ ] Saving an inserted section applies the previewed downstream renumbering.
- [ ] A save records actor, timestamp, and a change note compatible with version history (Module 0 BR-M0-006).
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M3-001-1: The system must provide a single shared Section Editor component reused across all managed document types.
- FR-M3-001-2: The system must expose Content, Metadata, and Linkages tabs within the Section Editor.
- FR-M3-001-3: The system must support edit mode (existing section) and add mode (new section) within the same editor.
- FR-M3-001-4: The system must support append and insert-between placement when adding a section.
- FR-M3-001-5: The system must display a downstream renumbering preview when insert-between placement is selected, before save is confirmed.
- FR-M3-001-6: The system must increment both section version and document version on save.

**Backend / Production Requirements:**
- BE-M3-001-1: The system must persist section drafts and committed sections to a durable store with section ID, document ID, version number, rendering kind, content, metadata, and linkages.
- BE-M3-001-2: The system must persist an immutable version snapshot for each saved section and parent-document version, consistent with cross-document version history (overview section 8; BR-M0-006).
- BE-M3-001-3: The system must record an audit event for every section save including actor, timestamp, project, document key, source version, target version, and affected sections (BR-M0-007).
- BE-M3-001-4: The system must atomically apply downstream section renumbering on insert so no two sections share a number after commit.

---

### BR-M3-002 — Section Rendering Mode Selection
**Priority:** Must

**Requirement:** SpecForge shall allow users to select a section rendering style from prose, bulleted, table, requirement cards, or process flow; store the selected kind on the draft section; render requirement-card sections as intro text plus individual card rows; and honor the selected kind consistently across editor, export, and version preview.

**User Stories:**

#### US-M3-002-1: Select a section rendering kind
**As a** Business Analyst, **I want** to choose how a section is rendered (prose, bulleted, table, requirement cards, or process flow) **so that** the section's structure matches its content type.

**Acceptance Criteria:**
- [ ] The Content tab displays the available section kinds as selectable controls: prose, bulleted, table, requirement cards, and process flow.
- [ ] The currently selected kind is visually indicated.
- [ ] Changing the selected kind updates the editor's content rendering to match.
- [ ] The selected kind is stored on the draft section and persisted on save.
- [ ] Verify in browser using dev-browser skill.

#### US-M3-002-2: Requirement-card section structure
**As a** Business Analyst, **I want** requirement-card sections to render as intro text plus individual card rows **so that** I can manage the section narrative and its requirement cards separately.

**Acceptance Criteria:**
- [ ] Selecting the requirement-cards kind renders an intro text area plus one row per requirement card.
- [ ] Individual card rows are independently editable (via Card-Level Editing, BR-M3-005).
- [ ] Verify in browser using dev-browser skill.

#### US-M3-002-3: Consistent rendering across surfaces
**As a** Compliance Reviewer, **I want** the selected rendering kind to be honored in editor, export, and version preview **so that** what I review and export matches what was authored.

**Acceptance Criteria:**
- [ ] A section's stored rendering kind is applied identically in the editor view.
- [ ] The same rendering kind is applied in document export output (Module 5).
- [ ] The same rendering kind is applied in version preview/compare (Module 5 / BR-M0-006).
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M3-002-1: The system must present the five rendering kinds (prose, bulleted, table, requirement cards, process flow) as selectable controls in the Section Editor.
- FR-M3-002-2: The system must store the selected rendering kind on the draft section and persist it on save.
- FR-M3-002-3: The system must render requirement-card sections as intro text plus individual card rows.
- FR-M3-002-4: The system must apply the stored rendering kind consistently in editor, export, and version preview surfaces.

**Backend / Production Requirements:**
- BE-M3-002-1: The system must persist the rendering kind as a typed attribute on the section record so downstream consumers (export, version preview, traceability) resolve it deterministically.
- BE-M3-002-2: The system must validate that the stored rendering kind is one of the supported enumerated values on save.

---

### BR-M3-003 — Section Metadata Management
**Priority:** Must

**Requirement:** SpecForge shall allow users to manage section number, status (Draft, AI draft, In review, Approved), lock state, owner, and approvers, and shall record skill version and model for AI-assisted edits. A section lock shall prevent AI modification while still allowing authorized manual edits.

**User Stories:**

#### US-M3-003-1: Edit section number and status
**As a** Business Analyst, **I want** to edit a section's number and status **so that** the document structure and lifecycle state stay accurate.

**Acceptance Criteria:**
- [ ] The Metadata tab allows the section number to be edited.
- [ ] Status can be set to one of: Draft, AI draft, In review, Approved.
- [ ] The currently selected status is clearly indicated.
- [ ] Editing the section number triggers the downstream renumbering rules consistent with BR-M3-001 where applicable.
- [ ] Verify in browser using dev-browser skill.

#### US-M3-003-2: Assign owner and approvers
**As a** Business Analyst, **I want** to set a section owner and add or remove approvers **so that** accountability and approval routing are explicit.

**Acceptance Criteria:**
- [ ] An owner can be selected for the section.
- [ ] One or more approvers can be added to the section.
- [ ] Approvers can be removed from the section.
- [ ] Owner and approver assignments persist on save.
- [ ] Verify in browser using dev-browser skill.

#### US-M3-003-3: Lock a section against AI modification
**As a** Solution Architect, **I want** to lock a section **so that** AI actions cannot modify it while authorized humans can still edit it.

**Acceptance Criteria:**
- [ ] The Metadata tab provides a lock state control.
- [ ] When a section is locked, AI actions (regenerate, improve, expand, etc.) are blocked or disabled for that section.
- [ ] When a section is locked, authorized users can still perform manual edits.
- [ ] The lock state is visually indicated on the section.
- [ ] Verify in browser using dev-browser skill.

#### US-M3-003-4: Record AI attribution metadata
**As a** Compliance Reviewer, **I want** the skill version and model to be recorded for AI-assisted edits **so that** AI provenance is auditable.

**Acceptance Criteria:**
- [ ] When a section is created or modified by an AI action, the skill version is recorded on the section metadata.
- [ ] When a section is created or modified by an AI action, the model is recorded on the section metadata.
- [ ] Recorded skill version and model are visible in section metadata and version history.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M3-003-1: The system must allow editing the section number from the Metadata tab.
- FR-M3-003-2: The system must support the section status set: Draft, AI draft, In review, Approved.
- FR-M3-003-3: The system must support setting and clearing a section lock state.
- FR-M3-003-4: The system must block AI modification of locked sections while permitting authorized manual edits.
- FR-M3-003-5: The system must allow selection of a section owner.
- FR-M3-003-6: The system must allow adding and removing approvers.
- FR-M3-003-7: The system must record skill version and model on metadata for AI-assisted edits.

**Backend / Production Requirements:**
- BE-M3-003-1: The system must persist section metadata (number, status, lock state, owner, approvers, skill version, model) on the section record and version it with each save.
- BE-M3-003-2: The system must enforce that AI generation/assistance services refuse to write to a section whose lock state is set, returning a governance error rather than silently editing.
- BE-M3-003-3: The system must enforce role-based authorization for status promotion to Approved, lock toggling, and approver assignment (BR-M0-008).
- BE-M3-003-4: The system must record skill version and model into immutable AI audit metadata for each AI-assisted edit (BR-M0-007 AI audit fields).

---

### BR-M3-004 — Section Linkage Management
**Priority:** Must

**Requirement:** SpecForge shall allow users to link sections to upstream source spans and BR/FR/NFR references, declare downstream dependency links with severity and reason, schedule a staleness check when a section with downstream links is saved, and treat all user-declared linkages as additive to automatically discovered links.

**User Stories:**

#### US-M3-004-1: Manage upstream source citations
**As a** Business Analyst, **I want** to add and remove source citations on a section **so that** the section's claims are grounded in evidence.

**Acceptance Criteria:**
- [ ] The Linkages tab allows adding a source citation (linked source span).
- [ ] The Linkages tab allows removing an existing source citation.
- [ ] Added citations persist on save and are inspectable as section citations.
- [ ] Verify in browser using dev-browser skill.

#### US-M3-004-2: Manage linked requirement references
**As a** Business Analyst, **I want** to add and remove BR/FR/NFR references on a section **so that** the section is connected to the requirement graph.

**Acceptance Criteria:**
- [ ] Users can add a linked BR, FR, or NFR reference.
- [ ] Users can remove a linked BR, FR, or NFR reference.
- [ ] Linked requirement references persist on save and contribute to traceability.
- [ ] Verify in browser using dev-browser skill.

#### US-M3-004-3: Declare downstream dependency links
**As a** Solution Architect, **I want** to declare downstream dependent sections with a severity and reason **so that** staleness can propagate correctly when this section changes.

**Acceptance Criteria:**
- [ ] Users can declare a downstream dependency link to a dependent section.
- [ ] Each downstream dependency link captures a severity.
- [ ] Each downstream dependency link captures a reason.
- [ ] Declared downstream links persist on save.
- [ ] Verify in browser using dev-browser skill.

#### US-M3-004-4: Trigger staleness check on save
**As a** Solution Architect, **I want** saving a section that has downstream links to schedule a staleness check **so that** affected downstream sections are flagged automatically.

**Acceptance Criteria:**
- [ ] Saving a section that has one or more downstream dependency links schedules a staleness check.
- [ ] The scheduled staleness check evaluates the declared downstream sections for invalidation.
- [ ] User-declared linkages are additive to automatically discovered links (declared links never delete or override auto-discovered links).
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M3-004-1: The system must allow adding and removing upstream source citations on a section.
- FR-M3-004-2: The system must allow adding and removing linked BR/FR/NFR references on a section.
- FR-M3-004-3: The system must allow declaring downstream dependency links with severity and reason.
- FR-M3-004-4: The system must schedule a staleness check when a section with downstream links is saved.
- FR-M3-004-5: The system must treat user-declared linkages as additive to automatically discovered links.

**Backend / Production Requirements:**
- BE-M3-004-1: The system must persist source-span links, requirement links, and downstream dependency links (with severity and reason) as first-class linkage records associated with the section and its version.
- BE-M3-004-2: The system must enqueue a staleness-check job on save of any section that carries downstream dependency links, feeding the stale-impact engine (BR-M2-011) consistent with overview section 8 traceability/stale enforcement.
- BE-M3-004-3: The system must distinguish user-declared linkages from auto-discovered linkages in storage so the additive guarantee can be enforced and audited.
- BE-M3-004-4: The system must record an audit event when linkages are added, removed, or changed (BR-M0-007).

---

### BR-M3-005 — Card-Level Editing
**Priority:** Must

**Requirement:** SpecForge shall allow users to edit requirement cards embedded in document sections, including requirement ID, title, description, acceptance criteria, rationale, priority, owner, and source citation; allow adding and removing acceptance criteria while retaining at least one; suggest new card IDs based on existing card prefix and highest numeric suffix; and notify the parent section editor when card changes are saved.

**User Stories:**

#### US-M3-005-1: Edit requirement card fields
**As a** Business Analyst, **I want** to edit all fields of a requirement card **so that** the requirement is complete and accurate.

**Acceptance Criteria:**
- [ ] The Card Editor allows editing requirement ID, title, description, rationale, priority, owner, and source citation.
- [ ] Edited card fields persist on save.
- [ ] Verify in browser using dev-browser skill.

#### US-M3-005-2: Manage acceptance criteria
**As a** QA Lead, **I want** to add and remove acceptance criteria on a requirement card while always keeping at least one **so that** every requirement remains testable.

**Acceptance Criteria:**
- [ ] Users can edit existing acceptance criteria text.
- [ ] Users can add a new acceptance criterion.
- [ ] Users can remove an acceptance criterion.
- [ ] At least one acceptance criterion is always retained (the last remaining criterion cannot be removed).
- [ ] Verify in browser using dev-browser skill.

#### US-M3-005-3: Suggest new card IDs
**As a** Business Analyst, **I want** new requirement cards to receive a suggested ID **so that** card IDs stay consistent and unique within the section.

**Acceptance Criteria:**
- [ ] When a new card is added, the system suggests an ID using the existing card prefix and the next value after the highest numeric suffix in use.
- [ ] The suggested ID is editable before save.
- [ ] Verify in browser using dev-browser skill.

#### US-M3-005-4: Notify parent section on card save
**As a** Business Analyst, **I want** saving a card to notify the parent Section Editor **so that** section state and version stay in sync with card edits.

**Acceptance Criteria:**
- [ ] Saving card changes notifies the parent Section Editor of the change.
- [ ] The parent section reflects the updated card content after notification.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M3-005-1: The system must allow editing requirement ID, title, description, acceptance criteria, rationale, priority, owner, and source citation on a requirement card.
- FR-M3-005-2: The system must allow adding and removing acceptance criteria.
- FR-M3-005-3: The system must enforce retention of at least one acceptance criterion per card.
- FR-M3-005-4: The system must suggest a new card ID derived from the existing card prefix and highest numeric suffix.
- FR-M3-005-5: The system must notify the parent Section Editor when card changes are saved.

**Backend / Production Requirements:**
- BE-M3-005-1: The system must persist requirement cards as structured records (ID, title, description, acceptance criteria, rationale, priority, owner, source citation) associated with their parent section and version.
- BE-M3-005-2: The system must enforce uniqueness of card IDs within a document/section scope on save.
- BE-M3-005-3: The system must propagate card edits into section versioning and trace links so the traceability matrix (BR-M2-013) reflects current cards.
- BE-M3-005-4: The system must record an audit event for card create/edit/delete actions (BR-M0-007).

---

### BR-M3-006 — Card AI Assistance
**Priority:** Should

**Requirement:** SpecForge shall provide AI assistance within the Card Editor for generating acceptance criteria, improving requirement wording, and finding conflicts with other requirements; generated acceptance criteria shall be testable and objective; conflict checks shall compare sibling requirements, assumptions, and trace links; and AI changes shall require user save/acceptance before becoming authoritative.

**User Stories:**

#### US-M3-006-1: Generate acceptance criteria with AI
**As a** QA Lead, **I want** AI to generate testable, objective acceptance criteria for a requirement card **so that** requirements have verifiable conditions without manual drafting.

**Acceptance Criteria:**
- [ ] AI actions are visible in the Card Editor.
- [ ] An AI action generates acceptance criteria for the current card.
- [ ] Generated acceptance criteria are phrased to be testable and objective.
- [ ] Generated criteria are presented as suggestions, not applied automatically.
- [ ] Verify in browser using dev-browser skill.

#### US-M3-006-2: Improve requirement wording with AI
**As a** Business Analyst, **I want** AI to improve the wording of a requirement **so that** the requirement is clearer without changing its meaning.

**Acceptance Criteria:**
- [ ] An AI action improves the wording of the current requirement card.
- [ ] The improved wording is presented as a suggestion that the user can accept or discard.
- [ ] Verify in browser using dev-browser skill.

#### US-M3-006-3: Find conflicts with other requirements
**As a** Solution Architect, **I want** AI to find conflicts between this requirement and others **so that** contradictions are caught before approval.

**Acceptance Criteria:**
- [ ] An AI conflict check compares the current card against sibling requirements.
- [ ] The conflict check considers assumptions.
- [ ] The conflict check considers trace links.
- [ ] Detected conflicts are surfaced to the user with enough context to act.
- [ ] Verify in browser using dev-browser skill.

#### US-M3-006-4: Require user acceptance of AI changes
**As a** Compliance Reviewer, **I want** AI-suggested card changes to require explicit user save/acceptance **so that** AI output never becomes authoritative without human judgement.

**Acceptance Criteria:**
- [ ] AI-suggested changes do not modify the authoritative card until the user saves/accepts them.
- [ ] The user can accept or reject AI suggestions before save.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M3-006-1: The system must surface AI actions for generate acceptance criteria, improve wording, and find conflicts within the Card Editor.
- FR-M3-006-2: The system must produce acceptance criteria that are testable and objective.
- FR-M3-006-3: The system must compare against sibling requirements, assumptions, and trace links when performing conflict checks.
- FR-M3-006-4: The system must require explicit user save/acceptance before AI-generated card changes become authoritative.

**Backend / Production Requirements:**
- BE-M3-006-1: The system must route card AI actions through the configured LLM provider/model and prompt template version (BR-M4-010) and respect the active confidence threshold (BR-M3-008).
- BE-M3-006-2: The system must record AI audit metadata (skill version, model, prompt template version, source references, confidence threshold used, output decision state) for each card AI action (BR-M0-007).
- BE-M3-006-3: The system must respect section lock state and data-classification clearance, refusing AI assistance where prohibited (BR-M3-003, BR-M4-011).
- BE-M3-006-4: The system must store AI suggestions in a non-authoritative draft state until user acceptance is recorded.

---

### BR-M3-007 — Template Application
**Priority:** Should

**Requirement:** SpecForge shall allow users to apply approved section templates to section drafts; template options shall include group-standard scope, business rules, assumptions, and open-questions templates; template application shall record template ID and version; template compatibility shall be validated against document type and section kind; and applying a template shall not remove existing content without confirmation.

**User Stories:**

#### US-M3-007-1: Apply an approved section template
**As a** Business Analyst, **I want** to apply an approved section template to a section draft **so that** the section follows the standard structure quickly.

**Acceptance Criteria:**
- [ ] Available template options include group-standard scope, business rules, assumptions, and open-questions templates.
- [ ] Applying a template populates the section draft with the template structure/content.
- [ ] The applied template's ID and version are recorded on the section.
- [ ] Verify in browser using dev-browser skill.

#### US-M3-007-2: Validate template compatibility
**As a** Platform Administrator, **I want** template compatibility to be validated against the document type and section kind **so that** users cannot apply an incompatible template.

**Acceptance Criteria:**
- [ ] The system validates the template against the current document type before applying.
- [ ] The system validates the template against the current section kind before applying.
- [ ] Incompatible templates are not offered or are blocked from application with a clear message.
- [ ] Verify in browser using dev-browser skill.

#### US-M3-007-3: Protect existing content on template apply
**As a** Business Analyst, **I want** to be warned before a template overwrites existing content **so that** I do not lose work unintentionally.

**Acceptance Criteria:**
- [ ] Applying a template to a section that already has content prompts for confirmation before any content is removed or replaced.
- [ ] Cancelling the confirmation leaves the existing content unchanged.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M3-007-1: The system must offer approved template options including group-standard scope, business rules, assumptions, and open-questions templates.
- FR-M3-007-2: The system must record applied template ID and version on the section.
- FR-M3-007-3: The system must validate template compatibility against document type and section kind before application.
- FR-M3-007-4: The system must require confirmation before applying a template removes existing content.

**Backend / Production Requirements:**
- BE-M3-007-1: The system must maintain a governed template catalogue with template ID, version, approval status, target document type(s), and compatible section kind(s).
- BE-M3-007-2: The system must restrict the catalogue to approved templates and enforce administrator-only template publishing (BR-M0-008, overview section 8 version governance).
- BE-M3-007-3: The system must persist the applied template ID and version on the section record and into AI/version audit metadata.
- BE-M3-007-4: The system must version templates so that an applied template's exact version is reconstructable for audit.

---

### BR-M3-008 — Prompt Confidence Threshold
**Priority:** Should

**Requirement:** SpecForge shall allow users or administrators to configure a confidence threshold for AI drafting actions, adjustable from 0 to 100, defaulting conservatively to 80, where lower thresholds permit more aggressive drafting but mark outputs with lower confidence, and the threshold used for generation shall be stored in AI audit metadata.

**User Stories:**

#### US-M3-008-1: Configure the confidence threshold
**As a** Platform Administrator, **I want** to configure the AI drafting confidence threshold from 0 to 100 **so that** I can govern how aggressively AI drafts content.

**Acceptance Criteria:**
- [ ] The confidence threshold control accepts values from 0 to 100.
- [ ] The default threshold is 80.
- [ ] Values outside 0–100 are rejected or clamped.
- [ ] Verify in browser using dev-browser skill.

#### US-M3-008-2: Threshold affects drafting behavior
**As a** Business Analyst, **I want** lowering the threshold to allow more aggressive drafting with appropriately lower-confidence marking **so that** I can trade thoroughness for caution deliberately.

**Acceptance Criteria:**
- [ ] Lowering the threshold permits AI to produce more content (more aggressive drafting).
- [ ] Outputs produced under a lower threshold are marked with lower confidence.
- [ ] The behavior change is reflected in subsequent AI drafting actions.
- [ ] Verify in browser using dev-browser skill.

#### US-M3-008-3: Record threshold in audit metadata
**As a** Compliance Reviewer, **I want** the threshold used for each generation stored in AI audit metadata **so that** I can audit the governance settings behind any AI output.

**Acceptance Criteria:**
- [ ] The threshold value in effect at generation time is stored in the AI audit metadata for that generation.
- [ ] The stored threshold is retrievable alongside skill version, model, and prompt template version.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M3-008-1: The system must provide a confidence-threshold control adjustable from 0 to 100.
- FR-M3-008-2: The system must default the threshold to 80.
- FR-M3-008-3: The system must allow lower thresholds to enable more aggressive drafting while marking outputs with lower confidence.
- FR-M3-008-4: The system must store the threshold used for each generation in AI audit metadata.

**Backend / Production Requirements:**
- BE-M3-008-1: The system must persist the confidence threshold at the appropriate governance scope (administrator default and any permitted per-user/per-project override) under access control (BR-M0-008).
- BE-M3-008-2: The system must pass the effective threshold to the AI drafting pipeline and apply it to output confidence marking.
- BE-M3-008-3: The system must record the effective threshold into immutable AI audit metadata alongside skill version, model, and prompt template version (BR-M0-007, overview section 8).
- BE-M3-008-4: The system must validate the threshold range (0–100) server-side, independent of client controls.

---

### BR-M3-009 — Global Tweak and Demo Controls
**Priority:** Could

**Requirement:** SpecForge shall provide restricted design/demo controls for changing the accent color and jumping to representative screens; the tweak panel shall be openable and closable through host edit mode; accent color changes shall update the runtime CSS variable; jump buttons shall route to representative screens; and tweak controls shall be restricted to prototype/demo/admin contexts in production.

> Restricted capability: This BR is a prototype/demo convenience. In production it MUST be gated to demo/admin contexts and never exposed to standard end users.

**User Stories:**

#### US-M3-009-1: Open and close the tweak panel via host edit mode
**As a** Platform Administrator (demo context), **I want** to open and close the tweak panel through host edit mode **so that** demo controls are only available when explicitly enabled.

**Acceptance Criteria:**
- [ ] The tweak panel can be opened through host edit mode.
- [ ] The tweak panel can be closed.
- [ ] The panel is not present/accessible outside host edit mode.
- [ ] Verify in browser using dev-browser skill.

#### US-M3-009-2: Change runtime accent color
**As a** Platform Administrator (demo context), **I want** to change the accent color and have it apply at runtime **so that** I can demonstrate theming without a rebuild.

**Acceptance Criteria:**
- [ ] Changing the accent color updates the runtime CSS variable.
- [ ] The updated accent color is reflected immediately in the UI.
- [ ] Verify in browser using dev-browser skill.

#### US-M3-009-3: Jump to representative screens
**As a** Platform Administrator (demo context), **I want** jump buttons that route to representative screens **so that** I can quickly navigate a demo.

**Acceptance Criteria:**
- [ ] Jump buttons route to Dashboard, New project, Interview, BRD, Review, Stale, Trace, and Workspace.
- [ ] Each jump button navigates to its corresponding screen.
- [ ] Verify in browser using dev-browser skill.

#### US-M3-009-4: Restrict demo controls in production
**As a** Platform Administrator, **I want** tweak controls restricted to prototype/demo/admin contexts in production **so that** standard users cannot alter theming or bypass navigation governance.

**Acceptance Criteria:**
- [ ] In production, tweak controls are only available in prototype/demo/admin contexts.
- [ ] Standard end users cannot access the tweak panel in production.
- [ ] Access to tweak controls is governed by role/context checks.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M3-009-1: The system must allow opening and closing the tweak panel through host edit mode.
- FR-M3-009-2: The system must update the runtime CSS accent variable when the accent color is changed.
- FR-M3-009-3: The system must provide jump buttons routing to Dashboard, New project, Interview, BRD, Review, Stale, Trace, and Workspace.
- FR-M3-009-4: The system must restrict tweak controls to prototype/demo/admin contexts in production.

**Backend / Production Requirements:**
- BE-M3-009-1: The system must gate availability of demo/tweak controls behind a server-enforced context/role flag so they cannot be enabled by client-side manipulation in production (BR-M0-008).
- BE-M3-009-2: The system must ensure accent/theme tweaks are scoped to the demo session and never persist to other users' governed configuration.
- BE-M3-009-3: The system must audit-log activation of demo/tweak mode in production contexts (BR-M0-007).

## 7. Non-Goals / Out of Scope

- Authoring or end-user document editing flows already owned by Module 2 (BRD/FS/NFR editors, targeted review, stale impact resolution UI, traceability matrix screens). Module 3 provides the shared editor and linkage primitives those screens consume but does not redefine the document-level workflows.
- Defining or governing LLM providers, model routing, skill catalogues, and prompt template content — owned by Module 4 (BR-M4-010). Module 3 consumes the active skill/model/template versions and records which were used.
- Export rendering, version compare UI, and restore mechanics — owned by Module 5. Module 3 ensures the rendering kind and provenance survive into those surfaces but does not implement them.
- App AI Brain fact governance and proposed-update workflows — owned by Module 4.
- Application shell, global navigation, version-history panel, audit-log infrastructure, and RBAC enforcement — owned by Module 0. Module 3 invokes and contributes to these.
- The actual LLM inference, RAG retrieval, OCR/parsing/embedding backends — implied production capabilities (overview section 9) and not built as part of Module 3 UI.
- Production-grade theming/branding management for end users (the BR-M3-009 tweak panel is explicitly a restricted demo-only convenience, not a customer-facing theming feature).

## 8. Technical Considerations

- **Single shared editor component.** The Section Editor and Card Editor should be implemented as reusable components consumed by every document module so behavior (tabs, modes, versioning, validation) is identical across document types and only registered section/template schemas vary.
- **Rendering-kind as data, not layout.** Persist rendering kind as a typed enumeration on the section record and resolve presentation from it in every consumer (editor, export, version preview) to satisfy the consistency requirement in BR-M3-002.
- **Versioning model.** Section save must create both a section version and a parent-document version, with immutable snapshots (cannot be restored, per BR-M0-006). Renumbering on insert must be transactional to preserve numbering integrity.
- **Linkage store and staleness scheduling.** Store source-span links, requirement links, and downstream dependency links (with severity/reason) as first-class records distinguishing user-declared from auto-discovered links. Saving a section with downstream links should enqueue an asynchronous staleness-check job feeding the stale-impact engine (BR-M2-011), decoupled from the save transaction for responsiveness.
- **Prompt/skill/template version governance store.** Per overview section 8, maintain a governance store of prompt template versions, skill versions, and section-template versions. Card AI actions (BR-M3-006) and threshold-governed drafting (BR-M3-008) must resolve the active versions at call time and record exactly which versions were used.
- **AI audit metadata capture.** Every AI-assisted section/card edit must capture skill version, model, prompt template version, source references, confidence threshold used, and output decision state into immutable audit records (BR-M0-007). These records must be queryable for compliance review and export (Module 5).
- **Lock enforcement at the service layer.** Section lock must be enforced server-side so AI generation services refuse to write to locked sections regardless of client behavior.
- **Confidence threshold enforcement server-side.** Range validation (0–100), default (80), and effect on drafting/confidence marking must be enforced in the drafting pipeline, not just the UI control.
- **Card ID generation.** ID suggestion (prefix + next numeric suffix) should be computed against persisted cards in the section scope to avoid collisions under concurrent editing; uniqueness must be enforced on save.
- **Demo-control gating.** BR-M3-009 controls must be gated by a server-enforced context/role flag and audit-logged when activated in production; runtime accent changes must be session-scoped CSS variable updates that never persist to governed configuration.
- **Access control everywhere.** Status promotion, locking, approver assignment, template publishing, threshold configuration, and demo-control access are subject to Module 0 RBAC (BR-M0-008).

## 9. Success Metrics

- 100% of managed document types use the single shared Section Editor (no document-specific editor forks).
- Every section save produces a section version and a document version with an associated immutable snapshot and audit record (target: 100%).
- Selected rendering kind matches across editor, export, and version preview for 100% of audited sections.
- 100% of saves of sections carrying downstream links enqueue a staleness check; measured median time from save to staleness-check completion within target SLA.
- 100% of AI-assisted section/card edits carry complete AI audit metadata (skill version, model, prompt template version, confidence threshold used).
- 0 instances of AI modifying a locked section in production audits.
- Acceptance-criterion retention rule holds: 0 cards persisted with zero acceptance criteria.
- Template applications record template ID and version 100% of the time; 0 incompatible template applications reach a section.
- 0 instances of demo/tweak controls being accessible to standard end users in production.
- Reduction in time to author a standard section after template application versus from scratch (baseline to be established).

## 10. Open Questions

- At what scope(s) is the confidence threshold configurable — global default only, or per-project / per-document / per-skill overrides — and who is authorized for each scope?
- What is the precise list of section status transitions allowed, and which roles may perform each (e.g., who may move In review to Approved)?
- Should the section number be a free-text field or a structured hierarchical numbering scheme (e.g., 3.2.1) with automatic descendant renumbering on insert?
- What is the conflict-resolution behavior when a user-declared downstream link contradicts an auto-discovered link (both retained, but how surfaced)?
- How are concurrent edits to the same section/card reconciled (locking, last-write-wins, or merge), and how does that interact with the lock state?
- Which roles may publish/approve section templates into the governed catalogue, and what is the template approval workflow?
- For BR-M3-006, what is the exact threshold for "low confidence" that should downgrade a suggestion's confidence marking, and is it the same threshold as BR-M3-008?
- What is the canonical definition of "host edit mode" for BR-M3-009 in a production deployment, and which admin/demo context flag controls it?
- Should applied-template provenance be visible to end users in the document, or only in audit/version metadata?

## 11. Traceability Map

| BR ID | User Stories | Functional Requirements | Backend Reqs |
|---|---|---|---|
| BR-M3-001 — Shared Section Editor | US-M3-001-1, US-M3-001-2, US-M3-001-3 | FR-M3-001-1, FR-M3-001-2, FR-M3-001-3, FR-M3-001-4, FR-M3-001-5, FR-M3-001-6 | BE-M3-001-1, BE-M3-001-2, BE-M3-001-3, BE-M3-001-4 |
| BR-M3-002 — Section Rendering Mode Selection | US-M3-002-1, US-M3-002-2, US-M3-002-3 | FR-M3-002-1, FR-M3-002-2, FR-M3-002-3, FR-M3-002-4 | BE-M3-002-1, BE-M3-002-2 |
| BR-M3-003 — Section Metadata Management | US-M3-003-1, US-M3-003-2, US-M3-003-3, US-M3-003-4 | FR-M3-003-1, FR-M3-003-2, FR-M3-003-3, FR-M3-003-4, FR-M3-003-5, FR-M3-003-6, FR-M3-003-7 | BE-M3-003-1, BE-M3-003-2, BE-M3-003-3, BE-M3-003-4 |
| BR-M3-004 — Section Linkage Management | US-M3-004-1, US-M3-004-2, US-M3-004-3, US-M3-004-4 | FR-M3-004-1, FR-M3-004-2, FR-M3-004-3, FR-M3-004-4, FR-M3-004-5 | BE-M3-004-1, BE-M3-004-2, BE-M3-004-3, BE-M3-004-4 |
| BR-M3-005 — Card-Level Editing | US-M3-005-1, US-M3-005-2, US-M3-005-3, US-M3-005-4 | FR-M3-005-1, FR-M3-005-2, FR-M3-005-3, FR-M3-005-4, FR-M3-005-5 | BE-M3-005-1, BE-M3-005-2, BE-M3-005-3, BE-M3-005-4 |
| BR-M3-006 — Card AI Assistance | US-M3-006-1, US-M3-006-2, US-M3-006-3, US-M3-006-4 | FR-M3-006-1, FR-M3-006-2, FR-M3-006-3, FR-M3-006-4 | BE-M3-006-1, BE-M3-006-2, BE-M3-006-3, BE-M3-006-4 |
| BR-M3-007 — Template Application | US-M3-007-1, US-M3-007-2, US-M3-007-3 | FR-M3-007-1, FR-M3-007-2, FR-M3-007-3, FR-M3-007-4 | BE-M3-007-1, BE-M3-007-2, BE-M3-007-3, BE-M3-007-4 |
| BR-M3-008 — Prompt Confidence Threshold | US-M3-008-1, US-M3-008-2, US-M3-008-3 | FR-M3-008-1, FR-M3-008-2, FR-M3-008-3, FR-M3-008-4 | BE-M3-008-1, BE-M3-008-2, BE-M3-008-3, BE-M3-008-4 |
| BR-M3-009 — Global Tweak and Demo Controls | US-M3-009-1, US-M3-009-2, US-M3-009-3, US-M3-009-4 | FR-M3-009-1, FR-M3-009-2, FR-M3-009-3, FR-M3-009-4 | BE-M3-009-1, BE-M3-009-2, BE-M3-009-3 |
