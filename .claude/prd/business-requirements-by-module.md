# SpecForge Business Requirements by Module

This catalogue converts the reverse-engineered prototype into explicit, testable business requirements. IDs are grouped by module and are intended to be traceable into functional specifications, design, test scenarios, and test cases.

Requirement priority scale:
- Must: required for production launch.
- Should: important for enterprise adoption but can be sequenced after launch if needed.
- Could: valuable enhancement.

## Module 0: Global System Architecture

### Module Purpose
Module 0 defines SpecForge as a secure, governed, single-page enterprise workbench. It is responsible for the application shell, navigation model, global route state, project/document/app context, design system, version history access, auditability, and role-based access. Without this module, the rest of SpecForge would be a set of disconnected screens rather than a coherent SDLC platform.

The business need is to give users one stable place to manage complex delivery artefacts. A BA should be able to move from portfolio to project to BRD to review to traceability without losing context. A reviewer should understand exactly which project, document, version, and section they are looking at. An auditor should be able to reconstruct how an artefact changed over time and which AI or human actions produced it.

### Business Capabilities Delivered
- Unified SDLC workbench shell.
- Persistent project/document/application context.
- Sidebar and breadcrumb navigation.
- 10-stage SDLC visibility.
- Cross-document version history.
- Enterprise visual language for AI, stale, approved, warning, and review states.
- Governed audit and access-control foundation.

### Key Business Objects
- Active project.
- Active route/view.
- SDLC stage.
- Document key.
- Review context.
- Application key.
- Version panel context.
- User identity and role.
- Design/theme tokens.

### BR-M0-001 - Single-Page Workbench Shell
Priority: Must

Requirement:
SpecForge shall provide a single-page workbench shell that coordinates portfolio, project, document, review, traceability, app registry, and app brain views without requiring a full page reload.

Acceptance Criteria:
- The system supports route states for dashboard, project workspace, requirement understanding, BRD, targeted review, stale impact, traceability matrix, generic document stages, app registry, and app brain detail.
- Users can navigate between primary views through sidebar, topbar breadcrumbs, quick links, and in-context buttons.
- Unknown or unauthorized routes resolve to a safe fallback or access-denied state.
- Route changes preserve the active project context unless the user explicitly switches projects.

### BR-M0-002 - Global Project and Document Context
Priority: Must

Requirement:
SpecForge shall maintain global context for the active project, active SDLC stage, active review document, active application brain, and active version panel.

Acceptance Criteria:
- The active project ID is available to all project, document, review, trace, and export workflows.
- The active document key is available to version history, review, trace, and section editing workflows.
- Review context includes document key, display label, and return route.
- Application context includes app key and app-brain details where the app is onboarded.

### BR-M0-003 - Persistent Navigation Chrome
Priority: Must

Requirement:
SpecForge shall display persistent sidebar and topbar navigation across all primary views to orient users within workspace, current project, SDLC stages, and organisation library.

Acceptance Criteria:
- Sidebar displays workspace links, current project link, 10-stage document progress, org library links, and current user identity.
- Sidebar stage rows display status, sequence number, active indicator, stale/review/current markers, and progress segment bar.
- Topbar breadcrumbs reflect the active route and allow navigation to dashboard, project workspace, app registry, and parent documents where applicable.
- Topbar exposes global search, notifications, settings, and New project entry points.

### BR-M0-004 - Responsive Design Scaling
Priority: Should

Requirement:
SpecForge shall preserve the enterprise desktop workbench layout by scaling the 1440px design canvas down for narrower browser widths.

Acceptance Criteria:
- The application fits within the viewport without horizontal layout breakage at supported desktop widths.
- The scaled app still fills viewport height.
- The scaling behavior recalculates on browser resize.
- Production accessibility documentation defines minimum supported viewport and browser zoom expectations.

### BR-M0-005 - Design Token Governance
Priority: Must

Requirement:
SpecForge shall use a centralized design-token system for colors, typography, spacing, shadows, status semantics, and component states.

Acceptance Criteria:
- All primary UI surfaces use shared tokens for background, canvas, surfaces, borders, text, status, AI, and app-brain colors.
- Status indicators use semantic styling for approved, edited, AI-generated, stale, warning, danger, info, and success states.
- Document AI output is visually distinct from human-edited content.
- App-brain grounding uses a distinct visual style from document-local content.

### BR-M0-006 - Global Version History Access
Priority: Must

Requirement:
SpecForge shall allow users to open version history for any generated or managed document from a consistent version chip or history button.

Acceptance Criteria:
- Version history can be opened for BRD, FS, NFR, Requirement Understanding, Traceability Matrix, and any future document module.
- Version history displays timeline, actor, timestamp, change note, changed sections, change count, generation type, and current marker.
- Users can preview and compare non-current versions.
- Immutable snapshots cannot be restored.

### BR-M0-007 - Global Auditability
Priority: Must

Requirement:
SpecForge shall audit all material user and AI actions that affect generated content, review status, assumptions, traceability, app-brain facts, or exports.

