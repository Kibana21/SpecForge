# AI SDLC Document Generation Portal — Requirements

**Status:** Draft for review
**Audience:** Engineering leadership, product, the BA/architecture community, governance & risk
**Owner:** Kartik

---

## 1. Executive summary

Project teams produce 8–12 interdependent SDLC artifacts per initiative — Tech Build Permit, Application Design Review, BRD, Functional Specification, Non-Functional Specification, Solution/Technical Design, Test Scenarios, Test Cases, Traceability Matrix, and security/compliance inputs. Today this work is slow, inconsistent, and gated to a few technical people who can operate AI tooling (Claude Code, VS Code, prompt files, Python skills).

This portal is an **AI-powered SDLC Document Factory**. Business users, BAs, architects, developers, testers, and project teams take a requirement from raw input to a complete, internally consistent, audit-traceable documentation set through a guided web workflow. The AI does the drafting and the cross-checking; humans own the judgement and the approval. No user ever touches Claude Code, VS Code, prompt files, or skill folders.

The differentiators that decide adoption are three: documents are modelled as an interdependent **graph** (so the set stays coherent over time, not just generated once), every non-trivial claim carries **provenance**, and the AI's own behaviour is **versioned and evaluated** so output quality improves after launch rather than freezing.

**One-line pitch:** an AI-powered SDLC Document Factory that lets business and technology teams generate, review, approve, and trace a complete, internally consistent project documentation set in a controlled portal — without ever using Claude Code, VS Code, or technical AI skills directly.

---

## 2. Problem statement

Producing SDLC artifacts with AI today is expensive in four specific ways:

- **The blank-page tax.** Every document starts from zero or from a stale copy-paste of a previous project, even when 60–80% is boilerplate or derivable from upstream approved artifacts.
- **The consistency tax.** The Functional Spec contradicts the BRD; test cases don't cover requirements; the design references systems the NFR never mentioned. These defects surface late — in review or in build — and are hunted by hand.
- **The tooling tax.** Doing this with AI requires technical knowledge of Claude Code, VS Code, prompt files, Python scripts, and skill folders. That gates the capability to a few people and makes output inconsistent across teams.
- **The traceability tax.** Audit and governance need BR → FR → Design → Test linkage. Today it is reconstructed by hand at the end, under time pressure — exactly when it is least reliable.

The portal must attack all four, not just the first.

---

## 3. Vision & guiding principles

The portal behaves like a disciplined senior BA and design reviewer that never tires — it drafts, it questions, it cross-checks, and it refuses to silently invent. Five principles govern every design decision:

1. **Draft, don't dictate.** AI produces a strong 80%; humans own the 20% that needs judgement and accountability. The human is always the approver of record.
2. **Derive, don't re-type.** Any field inferable from upstream approved content is pre-filled with provenance, not asked again.
3. **Consistency is a first-class output.** The portal's job is not just to write documents but to keep the whole set coherent as it evolves.
4. **Provenance over fluency.** Every non-trivial claim can answer "where did this come from?" — uploaded source, upstream document, or an explicitly flagged AI assumption.
5. **Boring on rails.** Long jobs run in the background, every action is logged, nothing reaches "Finalized" without a human, and the AI's behaviour is itself versioned and evaluated.

---

## 4. What users will love

Every capability is testable against these moments. If a feature doesn't ladder up to one of them, it is scope, not value.

