# PRD: Module 1 — Dashboard & Project Hub

> Part of the SpecForge detailed business-requirements PRD set. Sources: `.claude/prd/01-system-overview-and-business-context.md`, `.claude/prd/business-requirements-by-module.md`.

## 1. Introduction / Overview

Module 1 is the front door of SpecForge. It is where a delivery team finds existing work, starts new work, reuses prior organisational knowledge, selects the application context that should inform generation, ingests source evidence, and validates the system's initial understanding of a business change. This module is the bridge that turns a vague business initiative — typically arriving as a business case, workshop notes, a deck, or a rough description — into a structured, traceable SpecForge project that downstream modules can operate on.

The module has three connected surfaces. The **Dashboard / Portfolio** solves the portfolio-management problem: users need to see what projects exist, which they own, what needs review, what is stale, and what is high priority, without rereading everything. The **Project Creation Wizard** solves the intake problem: rather than starting from a blank form, SpecForge discovers similar past projects, recommends reusable assets, loads app AI Brain context, and ingests source documents so that setup is fast and grounded. The **Project Workspace** then becomes the command center for a single project, showing stage progress, the next action, sources, quality scores, open questions, assumptions, apps in scope, recent activity, and skill versions.

Module 1 is intentionally broader than a document editor because enterprise SDLC work is not just writing documents; it is coordinating evidence, decisions, dependencies, approvals, and system knowledge. The module culminates in **Adaptive Requirement Understanding**: SpecForge reads indexed sources plus app-brain facts, builds a structured interpretation of the problem, asks only the questions it cannot infer, and requires the user to validate that understanding before any downstream artefact is generated. This validation checkpoint is the governance gate that all of Module 2's generation depends on.

Because this is a real system to be built (not just a prototype), this PRD also specifies the backend and production capabilities Module 1 depends on: persistent project storage, real file upload with malware scanning, OCR/parsing/text-and-table extraction, embedding and similar-project search, PII detection, app-brain context loading, adaptive-interview LLM orchestration with provenance, and analytics computation for portfolio insights — all subject to the enterprise controls in section 8 of the overview (authentication, RBAC, source security, audit, secret management).

## 2. Goals

- Reduce time from project intake to a validated Requirement Understanding by eliminating blank-form setup through similar-project reuse, app-brain context, and source ingestion.
- Give every user a personalized, access-filtered portfolio view so they can locate any project by name, ID, business unit, or owner in a single search.
- Surface the highest-value portfolio actions (stale impact, pending reviews, approval tasks, low-confidence/open assumptions) in one prioritized triage panel so attention is directed correctly.
- Make project intake guided and reversible (multi-step wizard with forward/back navigation and cancel) so setup mistakes never create orphaned projects.
- Ensure all reused content, inferred claims, and ingested sources carry provenance from creation, so downstream traceability and audit are never broken at the source.
- Block all downstream document generation until a human validates the structured Requirement Understanding, enforcing the human-in-the-loop governance model.
- Provide a single project workspace that consolidates stage progress, sources, quality, questions, assumptions, app scope, activity, and skill versions so a project's health is understood at a glance.
- Enforce enterprise controls (RBAC, source security/PII classification, malware scanning, audit logging) on every Module 1 action that creates, ingests, or exposes content.

## 3. Scope

In scope (with priority):

- BR-M1-001 — Portfolio Project Search — Must
- BR-M1-002 — Portfolio Saved Views — Must
- BR-M1-003 — Table and Board Portfolio Modes — Should
- BR-M1-004 — Grouped Portfolio Table — Should
- BR-M1-005 — Portfolio Insights Triage — Must
- BR-M1-006 — Project Creation Intake — Must
- BR-M1-007 — Similar Project Discovery and Reuse — Must
- BR-M1-008 — Apps in Scope Selection — Must
- BR-M1-009 — Source Document Intake — Must
- BR-M1-010 — Project Workspace Stage Map — Must
- BR-M1-011 — Project Workspace Operational Panels — Must
- BR-M1-012 — Adaptive Requirement Understanding — Must

Priorities covered: Must (BR-M1-001, -002, -005, -006, -007, -008, -009, -010, -011, -012), Should (BR-M1-003, -004). No Could-priority requirements exist in Module 1.

## 4. Users & Roles

All seven SpecForge roles interact with Module 1, primarily through access-filtered views:

- **Business Analyst (BA)** — Primary operator. Creates projects via the wizard, performs similar-project reuse, confirms apps in scope, uploads sources, completes the adaptive interview, validates Requirement Understanding, and works from the project workspace. The "projects owned by me" saved view and most triage items target the BA.
- **Product Owner / Business Sponsor** — Uses the portfolio to see project status, completion, and priority; uses triage to find approval tasks and review items requiring business sign-off; opens the workspace to inspect scope, objectives, and quality.
- **Solution Architect** — Uses the portfolio and triage to find projects with stale downstream impact, FS/NFR review items, and design-readiness gates; opens the workspace stage map and quality panel to assess consistency and downstream impact.
- **App Owner** — Sees apps in scope linkage and project touchpoints from the workspace; appears as the owner/governor of app brains shown during apps-in-scope selection; triage may surface app-brain proposal items.
- **QA Lead** — Uses the portfolio (e.g., "needs review" view) and workspace quality panel (traceability/risk coverage) to spot coverage concerns early; navigates from the workspace to traceability.
- **Compliance / Risk Reviewer** — Relies on PII flags surfaced during source intake, source provenance, the assumption ledger panel, and audit trails; uses triage for low-confidence/open-assumption signals.
- **Platform Administrator / AI Engineer** — Configures source ingestion, providers, skills, access controls, and retention that Module 1 consumes; governs the skill versions shown in the workspace; ensures RBAC and audit policies apply across the module.

## 5. Key Business Objects