Acceptance Criteria:
- Audit events include actor, timestamp, project, document/app, action, source version, target version, and affected sections.
- AI audit events include skill version, model, prompt template version, source references, and output decision state.
- Restore, promotion, regeneration, approval, rejection, and export actions are audit logged.
- Audit records are immutable to non-admin users.

### BR-M0-008 - Role-Based Access Control
Priority: Must

Requirement:
SpecForge shall enforce role-based access to projects, documents, sources, app brains, settings, and exports.

Acceptance Criteria:
- Users only see projects and apps they are authorized to access.
- Restricted source documents are not retrievable through search, citations, export, or AI answers by unauthorized users.
- Only assigned reviewers or authorized approvers can approve review items and documents.
- Only app owners or delegated maintainers can merge app-brain proposals.

## Module 1: Dashboard & Project Hub

### Module Purpose
Module 1 covers the front door of the SpecForge workflow. It helps users find work, start new work, reuse existing organisational knowledge, select app context, ingest sources, and validate initial understanding. This module is where a vague business initiative becomes a structured, traceable SpecForge project.

The dashboard solves the portfolio-management problem: users need to know what projects exist, which projects they own, what needs review, what is stale, and what is high priority. The project wizard solves the intake problem: business changes usually arrive as documents, notes, or rough descriptions. SpecForge uses similar-project discovery, app-brain context, and source ingestion to reduce manual setup and avoid starting from a blank page.

The project workspace then becomes the command center for a single project. It shows stage progress, next action, sources, quality, open questions, assumptions, apps in scope, recent activity, and skill versions. It is intentionally broader than a document editor because enterprise SDLC work is not just writing documents; it is coordinating evidence, decisions, dependencies, approvals, and system knowledge.

### Business Capabilities Delivered
- Portfolio search and filtering.
- Portfolio triage and insight metrics.
- New project creation.
- Similar project discovery.
- Reuse by reference.
- App-in-scope selection.
- Source document intake.
- Adaptive requirement understanding.
- Project-level stage map.
- Project quality and governance panels.
- Project-to-app-brain linkage.

### Key Business Objects
- Project portfolio record.
- Saved view.
- Similar project candidate.
- Reusable artefact selection.
- Source file.
- App in scope.
- Requirement understanding.
- Quality score.
- Open question.
- Assumption.
- Project activity event.

### BR-M1-001 - Portfolio Project Search
Priority: Must

Requirement:
SpecForge shall allow users to search portfolio projects by project name, project ID, business unit, and owner.

Acceptance Criteria:
- Search is case-insensitive.
- Search applies to the current saved-view filter.
- Empty search returns the saved-view result set.
- Users can clear the search query in one action.

### BR-M1-002 - Portfolio Saved Views
Priority: Must

Requirement:
SpecForge shall provide saved portfolio views for all projects, projects owned by the user, projects needing review, stale projects, high-priority projects, and finalized projects.

Acceptance Criteria:
- Each saved view displays a count.
- Selecting a saved view updates the project result set.
- Saved view selection persists during table/board toggling.
- Counts respect the current user’s access permissions.

### BR-M1-003 - Table and Board Portfolio Modes
Priority: Should

Requirement:
SpecForge shall support table and board visualization modes for the project portfolio.

Acceptance Criteria:
- Table mode displays ID, project, business unit, stage, completion, reviews, priority, owner, status, updated, and go-live.
- Board mode groups visible projects by SDLC stage categories.
- Users can switch modes without losing filters or search query.
- Current project cards/rows can be opened directly.

### BR-M1-004 - Grouped Portfolio Table
Priority: Should

Requirement:
SpecForge shall allow users to group the portfolio table by business unit, stage, owner, or status.

Acceptance Criteria:
- Group headers show group name and project count.
- Group headers can be expanded and collapsed.
- Group headers summarize stale, review, and finalized counts where applicable.
- Grouping can be reset to none.

### BR-M1-005 - Portfolio Insights Triage
Priority: Must

Requirement:
SpecForge shall surface a prioritized triage panel showing the most important portfolio actions requiring the user’s attention.

Acceptance Criteria:
- Triage includes stale impact, review items, approval tasks, and low-confidence/open assumption signals.
- Each actionable triage item links to the relevant project, review queue, impact screen, or ledger.
- Triage indicates freshness or next recomputation time.
- Triage results are personalized to the current user.

### BR-M1-006 - Project Creation Intake
Priority: Must

Requirement:
SpecForge shall provide a guided project creation wizard that captures project identity, business unit, application, description, similar project reuse, apps in scope, and source documents.

Acceptance Criteria:
- Required fields include project name, business unit, application or app-scope selection, and description.
- The wizard shows a clear step indicator.
- Users can move forward and backward between steps.
- Cancel closes the wizard without creating a project.
- Generate understanding creates a new project intake package and routes to adaptive interview.

### BR-M1-007 - Similar Project Discovery and Reuse
Priority: Must

Requirement:
SpecForge shall identify similar past projects and allow users to reuse selected templates, requirements, NFR sections, and glossary assets by reference.