| # | Delight moment | What it replaces | Why it earns adoption |
|---|----------------|------------------|------------------------|
| D1 | **"It already knew."** On project creation, the portal finds similar past projects and pre-proposes business unit, systems, integrations, reusable requirements, and templates. | Starting from a blank template or hunting for "that other project's BRD". | First 90 seconds feel like the tool is on their side. |
| D2 | **The interview, not the form.** Instead of a 13-field form, the AI runs a short adaptive Q&A and asks only what it can't infer. | Filling structured-understanding fields by hand. | Feels like a sharp colleague, not data entry. |
| D3 | **Never a blank page.** Every document opens as a confident, sectioned draft with inline citations. | Writing from scratch or mangling a previous doc. | Removes the biggest source of procrastination. |
| D4 | **"What changed and why."** When an upstream document changes, downstream documents show a precise section-level diff and rationale, with one-click "regenerate only the affected sections". | Re-reading whole documents to find what's now inconsistent. | The killer capability — nothing in a manual process gives you this. |
| D5 | **Targeted review.** Reviewers see only what needs judgement — new content, low-confidence areas, open questions, contradictions. | Re-reading the full 40-page document every cycle. | Cuts review fatigue, the real SDLC bottleneck. |
| D6 | **The assumption ledger.** Every AI assumption collected in one visible, exportable list with confidence and source. | Hidden assumptions discovered in build/UAT. | Builds the trust that makes people rely on the output. |
| D7 | **Ask the document.** Chat answers from the project's own sources and generated docs, with citations. | Ctrl-F across five documents. | Turns the workspace into organizational memory. |
| D8 | **Open questions become work.** Each open question is assignable, trackable, and resolvable back into the document. | An open-questions list nobody actions. | Closes the loop instead of just flagging gaps. |
| D9 | **House style, automatically.** Output matches approved-document structure, tone, and mandated sections because the system learned from real exemplars. | Manual reformatting to match the "real" template. | Output looks like *our* documents, not generic AI text. |
| D10 | **Status without nagging.** PMs get a live, accurate view of stage, completion, blocking reviews, and staleness without asking anyone. | Status-chasing in standups and chat. | Adoption is pulled by PMs, not just pushed by authors. |

---

## 5. Target users & jobs-to-be-done

| Persona | Primary job | Success looks like | Moments that matter most |
|---------|-------------|--------------------|---------------------------|
| Business User | Get my requirement understood and a BRD I trust | Validated understanding + approved BRD in one sitting | D1, D2, D3 |
| Business Analyst | Produce a complete, consistent BRD & Functional Spec | No rework from contradictions; traceability automatic | D3, D4, D6, D9 |
| Solution Architect | Review design, NFRs, build-permit inputs | Design provably consistent with BRD/FR; gaps early | D4, D5, D7 |
| Developer | Build from unambiguous, current specs | Fewer "what does this mean" loops | D4, D7 |
| QA / Tester | Generate scenarios & cases with full coverage | Every requirement traced to a test; gaps flagged | D4, D5, traceability |
| Security / Governance | Review controls, risks, permits; audit | Complete audit trail; assumptions and citations visible | D6, audit, governance |
| Project Manager | Track status, approvals, staleness | Live truth without chasing | D10 |
| Skill Owner | Author & govern document skills | Skills versioned, tested against exemplars, safely rolled out | §12, §15 |

---

## 6. Experience principles

- **One surface, no tool juggling.** Upload, understand, generate, review, approve, export, and audit all live in the workspace. The user never sees a prompt file or skill folder.
- **Always a next action.** Every screen surfaces the single most valuable next step ("Validate understanding", "3 sections need review", "BRD changed — review 2 stale documents").
- **Streaming, not spinners.** Sections stream as they generate; long full-document jobs run in the background with notification on completion.
- **Confidence is visible, not buried.** Low-confidence content and assumptions are marked inline, not hidden in a report tab.
- **Edits are signal.** Human edits to AI output are captured (anonymized, under org-level consent) as improvement data for the relevant skill.

---

## 7. Core capabilities

### 7.1 Project workspace & organizational memory
Each project has its own workspace containing: project name, business unit, application name, owner, document stages, uploaded source documents, generated documents, review comments, approval status, version history, and audit log. Plus:
- **Similar-project discovery (D1):** on creation, retrieve comparable past projects (business unit, systems, requirement embeddings) and offer reuse of templates, requirements, and assumptions.
- **Reusable requirement library:** approved requirements can be promoted to an org library and referenced (not copied) with backlink.
- **Project clone / fork:** start a new project pre-seeded from a prior one.

### 7.2 Document upload & ingestion
Users can upload Word, PDF, Excel, PowerPoint, plain text, prior BRDs/specs, meeting notes, and (later) email extracts. The system extracts text, tables, and key requirement sections. Plus:
- **PII detection & handling at ingest:** detect and tag PII; configurable redaction or restricted handling per org policy.
- **Source map:** every file is chunked and indexed with source spans so any later claim can cite a precise origin.

### 7.3 Requirement understanding & conversational interview
Before any document is generated, the AI produces a structured understanding:

> Business Objective · Key Stakeholders · Current Pain Points · Target Process · Functional Areas · Systems Involved · Integrations · Data Requirements · User Roles · Business Rules · Assumptions · Open Questions · Risks

It then runs an **adaptive interview (D2)** to fill only the gaps and resolve ambiguities, rather than presenting an empty form. The portal never blindly generates documents from raw input.

### 7.4 Human validation checkpoints
The user reviews the AI's understanding before anything downstream is generated. They can accept, edit, add missing points, mark items wrong, add clarifications, or ask for regeneration. **No downstream generation proceeds past an unvalidated checkpoint** — this is enforced and audit-logged.

### 7.5 Stage-based generation as a dependency graph
The default stage path is retained:

| Stage | Output |
|-------|--------|
| 1 | Requirement Understanding Summary |
| 2 | BRD |
| 3 | Functional Specification |
| 4 | Non-Functional Specification |
| 5 | Application Design Review |
| 6 | Tech Build Permit |
| 7 | Solution / Technical Design Document |
| 8 | Test Scenarios |
| 9 | Test Cases |
| 10 | Traceability Matrix |

Each document declares its upstream dependencies, and the portal maintains a dependency graph:
- When an upstream approved document changes, downstream documents are marked **Stale** with a section-level impact list and a one-line rationale per impact.
- The user can **regenerate only affected sections (D4)**, preserving human edits elsewhere via a merge/diff view.
- A document cannot reach **Finalized** while an upstream dependency invalidates it — enforced, not advisory.
- The stage path is configurable per org/template.

### 7.6 AI skills engine & skill governance
Each document type uses a reusable skill defining input required, instructions, output format, validation rules, required sections, quality checklist, examples, and guardrails:

```
skills/
  brd/                instructions.md  template.md  validator.py
  functional_spec/    instructions.md  template.md  validator.py
  non_functional_spec/instructions.md  template.md  validator.py
  design_review/      instructions.md  template.md  validator.py
  test_cases/         instructions.md  template.md  validator.py
```

Governed by a Skill Owner layer:
- **Skill registry** with semantic versioning; every generated document records the skill version that produced it.
- **Exemplar set per skill:** curated approved real documents used both as few-shot context and as the evaluation set.
- **Promotion workflow:** a new skill version must pass the exemplar/regression evaluation before becoming active; rollback is one action.
- Skills are authored and maintained only by Skill Owners through an admin UI — **end users never see or edit skill internals.**

### 7.7 AI orchestration
The system uses an orchestrated workflow, not one prompt for everything:

> Extract requirements → classify requirement type → identify missing information → generate outline → generate section by section → validate completeness → check consistency → ask clarification questions → finalize.

**Recommended substrate:** per-skill generation and validation as typed DSPy modules (signatures map to skills; validators become metrics/assertions, optimizable against the approved-exemplar set), with the human-in-the-loop stage flow as an explicit state machine (LangGraph or a thin Python workflow engine) plus Celery/Redis for long-running, resumable jobs and staleness propagation. This hybrid gives both a measurable, improvable quality story and auditable, resumable workflows. A LangGraph-only path is a viable simpler alternative; the hybrid is recommended.

### 7.8 Section-by-section generation & streaming
Large documents are generated section by section, each independently reviewable. For example, a Functional Spec: Overview · Scope · User Roles · Functional Requirements · Business Rules · Process Flow · Screen Requirements · Data Requirements · Integration Requirements · Exception Handling · Audit & Logging · Assumptions · Open Questions. Sections stream into the editor as generated; per-section regenerate preserves siblings; each section carries its own confidence and citations.

### 7.9 Review, edit & collaboration
Users edit generated documents inside the portal with a rich-text editor and AI actions: regenerate section, improve wording, make more detailed, simplify, add reviewer comments, compare versions, accept/reject AI suggestions. Plus:
- **Targeted review mode (D5):** filter the document to only new / changed / low-confidence / open-question / contradiction content.
- **Concurrent collaboration:** multiple users in a workspace with presence and section-level soft locks.
- **Suggestion mode:** AI changes land as tracked suggestions, not silent overwrites.

### 7.10 Quality engine & scoring
Every document runs automated checks: missing sections, contradictions, ambiguous requirements, unanswered open questions, inconsistent terminology, missing NFRs, missing test coverage, missing integration detail, unsupported assumptions, traceability gaps. Surfaced as a scorecard:

> Completeness 82% · Clarity 76% · Traceability 68% · Risk Coverage 70% · Ready for Review: No

Plus:
- **Cross-document consistency check:** does the Functional Spec contradict the approved BRD? Does a test case reference a requirement that no longer exists?
- **Terminology / glossary engine:** a per-project glossary; flags and offers to normalize inconsistent terms across the whole set.

### 7.11 Traceability matrix
The portal maintains traceability across documents:

| Business Requirement | Functional Requirement | Design Section | Test Case |
|----------------------|------------------------|----------------|-----------|
| BR-001 | FR-001 | DD-003 | TC-001 |
| BR-002 | FR-004 | DD-008 | TC-006 |

The matrix is **generated and maintained automatically** from the dependency graph, not authored by hand. Gaps (an FR with no test, a BR with no FR) are flagged as quality defects and are clickable to source.

### 7.12 Approval workflow
Each document has a lifecycle status: Draft → AI Generated → User Reviewed → Pending Approval → Approved → Rejected → Rework Required → Finalized. Approver roles are configurable per document type; approvers comment and request changes. "Approved" snapshots are immutable and versioned; staleness can move a Finalized document to "Needs Re-review" with full audit trail.

### 7.13 Export options
Word, PDF, Markdown, Excel (for the traceability matrix), and a ZIP package of all project documents. Notification of "review needed" / "document went stale" (Teams/email) is scheduled immediately after MVP because it is what makes status-without-nagging actually work.

### 7.14 Trust surface
- **Assumption ledger (D6):** every assumption with confidence and source, collected per document and exportable; nothing critical invented silently.
- **Inline citations:** generated claims link to a source span or an upstream document section.
- **Ask the document (D7):** retrieval-grounded chat over the project's sources and generated docs; answers are cited or the system declines.

---

## 8. Recommended UI structure

**8.1 Main dashboard** — all projects, with columns: Project Name · Business Unit · Current Stage · Completion % · Pending Reviews · Last Updated · Owner · Status.

**8.2 Project workspace**
- **Left panel:** project stages, uploaded documents, generated documents.
- **Center panel:** current document editor (streaming, targeted-review filter, suggestion mode).
- **Right panel:** AI assistant, quality checks, missing information, assumption ledger, comments.

**8.3 Stage progress**

```
[1 Requirement Understanding]  ✅
[2 BRD]                        ✅
[3 Functional Spec]            In Review
[4 NFR]                        Pending
[5 Design Review]              Pending   (Stale — upstream BRD changed)
[6 Test Cases]                 Pending
```

Staleness is shown directly on the stage map so it is impossible to miss.

---

## 9. Functional requirements (selected, with acceptance criteria)

| ID | Requirement | Acceptance criteria |
|----|-------------|---------------------|
| FR-01 | Create a project workspace and surface ≥1 similar prior project when one exists. | Creation flow displays a comparable project with a reuse option; absence handled gracefully. |
| FR-02 | Produce a structured requirement understanding and run an adaptive interview for gaps before any downstream generation. | No Stage ≥2 document can be generated until the understanding artifact is "Validated". |
| FR-03 | Generate each document type section-by-section with per-section citations and confidence. | Every section has ≥1 provenance reference or an explicit assumption entry. |
| FR-04 | Maintain a document dependency graph and mark downstream docs Stale on upstream change, with section-level impact. | Changing an approved BRD section marks dependent FR sections Stale and lists them within one job cycle. |
| FR-05 | Regenerate only impacted sections while preserving human edits elsewhere. | Regeneration produces a diff; unaffected, human-edited sections are unchanged unless explicitly accepted. |
| FR-06 | Prevent Finalization of a document with unresolved upstream invalidation. | Finalize is blocked with a clear, actionable reason. |
| FR-07 | Auto-generate and maintain the traceability matrix and flag coverage gaps. | An FR with no linked test and a BR with no linked FR appear as defects, navigable to source. |
| FR-08 | Provide a targeted review mode filtering to new/changed/low-confidence/open-question/contradiction content. | Reviewer can reduce a document to only review-worthy content in one action. |
| FR-09 | Capture every AI generation and human edit in an immutable audit log with skill version, model, inputs hash, and actor. | Audit export reconstructs who/what/when/with-which-skill-version for any document state. |
| FR-10 | Make open questions assignable, trackable, and resolvable back into the document. | An answered, assigned question can be merged into the relevant section with provenance. |
| FR-11 | Never expose skill internals, prompt files, or tooling to end users. | No UI path exposes instructions/template/validator to non–Skill-Owner roles. |
| FR-12 | Allow skill versions to go active only after passing the exemplar/regression evaluation. | A sub-threshold skill version cannot be activated; rollback is one action. |