- **Project portfolio record** — A row/card representation of a project including ID, name, business unit, stage, completion, reviews, priority, owner, status, updated date, and go-live date.
- **Saved view** — A named, count-bearing portfolio filter (all, mine, needs review, stale, high priority, finalized) respecting the user's access permissions.
- **Similar project candidate** — A past project surfaced as a reuse source, with match percentage, business unit, finalized date, and reusable asset tags.
- **Reusable artefact selection** — A user's choice of which similar-project asset categories (templates, requirements, NFR sections, glossary) to reuse by reference, retaining provenance.
- **Source file** — An uploaded project document (DOCX, PDF, XLSX, MD, PPTX, TXT) with extraction state, indexing state, size, and PII status.
- **App in scope** — An onboarded application selected to provide app AI Brain context for downstream generation, with tier, facts, corpus, version, and owner.
- **Requirement understanding** — The validated structured interpretation of the business problem (objective, stakeholders, pain points, target process, functional areas, systems, integrations, roles, assumptions, open questions, risks) that must be approved before BRD generation.
- **Quality score** — Project-level subscores for completeness, clarity, traceability, risk coverage, consistency, and NFR coverage.
- **Open question** — An unresolved decision/missing fact with ID, section, due date, assignee, and question text.
- **Assumption** — An inferred claim with ID, text, confidence, source, and status.
- **Project activity event** — A timeline entry distinguishing AI and human actions on the project.

## 6. Detailed Business Requirements

### BR-M1-001 — Portfolio Project Search
**Priority:** Must

**Requirement:** SpecForge shall allow users to search portfolio projects by project name, project ID, business unit, and owner, with case-insensitive matching applied within the currently selected saved view and the ability to clear the query in one action.

**User Stories:**

#### US-M1-001-1: Search the portfolio by multiple fields
**As a** Business Analyst, **I want** to search my portfolio by project name, project ID, business unit, or owner **so that** I can locate a specific project quickly without scrolling.

**Acceptance Criteria:**
- [ ] A search input is available on the dashboard/portfolio surface.
- [ ] Typing a query matches against project name, project ID, business unit, and owner fields.
- [ ] Matching is case-insensitive (e.g., "payhub", "PayHub", "PAYHUB" return the same results).
- [ ] Search is applied only within the currently selected saved-view result set (it narrows, never broadens beyond the view).
- [ ] An empty search query returns the full result set of the currently selected saved view.
- [ ] Search results respect the current user's access permissions (no project the user cannot access is returned).
- [ ] Verify in browser using dev-browser skill.

#### US-M1-001-2: Clear the search in one action
**As a** Business Analyst, **I want** a single control to clear my search query **so that** I can return to the full saved-view list without manually deleting text.

**Acceptance Criteria:**
- [ ] A clear control (e.g., clear button) is visible whenever the search input is non-empty.
- [ ] Activating clear empties the query and immediately restores the current saved-view result set in one action.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M1-001-1: The system must provide a portfolio search input that filters the visible project list by name, ID, business unit, and owner.
- FR-M1-001-2: The system must perform case-insensitive matching on all searchable fields.
- FR-M1-001-3: The system must intersect search results with the active saved-view filter and not display projects outside that view.
- FR-M1-001-4: The system must return the active saved-view result set when the query is empty.
- FR-M1-001-5: The system must provide a one-action control to clear the search query.

**Backend / Production Requirements:**
- BE-M1-001-1: The portfolio query service must execute access-permission-filtered searches against the persistent project store so unauthorized projects are never returned (overview §8 RBAC, §9 persistent database).
- BE-M1-001-2: The search backend must support case-insensitive, partial-match queries across indexed name/ID/business-unit/owner fields with pagination for large portfolios.

### BR-M1-002 — Portfolio Saved Views
**Priority:** Must

**Requirement:** SpecForge shall provide saved portfolio views — all projects, projects owned by the user, projects needing review, stale projects, high-priority projects, and finalized projects — each with a permission-respecting count, where selecting a view updates the result set and selection persists across table/board toggling.

**User Stories:**

#### US-M1-002-1: Switch between saved portfolio views
**As a** Business Analyst, **I want** predefined saved views for all, mine, needs review, stale, high priority, and finalized projects **so that** I can triage my portfolio by the dimension I care about.

**Acceptance Criteria:**
- [ ] Saved views are available for: all projects, projects owned by the user, projects needing review, stale projects, high-priority projects, and finalized projects.
- [ ] Each saved view displays a count of matching projects.
- [ ] Selecting a saved view updates the displayed project result set to that view's projects.
- [ ] Each view's count and result set respect the current user's access permissions (counts never include inaccessible projects).
- [ ] Verify in browser using dev-browser skill.

#### US-M1-002-2: Preserve the selected view when toggling visualization
**As a** Business Analyst, **I want** my selected saved view to persist when I switch between table and board modes **so that** I do not lose my filtering context.

**Acceptance Criteria:**
- [ ] The selected saved view remains active when the user toggles between table and board visualization modes.
- [ ] The displayed counts and result set remain consistent with the selected view after toggling.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M1-002-1: The system must provide the six named saved views and display a count for each.
- FR-M1-002-2: The system must update the project result set when a saved view is selected.
- FR-M1-002-3: The system must persist the selected saved view across table/board mode toggling and across search clear.
- FR-M1-002-4: The system must compute counts and result sets using the current user's access permissions.

**Backend / Production Requirements:**
- BE-M1-002-1: The portfolio service must compute saved-view membership (mine/owner, needs-review, stale, high-priority, finalized) from persisted project state, review queues, stale-impact state, and priority fields (overview §9 persistent database, analytics).
- BE-M1-002-2: Saved-view counts must be derived server-side with RBAC filtering so counts cannot reveal the existence of inaccessible projects.

### BR-M1-003 — Table and Board Portfolio Modes
**Priority:** Should

**Requirement:** SpecForge shall support table and board visualization modes for the project portfolio, where table mode shows defined columns, board mode groups projects by SDLC stage categories, mode switching preserves filters and search query, and project cards/rows open directly.

**User Stories:**

#### US-M1-003-1: View the portfolio as a table
**As a** Product Owner, **I want** a table view with key project columns **so that** I can scan many projects and their status at once.