Acceptance Criteria:
- Similar projects show match percentage, business unit, finalized date, and reusable asset tags.
- Users can select or deselect a similar project.
- Users can toggle reusable asset categories independently.
- Reused content retains provenance to the source project.

### BR-M1-008 - Apps in Scope Selection
Priority: Must

Requirement:
SpecForge shall allow users to confirm applications in scope for a project and load those app AI Brains as context for downstream generation.

Acceptance Criteria:
- The wizard displays all onboarded applications with tier, facts, corpus, version, and owner.
- AI-suggested apps are preselected and visually marked.
- Users can include or exclude each app.
- The system displays how many apps are selected.
- If no apps are selected, the system warns that the interview will start from scratch.

### BR-M1-009 - Source Document Intake
Priority: Must

Requirement:
SpecForge shall allow users to add source documents during project creation and show indexing/PII status before generation.

Acceptance Criteria:
- Supported file types include DOCX, PDF, XLSX, MD, PPTX, and TXT.
- Each source row shows file name, size, extraction state, and indexing state.
- PII detection is surfaced before generation.
- Users can remove a source before launching generation.

### BR-M1-010 - Project Workspace Stage Map
Priority: Must

Requirement:
SpecForge shall provide a project workspace stage map showing all 10 SDLC stages, status, progress, stale signals, and navigation.

Acceptance Criteria:
- The stage map lists Requirement Understanding, BRD, FS, NFR, ADR, TBP, SDD, TS, TC, and Traceability Matrix.
- Each stage displays progress percentage and status.
- Clicking a stage routes to the appropriate document or screen.
- Stale and review statuses are visually distinct.

### BR-M1-011 - Project Workspace Operational Panels
Priority: Must

Requirement:
SpecForge shall display project-level sources, quality scores, open questions, assumption ledger, recent activity, skill versions, and quick links.

Acceptance Criteria:
- Sources panel shows source type, page count, date added, and PII tag.
- Quality panel shows completeness, clarity, traceability, risk coverage, consistency, and NFR coverage.
- Open questions show ID, section, due date, assignee, and question text.
- Assumptions show ID, text, confidence, source, and status.
- Recent activity distinguishes AI and human events.
- Quick links route to BRD, review, stale impact, trace, interview, and app brain.

### BR-M1-012 - Adaptive Requirement Understanding
Priority: Must

Requirement:
SpecForge shall generate a structured Requirement Understanding from indexed sources and app-brain context, then ask only unresolved questions before downstream document generation.

Acceptance Criteria:
- The interview displays AI, user, question, and structured understanding messages.
- The system shows source references for inferred claims.
- The understanding includes objective, stakeholders, pain points, target process, functional areas, systems, integrations, roles, assumptions, open questions, and risks.
- The system shows confidence/completeness by understanding field.
- Downstream document generation is blocked until the user validates the understanding.

## Module 2: SDLC Document Workbench

### Module Purpose
Module 2 is the core production engine of SpecForge. It turns validated requirement understanding into structured SDLC artefacts and keeps those artefacts consistent over time. It covers the BRD editor, right-side intelligence panels, targeted review, stale impact, traceability matrix, Functional Specification, Non-Functional Specification, and pending downstream modules.

The business need is not simply “generate a BRD.” Enterprise delivery requires a chain of artefacts that must stay aligned. A BRD describes business intent. A Functional Specification turns that intent into system behavior. An NFR document defines measurable quality targets. Architecture and build permits rely on approved upstream artefacts. Test scenarios and test cases must prove the requirements. SpecForge models this lifecycle as a dependency graph so changes can be controlled instead of silently drifting across documents.

This module also defines the human-in-the-loop governance model. AI may draft, improve, cite, check, and suggest, but the user validates understanding, accepts suggestions, resolves assumptions, reviews targeted issues, and submits documents for approval. The system must make AI assistance visible and auditable rather than invisible prose generation.

### Business Capabilities Delivered
- BRD section rendering and editing.
- Requirement card management.
- Citation and assumption inspection.
- App-brain grounding.
- AI section actions.
- Ask-the-document.
- Quality scoring.
- Assumption and open-question management.
- Targeted review queues.
- Stale impact graph.
- Section-scoped regeneration.
- Traceability matrix and gap management.
- FS and NFR generation.
- Downstream document gating.

### Key Business Objects
- Document module.
- Document section.
- Requirement card.
- Citation/source span.
- AI assumption.
- Open question.
- Review item.
- Stale impact item.
- Trace row.
- Functional requirement.
- Non-functional requirement.
- Version snapshot.
- AI action.

### BR-M2-001 - BRD Document Editing
Priority: Must

Requirement:
SpecForge shall provide a BRD editor that renders structured sections, generated content, human edits, requirement cards, citations, assumptions, traceability links, and app-brain grounding.