---

## 10. Non-functional requirements

| Area | Requirement |
|------|-------------|
| Security | Role-based access control; workspace/document isolation; no cross-project leakage; SSO via org IdP; least-privilege service accounts (managed identity where available). |
| Data residency & privacy | Uploaded content and derived artifacts stay within approved data boundaries; PII detected at ingest with configurable handling; per-org retention policy. |
| Auditability | Every AI call and human edit logged immutably with correlation ID, skill version, model, prompt-version hash, inputs hash, actor, timestamp. |
| Reliability | Long generations run as resumable background jobs; partial progress preserved on failure; idempotent retries. |
| Scalability | Multiple concurrent projects and users; graceful degradation under load. |
| Explainability | Inline source references; assumption ledger per document; "Ask the document" answers cited or declined. |
| Versioning | Every document version retained; approved snapshots immutable; skill version tracked per generation. |
| Governance | Human approval mandatory before Finalized; AI behaviour itself versioned and evaluated. |
| Cost control | Per-project / per-org token budgets and visibility; section-level caching; model tiering (cheaper models for extraction/classification, stronger for drafting). |
| Performance | First streamed section within seconds of request; published background-job SLA per document type. |
| Evaluation | Standing offline evaluation harness scoring skill output against approved exemplars; releases gated on it. |

---

## 11. AI governance & guardrails

The system shall:
- Never silently invent critical requirements; all inventions surface in the assumption ledger with confidence.
- Clearly mark assumptions, open questions, and low-confidence areas inline.
- Cite source spans where possible and decline to assert when unsupported.
- Require human confirmation before final documents; no path to "Finalized" without an authorized human approver.
- Maintain version history of all AI-generated content and the skill/model version that produced it.
- Treat skill and prompt changes as change-controlled artifacts (registry, review, regression gate, rollback) — the AI's behaviour is governed, not a loose config string.
- Record model and skill version on every artifact so any output can be reproduced and explained during audit or review.

---

## 12. Technical architecture

- **Frontend:** React / Next.js — streaming section rendering, collaborative editing, targeted-review filtering.
- **Backend:** FastAPI / Python.
- **Generation layer:** typed DSPy modules per document-type skill, optimizable against the exemplar corpus.
- **Workflow layer:** explicit human-in-the-loop state machine (LangGraph or thin Python engine) + Celery/Redis for long-running, resumable jobs and staleness propagation.
- **Document processing:** PDF/Word/Excel/PPT parsers; chunking with source-span tracking; PII detection.
- **Storage:** PostgreSQL for metadata, dependency graph, and audit log; blob storage for files; vector store for retrieval and similar-project discovery.
- **LLM:** Azure OpenAI / Claude / Gemini behind a provider abstraction with model tiering and cost accounting.
- **Export:** docx / PDF / Markdown / Excel / ZIP.
- **Eval harness:** offline scoring service over the approved-exemplar set, wired into the skill promotion gate.

A linear-stage release can ship before the full dependency graph, but the graph and audit-log schema must be designed in from day one — retrofitting traceability and staleness is the expensive path.

---

## 13. Skill authoring lifecycle

1. **Draft** — Skill Owner authors instructions/template/validator and attaches an exemplar set.
2. **Evaluate** — automated scoring against exemplars + regression suite; quality delta vs the active version surfaced.
3. **Review** — second Skill Owner / governance sign-off.
4. **Promote** — version becomes active; all new generations record it.
5. **Monitor** — production edit-rate and quality scores tracked per skill.
6. **Iterate / rollback** — sustained high edit-rate or score regression triggers iteration; rollback is one action.

---

## 14. Evaluation & continuous improvement

