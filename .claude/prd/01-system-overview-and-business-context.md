# SpecForge System Overview and Business Context

## 1. What SpecForge Is

SpecForge is an AI-assisted SDLC documentation platform for enterprise delivery teams. Its purpose is to take a business change request, source documents, prior project knowledge, and organisation application knowledge, then guide the team through a governed documentation lifecycle from requirement understanding through BRD, functional specification, non-functional specification, design, test artefacts, review, traceability, and final approval.

The prototype is not a generic document editor. It is a structured workbench for business analysis and systems delivery. It treats SDLC documents as connected, versioned, traceable artefacts rather than independent files. A change in one upstream section, such as a BRD scope clause, can make downstream FS, NFR, design, or test sections stale. SpecForge tracks those relationships and tells the user exactly what changed, which sections are affected, why they are affected, and what can be regenerated safely.

The system is built around five product ideas:

1. Adaptive intake instead of blank forms.
   SpecForge reads business cases, notes, PDFs, specs, and app-brain facts, then asks only the questions it cannot infer.

2. Document generation with provenance.
   Every generated claim should be backed by a source span, an app-brain fact, or an explicit assumption.

3. Human judgement at the right points.
   The user validates understanding, accepts or rejects assumptions, resolves targeted review items, and approves generated outputs before they become authoritative.

4. Traceability as a living graph.
   BRs, FRs, design decisions, NFRs, test scenarios, and test cases are linked. Coverage gaps and stale dependencies are continuously visible.

5. Organisational memory through app AI Brains.
   Enterprise applications such as PayHub, PolicyHub, AML Screen, MyAccount, and GNS have governed knowledge bases. Projects use those facts, and finalized project learnings can be proposed back into the app brains.

## 2. Business Problem

Enterprise SDLC documentation is usually slow, fragmented, and hard to keep consistent. Business analysts and architects often work across multiple Word documents, spreadsheets, emails, meeting notes, source PDFs, and prior project examples. The resulting documents can be inconsistent:

- BRD limits may differ from FS limits.
- NFR targets may be sized against an outdated scope.
- Test cases may not cover all critical business requirements.
- Assumptions may be buried in prose rather than tracked.
- Reviewers may spend time reading stable sections instead of changed, risky, or low-confidence sections.
- App-specific constraints may be rediscovered project by project.
- Lessons learned rarely flow back into organisation standards.

SpecForge addresses this by turning documentation into a governed, AI-assisted system of record. It does not merely draft text. It manages evidence, assumptions, review focus, dependencies, versioning, and reuse.

## 3. Business Objectives

SpecForge should achieve the following business outcomes:

- Reduce time from project intake to first validated BRD draft.
- Improve consistency between BRD, FS, NFR, design, and test artefacts.
- Reduce reviewer effort by focusing review on changed, risky, contradictory, low-confidence, or unsourced content.
- Improve traceability coverage from business requirements through tests.
- Prevent downstream work from progressing on stale or invalidated assumptions.
- Make AI-generated content auditable and explainable.
- Capture reusable system knowledge in application-level AI Brains.
- Create a repeatable enterprise documentation lifecycle for regulated delivery environments.

## 4. Primary Users and Responsibilities

### Business Analyst
The Business Analyst is the primary creator and operator of SpecForge projects. They create projects, upload sources, confirm apps in scope, complete adaptive interviews, validate requirement understanding, edit BRDs, manage assumptions and open questions, respond to review feedback, and submit documents for approval.

### Product Owner / Business Sponsor
The Product Owner or Sponsor validates scope, business objectives, success metrics, and priority. They may review BRD content, confirm trade-offs, and approve business acceptance.

### Solution Architect
The Solution Architect reviews functional and non-functional consistency, application constraints, integrations, downstream stale impact, design readiness, and architecture gates such as ADR and SDD.

### App Owner
The App Owner governs the app AI Brain for their system. They approve or reject proposed facts from projects, maintain app constraints, validate app-specific skills, and ensure future projects inherit accurate system knowledge.

### QA Lead
The QA Lead uses the traceability matrix to confirm that business and functional requirements are covered by test scenarios and test cases. They review gaps, draft missing tests, and confirm boundary and exception coverage.

### Compliance / Risk Reviewer
The Compliance Reviewer inspects AML, PDPA, PCI-DSS, retention, auditability, PII handling, and assumption provenance. They rely on source citations, app-brain constraints, and exportable evidence.

### Platform Administrator / AI Engineer
The Administrator configures providers, skills, source ingestion, access controls, retention, export policy, and app onboarding. They govern prompt versions, model routing, benchmark scores, and audit policies.

## 5. End-to-End Business Lifecycle

### 5.1 Project Creation
The user creates a project by entering project name, business unit, application, and description. SpecForge searches for similar past projects and recommends reusable templates, requirements, NFR sections, and glossary items. The user confirms apps in scope so SpecForge can load app AI Brain context before generation begins.

### 5.2 Source Ingestion
The user uploads source files such as business cases, workshop notes, PDFs, spreadsheets, decks, text files, and technical specs. SpecForge indexes the files, extracts text and tables, tracks source spans, and flags PII where detected.

### 5.3 Requirement Understanding
SpecForge reads the sources and app-brain context, then creates a structured Requirement Understanding. It includes objective, stakeholders, pain points, target process, functional areas, systems, integrations, user roles, assumptions, open questions, and risks. The AI asks only questions it cannot infer. The user must validate this checkpoint before BRD generation.