**Acceptance Criteria:**
- [ ] Table mode displays columns for: ID, project (name), business unit, stage, completion, reviews, priority, owner, status, updated, and go-live.
- [ ] Each table row represents one project the user is authorized to see.
- [ ] Clicking a table row opens that project directly (routes to its workspace).
- [ ] Verify in browser using dev-browser skill.

#### US-M1-003-2: View the portfolio as a board
**As a** Business Analyst, **I want** a board view grouping projects by SDLC stage category **so that** I can see where projects sit in the lifecycle.

**Acceptance Criteria:**
- [ ] Board mode groups the visible projects into columns/lanes by SDLC stage categories.
- [ ] Each board card represents one project and shows enough identity to recognize it.
- [ ] Clicking a board card opens that project directly (routes to its workspace).
- [ ] Verify in browser using dev-browser skill.

#### US-M1-003-3: Switch modes without losing context
**As a** Business Analyst, **I want** to switch between table and board without losing my filters or search query **so that** I keep my working context.

**Acceptance Criteria:**
- [ ] Switching from table to board (and back) preserves the active saved view, group-by selection, and search query.
- [ ] The set of visible projects is identical across modes for the same filters/search.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M1-003-1: The system must provide table and board visualization modes for the portfolio.
- FR-M1-003-2: The system must render the specified table columns (ID, project, business unit, stage, completion, reviews, priority, owner, status, updated, go-live).
- FR-M1-003-3: The system must group board mode by SDLC stage categories.
- FR-M1-003-4: The system must preserve active filters and search query when switching modes.
- FR-M1-003-5: The system must allow opening a project directly from a table row or board card.

**Backend / Production Requirements:**
- BE-M1-003-1: The portfolio service must return per-project fields needed for both modes (stage, completion %, open review count, priority, status, updated/go-live dates) from the persistent store in a single query to support fast mode switching.

### BR-M1-004 — Grouped Portfolio Table
**Priority:** Should

**Requirement:** SpecForge shall allow users to group the portfolio table by business unit, stage, owner, or status, with collapsible group headers that show group name and project count, summarize stale/review/finalized counts where applicable, and can be reset to no grouping.

**User Stories:**

#### US-M1-004-1: Group the portfolio table
**As a** Product Owner, **I want** to group the table by business unit, stage, owner, or status **so that** I can analyze the portfolio along the dimension I need.

**Acceptance Criteria:**
- [ ] The user can group the table by business unit, stage, owner, or status.
- [ ] Each group header shows the group name and the count of projects in that group.
- [ ] Group headers display summarized stale, review, and finalized counts for the group where applicable.
- [ ] Verify in browser using dev-browser skill.

#### US-M1-004-2: Expand, collapse, and reset grouping
**As a** Product Owner, **I want** to expand/collapse groups and reset grouping to none **so that** I can focus on relevant groups or return to a flat list.

**Acceptance Criteria:**
- [ ] Each group header can be expanded and collapsed to show/hide its rows.
- [ ] Grouping can be reset to "none," returning the table to an ungrouped flat list.
- [ ] Resetting grouping preserves the active saved view and search query.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M1-004-1: The system must support grouping the portfolio table by business unit, stage, owner, or status.
- FR-M1-004-2: The system must render group headers with group name and project count.
- FR-M1-004-3: The system must summarize stale, review, and finalized counts in group headers where applicable.
- FR-M1-004-4: The system must allow expanding/collapsing each group and resetting grouping to none.

**Backend / Production Requirements:**
- BE-M1-004-1: The portfolio service must support server-side aggregation of group counts and stale/review/finalized rollups so grouping scales to large portfolios without client-side full scans (overview §9 analytics computation).

### BR-M1-005 — Portfolio Insights Triage
**Priority:** Must

**Requirement:** SpecForge shall surface a prioritized, personalized triage panel showing the most important portfolio actions requiring the user's attention — stale impact, review items, approval tasks, and low-confidence/open-assumption signals — where each item links to the relevant destination and the panel indicates data freshness/next recomputation.

**User Stories:**

#### US-M1-005-1: See my prioritized portfolio actions
**As a** Business Analyst, **I want** a triage panel listing the most important actions needing my attention **so that** I know what to work on first without inspecting every project.

**Acceptance Criteria:**
- [ ] The triage panel surfaces, at minimum, stale-impact items, review items, approval tasks, and low-confidence/open-assumption signals.
- [ ] Triage items are prioritized (most important/actionable first).
- [ ] Triage results are personalized to the current user (only items relevant to that user, within their access).
- [ ] Verify in browser using dev-browser skill.

#### US-M1-005-2: Navigate from a triage item to its destination
**As a** Solution Architect, **I want** each triage item to link to the relevant project, review queue, impact screen, or ledger **so that** I can act on it in one click.

**Acceptance Criteria:**
- [ ] Each actionable triage item links to the relevant project, review queue, stale-impact screen, or assumption ledger as appropriate to the item kind.
- [ ] Activating a triage item navigates to its destination with correct project/document context.
- [ ] Verify in browser using dev-browser skill.

#### US-M1-005-3: Understand triage freshness
**As a** Business Analyst, **I want** the triage panel to show how fresh its data is and when it will next recompute **so that** I can trust whether it reflects recent changes.

**Acceptance Criteria:**
- [ ] The triage panel indicates data freshness (e.g., last computed time) or the next recomputation time.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M1-005-1: The system must display a prioritized triage panel covering stale impact, review items, approval tasks, and low-confidence/open-assumption signals.
- FR-M1-005-2: The system must link each actionable triage item to its relevant destination (project, review queue, impact screen, ledger).
- FR-M1-005-3: The system must indicate triage data freshness or next recomputation time.
- FR-M1-005-4: The system must personalize triage results to the current user and their access permissions.

