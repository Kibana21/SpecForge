# PRD: Module 4 — Integrations, Configurations & AI Brains

> Part of the SpecForge detailed business-requirements PRD set. Sources: `.claude/prd/01-system-overview-and-business-context.md`, `.claude/prd/business-requirements-by-module.md`.

## 1. Introduction / Overview

Module 4 connects SpecForge's project-level documentation to organisation-level system knowledge. Its central concept is the **Application AI Brain**: an owner-governed, source-grounded knowledge base for each enterprise application (e.g., PayHub, MyAccount, PolicyHub, AML Screen, GNS). Each brain contains glossary terms, capabilities, limitations, constraints, integrations, corpus documents, app-specific skills, open questions, and project touchpoints.

The business problem this module solves is **repeated rediscovery**. Delivery teams ask the same questions across projects ("Does PayHub support AMEX?", "What is the transaction limit?", "Is `/capture` safe to retry?", "What are the PCI-DSS constraints?", "Which apps are downstream?"). Today those answers live in scattered PDFs, runbooks, ADRs, tribal knowledge, and prior project documents. App AI Brains turn that knowledge into source-grounded, owner-governed facts that SpecForge injects into project documents during generation.

Module 4 also **closes the learning loop**. When a project discovers or confirms a reusable fact, SpecForge does not bury it in a finished BRD. It proposes the fact back to the relevant app owner. If the owner merges it, future projects inherit it. This is the mechanism by which SpecForge becomes more valuable over time: project learnings → proposed updates → owner merge → reuse by future projects.

Finally, Module 4 owns the **enterprise configuration and security surface** that all AI generation depends on: LLM provider and model-routing configuration, skill and prompt-template version governance, credential/secret management, permission-filtered retrieval (RAG), and PII detection and data-classification enforcement across ingestion, retrieval, app-brain facts, prompts, and exports.

This PRD is implementation-ready: it covers every Module 4 business requirement (BR-M4-001 through BR-M4-011), all priorities, and adds the backend/production requirements implied by the system overview's enterprise controls (section 8) and implied production capabilities (section 9).

## 2. Goals

- Provide a governed Application Registry and per-app AI Brain that delivery teams trust as the single source of truth for application knowledge.
- Make every app-brain fact source-grounded, confidence-scored, and traceable to its originating corpus document or pipeline step.
- Enable natural-language Q&A against an app brain with permission-filtered retrieval and inline citations.
- Operate a closed learning loop: capture project learnings, route them as proposed updates to the correct app owner, and let owners merge, refine, or dismiss with full audit trail.
- Make app-brain grounding visible inside generated project documents so reviewers can see exactly which facts shaped which sections.
- Give administrators safe, governed control over LLM providers, model routing, skill/prompt versions, and credential policies — without ever exposing raw API keys to the client.
- Enforce data security and PII governance consistently across ingestion, retrieval, app-brain facts, prompts, and exports, with immutable audit logging of every security decision.
- Provide an onboarding path that converts apps discovered in projects into governed app-brain skeletons.

## 3. Scope

### In scope (with priority)

- BR-M4-001 — Application Registry — Must
- BR-M4-002 — App Onboarding Queue — Should
- BR-M4-003 — Application AI Brain Detail — Must
- BR-M4-004 — App Brain Pipeline Transparency — Must
- BR-M4-005 — App Brain Corpus Management — Must
- BR-M4-006 — Ask the App Brain — Must
- BR-M4-007 — App Brain Proposed Updates — Must
- BR-M4-008 — Promote Learnings from Project — Must
- BR-M4-009 — App-Brain Grounding in Documents — Must
- BR-M4-010 — LLM Provider and Skill Configuration — Must
- BR-M4-011 — Data Security and PII Governance — Must

### Priorities covered

- **Must:** BR-M4-001, BR-M4-003, BR-M4-004, BR-M4-005, BR-M4-006, BR-M4-007, BR-M4-008, BR-M4-009, BR-M4-010, BR-M4-011.
- **Should:** BR-M4-002.
- **Could:** None in Module 4 (no Could-priority BRs are defined for this module).

## 4. Users & Roles

The seven SpecForge roles interact with Module 4 as follows:

- **Business Analyst (BA):** Browses the registry, uses app brains as context when creating projects, asks the app brain questions, sees app-brain grounding in BRD sections, and promotes project learnings to app owners.
- **Product Owner / Business Sponsor:** Consumes app-brain grounding and Ask-the-App-Brain answers to validate scope and trade-offs; generally not an app-brain editor.
- **Solution Architect:** Reads app constraints, limitations, integrations, and the domain model to assess functional/non-functional consistency and downstream impact; may raise proposed updates.
- **App Owner:** Governs the AI Brain for their application(s). Approves/rejects proposed facts, manages the corpus, validates app-specific skills, merges or dismisses proposed updates, and ensures future projects inherit accurate knowledge. The primary editor/approver in this module.
- **QA Lead:** Uses app-brain constraints and gotchas to inform boundary and exception test coverage; consumer of grounding.
- **Compliance / Risk Reviewer:** Inspects PII handling, data classifications, source provenance, security-decision audit logs, and export redaction; relies on confidence and provenance metadata.
- **Platform Administrator / AI Engineer:** Configures LLM providers, model routing, skill versions, prompt templates, credential policies, app onboarding, and security/retention policies. Governs benchmark scores and audit policy.

Authorization rules (from BR-M0-008) that bind this module:

- Users only see apps they are authorized to access.
- Restricted source documents are not retrievable through search, citations, export, or AI answers by unauthorized users.
- Only app owners or delegated maintainers can merge app-brain proposals.
- Only authorized administrators access the onboarding queue and provider/skill/security configuration.

## 5. Key Business Objects

