# PRD: SpecForge AI — Requirements-to-Spec Portal

## Introduction

SpecForge AI is a guided workflow portal where business users upload messy requirements documents (PDFs, DOCXs, TXTs) and the system generates structured, versioned outputs: Functional Specifications, Technical Specifications, User Stories, Acceptance Criteria, Open Questions, and Review Comments. It is NOT a chatbot — it is a step-by-step pipeline that transforms raw input into enterprise-grade documentation.

**Primary users:** Business Analysts / Product Managers and Engineering Leads (dual persona).

---

## Goals

- Enable non-technical and technical users to go from raw requirements to structured specs in a single guided workflow
- Extract structured requirements and surface gaps/open questions automatically — never hallucinate missing information
- Generate versioned Functional Spec, Technical Spec, and Jira-ready User Stories via a reusable Skill Engine
- Support rich inline editing of all generated sections
- Export final specs as Markdown
- Provide a premium, clean, enterprise-grade UI with a three-panel layout

---

## User Stories

### US-001: Project scaffolding — database models and DB setup
**Description:** As a developer, I need the core database schema so all features have a persistence layer.

**Acceptance Criteria:**
- [ ] Postgres tables created: `projects`, `documents`, `extracted_requirements`, `spec_versions`, `gap_questions`, `review_comments`
- [ ] Each table has `id` (UUID), `created_at`, `updated_at`
- [ ] `spec_versions` has `version_number` (integer, auto-increment per project), `spec_type` (enum: functional | technical | user_stories | review), `content` (text), `project_id` (FK)
- [ ] Alembic migrations run cleanly on a fresh Postgres DB
- [ ] `db.py` exposes a SQLAlchemy async session factory
- [ ] `npm run typecheck` (frontend) passes

---

### US-002: Backend project CRUD API
**Description:** As a user, I want to create and manage projects so I can organise separate requirements efforts.

**Acceptance Criteria:**
- [ ] `POST /api/projects` — creates a project with `name`, `description`; returns project JSON
- [ ] `GET /api/projects` — lists all projects with doc count and latest spec version
- [ ] `GET /api/projects/{id}` — returns project detail including linked documents and spec versions
- [ ] `DELETE /api/projects/{id}` — soft-deletes project
- [ ] All endpoints return consistent JSON envelope: `{ data, error, meta }`
- [ ] FastAPI auto-generated docs (`/docs`) shows all routes

---

### US-003: Document upload and parsing API
**Description:** As a user, I want to upload requirement documents so the system can extract text from them.

**Acceptance Criteria:**
- [ ] `POST /api/projects/{id}/documents` accepts multipart form upload
- [ ] Supported formats: PDF, DOCX, TXT
- [ ] Files stored in `uploads/{project_id}/` on local filesystem
- [ ] Parser extracts plain text from each format (PyMuPDF for PDF, python-docx for DOCX, plain read for TXT)
- [ ] Extracted text stored in `documents.extracted_text` column
- [ ] Unsupported file types return `400` with a clear error message
- [ ] Files larger than 20 MB return `413`

---

### US-004: LLM abstraction layer + Gemini provider
**Description:** As a developer, I need a provider-agnostic LLM interface so the Skill Engine can call any model without knowing the provider.

**Acceptance Criteria:**
- [ ] `base.py` defines abstract `LLMProvider` with `async def complete(prompt: str, system: str) -> str`
- [ ] `gemini_provider.py` implements `LLMProvider` using `google-generativeai` SDK
- [ ] Provider is selected via `LLM_PROVIDER=gemini` env var (default)
- [ ] If `GEMINI_API_KEY` is missing, provider falls back to a `MockProvider` that returns realistic hardcoded JSON responses
- [ ] Mock responses are structured enough for all 6 skills to parse correctly
- [ ] Switching provider requires only an env var change, no code changes

---

### US-005: Skill Engine core
**Description:** As a developer, I need a reusable Skill Engine so each AI capability is encapsulated and independently testable.

**Acceptance Criteria:**
- [ ] `skill_engine.py` loads a skill by name from the `skills/` directory
- [ ] Each skill directory contains: `instruction.md`, `template.md`, `schema.json`
- [ ] Engine renders `template.md` with context variables using Jinja2
- [ ] Engine calls LLM with rendered prompt + `instruction.md` as system message
- [ ] Engine validates LLM response against `schema.json` using `jsonschema`
- [ ] Engine returns typed Python dict matching the schema
- [ ] If validation fails, engine retries once with an error correction prompt

---

### US-006: requirement_extractor skill
**Description:** As the system, I need to extract structured requirements from raw document text so downstream skills have clean input.