Acceptance Criteria:
- Sections display status as approved, edited, AI-generated, or stale.
- AI-generated sections display confidence percentage.
- Edited sections display section version and edit time.
- Requirement cards can expand and collapse.
- Citations and assumption chips are clickable.
- App-brain grounding is visible for sections that use app facts.

### BR-M2-002 - BRD Section Toolbar
Priority: Must

Requirement:
Each BRD section shall expose controls for edit, regenerate, improve wording, comment, section history, and additional section actions.

Acceptance Criteria:
- Edit opens the shared Section Editor with current section content.
- Regenerate starts section-specific generation.
- Improve wording creates an inline AI suggestion.
- Comment opens a section comment composer.
- Section history opens version history scoped to the document/section.
- More menu includes edit metadata, mark approved, lock, copy link, export, and delete actions.

### BR-M2-003 - Citation Source Popover
Priority: Must

Requirement:
SpecForge shall allow users to inspect the source behind every citation or AI assumption marker.

Acceptance Criteria:
- Clicking a citation opens a popover near the clicked chip.
- The popover displays source name, location, quote or assumption text, and reference ID.
- The popover provides actions to open source and copy reference.
- The popover closes on outside click.

### BR-M2-004 - Trace Path Popover
Priority: Must

Requirement:
SpecForge shall show the forward trace chain for business and functional requirements inline from document chips.

Acceptance Criteria:
- Trace chips display counts for FR, design, and test coverage.
- Missing links are marked as gaps.
- Clicking a trace chip opens a popover showing BR -> FR -> Design -> Test.
- Popover actions allow users to open the traceability matrix and related documents.

### BR-M2-005 - AI-Assisted Section Actions
Priority: Must

Requirement:
SpecForge shall support AI-assisted actions for regenerating, improving, expanding, simplifying, strengthening citations, and finding contradictions for focused sections.

Acceptance Criteria:
- Regeneration streams progress and preserves manual edits outside the target section.
- Inline suggestions show running and ready states.
- Users can accept replacement, insert alongside, or reject suggestions.
- Citation checks identify missing or weak citations.
- Contradiction checks can route users to targeted review.

### BR-M2-006 - Document Quality Panel
Priority: Must

Requirement:
SpecForge shall calculate and display document quality across completeness, clarity, traceability, risk coverage, consistency, and NFR coverage.

Acceptance Criteria:
- Overall score is displayed out of 100.
- Each subscore is displayed with a progress bar.
- Findings are grouped by severity.
- Cross-document checks identify BRD/FS, FS/test, BRD/NFR, and glossary consistency results.

### BR-M2-007 - Assumption Ledger
Priority: Must

Requirement:
SpecForge shall maintain an assumption ledger for every AI-introduced or inferred assumption.

Acceptance Criteria:
- Each assumption includes ID, text, confidence, source, section, and status.
- Users can filter all/open/accepted assumptions.
- Users can accept, reject, or ask the owner about open assumptions.
- Accepted assumptions are visibly distinguished.
- The ledger can be exported.

### BR-M2-008 - Open Question Management
Priority: Must

Requirement:
SpecForge shall maintain assignable open questions that merge back into relevant document sections with provenance when resolved.

Acceptance Criteria:
- Each question includes ID, text, section, assignee, due date, and status.
- Users can reassign, resolve, and add questions.
- Assigned and open statuses are visually distinct.
- Resolved questions produce traceable document updates.

### BR-M2-009 - Gated Submission for Approval
Priority: Must

Requirement:
SpecForge shall prevent document submission for approval while required review items remain unresolved.

Acceptance Criteria:
- Submit for approval is disabled when open review item count is greater than zero.
- Review button displays unresolved count.
- Tooltip explains why submission is disabled.
- Once required review items are resolved, submission becomes available for authorized users.

### BR-M2-010 - Targeted Review
Priority: Must

Requirement:
SpecForge shall provide document-specific targeted review queues for changed, new, low-confidence, open-question, and contradiction items.

Acceptance Criteria:
- Review queues can be filtered by item kind.
- Each item shows section, title, source, severity, and supporting text/diff.
- Users can resolve individual items.
- Center pane shows focused before/after or recommendation detail.
- Right rail shows reviewers, statuses, comments, and reply input.

### BR-M2-011 - Stale Impact Analysis
Priority: Must

Requirement:
SpecForge shall detect upstream document changes and identify downstream documents and sections invalidated by the change.

Acceptance Criteria:
- Stale impact view shows upstream change, changed section, actor, and timestamp.
- Dependency graph shows affected documents and pending downstream stages.
- Impact cards show affected document, section, severity, stale reason, current text, and proposed regenerated text.
- Users can regenerate only affected sections.
- Finalization of stale downstream documents is blocked until invalidation is resolved or explicitly accepted.

### BR-M2-012 - Section-Scoped Regeneration
Priority: Must

Requirement:
SpecForge shall regenerate only impacted sections when resolving stale downstream impact and preserve unrelated manual edits.

Acceptance Criteria:
- Regeneration progress is displayed.
- Completed regeneration marks affected impact cards as regenerated.
- Manual edits outside affected sections are preserved.
- Trace annotations are updated when regenerated text changes links.
- Regeneration creates version and audit records.