- **Application registry record:** name, short name, version, tier, environments, owner, fact count, indexed doc count, live project count, open-question count, proposed-update count, onboarded flag.
- **App AI Brain:** the governed knowledge base for one application (overview, domain model, capabilities, constraints, integrations, corpus, open questions, skills, projects touching, version history).
- **App fact:** ID, text, kind (capability/constraint/limitation/integration/glossary/etc.), source reference, confidence, provenance, owner-validation status, proposed/merged status.
- **App constraint / app capability / app limitation (gotcha):** typed facts with the same provenance and confidence model.
- **App corpus document:** source name, kind, page count, indexed date, primary status, classification, extraction/index state, view action.
- **App open question:** an unresolved app-level fact gap, optionally created from a low-confidence Ask-the-App-Brain query.
- **App skill:** name, version, owner, corpus binding, benchmark score, active status, compatible document types.
- **Project touchpoint:** a record linking a project to an app brain (apps in scope, facts used, learnings raised).
- **Proposed update:** kind, severity, target section, title, detail, originating project, source document, novelty, target app/owner, decision status.
- **App owner decision:** merge / refine / dismiss action with actor, timestamp, rationale, and resulting brain version.
- **Provider configuration:** provider, model IDs, endpoint, credential reference (never the raw secret), allowed data classifications, rate limits.
- **Prompt configuration:** template ID, version, output schema, citation policy, tool policy, safety policy.
- **Security classification:** data-classification label (e.g., Public, Internal, Confidential, Restricted/PII) attached to sources, facts, and exports.

## 6. Detailed Business Requirements

---

### BR-M4-001 — Application Registry
**Priority:** Must

**Requirement:** SpecForge shall provide an Application Registry that lists onboarded enterprise applications and their AI Brain health signals, with search, filtering, and navigation into each app's AI Brain detail.

**User Stories:**

#### US-M4-001-1: Browse the application registry
**As a** Business Analyst, **I want** to see a registry of onboarded enterprise applications with their AI Brain health signals **so that** I can find the right application knowledge before starting or scoping work.

**Acceptance Criteria:**
- [ ] The registry displays, for each app: app name, short name, version, tier, environments, owner, fact count, indexed-doc count, live-project count, open-question count, and proposed-update count.
- [ ] Health signals (e.g., facts, indexed docs, open questions, proposed updates) are shown numerically per app.
- [ ] Apps the user is not authorized to access are not listed.
- [ ] Counts (live projects, facts, etc.) respect the current user's access permissions.
- [ ] Verify in browser using dev-browser skill.

#### US-M4-001-2: Filter the registry
**As a** Business Analyst, **I want** to filter the registry by predefined views **so that** I can quickly narrow to relevant apps.

**Acceptance Criteria:**
- [ ] Users can filter to: all apps, Tier 1 apps, apps with pending updates, and apps owned by the current user.
- [ ] The selected filter updates the displayed app set without a full page reload.
- [ ] Filter selection is reflected in the UI (active filter is visually indicated).
- [ ] Verify in browser using dev-browser skill.

#### US-M4-001-3: Search the registry
**As a** Solution Architect, **I want** to search apps by name, owner, or functional area **so that** I can locate a specific application quickly.

**Acceptance Criteria:**
- [ ] Users can search by app name, owner, and functional area.
- [ ] Search is case-insensitive.
- [ ] Search applies within the currently selected filter view.
- [ ] Clearing the search restores the current filter's result set.
- [ ] Verify in browser using dev-browser skill.

#### US-M4-001-4: Open an app's AI Brain
**As a** Business Analyst, **I want** to click an app to open its AI Brain detail **so that** I can review its governed knowledge.

**Acceptance Criteria:**
- [ ] Clicking an onboarded app opens its AI Brain detail screen.
- [ ] Clicking a not-yet-onboarded app stub does not open a brain detail and instead surfaces its onboarding state (see BR-M4-002).
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M4-001-1: The system must render an Application Registry list/grid showing app name, short name, version, tier, environments, owner, fact count, indexed-doc count, live-project count, open-question count, and proposed-update count per app.
- FR-M4-001-2: The system must provide registry filters for all apps, Tier 1 apps, apps with pending updates, and apps owned by the current user.
- FR-M4-001-3: The system must provide a case-insensitive search across app name, owner, and functional area that operates within the active filter.
- FR-M4-001-4: The system must navigate to an app's AI Brain detail when an onboarded app is selected.
- FR-M4-001-5: The system must compute and display per-app health-signal counts (facts, indexed docs, live projects, open questions, proposed updates).

**Backend / Production Requirements:**
- BE-M4-001-1: The system must persist application registry records (identity, tier, environments, owner, onboarded flag) in the database.
- BE-M4-001-2: The system must compute health-signal counts from the underlying app-brain fact store, corpus index, project touchpoints, open-question store, and proposed-update store rather than from static values.
- BE-M4-001-3: The system must apply role-based access filtering server-side so that unauthorized apps and access-restricted counts are never returned to the client.
- BE-M4-001-4: The system must expose registry data via a paginated, filterable API to support large application portfolios.

---

### BR-M4-002 — App Onboarding Queue
**Priority:** Should

**Requirement:** SpecForge shall identify applications discovered in projects that are not yet onboarded and provide an administrator-accessible onboarding queue for creating governed app-brain skeletons through an approval workflow.

**User Stories:**

#### US-M4-002-1: See apps still to onboard
**As a** Platform Administrator, **I want** to see how many discovered apps are not yet onboarded **so that** I can plan onboarding work.

**Acceptance Criteria:**
- [ ] The registry footer displays a count of app stubs still to onboard.
- [ ] The count reflects apps referenced in projects (or otherwise discovered) that lack an AI Brain.
- [ ] Verify in browser using dev-browser skill.

#### US-M4-002-2: Propose discovered apps as skeletons
**As a** Platform Administrator, **I want** to propose un-onboarded apps discovered in projects as app-brain skeletons **so that** they can begin governance.

**Acceptance Criteria:**
- [ ] Un-onboarded apps discovered in projects can be proposed as skeletons from the onboarding queue.
- [ ] A proposed skeleton captures owner, capabilities, constraints, and a source corpus reference.
- [ ] Proposing a skeleton initiates the onboarding approval workflow.
- [ ] Verify in browser using dev-browser skill.

#### US-M4-002-3: Run the onboarding approval workflow
**As a** Platform Administrator, **I want** an onboarding workflow that requires approval before an app brain becomes active **so that** new brains are governed from creation.