### 5.4 BRD Drafting and Editing
SpecForge generates BRD sections with citations, confidence, requirement cards, assumptions, and app-brain grounding. The user can edit sections, add sections, regenerate sections, improve wording, add comments, inspect citations, and ask document-specific questions.

### 5.5 Review and Approval
Instead of asking reviewers to reread an entire document, SpecForge creates targeted review queues. These queues show changed sections, new content, low-confidence assumptions, open questions, contradictions, and downstream impacts. Documents cannot be submitted while required review items remain unresolved.

### 5.6 Downstream Document Generation
Once upstream artefacts are ready, SpecForge creates FS, NFR, ADR, TBP, SDD, TS, and TC artefacts according to dependency gates. Pending modules clearly show what upstream approvals are required and what sections will be generated.

### 5.7 Traceability and Coverage
SpecForge maintains a traceability matrix linking BRs to FRs, design sections, test cases, and NFRs. Gaps are visible and actionable. Users can generate missing downstream artefacts or explicitly accept gaps with governance.

### 5.8 Stale Impact Management
When upstream content changes, SpecForge identifies affected downstream sections. It shows what changed, why each downstream section is stale, what text needs to change, and allows regeneration only for affected sections while preserving unrelated manual edits.

### 5.9 App Brain Self-Update
When a project locks or finalizes useful learnings, SpecForge proposes updates to relevant app brains. App owners review, refine, merge, or dismiss those updates. Merged updates become reusable organisational knowledge for future projects.

### 5.10 Export and Evidence
Users can export documents, sections, trace matrices, assumption ledgers, app-brain facts, and version snapshots. Exports must preserve provenance, version, citations, trace links, and access controls.

## 6. Core Business Concepts

### Project
A project is a governed delivery initiative with business metadata, source documents, apps in scope, SDLC stage progress, generated artefacts, reviews, questions, assumptions, trace links, and activity history.

### Source Corpus
A source corpus is the evidence set used by the AI. It includes uploaded project files and app-brain documents. Every claim should trace back to this corpus unless explicitly marked as an assumption.

### Requirement Understanding
Requirement Understanding is the validated structured interpretation of the business problem. It is the foundation for downstream generation. It must be approved before the BRD is produced.

### Document Module
A document module is a structured SDLC artefact such as BRD, FS, NFR, ADR, TBP, SDD, TS, TC, or Traceability Matrix. Each module has dependencies, sections, version history, review queues, and quality expectations.

### Requirement Card
A requirement card is a structured requirement object with ID, priority, title, description, acceptance criteria, rationale, owner, source, and trace links.

### Assumption
An assumption is a claim used in generated content that is not fully proven by sources. Assumptions have confidence, source/inference reason, status, and resolution workflow.

### Open Question
An open question is an unresolved decision or missing fact assigned to a person or team. Once resolved, it merges back into a document section with provenance.

### Trace Link
A trace link connects artefacts across the lifecycle, such as BR-002 to FR-FS-006 to DD-004 to TC-003. Missing links are gaps.

### Stale Impact
Stale impact is the downstream invalidation caused by an upstream change. It is computed at section level so only affected content needs attention.

### App AI Brain
An app AI Brain is an owner-governed knowledge base for a system. It contains glossary terms, capabilities, limitations, constraints, integrations, corpus documents, skills, open questions, and project touchpoints.

## 7. Business Value by Module

### Module 0: Global Architecture
Provides the consistent workbench, navigation model, role-based access, auditability, route context, design system, and version infrastructure needed for a regulated documentation platform.

### Module 1: Dashboard and Project Hub
Helps users manage the portfolio, create projects, discover reusable prior work, select app-brain context, ingest sources, and validate requirement understanding before generating downstream artefacts.

### Module 2: SDLC Document Workbench
Provides the core document creation and governance experience: BRD editing, AI assistance, citations, assumptions, targeted review, stale impact, traceability, FS/NFR generation, and downstream stage gating.

### Module 3: Template and Prompt Engineer Workspace
Provides reusable editing infrastructure for sections, requirement cards, templates, metadata, linkages, AI action controls, prompt variables, and demo configuration.

### Module 4: Integrations, Configurations, and AI Brains
Connects project documentation to enterprise application knowledge. It manages application facts, constraints, skills, source corpora, proposed updates, provider/security configuration, and app-owner governance.

### Module 5: Asset Compilation and Export
Turns governed SpecForge content into external artefacts: documents, sections, trace matrices, ledgers, app-brain exports, JSON schemas, version snapshots, and standalone packages.

## 8. Enterprise Controls Required for Production

SpecForge must be productionized with enterprise controls:

- Authentication and role-based authorization.
- Project and document access controls.
- Source document security and PII classification.
- Secret management for model providers and integrations.
- Prompt, model, and skill version governance.
- Immutable audit logs.
- Export redaction and expiry policies.
- Owner approval for app-brain fact changes.
- Human approval gates before AI-generated content becomes final.
- Traceability and stale-impact enforcement before document finalization.

## 9. Out of Scope in the Prototype but Implied for Production

The audited prototype does not include fully implemented backend services. The following are implied production capabilities:

- Actual file upload, malware scanning, OCR, parsing, and embedding.
- Persistent database for projects, documents, versions, reviews, questions, assumptions, app brains, and trace links.
- Real LLM provider integration and model routing.
- Real source retrieval and permission-filtered RAG.
- Real export job generation.
- Real notification and inbox workflows.
- Real approval signatures.
- Real app onboarding workflow.
- Real analytics computation for portfolio insights.