**Acceptance Criteria:**
- [ ] Skill parses raw text and returns JSON with fields: `functional_requirements[]`, `non_functional_requirements[]`, `constraints[]`, `assumptions[]`, `stakeholders[]`
- [ ] Each requirement has: `id`, `text`, `source_reference` (quote from original doc), `confidence` (high | medium | low)
- [ ] Result stored in `extracted_requirements` table linked to the project
- [ ] `POST /api/projects/{id}/extract` triggers this skill and returns structured JSON
- [ ] Mock provider returns at least 5 sample requirements across categories

---

### US-007: gap_detector skill
**Description:** As the system, I need to detect missing or ambiguous information so users know what to clarify before generating specs.

**Acceptance Criteria:**
- [ ] Skill takes extracted requirements as input
- [ ] Returns JSON array of gap questions, each with: `id`, `question`, `category` (scope | data | security | integration | UX), `severity` (blocker | major | minor)
- [ ] Results stored in `gap_questions` table
- [ ] `POST /api/projects/{id}/detect-gaps` endpoint triggers this skill
- [ ] Gaps must NOT be hallucinated — if no gaps found, return empty array
- [ ] Mock provider returns at least 3 sample gap questions

---

### US-008: functional_spec_generator skill
**Description:** As the system, I need to generate a structured Functional Specification so BAs and PMs have a review-ready document.

**Acceptance Criteria:**
- [ ] Skill takes extracted requirements + resolved gap answers as input
- [ ] Returns JSON with sections: `overview`, `objectives[]`, `scope`, `features[]` (each with `name`, `description`, `acceptance_criteria[]`)
- [ ] Result stored as a new `spec_versions` record with `spec_type=functional`
- [ ] `POST /api/projects/{id}/specs/functional` triggers generation
- [ ] Each regeneration creates a new version (version_number increments)
- [ ] Mock provider returns a plausible functional spec JSON

---

### US-009: technical_spec_generator skill
**Description:** As the system, I need to generate a Technical Specification so engineering leads have an implementation-ready document.

**Acceptance Criteria:**
- [ ] Skill takes functional spec + extracted requirements as input
- [ ] Returns JSON with sections: `architecture_overview`, `components[]`, `data_models[]`, `api_endpoints[]`, `tech_stack`, `risks[]`
- [ ] Result stored as a new `spec_versions` record with `spec_type=technical`
- [ ] `POST /api/projects/{id}/specs/technical` triggers generation
- [ ] Mock provider returns a plausible technical spec JSON

---

### US-010: user_story_generator skill
**Description:** As the system, I need to generate Jira-ready User Stories so engineers can plan sprints directly.

**Acceptance Criteria:**
- [ ] Returns JSON array of stories, each with: `id`, `title`, `description` (As a… format), `acceptance_criteria[]`, `story_points` (estimated), `labels[]`
- [ ] Result stored as `spec_versions` record with `spec_type=user_stories`
- [ ] `POST /api/projects/{id}/specs/user-stories` triggers generation
- [ ] Stories are granular — one feature should produce multiple stories
- [ ] Mock provider returns at least 5 sample user stories

---

### US-011: reviewer skill
**Description:** As the system, I need to review generated specs for completeness, ambiguity, and risk so users get actionable feedback.

**Acceptance Criteria:**
- [ ] Reviews all generated specs and returns JSON array of comments, each with: `id`, `section`, `comment`, `severity` (critical | warning | suggestion), `category` (completeness | ambiguity | security | data | implementation)
- [ ] Result stored as `spec_versions` record with `spec_type=review` and in `review_comments` table
- [ ] `POST /api/projects/{id}/review` triggers this skill
- [ ] Mock provider returns at least 4 sample review comments across categories

---

### US-012: Dashboard — project list page
**Description:** As a user, I want to see all my projects on a dashboard so I can navigate to any active effort.

**Acceptance Criteria:**
- [ ] `/` route shows a grid of `ProjectCard` components
- [ ] Each card shows: project name, description, document count, latest spec type generated, last updated date
- [ ] "New Project" button opens a create project modal
- [ ] Empty state shown when no projects exist
- [ ] Loading skeleton shown while fetching
- [ ] `npm run typecheck` passes
- [ ] UI implemented using `ui-ux-pro-max-skill`
- [ ] Verify in browser using dev-browser skill

---

### US-013: Create project modal
**Description:** As a user, I want to create a new project so I can start a new requirements workflow.

**Acceptance Criteria:**
- [ ] Modal has fields: Project Name (required), Description (optional)
- [ ] Submit calls `POST /api/projects` and navigates to the new project page on success
- [ ] Validation error shown inline if Name is empty
- [ ] Modal closes on ESC or backdrop click
- [ ] `npm run typecheck` passes
- [ ] UI implemented using `ui-ux-pro-max-skill`
- [ ] Verify in browser using dev-browser skill

---