**Acceptance Criteria:**
- [ ] The skeleton includes owner, capabilities, constraints, source corpus, and an approval workflow.
- [ ] The onboarding queue is accessible only to authorized administrators.
- [ ] An approved skeleton transitions the app to onboarded and makes it available in the registry as a full app brain.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M4-002-1: The system must display a registry-footer count of app stubs still to onboard.
- FR-M4-002-2: The system must allow authorized administrators to propose discovered un-onboarded apps as skeletons capturing owner, capabilities, constraints, and source corpus.
- FR-M4-002-3: The system must implement an onboarding approval workflow that gates activation of a new app brain.
- FR-M4-002-4: The system must restrict onboarding-queue access to authorized administrators.

**Backend / Production Requirements:**
- BE-M4-002-1: The system must detect apps referenced in projects that have no corresponding app brain and persist them as onboarding candidates (real app onboarding workflow per overview section 9).
- BE-M4-002-2: The system must persist skeleton drafts and their approval state, and create a governed app-brain record only after approval.
- BE-M4-002-3: The system must audit-log onboarding proposals and approval decisions (actor, timestamp, app, decision).
- BE-M4-002-4: The system must enforce authorization so only administrators can read or act on the onboarding queue.

---

### BR-M4-003 — Application AI Brain Detail
**Priority:** Must

**Requirement:** SpecForge shall provide an app-brain detail screen presenting source-grounded application knowledge — overview, domain model, capabilities, constraints, integrations, corpus, open questions, skills, and projects touching — with navigation, per-fact provenance, and brain-level toolbar actions.

**User Stories:**

#### US-M4-003-1: Review app-brain knowledge sections
**As a** Solution Architect, **I want** to view all knowledge sections of an app brain **so that** I can assess application capabilities and constraints.

**Acceptance Criteria:**
- [ ] The app brain displays sections for overview, domain model, capabilities, constraints, integrations, corpus, open questions, skills, and projects touching.
- [ ] Each section presents its relevant facts/content in a readable, structured form.
- [ ] Verify in browser using dev-browser skill.

#### US-M4-003-2: Inspect a fact's provenance
**As a** Compliance / Risk Reviewer, **I want** each fact to show its ID, text, source, confidence, and kind **so that** I can verify it is grounded and trustworthy.

**Acceptance Criteria:**
- [ ] Each fact displays its ID, text, source, confidence, and kind.
- [ ] Facts that are proposed (not yet merged) are distinguishable from owner-validated facts.
- [ ] Verify in browser using dev-browser skill.

#### US-M4-003-3: Navigate the brain via the left shelf
**As a** Business Analyst, **I want** to jump between app-brain sections from a left navigation shelf **so that** I can move through a large brain efficiently.

**Acceptance Criteria:**
- [ ] A left shelf lists the app-brain sections and supports navigation to each.
- [ ] Selecting a section scrolls to / displays that section.
- [ ] The active section is visually indicated.
- [ ] Verify in browser using dev-browser skill.

#### US-M4-003-4: Use app-brain toolbar actions
**As a** Business Analyst, **I want** toolbar actions for history, export, and use-in-new-project **so that** I can act on the brain from one place.

**Acceptance Criteria:**
- [ ] The toolbar exposes a history action (opens app-brain version history).
- [ ] The toolbar exposes an export action (subject to permissions and redaction).
- [ ] The toolbar exposes a use-in-new-project action that carries the app into project creation as an app in scope.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M4-003-1: The system must render an app-brain detail screen with sections for overview, domain model, capabilities, constraints, integrations, corpus, open questions, skills, and projects touching.
- FR-M4-003-2: The system must display, for each fact, its ID, text, source, confidence, and kind.
- FR-M4-003-3: The system must provide a left-shelf navigation that jumps to each app-brain section and indicates the active section.
- FR-M4-003-4: The system must provide toolbar actions for history, export, and use-in-new-project.
- FR-M4-003-5: The system must visually distinguish proposed (unmerged) facts from owner-validated facts.

**Backend / Production Requirements:**
- BE-M4-003-1: The system must persist an app-brain fact store where each fact carries text, kind, source reference, confidence score, provenance (pipeline step / corpus span), and owner-validation status (per overview sections 8-9).
- BE-M4-003-2: The system must maintain app-brain version history capturing actor, timestamp, change note, and changed facts/sections so the history action can render a timeline.
- BE-M4-003-3: The system must serve app-brain detail through a permission-filtered API so restricted facts and sources are excluded for unauthorized users.
- BE-M4-003-4: The system must link projects-touching data to the project touchpoint store so the section reflects real project usage.

---

### BR-M4-004 — App Brain Pipeline Transparency
**Priority:** Must

**Requirement:** SpecForge shall show how each app brain was built through an ingest → extract → synthesize pipeline, with step-level metrics and click-through navigation to the relevant brain section.

**User Stories:**

#### US-M4-004-1: See the ingest step metrics
**As a** Platform Administrator, **I want** the ingest step to show document and page counts **so that** I can confirm the right corpus was ingested.

**Acceptance Criteria:**
- [ ] The ingest step displays the count of ingested documents and total pages.
- [ ] Verify in browser using dev-browser skill.

#### US-M4-004-2: See the extract step metrics
**As a** Compliance / Risk Reviewer, **I want** the extract step to show extracted-fact count and confidence distribution **so that** I can gauge extraction quality.

**Acceptance Criteria:**
- [ ] The extract step displays the count of extracted facts.
- [ ] The extract step displays a confidence distribution across extracted facts.
- [ ] Verify in browser using dev-browser skill.

#### US-M4-004-3: See the synthesize step metrics
**As a** App Owner, **I want** the synthesize step to show capability, constraint, integration, and proposal counts **so that** I understand what the brain synthesized.

**Acceptance Criteria:**
- [ ] The synthesize step displays counts for capabilities, constraints, integrations, and proposals.
- [ ] Verify in browser using dev-browser skill.

#### US-M4-004-4: Jump from a pipeline step to its section
**As a** App Owner, **I want** to click a pipeline step and land on the related brain section **so that** I can inspect the underlying content.

**Acceptance Criteria:**
- [ ] Clicking a pipeline step navigates to the relevant app-brain section (e.g., synthesize → capabilities/constraints; ingest → corpus).
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M4-004-1: The system must display a pipeline view with ingest, extract, and synthesize steps.
- FR-M4-004-2: The system must show ingest metrics (document count, page count), extract metrics (fact count, confidence distribution), and synthesize metrics (capability, constraint, integration, proposal counts).
- FR-M4-004-3: The system must make each pipeline step click-through to its corresponding app-brain section.