**Backend / Production Requirements:**
- BE-M1-005-1: A portfolio analytics/triage service must compute per-user actionable items by aggregating stale-impact state, open review items, pending approval gates, and low-confidence/open assumptions across the user's accessible projects (overview §9 analytics computation, real notification/inbox workflows).
- BE-M1-005-2: Triage computation must be scheduled/recomputed on a defined cadence (and/or event-driven), recording last-computed and next-recompute timestamps for display.
- BE-M1-005-3: Triage queries must be RBAC-filtered so a user never sees items for projects they cannot access (overview §8).

### BR-M1-006 — Project Creation Intake
**Priority:** Must

**Requirement:** SpecForge shall provide a guided project-creation wizard that captures project identity, business unit, application/app-scope, description, similar-project reuse, apps in scope, and source documents, with a clear step indicator, forward/backward navigation, cancel that creates nothing, and a "generate understanding" action that creates an intake package and routes to the adaptive interview.

**User Stories:**

#### US-M1-006-1: Capture required project identity
**As a** Business Analyst, **I want** to enter project name, business unit, application/app-scope, and description in a guided wizard **so that** my project is created with the minimum required metadata.

**Acceptance Criteria:**
- [ ] The wizard requires project name, business unit, application or app-scope selection, and description before a project can be generated.
- [ ] The wizard validates that required fields are present and prevents proceeding to generation without them.
- [ ] Verify in browser using dev-browser skill.

#### US-M1-006-2: Navigate the wizard steps
**As a** Business Analyst, **I want** a clear step indicator and the ability to move forward and backward **so that** I can review and correct earlier inputs before generating.

**Acceptance Criteria:**
- [ ] The wizard displays a clear step indicator showing the current step and overall progress.
- [ ] The user can move forward to the next step and backward to a previous step.
- [ ] Moving backward preserves previously entered inputs (identity, reuse, apps, sources).
- [ ] Verify in browser using dev-browser skill.

#### US-M1-006-3: Cancel without creating a project
**As a** Business Analyst, **I want** to cancel the wizard at any point **so that** abandoning intake never leaves an orphaned project.

**Acceptance Criteria:**
- [ ] A cancel action closes the wizard without creating a project.
- [ ] After cancel, no new project appears in the portfolio and no uploaded sources persist against a project record.
- [ ] Verify in browser using dev-browser skill.

#### US-M1-006-4: Generate understanding and route to interview
**As a** Business Analyst, **I want** a "generate understanding" action **so that** my intake inputs become a project and I am taken to the adaptive interview.

**Acceptance Criteria:**
- [ ] "Generate understanding" creates a new project intake package from the captured identity, reuse selections, apps in scope, and sources.
- [ ] After creation, the user is routed to the adaptive interview (Requirement Understanding) for the new project.
- [ ] The newly created project appears in the portfolio (subject to access).
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M1-006-1: The system must provide a multi-step project-creation wizard capturing identity, business unit, application/app-scope, description, similar-project reuse, apps in scope, and source documents.
- FR-M1-006-2: The system must enforce required fields: project name, business unit, application/app-scope, and description.
- FR-M1-006-3: The system must display a step indicator and support forward/backward navigation that preserves entered inputs.
- FR-M1-006-4: The system must support cancel that closes the wizard and creates no project.
- FR-M1-006-5: The system must create a project intake package and route to the adaptive interview on "generate understanding."

**Backend / Production Requirements:**
- BE-M1-006-1: A persistent project store must create a project record with identity metadata, reuse references, selected apps, and associated source files atomically on "generate understanding" (overview §9 persistent database).
- BE-M1-006-2: Wizard-session state (including any uploaded files) must be held in a draft/staging state until creation; cancel must discard staged files and create no project record.
- BE-M1-006-3: Project creation must emit an immutable audit event capturing actor, timestamp, project, and intake inputs (overview §8 audit).
- BE-M1-006-4: The intake package must trigger downstream orchestration (source indexing readiness check, app-brain context loading, interview generation) without blocking the route to the interview.

### BR-M1-007 — Similar Project Discovery and Reuse
**Priority:** Must

**Requirement:** SpecForge shall identify similar past projects and allow users to reuse selected templates, requirements, NFR sections, and glossary assets by reference, where candidates show match percentage, business unit, finalized date, and reusable asset tags, selections are toggleable independently, and reused content retains provenance to the source project.

**User Stories:**

#### US-M1-007-1: Discover similar past projects
**As a** Business Analyst, **I want** SpecForge to show similar past projects with match details **so that** I can avoid starting from a blank page.

**Acceptance Criteria:**
- [ ] Each similar-project candidate displays a match percentage, business unit, finalized date, and reusable asset tags.
- [ ] Candidates are presented during project creation based on the entered identity/description and selected app scope.
- [ ] Only projects the user is authorized to reuse from are shown.
- [ ] Verify in browser using dev-browser skill.

#### US-M1-007-2: Select and configure reuse
**As a** Business Analyst, **I want** to select/deselect similar projects and independently toggle which asset categories to reuse **so that** I reuse only what is relevant.

**Acceptance Criteria:**
- [ ] The user can select or deselect each similar project.
- [ ] The user can independently toggle reusable asset categories (templates, requirements, NFR sections, glossary).
- [ ] Toggling one asset category does not change the state of other categories.
- [ ] Verify in browser using dev-browser skill.

#### US-M1-007-3: Preserve provenance of reused content
**As a** Compliance Reviewer, **I want** reused content to retain a link to its source project **so that** provenance and audit are preserved from the start.

**Acceptance Criteria:**
- [ ] Reused content retains provenance referencing the source project (and asset) it was reused from.
- [ ] Provenance is persisted with the new project so it is later visible in citations/trace/audit.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M1-007-1: The system must surface similar past projects with match percentage, business unit, finalized date, and reusable asset tags.
- FR-M1-007-2: The system must allow selecting/deselecting each similar project.
- FR-M1-007-3: The system must allow independent toggling of reusable asset categories (templates, requirements, NFR sections, glossary).
- FR-M1-007-4: The system must attach source-project provenance to all reused content.