### US-014: Project workspace — three-panel layout
**Description:** As a user, I want a structured workspace so I can see documents, specs, and review feedback simultaneously.

**Acceptance Criteria:**
- [ ] `/projects/[id]` route renders a three-panel layout:
  - **Left panel:** project name, document list, upload button, workflow step indicator
  - **Center panel:** tabbed spec editor (Functional Spec | Technical Spec | User Stories | Review Comments | Open Questions)
  - **Right panel:** gap questions and review comments relevant to the active tab
- [ ] Panels are resizable or have fixed proportions (left 20%, center 55%, right 25%)
- [ ] Mobile: collapses to single-column with tab navigation
- [ ] `npm run typecheck` passes
- [ ] UI implemented using `ui-ux-pro-max-skill`
- [ ] Verify in browser using dev-browser skill

---

### US-015: Document upload UI
**Description:** As a user, I want to upload requirement documents via drag-and-drop or file picker so I can start the extraction workflow.

**Acceptance Criteria:**
- [ ] `UploadPanel` component accepts drag-and-drop and file picker
- [ ] Accepted types shown: PDF, DOCX, TXT
- [ ] Upload progress shown per file
- [ ] Uploaded files listed in left panel with filename, size, upload date
- [ ] Error shown inline if file type or size rejected
- [ ] After upload, "Extract Requirements" button appears
- [ ] `npm run typecheck` passes
- [ ] UI implemented using `ui-ux-pro-max-skill`
- [ ] Verify in browser using dev-browser skill

---

### US-016: Requirements extraction and gap questions UI
**Description:** As a user, I want to trigger extraction and see structured requirements and gap questions so I understand what the system understood.

**Acceptance Criteria:**
- [ ] "Extract Requirements" button calls `POST /api/projects/{id}/extract` then `POST /api/projects/{id}/detect-gaps`
- [ ] Loading state shown during processing (spinner + status message)
- [ ] Extracted requirements shown as a collapsible list with confidence badges (High/Medium/Low) and source reference tooltips
- [ ] Gap questions shown in right panel as a `GapQuestions` component, grouped by severity (Blocker → Major → Minor)
- [ ] Each gap question has a "Mark Resolved" toggle
- [ ] `npm run typecheck` passes
- [ ] UI implemented using `ui-ux-pro-max-skill`
- [ ] Verify in browser using dev-browser skill

---

### US-017: Spec generation UI — all spec types
**Description:** As a user, I want to generate all spec types from the workspace so I can review and edit each one.

**Acceptance Criteria:**
- [ ] "Generate Specs" button triggers all three generation endpoints sequentially: functional → technical → user stories → review
- [ ] Each tab in `OutputTabs` populates as its spec arrives (progressive, not wait-for-all)
- [ ] Loading indicator per tab while that spec is being generated
- [ ] Generated specs rendered as structured content (not raw JSON): headings, bullets, tables for user stories
- [ ] Version badge shown on each tab (e.g. "v2") when a spec has been regenerated
- [ ] `npm run typecheck` passes
- [ ] UI implemented using `ui-ux-pro-max-skill`
- [ ] Verify in browser using dev-browser skill

---

### US-018: Inline rich text editing of generated specs
**Description:** As a user, I want to edit generated spec content inline so I can correct or enhance the AI output.

**Acceptance Criteria:**
- [ ] `SpecEditor` component wraps generated content in a contenteditable rich text editor (use `tiptap` or `@uiw/react-md-editor`)
- [ ] Supports bold, italic, bullet lists, headings, and inline code
- [ ] Changes auto-saved to backend via debounced `PATCH /api/projects/{id}/specs/{version_id}` (500ms debounce)
- [ ] "Saved" / "Saving…" indicator shown
- [ ] Edited content persists on page refresh
- [ ] `npm run typecheck` passes
- [ ] UI implemented using `ui-ux-pro-max-skill`
- [ ] Verify in browser using dev-browser skill

---

### US-019: Export as Markdown
**Description:** As a user, I want to export the generated specs as a Markdown file so I can share or commit them.

**Acceptance Criteria:**
- [ ] "Export Markdown" button in each spec tab header
- [ ] Triggers `GET /api/projects/{id}/export/markdown?spec_type=functional` (or technical, user_stories, all)
- [ ] Backend `markdown_exporter.py` compiles the spec version content into a well-formatted `.md` file
- [ ] File downloads in browser with filename `{project-name}-{spec-type}-v{n}.md`
- [ ] "Export All" option downloads a single combined Markdown file
- [ ] `npm run typecheck` passes
- [ ] UI implemented using `ui-ux-pro-max-skill`
- [ ] Verify in browser using dev-browser skill

---

### US-020: Review Comments panel
**Description:** As a user, I want to see reviewer feedback categorised by severity so I know what to fix before finalising specs.