**Backend / Production Requirements:**
- BE-M4-004-1: The system must run a real app-corpus pipeline (ingest → extract → synthesize) and persist step-level metrics for each app brain build (per overview section 9: actual parsing, OCR, embedding; fact extraction; synthesis).
- BE-M4-004-2: The system must record pipeline run metadata (run timestamp, skill/prompt versions used, model used) for audit and reproducibility (per BR-M0-007).
- BE-M4-004-3: The system must associate extracted facts with confidence scores so the extract-step distribution is computed from real data.

---

### BR-M4-005 — App Brain Corpus Management
**Priority:** Must

**Requirement:** App owners shall be able to manage the app-brain source corpus used for AI grounding, including listing sources with metadata, adding new sources for ingestion, re-indexing the corpus, and triggering downstream fact and version updates.

**User Stories:**

#### US-M4-005-1: View the app corpus
**As a** App Owner, **I want** to see the list of corpus sources with metadata **so that** I know what grounds the brain.

**Acceptance Criteria:**
- [ ] The corpus section lists, per source: source name, kind, page count, indexed date, primary status, and a view action.
- [ ] The view action opens or previews the source (subject to permissions).
- [ ] Verify in browser using dev-browser skill.

#### US-M4-005-2: Add a source document
**As a** App Owner, **I want** to add source documents for ingestion **so that** I can expand the brain's grounding.

**Acceptance Criteria:**
- [ ] Users can add one or more source documents to the corpus for ingestion.
- [ ] Newly added sources display extraction and indexing state.
- [ ] PII/classification status is surfaced for added sources before they are used for grounding.
- [ ] Verify in browser using dev-browser skill.

#### US-M4-005-3: Re-index the corpus
**As a** App Owner, **I want** a re-index action **so that** I can refresh facts after corpus changes.

**Acceptance Criteria:**
- [ ] A re-index corpus action is available to authorized users.
- [ ] Re-indexing updates extracted facts and creates an app-brain version-history entry.
- [ ] Source ingestion (add or re-index) updates extracted facts and app-brain version history.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M4-005-1: The system must render a corpus section listing source name, kind, page count, indexed date, primary status, and a view action per source.
- FR-M4-005-2: The system must allow authorized users to add source documents for ingestion.
- FR-M4-005-3: The system must provide a re-index corpus action.
- FR-M4-005-4: The system must update extracted facts and app-brain version history when sources are added or re-indexed.
- FR-M4-005-5: The system must restrict corpus management actions to the app owner or delegated maintainers.

**Backend / Production Requirements:**
- BE-M4-005-1: The system must implement real file upload, malware scanning, OCR/parsing, text/table extraction, and embedding for app-corpus sources (per overview section 9).
- BE-M4-005-2: The system must run PII detection and data-classification on ingested corpus sources and persist the classification (links to BR-M4-011).
- BE-M4-005-3: The system must persist corpus documents with metadata (kind, page count, indexed date, primary status, classification, index state) and store embeddings/index entries for retrieval.
- BE-M4-005-4: The system must execute re-index/ingestion as an asynchronous job, update the fact store on completion, and write an app-brain version snapshot and audit record.
- BE-M4-005-5: The system must enforce that only the app owner or delegated maintainers can mutate the corpus, and audit-log all corpus mutations.

---

### BR-M4-006 — Ask the App Brain
**Priority:** Must

**Requirement:** SpecForge shall allow users to ask natural-language questions about an application and receive source-grounded, streamed answers with citations, with permission-filtered retrieval and the ability to convert low-confidence or unanswered queries into app open questions.

**User Stories:**

#### US-M4-006-1: Ask a question with typed or suggested queries
**As a** Business Analyst, **I want** to ask an app brain a question using free text or suggested prompts **so that** I can quickly get application answers.

**Acceptance Criteria:**
- [ ] The Ask panel accepts typed natural-language queries.
- [ ] The Ask panel offers suggested queries the user can select.
- [ ] Verify in browser using dev-browser skill.

#### US-M4-006-2: See answers stream with citations
**As a** Solution Architect, **I want** answers to stream and then show citations **so that** I can read progress and verify the source.

**Acceptance Criteria:**
- [ ] Answers stream while being generated.
- [ ] Completed answers display citations drawn from app facts or the source corpus.
- [ ] Citations reference identifiable facts/sources (e.g., fact IDs or source spans).
- [ ] Verify in browser using dev-browser skill.

#### US-M4-006-3: Convert weak answers into open questions
**As a** Business Analyst, **I want** to convert a low-confidence or unanswered query into an app open question **so that** the gap gets owned and resolved.

**Acceptance Criteria:**
- [ ] Low-confidence or unanswered queries can be converted into an app open question.
- [ ] A converted open question is recorded in the app brain's open-questions section.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M4-006-1: The system must provide an Ask-the-App-Brain panel accepting typed queries and offering suggested queries.
- FR-M4-006-2: The system must stream answers as they are generated.
- FR-M4-006-3: The system must attach citations (app facts or corpus source spans) to completed answers.
- FR-M4-006-4: The system must allow converting low-confidence or unanswered queries into app open questions.

**Backend / Production Requirements:**
- BE-M4-006-1: The system must implement real, permission-filtered RAG over the app-brain fact store and corpus index so that only sources/facts the user is cleared to see are retrieved (per overview section 9 and BR-M0-008, BR-M4-011).
- BE-M4-006-2: The system must route the answer-generation call through the configured LLM provider/model (BR-M4-010) and stream tokens to the client.
- BE-M4-006-3: The system must compute and return an answer confidence and the supporting citations (fact IDs / source spans) for grounding and auditability.
- BE-M4-006-4: The system must prevent restricted/PII content from being used in answers when the user lacks clearance, and audit-log the retrieval/security decision (links to BR-M4-011).
- BE-M4-006-5: The system must persist converted open questions into the app open-question store with originating-query provenance.

---

### BR-M4-007 — App Brain Proposed Updates
**Priority:** Must