**Backend / Production Requirements:**
- BE-M1-007-1: A similar-project discovery service must compute candidate matches using project embeddings/metadata similarity over the persistent project store and return a match score (overview §9 embeddings/persistent database).
- BE-M1-007-2: Reuse must be by reference, copying selected assets into the new project while persisting a provenance link (source project ID, asset ID/version) for traceability and audit.
- BE-M1-007-3: Similar-project candidates and reusable assets must be RBAC-filtered to the requesting user's authorized projects (overview §8).

### BR-M1-008 — Apps in Scope Selection
**Priority:** Must

**Requirement:** SpecForge shall allow users to confirm applications in scope for a project and load those app AI Brains as context for downstream generation, displaying all onboarded apps with tier/facts/corpus/version/owner, preselecting and marking AI-suggested apps, allowing include/exclude per app, showing the selected count, and warning when no apps are selected that the interview will start from scratch.

**User Stories:**

#### US-M1-008-1: Review onboarded applications
**As a** Business Analyst, **I want** to see all onboarded applications with their key health/context details **so that** I can decide which apps are in scope.

**Acceptance Criteria:**
- [ ] The wizard displays all onboarded applications.
- [ ] Each application shows tier, facts (count), corpus, version, and owner.
- [ ] Verify in browser using dev-browser skill.

#### US-M1-008-2: Confirm apps in scope with AI suggestions
**As a** Business Analyst, **I want** AI-suggested apps preselected and clearly marked, with the ability to include or exclude each **so that** I confirm the right context efficiently.

**Acceptance Criteria:**
- [ ] AI-suggested apps are preselected and visually marked as suggested.
- [ ] The user can include or exclude each application independently.
- [ ] The system displays how many apps are currently selected.
- [ ] Verify in browser using dev-browser skill.

#### US-M1-008-3: Be warned when no apps are selected
**As a** Business Analyst, **I want** a warning if I select no apps **so that** I understand the interview will start from scratch without app context.

**Acceptance Criteria:**
- [ ] If no apps are selected, the system displays a warning that the interview will start from scratch (without app-brain context).
- [ ] The user can still proceed after acknowledging the warning.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M1-008-1: The system must display all onboarded applications with tier, facts, corpus, version, and owner.
- FR-M1-008-2: The system must preselect and visually mark AI-suggested apps.
- FR-M1-008-3: The system must allow including/excluding each app independently and display the selected count.
- FR-M1-008-4: The system must warn when no apps are selected that the interview will start from scratch.
- FR-M1-008-5: The system must load the selected apps' AI Brains as context for downstream generation.

**Backend / Production Requirements:**
- BE-M1-008-1: An app-suggestion service must recommend likely-relevant apps from project identity/description/sources and onboarded app metadata, returning suggestion flags (overview §9 embeddings/RAG).
- BE-M1-008-2: On selection, the system must load the selected apps' AI Brain context (facts, constraints, glossary) for the project, respecting app-brain version and the user's clearance (overview §8 access controls, §9 RAG).
- BE-M1-008-3: Selected apps in scope must be persisted on the project record and used to establish project-to-app-brain linkage and project touchpoints.

### BR-M1-009 — Source Document Intake
**Priority:** Must

**Requirement:** SpecForge shall allow users to add source documents during project creation and show indexing/PII status before generation, supporting DOCX/PDF/XLSX/MD/PPTX/TXT, displaying file name/size/extraction state/indexing state per source, surfacing PII detection before generation, and allowing source removal before launching generation.

**User Stories:**

#### US-M1-009-1: Upload supported source documents
**As a** Business Analyst, **I want** to upload my business case, notes, specs, and spreadsheets **so that** SpecForge can ground its understanding in real evidence.

**Acceptance Criteria:**
- [ ] Supported file types include DOCX, PDF, XLSX, MD, PPTX, and TXT.
- [ ] Each uploaded source row shows file name, file size, extraction state, and indexing state.
- [ ] Unsupported file types are rejected with a clear message.
- [ ] Verify in browser using dev-browser skill.

#### US-M1-009-2: See indexing and PII status before generation
**As a** Compliance Reviewer, **I want** PII detection surfaced on sources before generation **so that** sensitive content is flagged before it is used.

**Acceptance Criteria:**
- [ ] Extraction and indexing states are visible per source and update as processing completes.
- [ ] PII detection results are surfaced on the relevant source(s) before generation can proceed.
- [ ] Verify in browser using dev-browser skill.

#### US-M1-009-3: Remove a source before generation
**As a** Business Analyst, **I want** to remove a source before launching generation **so that** I exclude irrelevant or inappropriate documents.

**Acceptance Criteria:**
- [ ] The user can remove a source before launching generation.
- [ ] A removed source is no longer listed and is excluded from the intake package and generation.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M1-009-1: The system must accept source uploads of DOCX, PDF, XLSX, MD, PPTX, and TXT during project creation.
- FR-M1-009-2: The system must display file name, size, extraction state, and indexing state for each source.
- FR-M1-009-3: The system must surface PII detection results before generation.
- FR-M1-009-4: The system must allow removing a source before launching generation.

**Backend / Production Requirements:**
- BE-M1-009-1: A real file-upload service must accept and store source files securely with size/type validation (overview §9 actual file upload).
- BE-M1-009-2: Uploaded files must be malware-scanned before processing; failed scans must block use of the file and surface an error (overview §9 malware scanning, §8 source security).
- BE-M1-009-3: An ingestion pipeline must perform text and table extraction (including OCR for image-based PDFs), track source spans, and update extraction state (overview §9 OCR/parsing).
- BE-M1-009-4: Extracted content must be chunked and embedded/indexed for retrieval, updating indexing state on completion (overview §9 embedding, permission-filtered RAG).
- BE-M1-009-5: A PII/sensitive-data classifier must run during ingestion and persist PII flags and data classification on each source (overview §8 PII classification, §9, BR-M4-011 alignment).
- BE-M1-009-6: Source visibility and downstream AI retrieval must enforce data classification and the user's clearance; restricted sources must not be retrievable by unauthorized users (overview §8).
- BE-M1-009-7: Source upload, removal, scan results, and classification decisions must be audit logged (overview §8 audit).