### BR-M2-013 - Traceability Matrix
Priority: Must

Requirement:
SpecForge shall maintain an auto-generated traceability matrix from BRs to FRs, design sections, test cases, and NFRs.

Acceptance Criteria:
- Matrix displays BR, statement, linked FRs, linked design sections, linked test cases, and status.
- Coverage strip displays counts and gaps for BRs, FRs, design sections, and test cases.
- Users can filter all, gaps, and complete rows.
- Selecting a BR updates the detail card and gap rail context.
- Matrix rebuild metadata is displayed.

### BR-M2-014 - Trace Gap Resolution
Priority: Must

Requirement:
SpecForge shall identify trace gaps and allow users to generate or ignore missing downstream artefacts.

Acceptance Criteria:
- Gaps identify missing FR, design section, or test case.
- Gap cards show BR, statement, and gap note.
- Generate missing action drafts the missing artefact from upstream content.
- Ignored gaps require a reason in production.
- Gap decisions are audit logged.

### BR-M2-015 - Functional Specification Generation
Priority: Must

Requirement:
SpecForge shall generate a Functional Specification from the approved BRD with traceable functional requirements, roles, process behavior, data, integrations, exception handling, and audit behavior.

Acceptance Criteria:
- Each FR has unique ID, upstream BR, description, preconditions, behavior, outputs, errors, acceptance criteria, dependencies, and NFR coupling.
- FS detects contradictions with current BRD values.
- FR cards expose upstream trace chips.
- Missing test coverage is propagated to the traceability matrix.

### BR-M2-016 - Non-Functional Specification Generation
Priority: Must

Requirement:
SpecForge shall generate measurable NFRs from BRD, FS, app-brain constraints, and group standards.

Acceptance Criteria:
- Each NFR includes ID, category, description, targets, measurement method, constrained FRs, and release gate.
- Performance, availability, throughput, auditability, privacy, security, observability, DR, and accessibility are supported.
- Stale sizing is detected when upstream scope changes.
- NFR failures can be marked release blockers.

### BR-M2-017 - Downstream Pending Gates
Priority: Must

Requirement:
SpecForge shall block ADR, TBP, SDD, TS, and TC generation until required upstream documents are approved.

Acceptance Criteria:
- Pending screens show required upstream documents.
- Pending screens display planned sections, purpose, validators, and estimated generation time.
- Users can open upstream documents from the pending state.
- Users can subscribe for notification when upstream dependencies are approved.

## Module 3: Template & Prompt Engineer Workspace

### Module Purpose
Module 3 provides the reusable editing and prompt-control layer underneath the document workbench. It is the part of SpecForge that makes sections, requirement cards, templates, metadata, linkages, confidence thresholds, and AI actions manageable across document types.

In a production system, this module is important because enterprise documents need standard structures. Teams need consistent section numbering, reusable templates, explicit owners, approvers, locks, citations, downstream links, and requirement-card schemas. Prompt engineers and platform administrators also need a place to govern how AI actions behave: what inputs are injected, what templates are used, what confidence thresholds apply, and how outputs are recorded.

This module ensures SpecForge is not just a set of hard-coded screens. It points toward a configurable document-generation platform where new document types, section templates, and AI actions can be added without rebuilding the whole product.

### Business Capabilities Delivered
- Shared section editor.
- Add/edit modes.
- Section numbering and renumbering.
- Section metadata governance.
- Section locking.
- Upstream and downstream linkage management.
- Requirement card editing.
- Acceptance criteria editing.
- Template selection.
- Prompt action controls.
- Confidence threshold controls.
- Restricted prototype/demo tweak controls.

### Key Business Objects
- Section draft.
- Section metadata.
- Section template.
- Rendering kind.
- Linked source span.
- Linked requirement.
- Downstream dependency.
- Requirement card.
- Acceptance criterion.
- Prompt action.
- Confidence threshold.

### BR-M3-001 - Shared Section Editor
Priority: Must

Requirement:
SpecForge shall provide a shared Section Editor for editing and adding sections across all managed documents.

Acceptance Criteria:
- Editor supports Content, Metadata, and Linkages tabs.
- Editor supports edit and add modes.
- Save increments section version and document version.
- Add mode can append or insert between sections.
- Insert between sections displays downstream renumbering preview.

### BR-M3-002 - Section Rendering Mode Selection
Priority: Must

Requirement:
Users shall be able to select section rendering style as prose, bulleted, table, requirement cards, or process flow.

Acceptance Criteria:
- Section kind is displayed as selectable controls.
- Selected kind is stored on the draft section.
- Requirement-card sections show intro text plus individual card rows.
- Production rendering honors the selected kind consistently in editor, export, and version preview.

### BR-M3-003 - Section Metadata Management
Priority: Must

Requirement:
SpecForge shall allow users to manage section number, status, lock state, owner, approvers, and skill metadata.