**Requirement:** SpecForge shall surface project-derived proposed updates to app brains for owner review, allowing owners to merge, refine, or dismiss each proposal, with merged proposals updating the brain and dismissed proposals remaining audit-visible.

**User Stories:**

#### US-M4-007-1: Review proposed updates
**As a** App Owner, **I want** to see proposed updates with full context **so that** I can decide whether to accept them.

**Acceptance Criteria:**
- [ ] Each proposed update shows kind, severity, target section, title, detail, originating project, and source document.
- [ ] Proposed updates are listed in a review surface within the app brain.
- [ ] Verify in browser using dev-browser skill.

#### US-M4-007-2: Merge, refine, or dismiss a proposal
**As a** App Owner, **I want** to merge, refine, or dismiss each proposal **so that** I keep the brain accurate.

**Acceptance Criteria:**
- [ ] App owners can merge a proposal.
- [ ] App owners can refine a proposal (edit title/detail) before merging.
- [ ] App owners can dismiss a proposal.
- [ ] Only app owners or delegated maintainers can act on proposals.
- [ ] Verify in browser using dev-browser skill.

#### US-M4-007-3: See the result of a decision
**As a** App Owner, **I want** decisions to be reflected clearly **so that** the team can see what changed.

**Acceptance Criteria:**
- [ ] Merged proposals update the app brain and are visibly marked merged.
- [ ] Dismissed proposals remain audit-visible and do not update the app brain.
- [ ] A merged proposal's resulting fact is reflected in the relevant brain section.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M4-007-1: The system must display proposed updates with kind, severity, target section, title, detail, originating project, and source document.
- FR-M4-007-2: The system must allow app owners to merge, refine (edit before merge), and dismiss proposals.
- FR-M4-007-3: The system must mark merged proposals as merged and apply their changes to the app brain.
- FR-M4-007-4: The system must keep dismissed proposals audit-visible without applying changes.
- FR-M4-007-5: The system must restrict merge/refine/dismiss actions to app owners or delegated maintainers.

**Backend / Production Requirements:**
- BE-M4-007-1: The system must implement an owner-approval workflow for app-brain fact changes (per overview section 8): proposals are pending until an authorized owner decision.
- BE-M4-007-2: The system must, on merge, create or update facts in the fact store with provenance (originating project, source document, refined text), bump the app-brain version, and write an audit record.
- BE-M4-007-3: The system must, on dismiss, persist the dismissal with actor, timestamp, and reason while retaining the proposal for audit (immutable audit per BR-M0-007).
- BE-M4-007-4: The system must enforce authorization so only app owners/delegated maintainers can change proposal state, and audit-log every decision.

---

### BR-M4-008 — Promote Learnings from Project
**Priority:** Must

**Requirement:** SpecForge shall allow users to promote generalizable project learnings to affected app owners after a document is locked or finalized, via a guided modal that lists candidate learnings, lets users include/exclude and refine each, groups confirmed proposals by app owner, and confirms the result with follow-up links.

**User Stories:**

#### US-M4-008-1: Review candidate learnings
**As a** Business Analyst, **I want** to see candidate learnings extracted from my finalized document **so that** I can decide what to promote.

**Acceptance Criteria:**
- [ ] The promote modal lists candidate learnings by app, target, kind, severity, title, detail, source document, novelty, and owner.
- [ ] Promotion is available after a document is locked or finalized.
- [ ] Verify in browser using dev-browser skill.

#### US-M4-008-2: Select and refine candidates
**As a** Business Analyst, **I want** to include/exclude and edit each candidate **so that** only good, well-worded learnings are sent.

**Acceptance Criteria:**
- [ ] Users can include or exclude each candidate learning.
- [ ] Users can refine a candidate's title and detail before sending.
- [ ] Verify in browser using dev-browser skill.

#### US-M4-008-3: Confirm and complete promotion
**As a** Business Analyst, **I want** a confirm step grouped by owner and a done step with follow-up links **so that** I know what was sent and where.

**Acceptance Criteria:**
- [ ] The confirm step groups included proposals by app owner.
- [ ] The done step confirms the count of proposals created.
- [ ] The done step provides follow-up links to the affected app brains.
- [ ] Promoted learnings appear as proposed updates in the target app brains (links to BR-M4-007).
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M4-008-1: The system must provide a promote-learnings modal available after a document is locked or finalized.
- FR-M4-008-2: The system must list candidate learnings with app, target, kind, severity, title, detail, source document, novelty, and owner.
- FR-M4-008-3: The system must allow include/exclude per candidate and allow refining title and detail.
- FR-M4-008-4: The system must provide a confirm step that groups included proposals by app owner.
- FR-M4-008-5: The system must provide a done step confirming proposal count and offering follow-up links to affected app brains.
- FR-M4-008-6: The system must create a proposed update in each target app brain for each promoted learning.

**Backend / Production Requirements:**
- BE-M4-008-1: The system must analyze locked/finalized document content to derive candidate learnings, computing novelty against existing app-brain facts (closed learning loop per overview section 5.9).
- BE-M4-008-2: The system must route each promoted learning to the correct target app owner as a proposed update, carrying originating project and source-document provenance (feeds BR-M4-007).
- BE-M4-008-3: The system must persist promotion actions and audit-log them (actor, timestamp, project, target apps, proposals created).
- BE-M4-008-4: The system must enforce that only authorized project members can promote learnings and that target-app routing respects owner assignments.

---

### BR-M4-009 — App-Brain Grounding in Documents
**Priority:** Must

**Requirement:** SpecForge shall expose which app-brain facts grounded generated document sections, via a grounding footer on BRD sections that lists the apps and facts used, links to the relevant brain, and shows totals.

**User Stories:**

#### US-M4-009-1: See grounding on document sections
**As a** Solution Architect, **I want** BRD sections to show which app-brain facts grounded them **so that** I can verify the system knowledge behind the content.

**Acceptance Criteria:**
- [ ] BRD sections that used app facts display an app-brain grounding footer.
- [ ] The grounding footer lists app names, fact IDs, fact text, fact kind, and proposed status for each grounding fact.
- [ ] Sections that did not use app facts do not show a grounding footer.
- [ ] Verify in browser using dev-browser skill.