**Acceptance Criteria:**
- [ ] Review Comments tab shows comments grouped by severity: Critical → Warning → Suggestion
- [ ] Each comment shows: section reference, comment text, category badge
- [ ] Right panel mirrors blockers and criticals while other tabs are active
- [ ] "Dismiss" action removes a comment from view (soft dismiss, stored in DB)
- [ ] `npm run typecheck` passes
- [ ] UI implemented using `ui-ux-pro-max-skill`
- [ ] Verify in browser using dev-browser skill

---

## Functional Requirements

- FR-1: The system must parse PDF, DOCX, and TXT files and store extracted plain text per document
- FR-2: The system must run `requirement_extractor` skill after document upload, storing structured requirements with confidence scores and source references
- FR-3: The system must run `gap_detector` skill and surface open questions grouped by severity — never hallucinate answers
- FR-4: The system must generate Functional Spec, Technical Spec, User Stories, and Review Comments via their respective skills
- FR-5: Each spec generation must create a new versioned record; previous versions must be retained
- FR-6: All LLM calls must go through the `LLMProvider` abstraction; the active provider is set by `LLM_PROVIDER` env var
- FR-7: If `GEMINI_API_KEY` is absent, the system must use mock responses that are structurally valid for all skills
- FR-8: The frontend must never expose the API key; all LLM calls happen server-side
- FR-9: The three-panel workspace layout must be maintained across all workflow steps
- FR-10: All spec content must be editable inline and auto-saved with debounce
- FR-11: Markdown export must be available per spec type and as a combined export
- FR-12: The UI must show confidence indicators and source references on extracted requirements

---

## Non-Goals (Out of Scope for MVP)

- DOCX export (Markdown only for now)
- Azure Blob Storage (local filesystem only, but designed for swap)
- Claude or Azure OpenAI providers (abstraction built, only Gemini implemented)
- Real-time collaboration / multi-user editing
- Authentication / user accounts
- Notifications or email delivery
- Commenting or annotation by reviewers
- Custom skill authoring via UI
- Mobile-native app
- Slack / Jira integration

---

## Design Considerations

> **Mandatory workflow rule:** All frontend/UI work MUST be implemented using the `ui-ux-pro-max-skill` Claude skill. Before writing any component, page, or style, invoke `/ui-ux-pro-max-skill` with the relevant context. Do not write UI code without it.

- **Aesthetic:** Premium, enterprise-grade. Think Linear or Notion — dark sidebar, clean typography, subtle borders, no gradients
- **Layout:** Fixed three-panel layout at `/projects/[id]`: left nav (20%), center editor (55%), right panel (25%)
- **Tabs:** `OutputTabs` uses pill-style tabs: Functional Spec | Technical Spec | User Stories | Review Comments | Open Questions
- **Confidence badges:** Color-coded chips — green (High), yellow (Medium), red (Low) — shown on extracted requirements
- **Skeleton loaders:** All async data fetches must show skeleton placeholders, not blank space
- **Empty states:** All lists must have meaningful empty states with CTAs
- **Tailwind CSS:** Use Tailwind utility classes throughout; no CSS-in-JS

---

## Technical Considerations

- **Backend:** FastAPI with async SQLAlchemy + asyncpg; Alembic for migrations
- **Frontend:** Next.js 14 App Router + React + Tailwind CSS
- **Database:** Postgres (local dev via Docker Compose)
- **File storage:** Local `uploads/` directory; `parser.py` abstracts reads so the path can later be replaced with Azure Blob URLs
- **LLM:** `google-generativeai` SDK; model `gemini-1.5-flash` as default
- **Rich text editor:** `tiptap` (preferred) or `@uiw/react-md-editor`
- **Skill Engine:** Jinja2 for prompt templating; `jsonschema` for output validation; one retry on validation failure
- **Environment:** `.env` file with `GEMINI_API_KEY`, `DATABASE_URL`, `LLM_PROVIDER`
- **CORS:** Backend must allow requests from `localhost:3000` in dev

---

## Success Metrics

- A user can go from uploading a document to viewing a full Functional Spec in under 2 minutes (with mock LLM)
- All 6 skills produce structurally valid output (passes schema validation) 100% of the time
- Inline edits persist correctly across page refreshes
- Markdown export produces a well-formatted file readable without further processing
- No API keys are ever visible in browser network requests

---

## Open Questions

- Should gap questions allow user-entered answers that get fed back into spec regeneration, or just toggle resolved?
- What is the maximum document size per project (single doc vs. total)?
- Should spec versioning show a diff view between versions, or just the latest?
- Should the reviewer skill run automatically after each spec generation, or be manually triggered?
- Is there a need for project-level tagging or search on the dashboard?