Acceptance Criteria:
- Section number can be edited.
- Status values include Draft, AI draft, In review, and Approved.
- Section lock prevents AI modification while allowing authorized manual edits.
- Owner can be selected.
- Approvers can be added and removed.
- Skill version and model are recorded for AI-assisted edits.

### BR-M3-004 - Section Linkage Management
Priority: Must

Requirement:
SpecForge shall allow users to link sections to upstream source spans, requirements, and downstream dependent sections.

Acceptance Criteria:
- Users can add and remove source citations.
- Users can add and remove linked BR/FR/NFR references.
- Users can declare downstream dependency links with severity and reason.
- Saving a section with downstream links schedules a staleness check.
- Linkages are additive to automatically discovered links.

### BR-M3-005 - Card-Level Editing
Priority: Must

Requirement:
SpecForge shall allow users to edit requirement cards embedded in document sections.

Acceptance Criteria:
- Users can edit requirement ID, title, description, acceptance criteria, rationale, priority, owner, and source citation.
- Users can add and remove acceptance criteria.
- At least one acceptance criterion is retained.
- New card IDs are suggested based on existing card prefix and highest numeric suffix.
- Saving card changes notifies the parent section editor.

### BR-M3-006 - Card AI Assistance
Priority: Should

Requirement:
SpecForge shall provide AI assistance for generating acceptance criteria, improving requirement wording, and finding conflicts with other requirements.

Acceptance Criteria:
- AI actions are visible in the Card Editor.
- Generated acceptance criteria are testable and objective.
- Conflict checks compare sibling requirements, assumptions, and trace links.
- AI changes require user save/acceptance before becoming authoritative.

### BR-M3-007 - Template Application
Priority: Should

Requirement:
SpecForge shall allow users to apply approved section templates to section drafts.

Acceptance Criteria:
- Template options include group-standard scope, business rules, assumptions, and open questions templates.
- Template application records template ID and version.
- Template compatibility is validated against document type and section kind.
- Applying a template does not remove existing content without confirmation.

### BR-M3-008 - Prompt Confidence Threshold
Priority: Should

Requirement:
SpecForge shall allow users or administrators to configure a confidence threshold for AI drafting actions.

Acceptance Criteria:
- Confidence threshold is adjustable from 0 to 100.
- Default threshold is conservative at 80.
- Lower thresholds allow more aggressive drafting but mark outputs with lower confidence.
- Threshold used for generation is stored in AI audit metadata.

### BR-M3-009 - Global Tweak and Demo Controls
Priority: Could

Requirement:
SpecForge shall provide restricted design/demo controls for changing accent color and jumping to representative screens.

Acceptance Criteria:
- Tweak panel can be opened and closed through host edit mode.
- Accent color changes update the runtime CSS variable.
- Jump buttons route to Dashboard, New project, Interview, BRD, Review, Stale, Trace, and Workspace.
- Tweak controls are restricted to prototype/demo/admin contexts in production.

## Module 4: Integrations, Configurations & AI Brains

### Module Purpose
Module 4 connects SpecForge’s project-level documentation to organisation-level system knowledge. Its central concept is the Application AI Brain: a governed knowledge base for each enterprise application. In the prototype, PayHub is the fully detailed example, while MyAccount, PolicyHub, AML Screen, GNS, and other apps appear in the registry.

The business problem is repeated rediscovery. Delivery teams repeatedly ask: Does PayHub support AMEX? What is the transaction limit? Is `/capture` safe to retry? What are the PCI-DSS constraints? Which apps are downstream? In many organisations, those answers live in scattered PDFs, runbooks, ADRs, tribal knowledge, and previous project documents. App AI Brains convert that knowledge into source-grounded, owner-governed facts that can be injected into project documents.

This module also closes the learning loop. When a project discovers or confirms a reusable fact, SpecForge does not bury that learning in a finished BRD. It proposes the fact back to the relevant app owner. If the owner merges it, future projects inherit it. This is how SpecForge becomes more valuable over time.

### Business Capabilities Delivered
- Application registry.
- App-brain detail pages.
- App corpus ingestion.
- App fact extraction.
- App constraints and gotchas.
- App integration mapping.
- App-specific skills.
- Ask-the-app-brain.
- Proposed app-brain updates.
- Promote learnings from project.
- LLM provider and skill configuration.
- Data security and PII governance.

### Key Business Objects
- Application registry record.
- App AI Brain.
- App fact.
- App constraint.
- App capability.
- App limitation/gotcha.
- App corpus document.
- App open question.
- App skill.
- Project touchpoint.
- Proposed update.
- App owner decision.
- Provider configuration.
- Security classification.

### BR-M4-001 - Application Registry
Priority: Must

Requirement:
SpecForge shall provide an Application Registry that lists onboarded enterprise applications and their AI Brain health signals.

Acceptance Criteria:
- Registry displays app name, short name, version, tier, environments, owner, facts, indexed docs, live projects, open questions, and proposed updates.
- Users can filter all apps, Tier 1 apps, apps with pending updates, and apps owned by the user.
- Users can search by app, owner, or area.
- Clicking an app opens its AI Brain detail when onboarded.