#### US-M4-009-2: Navigate from grounding to the brain
**As a** Business Analyst, **I want** to click an app/fact chip to open the relevant app brain **so that** I can inspect the source fact.

**Acceptance Criteria:**
- [ ] Clicking an app or fact chip in the grounding footer opens the relevant app brain (and ideally the relevant fact/section).
- [ ] Verify in browser using dev-browser skill.

#### US-M4-009-3: See grounding totals
**As a** Compliance / Risk Reviewer, **I want** a grounding count of total facts and apps used **so that** I can gauge app-knowledge reliance.

**Acceptance Criteria:**
- [ ] The grounding display shows the total number of facts used and the total number of apps used.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M4-009-1: The system must render an app-brain grounding footer on BRD sections that used app facts.
- FR-M4-009-2: The system must list, per grounding fact, app name, fact ID, fact text, fact kind, and proposed status.
- FR-M4-009-3: The system must make app and fact chips click-through to the relevant app brain.
- FR-M4-009-4: The system must show a grounding count of total facts and total apps used.

**Backend / Production Requirements:**
- BE-M4-009-1: The system must record, at generation time, which app-brain facts were injected into each document section and persist that grounding linkage (provenance per overview's "generation with provenance" idea).
- BE-M4-009-2: The system must keep grounding references stable to fact IDs so footers remain accurate as facts are merged/updated, flagging when a grounding fact's proposed status changes.
- BE-M4-009-3: The system must serve grounding data through permission filtering so restricted facts/apps are not exposed to unauthorized readers.

---

### BR-M4-010 — LLM Provider and Skill Configuration
**Priority:** Must

**Requirement:** SpecForge shall support enterprise configuration of LLM providers, model routing, skill versions, prompt templates, and credential policies, ensuring raw API keys are never exposed in client-side state.

**User Stories:**

#### US-M4-010-1: Configure LLM providers
**As a** Platform Administrator, **I want** to configure LLM providers with models, endpoint, credential reference, allowed data classifications, and rate limits **so that** generation routes safely and within policy.

**Acceptance Criteria:**
- [ ] Provider configuration captures provider, model IDs, endpoint, credential reference, allowed data classifications, and rate limits.
- [ ] The credential is stored/referenced indirectly; raw API keys are never displayed or held in client-side state.
- [ ] Allowed data classifications restrict which content classifications a provider may process.
- [ ] Verify in browser using dev-browser skill.

#### US-M4-010-2: Configure skills
**As a** AI Engineer, **I want** to configure skills with version, owner, corpus, benchmark score, active status, and compatible document types **so that** AI actions use governed, versioned skills.

**Acceptance Criteria:**
- [ ] Skill configuration captures skill name, version, owner, corpus, benchmark score, active status, and compatible document types.
- [ ] Active status controls whether a skill version is usable.
- [ ] Compatible document types constrain where a skill can be applied.
- [ ] Verify in browser using dev-browser skill.

#### US-M4-010-3: Configure prompt templates
**As a** AI Engineer, **I want** to configure prompt templates with template ID, version, output schema, citation policy, tool policy, and safety policy **so that** AI output is governed and auditable.

**Acceptance Criteria:**
- [ ] Prompt configuration captures template ID, version, output schema, citation policy, tool policy, and safety policy.
- [ ] Prompt and skill versions are recorded for AI-assisted generation (links to BR-M0-007 audit).
- [ ] Verify in browser using dev-browser skill.

#### US-M4-010-4: Protect credentials
**As a** Compliance / Risk Reviewer, **I want** assurance that raw API keys are never exposed in client-side state **so that** secrets stay protected.

**Acceptance Criteria:**
- [ ] Raw API keys are never exposed in client-side state, API responses to the browser, or exports.
- [ ] Only a credential reference/identifier (not the secret value) is visible in configuration UIs.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M4-010-1: The system must provide provider configuration capturing provider, model IDs, endpoint, credential reference, allowed data classifications, and rate limits.
- FR-M4-010-2: The system must provide skill configuration capturing skill name, version, owner, corpus, benchmark score, active status, and compatible document types.
- FR-M4-010-3: The system must provide prompt configuration capturing template ID, version, output schema, citation policy, tool policy, and safety policy.
- FR-M4-010-4: The system must ensure raw API keys are never present in client-side state, never returned to the browser, and never included in exports.
- FR-M4-010-5: The system must record the skill version, model, and prompt-template version used for each AI-assisted generation.

**Backend / Production Requirements:**
- BE-M4-010-1: The system must store provider credentials in a secret manager and reference them by ID; the application must resolve secrets server-side only at call time (secret management per overview section 8).
- BE-M4-010-2: The system must implement model routing that selects the configured provider/model per skill and per content data-classification, honoring allowed classifications and rate limits (real LLM provider integration and routing per overview section 9).
- BE-M4-010-3: The system must version prompts, models, and skills and enforce active-status and compatibility constraints at generation time (prompt/model/skill version governance per overview section 8).
- BE-M4-010-4: The system must restrict provider/skill/prompt configuration to authorized administrators/AI engineers and audit-log all configuration changes.
- BE-M4-010-5: The system must reject or block generation requests that would route content to a provider not permitted for that content's data classification.

---

### BR-M4-011 — Data Security and PII Governance
**Priority:** Must

**Requirement:** SpecForge shall enforce data security controls for source ingestion, AI retrieval, app-brain facts, prompts, and exports — including PII detection, classification-based visibility/retrieval restriction, export redaction, clearance-gated AI calls, and immutable audit logging of security decisions.

**User Stories:**

#### US-M4-011-1: Detect PII at ingestion
**As a** Compliance / Risk Reviewer, **I want** PII detection to run during ingestion **so that** sensitive data is identified before it is used.

**Acceptance Criteria:**
- [ ] PII detection runs during source ingestion (project sources and app corpus).
- [ ] Detected PII and sensitive classifications are surfaced to authorized users.
- [ ] Verify in browser using dev-browser skill.

#### US-M4-011-2: Restrict visibility and retrieval by classification
**As a** Compliance / Risk Reviewer, **I want** PII/sensitive classifications to restrict who can see and retrieve content **so that** unauthorized users cannot access it.

**Acceptance Criteria:**
- [ ] PII and sensitive classifications restrict source visibility for unauthorized users.
- [ ] PII and sensitive classifications restrict AI retrieval (RAG) for unauthorized users.
- [ ] Restricted content does not appear in search, citations, or AI answers for unauthorized users.
- [ ] Verify in browser using dev-browser skill.

#### US-M4-011-3: Apply redaction to exports
**As a** Compliance / Risk Reviewer, **I want** export jobs to apply redaction policies **so that** exports do not leak restricted content.

**Acceptance Criteria:**
- [ ] Export jobs apply configured redaction policies to restricted content.
- [ ] Restricted source text is excluded from exports unless the user is explicitly authorized.
- [ ] Verify in browser using dev-browser skill.

#### US-M4-011-4: Gate AI calls by clearance
**As a** Platform Administrator, **I want** AI calls prevented from using restricted content when the user lacks clearance **so that** generation cannot bypass access control.

**Acceptance Criteria:**
- [ ] AI calls are prevented from using restricted content when the requesting user lacks clearance.
- [ ] The system degrades safely (e.g., excludes restricted content) rather than leaking it.
- [ ] Verify in browser using dev-browser skill.

#### US-M4-011-5: Audit security decisions
**As a** Compliance / Risk Reviewer, **I want** security decisions audit logged **so that** I can prove enforcement.

**Acceptance Criteria:**
- [ ] Security decisions (classification, visibility denial, retrieval exclusion, redaction, clearance gating) are audit logged.
- [ ] Audit records are immutable to non-admin users (per BR-M0-007).
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M4-011-1: The system must run PII detection during ingestion of project sources and app-corpus sources.
- FR-M4-011-2: The system must apply data classifications that restrict source visibility and AI retrieval for unauthorized users.
- FR-M4-011-3: The system must apply redaction policies to export jobs and exclude restricted source text unless explicitly authorized.
- FR-M4-011-4: The system must prevent AI calls from using restricted content when the user lacks clearance.
- FR-M4-011-5: The system must audit-log all security decisions immutably.

**Backend / Production Requirements:**
- BE-M4-011-1: The system must implement a PII/sensitive-data detection and classification pipeline at ingestion (per overview sections 8-9) and persist classification labels on sources, facts, and corpus chunks.
- BE-M4-011-2: The system must enforce classification- and clearance-based filtering in the retrieval/RAG layer so restricted chunks/facts are never returned to or used for unauthorized users (links to BR-M4-006, BR-M0-008).
- BE-M4-011-3: The system must apply redaction at export time according to tenant redaction policy and the requesting user's authorization (links to Module 5).
- BE-M4-011-4: The system must integrate classification checks with model routing so restricted content is only sent to providers whose allowed-classifications permit it (links to BR-M4-010).
- BE-M4-011-5: The system must write immutable audit records for every security decision (classification, denial, exclusion, redaction, clearance gating) with actor, timestamp, resource, decision, and reason (per BR-M0-007).

## 7. Non-Goals / Out of Scope

- Authoring or editing project SDLC documents (BRD/FS/NFR/etc.) — owned by Module 2; Module 4 only supplies grounding facts and surfaces grounding footers.
- The shared Section Editor, requirement-card editing, templates, and the prompt-confidence threshold UI — owned by Module 3 (Module 4 governs provider/skill/prompt versions, not the per-section editing surface).
- Document, trace-matrix, ledger, app-brain export rendering/packaging mechanics and export-job lifecycle UI — owned by Module 5 (Module 4 defines redaction/classification rules that exports must honor and the use-in-new-project/export entry points).
- Project portfolio, project creation wizard, and apps-in-scope selection UI — owned by Module 1 (Module 4 provides the registry/brain content and the use-in-new-project hand-off).
- Global navigation shell, design tokens, version-history panel chrome, audit infrastructure, and RBAC primitives — owned by Module 0 (Module 4 consumes them).
- Building or fine-tuning the LLMs themselves; SpecForge integrates external providers, it does not train models.
- General-purpose enterprise integration bus / iPaaS connectors beyond LLM providers and source ingestion.

## 8. Technical Considerations

- **App-brain fact store:** Facts should be stored with stable IDs, kind, text, confidence score, provenance (corpus span / pipeline run / originating project), owner-validation status, and proposed/merged state. Grounding linkages from document sections reference fact IDs.
- **Ingestion & RAG:** Real ingestion requires malware scanning, OCR/parsing, table extraction, chunking, embedding, and a vector/index store. Retrieval must be permission- and classification-filtered before results reach the model. Ask-the-App-Brain and document generation share this retrieval layer.
- **Pipeline:** The ingest → extract → synthesize pipeline should run as asynchronous jobs and emit step-level metrics (doc/page counts, fact counts, confidence distribution, synthesized capability/constraint/integration/proposal counts) plus run metadata (skill/prompt/model versions) for audit and the transparency view.
- **Owner-approval workflow:** Proposed updates (from promotion or other sources) are pending until an owner merges/refines/dismisses. Merges mutate the fact store and bump app-brain version; dismissals are retained for audit. All transitions are RBAC-gated to app owners/delegated maintainers.
- **Closed learning loop:** Promotion derives candidate learnings from locked/finalized documents, scores novelty against existing facts, routes proposals to the correct app owner, and links back to the resulting proposed updates. This must remain idempotent against re-promotion.
- **Secret management:** Provider credentials live in a secret manager and are referenced by ID. Secrets resolve server-side only at call time. The client and any exports must only ever see credential references, never raw keys. Configuration APIs must scrub secret values from all responses.
- **Model routing:** Routing selects provider/model per skill and per content data-classification, honoring allowed classifications, active status, skill/document-type compatibility, and rate limits. Requests that would violate classification policy are blocked.
- **Data classification & PII enforcement:** Classification is computed at ingestion and carried on sources, facts, and chunks. Enforcement is layered: visibility (UI/search), retrieval (RAG), generation (model routing), and export (redaction). Every decision is audit-logged immutably.
- **Versioning & audit:** App brains, facts, skills, prompts, and provider configs are versioned. All material actions (corpus mutation, re-index, merge, dismiss, promotion, configuration change, security decisions, exports) produce immutable audit records consistent with BR-M0-007.
- **Permission filtering everywhere:** Registry counts, brain detail, grounding footers, Ask answers, and exports must all apply the same RBAC + classification filters server-side; the client must never receive content the user is not cleared to see.
- **Frontend states:** UI should follow Module 0 design tokens, with distinct visual treatment for AI-generated/proposed vs. owner-validated facts and for app-brain grounding (distinct from document-local content). UI-facing stories are verifiable via the dev-browser skill.

## 9. Success Metrics

- Reduction in duplicate app-knowledge questions across projects (fewer repeat open questions for the same app fact).
- Percentage of generated document sections that carry app-brain grounding where applicable.
- App-brain fact coverage and average fact confidence per Tier 1 application.
- Proposed-update throughput: median time from promotion to owner decision, and merge rate vs. dismiss rate.
- Onboarding velocity: number of app stubs converted to governed brains per period; backlog count trend.
- Ask-the-App-Brain answer quality: proportion of answers with citations; rate of low-confidence queries converted to open questions and subsequently resolved.
- Zero incidents of raw API keys appearing in client-side state, API responses, or exports.
- Zero incidents of restricted/PII content reaching unauthorized users via search, citations, AI answers, or exports.
- Completeness of security-decision audit coverage (every classification/denial/exclusion/redaction/clearance decision logged).
- Reuse impact: number of future projects that inherit merged learnings.

## 10. Open Questions

- What is the canonical data-classification taxonomy (e.g., Public / Internal / Confidential / Restricted-PII), and how does it map to user clearance levels?
- Who, beyond the app owner, qualifies as a "delegated maintainer," and how is that delegation granted and revoked?
- What is the policy for handling facts whose grounding corpus document is later removed or reclassified — auto-stale, auto-dismiss, or owner review?
- Should merged-but-later-contradicted facts trigger stale-impact signals into projects that were grounded on them (cross-module link to Module 2 stale impact)?
- What benchmark methodology defines a skill's "benchmark score," and what threshold gates active status?
- What rate-limit and cost-budget controls are required per provider/model, and how are overages handled (queue, downgrade, block)?
- How is novelty scored for promoted learnings, and what novelty threshold should pre-exclude near-duplicates?
- Which secret-management backend is standard for the enterprise, and what key-rotation cadence/policy applies?
- For Ask-the-App-Brain, should answers be persisted/cached, and if so under what retention and classification rules?
- What is the approval quorum for onboarding a Tier 1 app brain (single admin vs. multi-party)?

## 11. Traceability Map

| BR ID | User Stories | Functional Requirements | Backend Reqs |
| --- | --- | --- | --- |
| BR-M4-001 | US-M4-001-1, US-M4-001-2, US-M4-001-3, US-M4-001-4 | FR-M4-001-1, FR-M4-001-2, FR-M4-001-3, FR-M4-001-4, FR-M4-001-5 | BE-M4-001-1, BE-M4-001-2, BE-M4-001-3, BE-M4-001-4 |
| BR-M4-002 | US-M4-002-1, US-M4-002-2, US-M4-002-3 | FR-M4-002-1, FR-M4-002-2, FR-M4-002-3, FR-M4-002-4 | BE-M4-002-1, BE-M4-002-2, BE-M4-002-3, BE-M4-002-4 |
| BR-M4-003 | US-M4-003-1, US-M4-003-2, US-M4-003-3, US-M4-003-4 | FR-M4-003-1, FR-M4-003-2, FR-M4-003-3, FR-M4-003-4, FR-M4-003-5 | BE-M4-003-1, BE-M4-003-2, BE-M4-003-3, BE-M4-003-4 |
| BR-M4-004 | US-M4-004-1, US-M4-004-2, US-M4-004-3, US-M4-004-4 | FR-M4-004-1, FR-M4-004-2, FR-M4-004-3 | BE-M4-004-1, BE-M4-004-2, BE-M4-004-3 |
| BR-M4-005 | US-M4-005-1, US-M4-005-2, US-M4-005-3 | FR-M4-005-1, FR-M4-005-2, FR-M4-005-3, FR-M4-005-4, FR-M4-005-5 | BE-M4-005-1, BE-M4-005-2, BE-M4-005-3, BE-M4-005-4, BE-M4-005-5 |
| BR-M4-006 | US-M4-006-1, US-M4-006-2, US-M4-006-3 | FR-M4-006-1, FR-M4-006-2, FR-M4-006-3, FR-M4-006-4 | BE-M4-006-1, BE-M4-006-2, BE-M4-006-3, BE-M4-006-4, BE-M4-006-5 |
| BR-M4-007 | US-M4-007-1, US-M4-007-2, US-M4-007-3 | FR-M4-007-1, FR-M4-007-2, FR-M4-007-3, FR-M4-007-4, FR-M4-007-5 | BE-M4-007-1, BE-M4-007-2, BE-M4-007-3, BE-M4-007-4 |
| BR-M4-008 | US-M4-008-1, US-M4-008-2, US-M4-008-3 | FR-M4-008-1, FR-M4-008-2, FR-M4-008-3, FR-M4-008-4, FR-M4-008-5, FR-M4-008-6 | BE-M4-008-1, BE-M4-008-2, BE-M4-008-3, BE-M4-008-4 |
| BR-M4-009 | US-M4-009-1, US-M4-009-2, US-M4-009-3 | FR-M4-009-1, FR-M4-009-2, FR-M4-009-3, FR-M4-009-4 | BE-M4-009-1, BE-M4-009-2, BE-M4-009-3 |
| BR-M4-010 | US-M4-010-1, US-M4-010-2, US-M4-010-3, US-M4-010-4 | FR-M4-010-1, FR-M4-010-2, FR-M4-010-3, FR-M4-010-4, FR-M4-010-5 | BE-M4-010-1, BE-M4-010-2, BE-M4-010-3, BE-M4-010-4, BE-M4-010-5 |
| BR-M4-011 | US-M4-011-1, US-M4-011-2, US-M4-011-3, US-M4-011-4, US-M4-011-5 | FR-M4-011-1, FR-M4-011-2, FR-M4-011-3, FR-M4-011-4, FR-M4-011-5 | BE-M4-011-1, BE-M4-011-2, BE-M4-011-3, BE-M4-011-4, BE-M4-011-5 |