### BR-M1-010 — Project Workspace Stage Map
**Priority:** Must

**Requirement:** SpecForge shall provide a project workspace stage map showing all 10 SDLC stages (Requirement Understanding, BRD, FS, NFR, ADR, TBP, SDD, TS, TC, Traceability Matrix) with per-stage progress percentage and status, navigation to the relevant document/screen on click, and visually distinct stale and review statuses.

**User Stories:**

#### US-M1-010-1: See all 10 SDLC stages and their progress
**As a** Business Analyst, **I want** a stage map of all 10 SDLC stages with progress and status **so that** I understand where the project stands.

**Acceptance Criteria:**
- [ ] The stage map lists all 10 stages: Requirement Understanding, BRD, FS, NFR, ADR, TBP, SDD, TS, TC, and Traceability Matrix.
- [ ] Each stage displays a progress percentage and a status.
- [ ] Stale and review statuses are visually distinct from normal/in-progress/approved statuses.
- [ ] Verify in browser using dev-browser skill.

#### US-M1-010-2: Navigate to a stage's document or screen
**As a** Solution Architect, **I want** to click a stage to open its document or screen **so that** I can act on it directly.

**Acceptance Criteria:**
- [ ] Clicking a stage routes to the appropriate document or screen for that stage (e.g., Requirement Understanding interview, BRD editor, traceability matrix), preserving project context.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M1-010-1: The system must render a stage map of all 10 SDLC stages in lifecycle order.
- FR-M1-010-2: The system must display per-stage progress percentage and status.
- FR-M1-010-3: The system must visually distinguish stale and review statuses.
- FR-M1-010-4: The system must route to the appropriate document/screen when a stage is clicked.

**Backend / Production Requirements:**
- BE-M1-010-1: The project service must compute and persist per-stage progress and status (including stale and review signals) for all 10 stages from document, review, and stale-impact state (overview §9 analytics, persistent database).

### BR-M1-011 — Project Workspace Operational Panels
**Priority:** Must

**Requirement:** SpecForge shall display project-level sources, quality scores, open questions, assumption ledger, recent activity, skill versions, and quick links, with the specified fields per panel and quick links routing to BRD, review, stale impact, trace, interview, and app brain.

**User Stories:**

#### US-M1-011-1: Review project sources and quality
**As a** Business Analyst, **I want** panels showing project sources and quality scores **so that** I can assess evidence and document health.

**Acceptance Criteria:**
- [ ] The sources panel shows source type, page count, date added, and PII tag for each source.
- [ ] The quality panel shows completeness, clarity, traceability, risk coverage, consistency, and NFR coverage subscores.
- [ ] Verify in browser using dev-browser skill.

#### US-M1-011-2: Review open questions and assumptions
**As a** Compliance Reviewer, **I want** panels for open questions and the assumption ledger **so that** I can track unresolved items and inferred claims.

**Acceptance Criteria:**
- [ ] Open questions show ID, section, due date, assignee, and question text.
- [ ] Assumptions show ID, text, confidence, source, and status.
- [ ] Verify in browser using dev-browser skill.

#### US-M1-011-3: Review activity and skill versions
**As a** Platform Administrator, **I want** to see recent activity (AI vs human) and skill versions **so that** I can audit how the project evolved and which skills were used.

**Acceptance Criteria:**
- [ ] The recent activity panel distinguishes AI events from human events.
- [ ] The workspace displays the skill versions used on the project.
- [ ] Verify in browser using dev-browser skill.

#### US-M1-011-4: Navigate via quick links
**As a** Business Analyst, **I want** quick links from the workspace **so that** I can jump to common destinations in one click.

**Acceptance Criteria:**
- [ ] Quick links route to BRD, review, stale impact, trace, interview, and app brain, each with correct project context.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M1-011-1: The system must display a sources panel with source type, page count, date added, and PII tag.
- FR-M1-011-2: The system must display a quality panel with completeness, clarity, traceability, risk coverage, consistency, and NFR coverage.
- FR-M1-011-3: The system must display open questions with ID, section, due date, assignee, and text.
- FR-M1-011-4: The system must display assumptions with ID, text, confidence, source, and status.
- FR-M1-011-5: The system must display recent activity distinguishing AI and human events.
- FR-M1-011-6: The system must display project skill versions.
- FR-M1-011-7: The system must provide quick links to BRD, review, stale impact, trace, interview, and app brain.

**Backend / Production Requirements:**
- BE-M1-011-1: The project service must aggregate and return sources, quality subscores, open questions, assumptions, recent activity, and skill versions for the workspace from the persistent store (overview §9 persistent database).
- BE-M1-011-2: Quality subscores must be computed by an analytics/quality service over project content (overview §9 analytics).
- BE-M1-011-3: Recent activity must be sourced from the immutable audit/activity log, tagging each event as AI or human with actor and timestamp (overview §8 audit).
- BE-M1-011-4: Skill versions displayed must reflect the governed skill/prompt/model versions recorded for AI actions on the project (overview §8 version governance).

### BR-M1-012 — Adaptive Requirement Understanding
**Priority:** Must

**Requirement:** SpecForge shall generate a structured Requirement Understanding from indexed sources and app-brain context, then ask only unresolved questions before downstream document generation, displaying AI/user/question/structured-understanding messages, showing source references for inferred claims, populating all understanding fields, showing per-field confidence/completeness, and blocking downstream generation until the user validates the understanding.

**User Stories:**

#### US-M1-012-1: Run the adaptive interview
**As a** Business Analyst, **I want** an adaptive interview that reads my sources and app context and asks only what it cannot infer **so that** I am not filling in a blank form.

**Acceptance Criteria:**
- [ ] The interview displays distinct message types: AI messages, user messages, question messages, and structured understanding messages.
- [ ] The system asks only questions it cannot infer from indexed sources and app-brain context.
- [ ] The user can answer questions and have answers incorporated into the understanding.
- [ ] Verify in browser using dev-browser skill.