### BR-M4-002 - App Onboarding Queue
Priority: Should

Requirement:
SpecForge shall identify apps not yet onboarded and provide an onboarding queue for creating app-brain skeletons.

Acceptance Criteria:
- Registry footer displays count of app stubs still to onboard.
- Un-onboarded apps discovered in projects can be proposed as skeletons.
- Skeleton includes owner, capabilities, constraints, source corpus, and approval workflow.
- Onboarding queue is accessible to authorized administrators.

### BR-M4-003 - Application AI Brain Detail
Priority: Must

Requirement:
SpecForge shall provide an app-brain detail screen containing source-grounded app knowledge used by project document generation.

Acceptance Criteria:
- App brain displays overview, domain model, capabilities, constraints, integrations, corpus, open questions, skills, and projects touching.
- Each fact displays ID, text, source, confidence, and kind.
- Users can navigate app-brain sections from the left shelf.
- App-brain toolbar exposes history, export, and use-in-new-project actions.

### BR-M4-004 - App Brain Pipeline Transparency
Priority: Must

Requirement:
SpecForge shall show how each app brain was built through ingest, extract, and synthesize pipeline steps.

Acceptance Criteria:
- Ingest step shows document and page counts.
- Extract step shows extracted fact count and confidence distribution.
- Synthesize step shows capabilities, constraints, integrations, and proposal counts.
- Clicking a pipeline step jumps to relevant app-brain section.

### BR-M4-005 - App Brain Corpus Management
Priority: Must

Requirement:
App owners shall be able to manage the app-brain source corpus used for AI grounding.

Acceptance Criteria:
- Corpus section lists source name, kind, page count, indexed date, primary status, and view action.
- Users can add source documents for ingestion.
- Re-index corpus action is available.
- Source ingestion updates extracted facts and app-brain version history.

### BR-M4-006 - Ask the App Brain
Priority: Must

Requirement:
SpecForge shall allow users to ask natural-language questions about an app and receive source-grounded answers with citations.

Acceptance Criteria:
- Ask panel accepts typed queries and suggested queries.
- Answers stream while being generated.
- Completed answers show citations from app facts or source corpus.
- Low-confidence or unanswered queries can be converted into open questions.

### BR-M4-007 - App Brain Proposed Updates
Priority: Must

Requirement:
SpecForge shall surface project-derived proposed updates to app brains for owner review.

Acceptance Criteria:
- Proposed updates show kind, severity, target section, title, detail, originating project, and source document.
- App owners can merge, refine, or dismiss proposals.
- Merged proposals update the app brain and are visibly marked merged.
- Dismissed proposals remain audit-visible and do not update the app brain.

### BR-M4-008 - Promote Learnings from Project
Priority: Must

Requirement:
SpecForge shall allow users to promote generalizable project learnings to affected app owners after a document is locked or finalized.

Acceptance Criteria:
- Promote modal lists candidate learnings by app, target, kind, severity, title, detail, source document, novelty, and owner.
- Users can include/exclude each candidate.
- Users can refine candidate title and detail before sending.
- Confirm step groups included proposals by app owner.
- Done step confirms proposal count and provides follow-up links to affected app brains.

### BR-M4-009 - App-Brain Grounding in Documents
Priority: Must

Requirement:
SpecForge shall expose which app-brain facts grounded generated document sections.

Acceptance Criteria:
- BRD sections display app-brain grounding footer where applicable.
- Grounding footer lists app names, fact IDs, fact text, fact kind, and proposed status.
- Clicking app/fact chips opens the relevant app brain.
- Grounding count shows total facts and apps used.

### BR-M4-010 - LLM Provider and Skill Configuration
Priority: Must

Requirement:
SpecForge shall support enterprise configuration of LLM providers, model routing, skill versions, prompt templates, and credential policies.

Acceptance Criteria:
- Provider configuration includes provider, model IDs, endpoint, credential reference, allowed data classifications, and rate limits.
- Skill configuration includes skill name, version, owner, corpus, benchmark score, active status, and compatible document types.
- Prompt configuration includes template ID, version, output schema, citation policy, tool policy, and safety policy.
- Raw API keys are never exposed in client-side state.

### BR-M4-011 - Data Security and PII Governance
Priority: Must

Requirement:
SpecForge shall enforce data security controls for source ingestion, AI retrieval, app-brain facts, prompts, and exports.

Acceptance Criteria:
- PII detection runs during ingestion.
- PII and sensitive classifications restrict source visibility and AI retrieval.
- Export jobs apply redaction policies.
- AI calls are prevented from using restricted content when the user lacks clearance.
- Security decisions are audit logged.

## Module 5: Asset Compilation & Export

### Module Purpose
Module 5 covers how SpecForge content leaves the workbench as governed artefacts. Enterprise SDLC outputs often need to be shared with stakeholders, attached to approval workflows, stored in records systems, reviewed offline, sent to QA, or archived for audit. Export cannot be an afterthought because SpecForge content includes citations, assumptions, review state, AI provenance, source security, and version history.