Output quality must improve after launch, not freeze:
- **Approved documents are the gold set.** Every human-approved document becomes labelled data for its skill.
- **Edits are the signal.** Sections heavily edited before approval are negative signal; sections approved unchanged are positive — driving skill optimization and prioritization.
- **Release gate.** No skill version goes active without beating the current one on the offline harness.
- **Drift watch.** Per-skill production edit-rate and quality scores are dashboards Skill Owners own; sustained regression is an alert, not a surprise.

This is the difference between an AI document tool and one that gets measurably better every quarter.

---

## 15. MVP scope

The MVP must prove the delight, not just the coverage:

1. Project creation **with similar-project discovery (D1)** — even a simple version.
2. Requirement upload + structured understanding + **adaptive interview (D2)**.
3. Validation checkpoint (enforced).
4. BRD, Functional Spec, NFR, and Test Cases generation — section-by-section, streamed, **with citations and assumption ledger (D3, D6)**.
5. **Auto traceability matrix + coverage-gap flags.**
6. Review/edit with **targeted review mode (D5)** and version compare.
7. Cross-document consistency check between BRD ↔ Functional Spec — the smallest slice that proves the consistency concept.
8. Word/PDF export; full version history; immutable audit log.
9. Skill registry with versioning (Skill Owner facing).

Deferred from MVP but scheduled next: full dependency-graph staleness across all stages, Teams/email notifications, "Ask the document", concurrent collaboration. A thin slice of the consistency capability (item 7) is intentionally in the MVP — an MVP with no consistency capability is just a faster Word.

---

## 16. Phased roadmap

| Phase | Theme | Headline capabilities |
|-------|-------|------------------------|
| MVP | Prove delight on the core path | §15 items 1–9 |
| Phase 2 | Consistency & visibility | Full dependency-graph staleness (D4), Teams/email notifications (D10), "Ask the document" (D7), open-question assignment (D8) |
| Phase 3 | Design & permits | Application Design Review, Tech Build Permit, Solution/Technical Design automation; security design review inputs |
| Phase 4 | Ecosystem | Jira story generation, Confluence/SharePoint integration, enterprise/department template management, architecture diagram generation |
| Continuous | Self-improvement | Eval harness, skill optimization loop, drift dashboards — running from Phase 2 onward |

---

## 17. Success metrics

| Type | Metric | Target |
|------|--------|--------|
| Leading | Time to first BRD draft | < 10 min |
| Leading | % of generated sections accepted with no/minor edit | > 60% by Phase 2 |
| Leading | Median sections touched per review cycle (targeted mode) | ≥ 50% reduction vs full-doc review |
| Lagging | Reduction in manual documentation effort | 50–70% |
| Lagging | Review cycle time reduction | 30–40% |
| Lagging | Document completeness score | > 85% |
| Lagging | Traceability coverage | > 90% |
| Adoption | Eligible project teams using it for ≥1 artifact | 70% |
| Trust | Approved docs whose assumption ledger was reviewed | rising trend |
| Quality | Per-skill offline eval score | non-decreasing release over release |

Leading metrics matter because adoption and effort numbers lag by quarters; section-acceptance rate and review-touch reduction reveal within weeks whether the experience is landing.

---

## 18. Risks & open questions

- **R1 — Trust adoption.** Mediocre early output permanently sends users back to Word. Mitigation: launch on document types with the strongest exemplars; gate on the eval harness.
- **R2 — Dependency-graph complexity.** Section-level staleness across 10 document types is non-trivial. Mitigation: design schema in early; ship linear first; prove the BRD↔FS slice in MVP.
- **R3 — Data residency / PII.** Regulated content may constrain model choice and storage. *Open question:* confirm approved model endpoints and data boundary before architecture lock.
- **R4 — Skill governance ownership.** *Open question:* central CoE or per-business-unit ownership of the Skill Owner role.
- **R5 — Edits-as-signal consent.** *Open question:* org-level consent/privacy posture for using human edits to improve skills.
- **R6 — Template authority.** *Open question:* whose templates are canonical, and who approves changes.

---

## 19. Appendix: document type catalog

Requirement Understanding Summary · BRD · Functional Specification · Non-Functional Specification · Application Design Review · Tech Build Permit · Solution Design Document · Technical Design Document · Test Scenarios · Test Cases · Traceability Matrix · Security/Compliance Review Inputs.

Each entry in detailed design will specify: upstream dependencies, required sections, validator rules, exemplar set, owning Skill Owner, and default approvers.