#### US-M1-012-2: See provenance and completeness of the understanding
**As a** Compliance Reviewer, **I want** source references for inferred claims and per-field confidence/completeness **so that** I can judge how grounded the understanding is.

**Acceptance Criteria:**
- [ ] The system shows source references for inferred claims.
- [ ] The structured understanding includes objective, stakeholders, pain points, target process, functional areas, systems, integrations, roles, assumptions, open questions, and risks.
- [ ] The system shows confidence/completeness by understanding field.
- [ ] Verify in browser using dev-browser skill.

#### US-M1-012-3: Validate the understanding to unblock generation
**As a** Business Analyst, **I want** to validate the understanding as a checkpoint **so that** downstream generation only proceeds on a confirmed foundation.

**Acceptance Criteria:**
- [ ] Downstream document generation is blocked until the user validates the Requirement Understanding.
- [ ] After validation, the user can proceed to downstream generation (e.g., BRD).
- [ ] Validation is recorded so the checkpoint is auditable.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M1-012-1: The system must generate a structured Requirement Understanding from indexed sources and app-brain context.
- FR-M1-012-2: The system must display AI, user, question, and structured-understanding message types in the interview.
- FR-M1-012-3: The system must ask only unresolved questions it cannot infer.
- FR-M1-012-4: The system must show source references for inferred claims.
- FR-M1-012-5: The system must populate the full understanding (objective, stakeholders, pain points, target process, functional areas, systems, integrations, roles, assumptions, open questions, risks).
- FR-M1-012-6: The system must show confidence/completeness per understanding field.
- FR-M1-012-7: The system must block downstream document generation until the user validates the understanding.

**Backend / Production Requirements:**
- BE-M1-012-1: An LLM orchestration service must build the Requirement Understanding by retrieving relevant indexed source spans and selected app-brain facts via permission-filtered RAG and synthesizing the structured fields (overview §9 LLM integration, RAG; §8 access controls).
- BE-M1-012-2: The orchestrator must compute what is inferable vs. unresolved and generate targeted questions only for gaps, attaching source-span citations to inferred claims for provenance.
- BE-M1-012-3: Per-field confidence/completeness must be computed and persisted with the understanding; assumptions and open questions generated here must be persisted to the project's assumption ledger and open-question store.
- BE-M1-012-4: The validated understanding must be persisted as the approved checkpoint that gates downstream generation, with a version snapshot and an immutable audit record of the validation action (overview §8 audit, human approval gates).
- BE-M1-012-5: AI calls must record skill version, model, prompt template version, and source references in AI audit metadata, and must never use restricted content when the user lacks clearance (overview §8).

## 7. Non-Goals / Out of Scope

- Authoring/editing of BRD, FS, NFR, and downstream document content (covered by Module 2).
- The targeted review queue, stale-impact graph, and traceability matrix UIs themselves (Module 2); Module 1 only links to them and reflects their summary signals.
- App AI Brain detail authoring, app onboarding workflow, fact extraction governance, and proposed-update merge (Module 4); Module 1 only consumes app-brain context and shows linkage.
- Section/template/prompt configuration and confidence-threshold controls (Module 3).
- Export job generation, redaction policy execution, and packaging (Module 5); Module 1 panels may surface assumptions/quality that are exported elsewhere.
- The global shell, sidebar/breadcrumb chrome, design tokens, and RBAC/audit foundation itself (Module 0); Module 1 operates within and relies on them.
- Building the actual LLM models, embedding models, malware-scan engine, and OCR engine; Module 1 integrates with these as services.

## 8. Technical Considerations

**Data model entities (Module 1 owned/primary):**
- Project (id, name, business unit, application/app-scope, description, owner, status, priority, stage progress map, completion %, updated, go-live, created-by, access list).
- SavedView definition + per-user computed counts (logical, RBAC-filtered).
- SimilarProjectCandidate (source project ref, match score, business unit, finalized date, reusable asset tags).
- ReuseSelection (target project, source project ref, asset category, asset ref/version, provenance).
- SourceFile (id, project, name, type, size, storage ref, extraction state, indexing state, page count, PII flags, data classification, added date, added-by).
- AppInScope (project, app key, tier, version, owner, facts count, corpus ref, suggested flag, included flag).
- RequirementUnderstanding (project, fields: objective, stakeholders, pain points, target process, functional areas, systems, integrations, roles, assumptions, open questions, risks; per-field confidence/completeness; validation state; version).
- InterviewMessage (project, role/type: ai/user/question/understanding, content, citations).
- QualityScore (project, completeness, clarity, traceability, risk coverage, consistency, NFR coverage).
- OpenQuestion (id, project, section, due date, assignee, text, status) and Assumption (id, project, text, confidence, source, status) — shared with Module 2.
- ActivityEvent (project, actor, ai/human flag, action, timestamp) — sourced from audit log.

**API / service surface (illustrative, tech-agnostic):**
- Portfolio query service: list/search projects with saved-view filter, group-by, table/board projection, RBAC-filtered, paginated.
- Triage/analytics service: per-user prioritized actions with freshness metadata.
- Project lifecycle service: create intake package, draft staging, generate-understanding, route to interview.
- Similar-project discovery service: embedding/metadata similarity search with scores.
- App suggestion + app-brain context loader.
- Source ingestion pipeline: upload → malware scan → extract (OCR/tables) → embed/index → PII classify; with state callbacks.
- Requirement-understanding orchestrator: RAG retrieval + LLM synthesis + question generation + validation persistence.

**Integration points:** Module 0 (shell, routing, RBAC, audit, version infra), Module 2 (review/stale/trace/quality signals; downstream generation gate), Module 4 (app AI Brains, providers/skills, PII governance), Module 5 (export consumers of assumptions/quality).