The module also covers source compilation, version snapshots, trace and governance exports, standalone HTML packaging, JSON schema output, and export job management. Production exports must preserve meaning and control. A BRD export should not lose requirement-card structure. A trace export should not lose gap status. An assumption ledger export should not hide low-confidence assumptions. An app-brain export should not leak restricted source text.

### Business Capabilities Delivered
- Source corpus compilation.
- Full document export.
- Section export.
- Trace matrix export.
- App-brain export.
- Assumption ledger export.
- Version preview and compare.
- Non-destructive restore.
- Standalone package export.
- JSON schema export.
- Background export jobs.
- Redaction and access-controlled downloads.

### Key Business Objects
- Source document.
- Export request.
- Export job.
- Export artefact.
- Version snapshot.
- Trace export row.
- Ledger export row.
- App-brain export package.
- Redaction policy.
- Secure download link.

### BR-M5-001 - Document Export
Priority: Must

Requirement:
SpecForge shall allow users to export managed documents in approved enterprise formats.

Acceptance Criteria:
- Export supports full document scope.
- Export includes document title, project metadata, version, sections, requirement cards, citations, assumptions, and approval state.
- Export respects user permissions and redaction policies.
- Export creates an audit record.

### BR-M5-002 - Section Export
Priority: Should

Requirement:
SpecForge shall allow users to export individual document sections.

Acceptance Criteria:
- Section export is accessible from section more menu.
- Export includes section number, title, content, citations, linked requirements, version, and status.
- Export warns when the section is stale or has unresolved review items.
- Section export is audit logged.

### BR-M5-003 - Trace Matrix Export
Priority: Must

Requirement:
SpecForge shall allow users to export the Traceability Matrix to spreadsheet-compatible and machine-readable formats.

Acceptance Criteria:
- Export includes BR, statement, FRs, design sections, test cases, NFRs, status, gap notes, and rebuild metadata.
- Users can export all rows or current filter results.
- Excel export preserves gap highlighting.
- Exported trace data is consistent with latest trace rebuild.

### BR-M5-004 - App Brain Export
Priority: Should

Requirement:
SpecForge shall allow authorized users to export app-brain data.

Acceptance Criteria:
- Export includes overview, glossary, capabilities, limitations, constraints, integrations, corpus summary, open questions, skills, projects touching, and proposed updates.
- Export includes fact IDs, sources, confidence, proposed/merged status, and owner validation.
- Restricted source text is excluded unless explicitly authorized.
- Export is audit logged.

### BR-M5-005 - Assumption Ledger Export
Priority: Must

Requirement:
SpecForge shall allow users to export the assumption ledger for compliance and review.

Acceptance Criteria:
- Export includes assumption ID, text, confidence, source, section, status, owner/question link, and decision history.
- Export supports CSV/XLSX/JSON formats.
- Accepted, rejected, and open assumptions are distinguishable.
- Export respects data classification and access controls.

### BR-M5-006 - Version Snapshot Preview and Compare
Priority: Must

Requirement:
SpecForge shall allow users to preview and compare historical document versions before export or restore.

Acceptance Criteria:
- Preview shows a read-only version snapshot.
- Compare shows selected version against current version side-by-side.
- Diff additions and deletions are visually marked.
- Snapshot versions are marked immutable.

### BR-M5-007 - Non-Destructive Restore
Priority: Must

Requirement:
SpecForge shall allow authorized users to restore prior non-snapshot versions non-destructively by creating a new current version.

Acceptance Criteria:
- Restore confirmation explains the selected version, current version, and new version behavior.
- Current version is preserved in history.
- Restore creates a new version with restored content.
- Downstream staleness checks run after restore.
- Restore is audit logged.

### BR-M5-008 - Standalone HTML Packaging
Priority: Could

Requirement:
SpecForge shall support a standalone HTML prototype/package export for offline stakeholder review.

Acceptance Criteria:
- Standalone file includes required CSS, data, scripts, and assets.
- Package preserves runtime behavior of the source shell.
- External dependencies are pinned or embedded according to enterprise policy.
- Exported standalone packages exclude unauthorized source data and secrets.

### BR-M5-009 - JSON Schema Export
Priority: Should

Requirement:
SpecForge shall provide JSON schema exports for generated documents, traceability, review queues, app-brain facts, and assumption ledgers.

Acceptance Criteria:
- JSON export uses stable schema versions.
- Export includes IDs and relationships needed for downstream integration.
- Consumers can validate exports against published schemas.
- Schema changes are versioned and backward-compatible where possible.

### BR-M5-010 - Export Job Management
Priority: Should

Requirement:
SpecForge shall manage long-running exports as background jobs with status, notifications, and retry behavior.

Acceptance Criteria:
- Users receive export job status: queued, running, completed, failed.
- Completed exports provide secure download links.
- Failed exports show actionable error messages.
- Export links expire according to tenant policy.
- Export retries preserve original request parameters and audit chain.