**Production capabilities (overview §9) relied upon:** actual file upload + malware scanning + OCR/parsing + embedding; persistent database for projects/sources/understanding/questions/assumptions; real LLM provider integration + model routing; permission-filtered RAG; analytics computation for portfolio insights and quality; notification/inbox for triage; approval/validation records.

**Performance:** Portfolio search/grouping must remain responsive on large portfolios via server-side filtering, indexing, and aggregation. Source ingestion runs asynchronously with visible state; the wizard must not block on ingestion completion to reach the interview. Triage is precomputed/cached with displayed freshness rather than computed synchronously per page load.

**Security (overview §8):** All Module 1 reads/writes are RBAC-filtered; restricted sources are never returned via search, citations, or AI answers to unauthorized users; PII classification gates retrieval; secrets for providers/scanners are server-side only and never in client state; all create/ingest/validate/reuse actions are immutably audit logged with actor, timestamp, and affected entities.

## 9. Success Metrics

- Median time from "generate understanding" to validated Requirement Understanding decreases versus blank-form baseline.
- Percentage of new projects that reuse at least one similar-project asset by reference.
- Percentage of new projects created with at least one app in scope (i.e., interview not "from scratch").
- Percentage of inferred understanding claims carrying a source reference (provenance coverage) — target ~100%.
- Time-to-locate: median time/interactions to find a target project via search/saved views/grouping.
- Triage actionability: percentage of triage items acted on (clicked through) within a target window; triage data freshness within SLA.
- Source intake quality: percentage of uploads successfully scanned, extracted, and indexed; PII flagged before generation in 100% of cases where present.
- Zero unauthorized exposures: no inaccessible project/source surfaced in search, counts, triage, or citations.

## 10. Open Questions

- What exact thresholds define "needs review," "stale," and "high priority" for saved views and triage, and are they configurable per tenant?
- What is the similar-project match algorithm and the minimum match threshold for a candidate to be shown?
- What is the maximum source file size and per-project source count, and how are oversized/over-count uploads handled?
- Should the wizard support saving an in-progress intake as a draft to resume later (beyond cancel/no-create)?
- What is the triage recomputation cadence/SLA, and is it event-driven, scheduled, or hybrid?
- Can reuse-by-reference assets be later detached/overridden, and how is provenance preserved if so?
- What governs which skill versions appear in the workspace, and who can change them (delegated from Module 0/4)?
- Are saved views fixed, or can users create custom saved views in a future iteration?

## 11. Traceability Map

| BR ID | User Stories | Functional Requirements | Backend Reqs |
|---|---|---|---|
| BR-M1-001 | US-M1-001-1, US-M1-001-2 | FR-M1-001-1, FR-M1-001-2, FR-M1-001-3, FR-M1-001-4, FR-M1-001-5 | BE-M1-001-1, BE-M1-001-2 |
| BR-M1-002 | US-M1-002-1, US-M1-002-2 | FR-M1-002-1, FR-M1-002-2, FR-M1-002-3, FR-M1-002-4 | BE-M1-002-1, BE-M1-002-2 |
| BR-M1-003 | US-M1-003-1, US-M1-003-2, US-M1-003-3 | FR-M1-003-1, FR-M1-003-2, FR-M1-003-3, FR-M1-003-4, FR-M1-003-5 | BE-M1-003-1 |
| BR-M1-004 | US-M1-004-1, US-M1-004-2 | FR-M1-004-1, FR-M1-004-2, FR-M1-004-3, FR-M1-004-4 | BE-M1-004-1 |
| BR-M1-005 | US-M1-005-1, US-M1-005-2, US-M1-005-3 | FR-M1-005-1, FR-M1-005-2, FR-M1-005-3, FR-M1-005-4 | BE-M1-005-1, BE-M1-005-2, BE-M1-005-3 |
| BR-M1-006 | US-M1-006-1, US-M1-006-2, US-M1-006-3, US-M1-006-4 | FR-M1-006-1, FR-M1-006-2, FR-M1-006-3, FR-M1-006-4, FR-M1-006-5 | BE-M1-006-1, BE-M1-006-2, BE-M1-006-3, BE-M1-006-4 |
| BR-M1-007 | US-M1-007-1, US-M1-007-2, US-M1-007-3 | FR-M1-007-1, FR-M1-007-2, FR-M1-007-3, FR-M1-007-4 | BE-M1-007-1, BE-M1-007-2, BE-M1-007-3 |
| BR-M1-008 | US-M1-008-1, US-M1-008-2, US-M1-008-3 | FR-M1-008-1, FR-M1-008-2, FR-M1-008-3, FR-M1-008-4, FR-M1-008-5 | BE-M1-008-1, BE-M1-008-2, BE-M1-008-3 |
| BR-M1-009 | US-M1-009-1, US-M1-009-2, US-M1-009-3 | FR-M1-009-1, FR-M1-009-2, FR-M1-009-3, FR-M1-009-4 | BE-M1-009-1, BE-M1-009-2, BE-M1-009-3, BE-M1-009-4, BE-M1-009-5, BE-M1-009-6, BE-M1-009-7 |
| BR-M1-010 | US-M1-010-1, US-M1-010-2 | FR-M1-010-1, FR-M1-010-2, FR-M1-010-3, FR-M1-010-4 | BE-M1-010-1 |
| BR-M1-011 | US-M1-011-1, US-M1-011-2, US-M1-011-3, US-M1-011-4 | FR-M1-011-1, FR-M1-011-2, FR-M1-011-3, FR-M1-011-4, FR-M1-011-5, FR-M1-011-6, FR-M1-011-7 | BE-M1-011-1, BE-M1-011-2, BE-M1-011-3, BE-M1-011-4 |
| BR-M1-012 | US-M1-012-1, US-M1-012-2, US-M1-012-3 | FR-M1-012-1, FR-M1-012-2, FR-M1-012-3, FR-M1-012-4, FR-M1-012-5, FR-M1-012-6, FR-M1-012-7 | BE-M1-012-1, BE-M1-012-2, BE-M1-012-3, BE-M1-012-4, BE-M1-012-5 |
