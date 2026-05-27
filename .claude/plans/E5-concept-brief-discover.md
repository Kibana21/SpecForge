# Concept Brief — Discovery Phase (Pre-Generation Q&A)

## Goal

Insert a structured "Discover" step before DSPy generation, grounded in the 14 questions from
`reference_mds/skills/concept-brief-builder/SKILL.md`. Three context layers are used throughout:

1. **App Brain** — per-app `AppDocTree` facts + wiki for all apps in `project.apps_in_scope`
2. **Project documents** — `DocumentTree` rows searched via PageIndex
3. **User's brief text** — whatever the user typed in the textarea

A ✨ **AI Enhance** button in the brief textarea synthesises all three layers into a rich brief
before the user even clicks Analyze. Discover analysis then reads the enhanced brief + both
document layers to auto-answer questions with source attribution stored in the DB.

---

## The 14 Discovery Questions (fixed catalog)

| Key | Category | Question | Primary sources |
|-----|----------|----------|----------------|
| 1a | initiative_context | What is the initiative name or working title? | project (direct) |
| 1b | initiative_context | What business problem does this initiative solve? | project docs + app brain |
| 1c | initiative_context | What is driving this initiative right now? (regulatory, competitive, cost) | project docs + brief |
| 2a | business_context | Which business unit or department owns this initiative? | project (direct) |
| 2b | business_context | Who are the primary customers or end users? | app brain facts + project docs |
| 2c | business_context | What is the current situation (as-is) — what exists today that is insufficient? | project docs + app brain |
| 3a | value_outcomes | What value does this initiative create if successful? | brief + project docs |
| 3b | value_outcomes | What outcomes would indicate success? (qualitative and quantitative) | brief + project docs |
| 3c | value_outcomes | Are there any initial success metrics or KPIs in mind? | app brain (existing KPIs) + docs |
| 4a | scope_assumptions | What capabilities or features are expected to be in scope? | brief + project docs |
| 4b | scope_assumptions | What is explicitly out of scope or deferred to a later phase? | brief |
| 4c | scope_assumptions | What assumptions is the business making at this stage? | brief + project docs |
| 5a | delivery | Are there any known milestones, deadlines, or delivery constraints? | brief + project docs |
| 5b | delivery | Is there an MVP or phased delivery approach in mind? | brief |

**Unit → question mapping** (which questions feed which DSPy unit):
```python
UNIT_DISCOVER_MAP = {
    "problem_context":  ["1a","1b","1c","2a","2b","2c"],
    "value_hypothesis": ["3a","3b"],
    "metrics":          ["3c"],
    "capabilities":     ["4a"],
    "scope":            ["4b","4c"],
    "milestones":       ["5a","5b"],
}
```

**Project-field direct prefills** (no LLM needed):
```python
PROJECT_PREFILL = {
    "1a": lambda p: p.name,
    "2a": lambda p: p.business_unit,
}
```

---

## Complete User Flow

```
Project page → Concept Brief tab
        │
        ▼  (no doc / first visit)
┌──────────────────────────────────────────────────────┐
│  EMPTY STATE                                          │
│                                                       │
│  "Describe your initiative"                          │
│  ┌─────────────────────────────────────────────┐    │
│  │ [textarea — user types or edits]            │    │
│  │                                             │    │
│  │                                   [✨ Enhance]│  │
│  └─────────────────────────────────────────────┘    │
│                                                       │
│  ⚡ 2 apps in scope  ·  1 document indexed           │
│                                                       │
│             [Analyze & Continue →]                    │
└──────────────────────────────────────────────────────┘
        │
        │  ✨ Enhance clicked  →  POST /discover/enhance-brief
        │     (streams/returns enhanced brief text, user can edit)
        │
        ▼  "Analyze & Continue" clicked  →  POST /discover/analyze
┌──────────────────────────────────────────────────────┐
│  DISCOVER PHASE                                       │
│                                                       │
│  🔍 Discovery Questions                              │
│  SpecForge analyzed your brief and knowledge base.   │
│  Progress ████████░░  9 / 14                         │
│                                                       │
│  ▼ 9 answered  (collapsible)                         │
│    ✅ 1a. Initiative name    PayHub Settlement [proj] │
│    ✅ 1b. Business problem   [...extracted...]  [doc] │
│    ✅ 2b. Customers          [...extracted...]  [app] │
│    ...                                               │
│                                                       │
│  ─── ❓ 5 gaps to fill ──────────────────────────── │
│  1c. What is driving this initiative?                 │
│      [textarea                              ] [hint?] │
│                                                       │
│  3a. What value does this create if successful?       │
│      [textarea                              ]         │
│  ...                                                  │
│                                                       │
│  [← Back]          [Generate Concept Brief →]        │
│                     (disabled until all ❓ answered)  │
└──────────────────────────────────────────────────────┘
        │
        ▼  POST /discover/complete
[ Generating… ]  (existing progress view, unchanged)
        │
        ▼
[ Two-column builder ]  (existing view + "Discovery Q&A ↗" button)
        │
        ▼  optional
[ Discovery Q&A Drawer ]
  Read-only list of all 14 Q&A with source badges:
  "from project" · "from documents" · "from app brain" · "you answered" · "AI enhanced"
```

**Resume:** If `doc.status === "in_discover"`, skip straight to Discover Phase with saved questions.

---

## Backend

### 1. Migration `0017_cb_discover_questions.py`

```sql
-- Extend artifact_status enum
ALTER TYPE artifact_status ADD VALUE IF NOT EXISTS 'in_discover';

-- Discovery questions table
CREATE TABLE IF NOT EXISTS cb_discover_questions (
    id                   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_document_id UUID        NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
    question_key         VARCHAR(10) NOT NULL,
    category             VARCHAR(50) NOT NULL,
    question_text        TEXT        NOT NULL,
    answer               TEXT,           -- final answer used in generation
    inferred_answer      TEXT,           -- raw extraction before user edits
    source               VARCHAR(30),    -- see Source enum below
    context_sources      JSONB,          -- attribution: which docs/apps contributed
    seq                  INTEGER     NOT NULL,
    created_at           TIMESTAMPTZ DEFAULT now(),
    updated_at           TIMESTAMPTZ DEFAULT now(),
    UNIQUE (artifact_document_id, question_key)
);

CREATE INDEX IF NOT EXISTS ix_cb_discover_questions_doc
    ON cb_discover_questions(artifact_document_id);

-- Enhanced brief text (stored separately for audit / re-use)
CREATE TABLE IF NOT EXISTS cb_discover_enhanced_briefs (
    id                   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_document_id UUID        NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
    original_brief       TEXT        NOT NULL,
    enhanced_brief       TEXT        NOT NULL,
    doc_sources          JSONB,      -- list of {doc_id, filename, sections_used}
    app_sources          JSONB,      -- list of {app_id, app_name}
    created_at           TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_cb_discover_enhanced_briefs_doc
    ON cb_discover_enhanced_briefs(artifact_document_id);
```

**`source` values:**
- `"project"` — from `project.name` / `project.business_unit` (no LLM)
- `"brief"` — extracted from user's brief text
- `"documents"` — extracted from project PageIndex
- `"app_brain"` — extracted from app brain context
- `"combined"` — from multiple non-user sources
- `"user"` — user explicitly typed/overrode
- `"ai_enhanced"` — from the AI Enhance step
- `null` — pending, must fill

**`context_sources` JSONB shape:**
```json
{
  "docs": [
    {"doc_id": "uuid", "filename": "151012-Press-Release.pdf", "section": "Problem Overview"}
  ],
  "apps": [
    {"app_id": "uuid", "app_name": "PayHub Core"}
  ]
}
```

### 2. Models — `app/models/artifact.py`

```python
class CbDiscoverQuestion(Base):
    __tablename__ = "cb_discover_questions"
    id                   = Column(UUID, primary_key=True, default=uuid.uuid4)
    artifact_document_id = Column(UUID, ForeignKey("artifact_documents.id"), nullable=False)
    question_key         = Column(String(10), nullable=False)
    category             = Column(String(50), nullable=False)
    question_text        = Column(Text, nullable=False)
    answer               = Column(Text, nullable=True)
    inferred_answer      = Column(Text, nullable=True)
    source               = Column(String(30), nullable=True)
    context_sources      = Column(JSONB, nullable=True)
    seq                  = Column(Integer, nullable=False)
    created_at           = Column(DateTime(timezone=True), server_default=func.now())
    updated_at           = Column(DateTime(timezone=True), onupdate=func.now(),
                                  server_default=func.now())

class CbDiscoverEnhancedBrief(Base):
    __tablename__ = "cb_discover_enhanced_briefs"
    id                   = Column(UUID, primary_key=True, default=uuid.uuid4)
    artifact_document_id = Column(UUID, ForeignKey("artifact_documents.id"), nullable=False)
    original_brief       = Column(Text, nullable=False)
    enhanced_brief       = Column(Text, nullable=False)
    doc_sources          = Column(JSONB, nullable=True)
    app_sources          = Column(JSONB, nullable=True)
    created_at           = Column(DateTime(timezone=True), server_default=func.now())
```

Register both in `app/models/__init__.py`.

### 3. Discover catalog — `app/services/artifacts/discover_catalog.py`

```python
DISCOVER_QUESTIONS: list[dict] = [
    {"key": "1a", "category": "initiative_context",
     "text": "What is the initiative name or working title?"},
    {"key": "1b", "category": "initiative_context",
     "text": "What business problem does this initiative solve?"},
    # ... all 14 ...
]

UNIT_DISCOVER_MAP: dict[str, list[str]] = {
    "problem_context":  ["1a","1b","1c","2a","2b","2c"],
    "value_hypothesis": ["3a","3b"],
    "metrics":          ["3c"],
    "capabilities":     ["4a"],
    "scope":            ["4b","4c"],
    "milestones":       ["5a","5b"],
}

PROJECT_PREFILL: dict[str, callable] = {
    "1a": lambda p: p.name or "",
    "2a": lambda p: p.business_unit or "",
}
```

### 4. DSPy modules — `app/services/skills/dspy_discover.py`

Two modules:

#### 4a. `BriefEnhancerModule`

Synthesises a comprehensive brief from all available context. Called by the ✨ button.

```python
class BriefEnhancerOutput(BaseModel):
    enhanced_brief: str = Field(
        description=(
            "Comprehensive initiative brief (200–400 words) written as flowing prose. "
            "Must address: initiative name and working title, the business problem and "
            "what cannot be done today, the strategic driver (regulatory / competitive / "
            "cost / growth), owning business unit, primary customers and end users, "
            "the as-is situation (what exists today that is insufficient), value the "
            "initiative creates, expected outcomes (qualitative and quantitative), "
            "initial success metrics or KPIs, in-scope capabilities, explicit exclusions, "
            "key assumptions, and known delivery milestones or MVP approach. "
            "Solution-agnostic — describe the problem and desired outcomes, not implementation. "
            "User's own text takes priority; expand and enrich it, never contradict it."
        )
    )

class BriefEnhancerSignature(dspy.Signature):
    """Synthesise a comprehensive initiative brief from project metadata, source documents,
    and app brain context.

    Use the user's text as the primary voice — expand and enrich it from the provided
    document sections and app brain context but never contradict it.
    Ground every claim in [D#] document excerpts or app brain facts where available.
    Be specific and concrete. Keep the brief solution-agnostic.
    Cover all 14 discovery areas so that downstream analysis can extract answers directly.
    """
    project_name:         str = dspy.InputField(desc="Name of the initiative / project")
    business_unit:        str = dspy.InputField(
        desc="Owning business unit or department; '—' if not yet confirmed"
    )
    user_brief:           str = dspy.InputField(
        desc=(
            "Initiative description entered by the user — may be empty, a single sentence, "
            "or a multi-paragraph narrative. Treat as authoritative; do not contradict."
        )
    )
    project_doc_sections: str = dspy.InputField(
        desc=(
            "Relevant excerpts retrieved from project source documents via PageIndex. "
            "Each excerpt is tagged [D#] with the document name and section title, "
            "followed by up to 1000 characters of text. "
            "Value: '(no project documents indexed)' when none are available."
        )
    )
    app_brain_context:    str = dspy.InputField(
        desc=(
            "Structured context from all in-scope application brains: per-app capabilities, "
            "known limitations, integration constraints, existing KPIs, and user segment "
            "information extracted from app documentation. "
            "Value: '(no linked apps)' when no apps are in scope."
        )
    )
    result: BriefEnhancerOutput = dspy.OutputField()
```

Mock: `_load_fixture("discover_enhance_brief")` — returns a canned enhanced brief.

#### 4b. `DiscoverAnalysisModule`

Analyses a (possibly enhanced) brief + document context to auto-answer discovery questions.

```python
class DiscoverAnalysisRow(BaseModel):
    question_key:     str  = Field(
        description="The question key from the input list, e.g. '1a', '2c', '4b'."
    )
    answered:         bool = Field(
        description=(
            "True only if the context clearly and specifically addresses this question "
            "and the extracted answer can stand on its own without user confirmation. "
            "A vague mention, a single word, or an uncertain inference → false. "
            "When in doubt, set false."
        )
    )
    extracted_answer: str  = Field(
        description=(
            "Best verbatim excerpt or ≤2-sentence synthesis drawn from the source layer(s). "
            "When answered=true: the final stored answer — must be specific and complete. "
            "When answered=false: a partial extraction or uncertain hint shown as a "
            "textarea placeholder to guide the user — may be a sentence fragment, an "
            "uncertain inference, or empty string '' if the context is completely silent. "
            "Do not fabricate facts not present in the provided context."
        )
    )
    source:           str  = Field(
        description=(
            "Which context layer provided the answer or hint: "
            "'brief' (from user brief text), "
            "'documents' (from [D#] project document excerpts), "
            "'app_brain' (from app brain context), "
            "'combined' (draws from multiple layers), "
            "or '' (empty string) when extracted_answer is also empty."
        )
    )

class DiscoverAnalysisOutput(BaseModel):
    analyses: list[DiscoverAnalysisRow] = Field(
        description=(
            "Exactly one DiscoverAnalysisRow per entry in questions_json, "
            "in the same order as the input list. "
            "Do not add, skip, or reorder rows."
        )
    )

class DiscoverAnalysisSignature(dspy.Signature):
    """Analyse a project brief and supporting context to determine which discovery
    questions are answered and extract the relevant answers.

    For each question in questions_json, produce one DiscoverAnalysisRow.
    answered=true only when the context explicitly and specifically addresses the question.
    Use conflict resolution priority: user brief > project documents > app brain context.
    Do NOT fabricate. If the context is silent on a question, set answered=false and
    extracted_answer=''.
    """
    project_name:         str = dspy.InputField(desc="Name of the initiative / project")
    business_unit:        str = dspy.InputField(
        desc="Owning business unit or department; '—' if not yet confirmed"
    )
    brief_text:           str = dspy.InputField(
        desc=(
            "User's initiative description — may be original or AI-enhanced. "
            "Highest-priority source; its statements take precedence over documents."
        )
    )
    project_doc_sections: str = dspy.InputField(
        desc=(
            "Relevant excerpts from project source documents retrieved via PageIndex. "
            "Tagged [D#] with document name and section title followed by up to 1000 "
            "characters of text. Second-highest priority source. "
            "Value: '(no project documents indexed)' when none are available."
        )
    )
    app_brain_context:    str = dspy.InputField(
        desc=(
            "Structured context from in-scope application brains: capabilities, known "
            "limitations, integration constraints, existing KPIs, and user segments. "
            "Lowest-priority source — use only when brief and documents are silent. "
            "Value: '(no linked apps)' when no apps are in scope."
        )
    )
    questions_json:       str = dspy.InputField(
        desc=(
            "JSON array of discovery questions to analyse: "
            "[{\"key\": \"1a\", \"text\": \"What is the initiative name?\"}, ...]. "
            "Return exactly one DiscoverAnalysisRow per entry, in the same order."
        )
    )
    result: DiscoverAnalysisOutput = dspy.OutputField()
```

Mock: `_load_fixture("discover_analysis")`.

### 5. Context gathering helpers — `app/services/artifacts/discover.py`

```python
async def _gather_discover_context(
    project: Project,
    brief_text: str,
    db: AsyncSession,
) -> tuple[str, str, list[dict], list[dict]]:
    """
    Returns (project_doc_sections, app_brain_context, doc_sources, app_sources).

    project_doc_sections: PageIndex search over project documents using a
        broad query covering all 14 question areas.

    app_brain_context: existing gather_impacted_apps_context() output.

    doc_sources / app_sources: structured attribution for storage in context_sources.
    """
    # Project documents via PageIndex (same pattern as _retrieve_artifact_sections)
    query = (
        f"{project.name} business problem customers value outcomes "
        f"scope milestones KPI assumptions strategic driver"
    )
    rows = (await db.execute(
        select(DocumentTree, Document.filename)
        .join(Document, Document.id == DocumentTree.document_id)
        .where(DocumentTree.project_id == project.id)
    )).all()

    doc_sources = []
    if rows:
        docs = [IndexedDoc(document_id=t.document_id, doc_name=name,
                           tree=t.tree_json, page_texts=t.page_texts)
                for t, name in rows]
        top_k = get_settings().tree_search_top_k
        sections = await get_corpus_index_provider().tree_search(
            query=query, docs=docs, top_k=top_k * 2  # broader search for discover
        )
        project_doc_sections = "\n\n".join(
            f"[D{i}] {s.doc_name} › {s.title}\n{s.text[:1000]}"
            for i, s in enumerate(sections, 1)
        ) if sections else "(no project documents indexed)"
        doc_sources = [
            {"doc_id": str(s.document_id), "filename": s.doc_name, "section": s.title}
            for s in (sections or [])
        ]
    else:
        project_doc_sections = "(no project documents indexed)"

    # App brain context (existing helper, already used by orchestrator)
    app_brain_context = await gather_impacted_apps_context(project.id, db) or "(no linked apps)"

    # App sources for attribution
    app_rows = (await db.execute(
        select(ProjectApp).where(
            ProjectApp.project_id == project.id,
            ProjectApp.included.is_(True),
        )
    )).scalars().all()
    app_sources = [{"app_id": str(a.app_id), "app_name": a.name} for a in app_rows]

    return project_doc_sections, app_brain_context, doc_sources, app_sources
```

### 6. Discover service functions — `app/services/artifacts/discover.py`

**`enhance_brief(project, brief_text, db)`**
1. Calls `_gather_discover_context()`
2. Runs `BriefEnhancerModule`
3. Persists `CbDiscoverEnhancedBrief` row
4. Returns `{enhanced_brief, doc_sources, app_sources}`

**`analyze_brief(project, brief_text, db)`**
1. Calls `_ensure_document()` → sets `doc.status = "in_discover"`
2. Project-prefills 1a, 2a from `project` fields
3. Calls `_gather_discover_context()`
4. Runs `DiscoverAnalysisModule` on questions 1b-5b
5. Upserts all 14 `CbDiscoverQuestion` rows using this split logic:
   - **answered=true:** `answer = extracted_answer`, `inferred_answer = extracted_answer`, `source` from analysis — question hidden in accordion, generation context ready
   - **answered=false:** `answer = None`, `inferred_answer = extracted_answer` (may be a partial hint or `""`), `source` from analysis — question shown as required textarea with placeholder hint
   - **direct prefills (1a, 2a):** `answer = project field value`, `inferred_answer = same`, `source = "project"` — shown in accordion only if non-empty, else become gap questions
   - `context_sources = {docs: [...], apps: [...]}` on all rows
6. Stores brief as `ArtifactMessage(role="user", meta.is_initial_context=True)`
7. Returns list of `CbDiscoverQuestion`

**`get_questions(project_id, artifact_type, db)`**
Returns current questions + most recent enhanced brief for the document.

**`answer_question(question_id, answer, db)`**
Sets `question.answer`, `question.source = "user"`.

**`complete_discover(project, artifact_type, db)`**
1. Validates all 14 questions have a non-empty `answer` (i.e. `answer is not None and answer.strip() != ""`) — raises 409 with the list of unanswered keys if any gap remains
2. Sets `doc.status = "in_interview"`
3. Builds discover context string using `UNIT_DISCOVER_MAP`
4. Dispatches Celery `generate_concept_brief(project_id, atype, discover_context)`
5. Returns current artifact detail

### 7. Discover context format for DSPy units

Formatted string injected as an additional `discover_context` param to each `generate_unit` call,
filtered to only the questions relevant to that unit via `UNIT_DISCOVER_MAP`:

```
=== Pre-Generation Discovery ===

[Initiative Context]
Q: What is the initiative name or working title?
A: PayHub Settlement  [from: project]

Q: What business problem does this initiative solve?
A: AIA Singapore faces manual reconciliation and settlement delays across premium
   collections, agent commissions, and refunds.  [from: documents · 151012-Press-Release.pdf]

Q: What is driving this initiative?
A: Regulatory compliance and operational cost reduction.  [from: you]

[Business Context]
Q: Which business unit or department owns this?
A: Insurance Operations  [from: project]

Q: Who are the primary customers or end users?
A: Insurance agents, finance teams, and end customers seeking refund payouts.
   [from: app brain · PayHub Core]
...
```

This replaces the current `qa_pairs` input for units (the post-generation clarification Q&A is
appended after it).

### 8. API endpoints — `app/api/artifacts.py`

```python
# ✨ AI Enhance brief — uses project docs + app brain → returns enriched text
POST  /projects/{id}/artifacts/{type}/discover/enhance-brief
      body:  { brief_text: str }
      return: { enhanced_brief: str, doc_count: int, app_count: int,
                doc_sources: [...], app_sources: [...] }

# Analyze brief (+ docs + app brain) → create/refresh discover questions
POST  /projects/{id}/artifacts/{type}/discover/analyze
      body:  { brief_text: str }
      return: { questions: DiscoverQuestionOut[], doc_count: int, app_count: int }

# Get existing questions + last enhanced brief
GET   /projects/{id}/artifacts/{type}/discover
      return: { questions: DiscoverQuestionOut[], enhanced_brief: str | null }

# User answers one question
PATCH /projects/{id}/artifacts/{type}/discover/questions/{question_id}
      body:  { answer: str }
      return: DiscoverQuestionOut

# All answered → trigger generation
POST  /projects/{id}/artifacts/{type}/discover/complete
      return: ArtifactDetailResponse
```

### 9. Orchestrator changes — `app/services/artifacts/orchestrator.py`

- `generate_unit` gets optional `discover_context: str = ""` param
- `discover_context` is prepended to `qa_pairs` inside `generate_unit`
- `generate_all` accepts `discover_context: str | None = None` and passes to each unit
- `_ensure_document` default status stays `"in_interview"` (discover phase sets it explicitly)

### 10. Celery task — `workers/tasks.py`

```python
@celery_app.task
def generate_concept_brief(project_id: str, artifact_type: str,
                            context: str | None = None,
                            discover_context: str | None = None):
    ...
    await generate_all(project, artifact_type, db,
                       context=context, discover_context=discover_context)
```

### 11. Mock fixtures

- `artifact_discover_enhance_brief.json` — canned enhanced brief (~250 words)
- `artifact_discover_analysis.json` — 14 analyses, ~8 answered (mix of sources), ~6 pending; gap questions include a mix of partial hints and empty extractions to exercise both UI paths

```json
// artifact_discover_analysis.json
{
  "analyses": [
    {"question_key":"1a","answered":true, "extracted_answer":"PayHub Settlement","source":"brief"},
    {"question_key":"1b","answered":true, "extracted_answer":"Manual reconciliation and settlement delays across premium collections and refunds.","source":"documents"},
    {"question_key":"1c","answered":false,"extracted_answer":"AIA is facing upcoming regulatory changes from MAS around payment infrastructure.","source":"documents"},
    {"question_key":"2a","answered":false,"extracted_answer":"","source":""},
    {"question_key":"2b","answered":true, "extracted_answer":"Insurance agents, finance teams, and end customers seeking refund payouts.","source":"app_brain"},
    {"question_key":"2c","answered":true, "extracted_answer":"No centralized payment platform; manual processes via spreadsheets and disparate systems.","source":"combined"},
    {"question_key":"3a","answered":false,"extracted_answer":"Reduce settlement time and operational cost of reconciliation.","source":"brief"},
    {"question_key":"3b","answered":true, "extracted_answer":"Reduced reconciliation time by 70%, fewer payment exceptions.","source":"documents"},
    {"question_key":"3c","answered":false,"extracted_answer":"","source":""},
    {"question_key":"4a","answered":true, "extracted_answer":"Automated reconciliation, exception handling, audit ledger, multi-rail payment support.","source":"brief"},
    {"question_key":"4b","answered":false,"extracted_answer":"","source":""},
    {"question_key":"4c","answered":false,"extracted_answer":"Assumes SEPA and domestic ACH rails are available in the target markets.","source":"brief"},
    {"question_key":"5a","answered":false,"extracted_answer":"","source":""},
    {"question_key":"5b","answered":false,"extracted_answer":"Phased delivery is preferred; MVP focuses on reconciliation.","source":"brief"}
  ]
}
```

---

## Frontend

### New types — `lib/types.ts`

```typescript
export type DiscoverSource =
  | 'project' | 'brief' | 'documents' | 'app_brain' | 'combined' | 'ai_enhanced'
  | 'user' | null

export interface DiscoverQuestion {
  id: string
  question_key: string        // "1a", "2b", ...
  category: string            // "initiative_context", ...
  question_text: string
  answer: string | null       // final answer (generation context)
  inferred_answer: string | null   // what was auto-extracted (editable hint)
  source: DiscoverSource
  context_sources: {
    docs: { doc_id: string; filename: string; section: string }[]
    apps: { app_id: string; app_name: string }[]
  } | null
  seq: number
}

export interface DiscoverEnhanceBriefResult {
  enhanced_brief: string
  doc_count: number
  app_count: number
  doc_sources: { doc_id: string; filename: string }[]
  app_sources: { app_id: string; app_name: string }[]
}

// Extend ArtifactDocumentStatus:
export type ArtifactDocumentStatus = 'in_discover' | 'in_interview' | 'generating' | 'validated'
```

### New API calls — `lib/api.ts`

```typescript
enhanceBrief: (projectId, type, briefText) =>
  apiFetch<DiscoverEnhanceBriefResult>(
    `/api/projects/${projectId}/artifacts/${type}/discover/enhance-brief`,
    { method: 'POST', body: JSON.stringify({ brief_text: briefText }) }
  ),

analyzeDiscover: (projectId, type, briefText) =>
  apiFetch<{ questions: DiscoverQuestion[]; doc_count: number; app_count: number }>(
    `/api/projects/${projectId}/artifacts/${type}/discover/analyze`,
    { method: 'POST', body: JSON.stringify({ brief_text: briefText }) }
  ),

getDiscover: (projectId, type) =>
  apiFetch<{ questions: DiscoverQuestion[]; enhanced_brief: string | null }>(
    `/api/projects/${projectId}/artifacts/${type}/discover`
  ),

answerDiscover: (projectId, type, questionId, answer) =>
  apiFetch<DiscoverQuestion>(
    `/api/projects/${projectId}/artifacts/${type}/discover/questions/${questionId}`,
    { method: 'PATCH', body: JSON.stringify({ answer }) }
  ),

completeDiscover: (projectId, type) =>
  apiFetch<ArtifactDetail>(
    `/api/projects/${projectId}/artifacts/${type}/discover/complete`,
    { method: 'POST' }
  ),
```

### State machine — `ArtifactBuilderPanel.tsx`

```
isLoading              → <Skeleton>
status = 'generating'  → <GeneratingProgress>       (unchanged)
status = 'in_discover' → <DiscoverPhase>            (NEW — resume path)
!doc                   → <EmptyState>               (enhanced with ✨ button)
doc exists             → <TwoColumnBuilder>          (add "Discovery Q&A" button)
```

### `<EmptyState>` changes

```
┌──────────────────────────────────────────────────────┐
│                                                       │
│  [sparkles icon]                                      │
│  Generate your Concept Brief                         │
│  "SpecForge synthesises a structured brief from..."  │
│                                                       │
│  ⚡ 2 apps · 1 document   (grounding indicator)      │
│                                                       │
│  Describe your initiative (optional)                 │
│  ┌────────────────────────────────────────────────┐  │
│  │                                                │  │
│  │                                                │  │
│  │                               [✨ AI Enhance] │  │  ← NEW button inside textarea
│  └────────────────────────────────────────────────┘  │
│   ↑ button calls /discover/enhance-brief             │
│     populates textarea with enriched text            │
│     shows "Enhanced using 2 docs + PayHub Core ✓"   │
│                                                       │
│  [Analyze & Continue →]                              │  ← was "Generate"
└──────────────────────────────────────────────────────┘
```

UX for ✨ Enhance:
- Shows spinner while running
- On success: replaces textarea content with enhanced text
- Shows a subtle banner: "✨ Enriched using 1 document + PayHub Core app brain"
- User can edit the enhanced text freely before analyzing
- Calling Enhance again re-runs (user can keep refining)

### `<DiscoverPhase>` component

```typescript
// Props
{
  projectId: string
  artifactType: string
  questions: DiscoverQuestion[]
  docCount: number
  appCount: number
  busy: boolean
  onAnswer: (questionId: string, answer: string) => void    // PATCH (autosave on blur)
  onComplete: () => void                                     // POST /complete
  onBack: () => void
}
```

Layout:
- Header: "🔍 Discovery Questions" + "X of 14 complete" progress chip
- Sub-header: "SpecForge analyzed your brief, 1 document, and 2 apps"
- **Answered section** (collapsible, default collapsed):
  - Each pre-answered question as a read-only row with source badge
  - Source badges: `[project]` grey · `[from document]` blue · `[from app brain]` purple · `[you]` green
  - Click to expand and edit (changes source to "user")
- **Gap questions** (always visible, required):
  - Grouped by category with emoji headers (🎯 🏢 💡 📦 🚀)
  - Each question: label, auto-sized textarea, optional hint text from `inferred_answer`
  - Autosave on blur (PATCH call)
  - Filled → green border, empty → default border
- Footer: [← Back] [Generate Concept Brief →] (disabled until pending_count === 0)

### `<DiscoverQADrawer>` component

Triggered by "Discovery Q&A" button in the top action bar of the generated two-column view.
Slide-in from the right, 400px.

- All 14 questions in category order
- Source badge per answer:
  - `from project` — grey
  - `from document · filename.pdf` — blue (with doc name)
  - `from app brain · AppName` — purple (with app name)
  - `AI enhanced` — emerald
  - `you answered` — accent

---

## Scope of changes

| File | Change type |
|------|-------------|
| `backend/alembic/versions/0017_cb_discover_questions.py` | New migration |
| `backend/app/models/artifact.py` | +2 models (`CbDiscoverQuestion`, `CbDiscoverEnhancedBrief`) |
| `backend/app/models/__init__.py` | Register 2 new models |
| `backend/app/schemas/artifact.py` | +3 schemas (`DiscoverAnalyzeIn`, `DiscoverAnswerIn`, `DiscoverQuestionOut`) |
| `backend/app/services/artifacts/discover_catalog.py` | New — 14 questions, unit map, prefill map |
| `backend/app/services/artifacts/discover.py` | New — 5 service functions + `_gather_discover_context` |
| `backend/app/services/skills/dspy_discover.py` | New — 2 DSPy modules |
| `backend/app/services/llm/fixtures/artifact_discover_enhance_brief.json` | New mock |
| `backend/app/services/llm/fixtures/artifact_discover_analysis.json` | New mock |
| `backend/app/api/artifacts.py` | +5 endpoints |
| `backend/app/services/artifacts/orchestrator.py` | `generate_unit` + `generate_all` accept `discover_context` |
| `backend/workers/tasks.py` | `generate_concept_brief` passes `discover_context` |
| `frontend/lib/types.ts` | `DiscoverQuestion`, `DiscoverSource`, `DiscoverEnhanceBriefResult` |
| `frontend/lib/api.ts` | +5 API calls |
| `frontend/app/components/ArtifactBuilderPanel.tsx` | New states + `<DiscoverPhase>` + `<DiscoverQADrawer>` + ✨ enhance in EmptyState |

**Nothing changes** in: existing DSPy unit logic, two-column builder, row editing, validation,
clarification Q&A panel, export, or any other artifact endpoints.

---

## Key design decisions

1. **✨ Enhance writes to the textarea, not directly to questions.** User always sees and approves
   the enhanced brief before Analyze runs. This keeps them in control.

2. **Analyze uses all three layers simultaneously.** One LLM call receives brief text + project doc
   sections + app brain context. The `source` field records which layer answered each question.

3. **`context_sources` JSONB stores attribution per question.** The drawer can show exactly which
   document section or app contributed to each auto-answer — building trust in the pre-fills.

4. **`inferred_answer` is the hint; `answer` is the final value.** Pre-filled questions start with
   `answer = inferred_answer`. If user edits, `answer` changes but `inferred_answer` is preserved
   for comparison. Source becomes `"user"` on any manual change.

5. **Two separate tables** (`cb_discover_questions` + `cb_discover_enhanced_briefs`). The enhanced
   brief is auditable separately — we store original + enhanced + which sources contributed.

6. **Re-running Analyze is safe.** It upserts questions: preserves `source="user"` answers,
   re-runs inference for non-user-answered questions, refreshes `context_sources`.

7. **Discover context is filtered per DSPy unit.** `UNIT_DISCOVER_MAP` ensures `problem_context`
   only sees questions 1a-2c; `milestones` only sees 5a-5b. Prevents prompt bloat and keeps
   each unit focused.

8. **`in_discover` as a real enum value.** Resumable — if you leave and come back, the discover
   screen reloads from stored questions. Alternative (JSONB flag) was rejected.

---

## UI Design

### State machine diagram

```
ArtifactBuilderPanel renders one of 5 views based on (isLoading, doc, doc.status):

  isLoading = true
        │
        ▼  <Skeleton className="h-64 rounded-xl" />

  isLoading = false, doc = null
        │
        ▼  <EmptyState>           ← ENHANCED: textarea + ✨ Enhance button

  isLoading = false, doc.status = "in_discover"
        │
        ▼  <DiscoverPhase>        ← NEW: guided Q&A before generation

  isLoading = false, doc.status = "generating"
        │
        ▼  <GeneratingProgress>   ← unchanged

  isLoading = false, doc.status ∈ {"in_interview","validated"}
        │
        ▼  <TwoColumnBuilder>     ← unchanged + "Discovery Q&A" button in action bar
                                    + <DiscoverQADrawer> (slide-in, right)
```

---

### Enhanced `<EmptyState>` wireframe

```
┌──────────────────────────────────────────────────────────────┐
│  (vertically centered in flex-1)                             │
│                                                              │
│          ┌──────────────────┐                                │
│          │  ✦ (Sparkles)    │   w-16 h-16 rounded-2xl       │
│          │                  │   bg-[var(--accent-subtle)]    │
│          └──────────────────┘                                │
│                                                              │
│          Generate your Concept Brief                         │
│          text-lg font-semibold text-[var(--text-primary)]    │
│                                                              │
│          SpecForge will synthesize a structured brief…        │
│          text-sm text-[var(--text-secondary)] max-w-md       │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ ⚡ Grounded in 2 in-scope apps · 1 document indexed  │   │
│  └──────────────────────────────────────────────────────┘   │
│  text-xs, border border-[var(--border-default)] rounded-lg   │
│  px-3 py-2 bg-[var(--bg-surface)]                           │
│  (shown when apps > 0 OR doc_count > 0)                     │
│                                                              │
│  Describe your initiative (optional)                         │
│  text-xs font-semibold text-[var(--text-secondary)] mb-1.5   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                                                      │   │
│  │  e.g. We're building a real-time payment gateway…    │   │
│  │                                                      │   │
│  │                               [✨ AI Enhance]        │   │
│  └──────────────────────────────────────────────────────┘   │
│  outer: relative  inner button: absolute bottom-2 right-2   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ ✨ Enhanced using "AIA Press Release.pdf" + PayHub ✓ │   │
│  └──────────────────────────────────────────────────────┘   │
│  (appears after enhance succeeds — hidden by default)       │
│  bg-[var(--accent-subtle)] border-[var(--accent-subtle)]    │
│  rounded-lg px-3 py-2 text-xs text-[var(--accent)]          │
│  flex items-center gap-1.5  animate-fade-in                  │
│                                                              │
│              [  Analyze & Continue →  ]                      │
│              Button size="lg", full accent                   │
│              shows Loader2 + "Analyzing…" while busy         │
└──────────────────────────────────────────────────────────────┘
```

**✨ Enhance button** (positioned inside textarea, bottom-right):
```tsx
// wrapper
<div className="relative w-full max-w-md">
  <textarea
    rows={4}
    className="w-full resize-y rounded-lg border border-[var(--border-default)]
               bg-[var(--bg-surface)] px-3 py-2 pb-9 text-sm
               text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)]
               focus:outline-none focus:ring-2 focus:ring-[var(--accent-ring)]"
  />
  <button
    onClick={handleEnhance}
    disabled={enhancing}
    className="absolute bottom-2 right-2 inline-flex items-center gap-1
               rounded-md border border-[var(--border-default)]
               bg-[var(--bg-surface)] px-2 py-1
               text-[11px] font-medium text-[var(--text-secondary)]
               hover:bg-[var(--bg-elevated)] hover:text-[var(--accent)]
               transition-colors disabled:opacity-50"
  >
    {enhancing
      ? <><Loader2 size={11} className="animate-spin" /> Enhancing…</>
      : <><Sparkles size={11} /> AI Enhance</>}
  </button>
</div>
```

**Post-enhance attribution banner:**
```tsx
{enhanceResult && (
  <div className="flex items-center gap-1.5 w-full max-w-md
                  rounded-lg border border-[var(--accent-subtle)]
                  bg-[var(--accent-subtle)] px-3 py-2
                  text-xs text-[var(--accent)]">
    <CheckCircle2 size={13} className="shrink-0" />
    Enhanced using{' '}
    {enhanceResult.doc_sources.map(d => d.filename).join(', ')}
    {enhanceResult.app_sources.length > 0 && (
      <> + {enhanceResult.app_sources.map(a => a.app_name).join(', ')}</>
    )}
  </div>
)}
```

---

### Source badge design

Used in `<DiscoverPhase>` answered accordion and `<DiscoverQADrawer>`.

| `source` value | Label | Tailwind classes |
|---|---|---|
| `"project"` | `from project` | `bg-[var(--bg-elevated)] text-[var(--text-secondary)] border-[var(--border-default)]` |
| `"brief"` | `from your brief` | `bg-[var(--status-info-bg)] text-[var(--status-info)] border-[var(--status-info-border)]` |
| `"documents"` | `from document` + filename | `bg-[var(--status-info-bg)] text-[var(--status-info)] border-[var(--status-info-border)]` |
| `"app_brain"` | `from app brain` + app name | `bg-purple-50 text-purple-700 border-purple-200` |
| `"combined"` | `multi-source` | `bg-[var(--status-warning-bg)] text-[var(--status-warning)] border-[var(--status-warning-border)]` |
| `"ai_enhanced"` | `AI enhanced` | `bg-[var(--accent-subtle)] text-[var(--accent)] border-[var(--accent-subtle)]` |
| `"user"` | `you answered` | `bg-[var(--status-success-bg)] text-[var(--status-success)] border-[var(--status-success-border)]` |
| `null` | (none) | — |

```tsx
// SourceBadge component (self-contained, ~12 lines)
function SourceBadge({ source, contextSources }: {
  source: DiscoverSource
  contextSources?: DiscoverQuestion['context_sources']
}) {
  const docName = contextSources?.docs?.[0]?.filename?.split('/').pop()
  const appName = contextSources?.apps?.[0]?.app_name

  const map: Record<string, { label: string; cls: string }> = {
    project:     { label: 'from project',    cls: 'bg-[var(--bg-elevated)] text-[var(--text-secondary)] border-[var(--border-default)]' },
    brief:       { label: 'from your brief', cls: 'bg-[var(--status-info-bg)] text-[var(--status-info)] border-[var(--status-info-border)]' },
    documents:   { label: docName ? `doc · ${docName}` : 'from document', cls: 'bg-[var(--status-info-bg)] text-[var(--status-info)] border-[var(--status-info-border)]' },
    app_brain:   { label: appName ? `app · ${appName}` : 'from app brain', cls: 'bg-purple-50 text-purple-700 border-purple-200' },
    combined:    { label: 'multi-source',    cls: 'bg-[var(--status-warning-bg)] text-[var(--status-warning)] border-[var(--status-warning-border)]' },
    ai_enhanced: { label: 'AI enhanced',     cls: 'bg-[var(--accent-subtle)] text-[var(--accent)] border-[var(--accent-subtle)]' },
    user:        { label: 'you answered',    cls: 'bg-[var(--status-success-bg)] text-[var(--status-success)] border-[var(--status-success-border)]' },
  }
  if (!source || !map[source]) return null
  const { label, cls } = map[source]
  return (
    <span className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-medium ${cls}`}>
      {label}
    </span>
  )
}
```

---

### `<DiscoverPhase>` full wireframe

```
┌──────────────────────────────────────────────────────────────────┐
│  FIXED HEADER  (shrink-0, border-b border-[var(--border-default)])│
│                                                                  │
│  🔍 Discovery Questions                     9 of 14 complete ●  │
│  text-base font-semibold                    Badge variant="info"  │
│                                                                  │
│  SpecForge analysed your brief, 1 document, and 2 apps.          │
│  text-xs text-[var(--text-tertiary)] mt-0.5                      │
│                                                                  │
│  ████████████░░░░  9 / 14                                        │
│  w-full h-1.5 rounded-full bg-[var(--bg-sunken)] mt-2           │
│  inner: bg-[var(--accent)] rounded-full transition-[width]       │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  SCROLLABLE BODY  (flex-1 overflow-y-auto p-4 space-y-4)        │
│                                                                  │
│  ▼ 9 answered  ──────────────────────────────────────────────── │
│  <Collapsible defaultOpen={false}>                              │
│  trigger: flex items-center gap-2 w-full py-2                   │
│    ChevronDown/Up size=14, text-xs font-medium text-secondary   │
│                                                                  │
│  [inside accordion, space-y-2]                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ ✓ 1a.  Initiative name                                   │  │
│  │        "PayHub Settlement"          [from project]  [Edit]│  │
│  └──────────────────────────────────────────────────────────┘  │
│  rounded-lg border border-[var(--border-default)]               │
│  bg-[var(--bg-surface)] px-3 py-2.5                            │
│  grid grid-cols-[auto_1fr_auto_auto] gap-2 items-start         │
│  CheckCircle2 size=14 text-[var(--accent)] shrink-0             │
│  question text: text-xs text-[var(--text-secondary)]            │
│  answer: text-sm text-[var(--text-primary)] truncate            │
│  [Edit] button: text-[10px] text-[var(--text-tertiary)]         │
│         hover:text-[var(--accent)] — clicking shows textarea    │
│                                                                  │
│  ─── ❓ 5 gaps to fill ─────────────────────────────────────── │
│  text-xs font-semibold text-[var(--text-secondary)] mb-2        │
│  flex items-center gap-2                                        │
│  divider: flex-1 h-px bg-[var(--border-default)]                │
│                                                                  │
│  [Category header: 🎯 Initiative Context]                       │
│  text-[11px] font-semibold text-[var(--text-tertiary)]          │
│  uppercase tracking-wide mt-3 mb-2                              │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 1c.  What is driving this initiative?                    │  │
│  │      (regulatory, competitive, cost)                     │  │
│  │  ┌──────────────────────────────────────────────────┐   │  │
│  │  │                                                  │   │  │
│  │  │  Hint: "AIA is facing upcoming MAS regulation…" │   │  │
│  │  └──────────────────────────────────────────────────┘   │  │
│  │  textarea placeholder = inferred_answer (greyed)         │  │
│  └──────────────────────────────────────────────────────────┘  │
│  rounded-lg border border-[var(--border-default)]               │
│  bg-[var(--bg-surface)] px-3 py-2.5 space-y-1.5                │
│  question key: text-[10px] text-[var(--text-tertiary)]          │
│  question text: text-xs font-medium text-[var(--text-primary)]  │
│  textarea:                                                       │
│    w-full resize-none rounded border border-[var(--border-default)]│
│    bg-[var(--bg-elevated)] px-2.5 py-1.5                       │
│    text-sm text-[var(--text-primary)]                           │
│    placeholder:text-[var(--text-tertiary)] italic text-xs       │
│    focus:outline-none focus:ring-1 focus:ring-[var(--accent-ring)]│
│    focus:border-[var(--accent)]                                  │
│    answered state: border-[var(--status-success-border)]        │
│                    bg-[var(--status-success-bg)] / 20            │
│    onBlur: autosave → PATCH /discover/questions/:id             │
│                                                                  │
│  (more gap questions, grouped by category…)                     │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  FIXED FOOTER  (shrink-0, border-t border-[var(--border-default)])│
│  flex items-center justify-between px-4 py-3                    │
│                                                                  │
│  [← Back to brief]          [Generate Concept Brief →]          │
│  Button variant="outline"   Button size="default"                │
│  size="sm"                  disabled when pendingCount > 0       │
│                             shows Loader2 while busy             │
│                             tooltip="Answer all X questions…"    │
│                             when disabled                        │
└──────────────────────────────────────────────────────────────────┘
```

**Category headers with emojis:**
```typescript
const CATEGORY_META: Record<string, { emoji: string; label: string }> = {
  initiative_context: { emoji: '🎯', label: 'Initiative Context' },
  business_context:   { emoji: '🏢', label: 'Business Context' },
  value_outcomes:     { emoji: '💡', label: 'Value & Outcomes' },
  scope_assumptions:  { emoji: '📦', label: 'Scope & Assumptions' },
  delivery:           { emoji: '🚀', label: 'Delivery' },
}
```

**Textarea placeholder logic:**
- `inferred_answer` is non-empty → show it as greyed italic placeholder text: *"Hint: AIA is facing upcoming MAS regulation changes…"*
- `inferred_answer` is empty → show the generic question prompt: *"Type your answer…"*
- When the user types, the placeholder disappears; if they clear it, the hint reappears.
- Submitting a gap question pre-fills `answer` from the hint only if the user explicitly edits and blurs. An untouched hint does NOT count as answered.

**Autosave behaviour:** `onBlur` fires PATCH only when the textarea has a non-empty user value; show subtle `Saving…` → `Saved ✓` inline under the textarea using local state (fades out after 1.5s). No toast — avoids noise when tabbing through questions.

**Edit in answered accordion:** clicking [Edit] on a pre-filled answer converts that row from read-only display to an inline textarea. On blur → PATCH + sets `source = "user"` (handled in backend). Source badge updates to `[you answered]` after save.

---

### `<DiscoverQADrawer>` wireframe

Triggered by "Discovery Q&A" button in the two-column action bar. Slides in from the right.

```
                                          ┌────────────────────────┐
  ← (click outside to close)             │  Discovery Q&A      ✕  │
                                          │  text-sm font-semibold  │
  backdrop: fixed inset-0                 │  ─────────────────────  │
  bg-[var(--text-primary)]/20             │                         │
  z-40, onClick → close                  │  🎯 Initiative Context  │
                                          │  text-[11px] uppercase  │
  drawer panel:                           │  tracking-wide          │
  fixed top-0 right-0 h-full             │                         │
  w-[400px] max-w-[90vw]                 │  1a. Initiative name    │
  bg-[var(--bg-surface)]                 │      "PayHub Settlement" │
  border-l border-[var(--border-default)] │      [from project]     │
  shadow-[-4px_0_24px_rgba(0,0,0,0.08)]  │                         │
  z-50                                   │  1b. Business problem   │
  flex flex-col                           │      "Manual reconcilia-│
  transition-transform duration-300      │       tion and settle-  │
  translate-x-0 / translate-x-full       │       ment delays…"     │
                                          │      [doc · Press Rele-]│
                                          │                         │
                                          │  1c. Strategic driver   │
                                          │      "Regulatory and    │
                                          │       cost reduction"   │
                                          │      [you answered]     │
                                          │                         │
                                          │  ─────────────────────  │
                                          │  🏢 Business Context   │
                                          │  ...                    │
                                          │                         │
                                          └────────────────────────┘

Header: flex items-center justify-between px-4 py-3
        border-b border-[var(--border-default)] shrink-0
Body:   flex-1 overflow-y-auto px-4 py-3 space-y-4
Q rows: space-y-3 per category
  each: text-xs text-[var(--text-secondary)] (question)
        text-sm text-[var(--text-primary)] mt-0.5 (answer)
        <SourceBadge> mt-1
  unanswered: text-[var(--text-tertiary)] italic "—"
```

**Trigger button in two-column action bar** (add alongside Validate / Export):
```tsx
<button
  onClick={() => setDiscoverDrawerOpen(true)}
  className="inline-flex items-center gap-1 rounded-lg border border-[var(--border-default)]
             bg-[var(--bg-surface)] px-2.5 py-1.5 text-xs text-[var(--text-secondary)]
             hover:bg-[var(--bg-elevated)] transition-colors"
>
  <Search size={13} />
  Discovery Q&A
</button>
```

---

### Key Tailwind patterns (tokens → utilities cheatsheet)

| Token | Tailwind usage |
|---|---|
| `--accent` | `text-[var(--accent)]` / `bg-[var(--accent)]` / `border-[var(--accent)]` |
| `--accent-subtle` | `bg-[var(--accent-subtle)]` |
| `--accent-ring` | `focus:ring-[var(--accent-ring)]` (with `focus:ring-2`) |
| `--bg-surface` | `bg-[var(--bg-surface)]` (card/panel backgrounds) |
| `--bg-elevated` | `bg-[var(--bg-elevated)]` (hover fills, textarea in question card) |
| `--bg-sunken` | `bg-[var(--bg-sunken)]` (progress track) |
| `--border-default` | `border-[var(--border-default)]` |
| `--border-strong` | `border-[var(--border-strong)]` (on hover) |
| `--text-primary` | `text-[var(--text-primary)]` |
| `--text-secondary` | `text-[var(--text-secondary)]` |
| `--text-tertiary` | `text-[var(--text-tertiary)]` |
| `--status-success-*` | answered/confirmed rows |
| `--status-info-*` | document source badges |
| `--status-warning-*` | combined-source badges |
| Progress fill | `bg-[var(--accent)] h-1.5 rounded-full transition-[width] duration-300` |
| Card row (answered) | `rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-2.5` |
| Card row (gap) | same as above, focus-within: `ring-1 ring-[var(--accent-ring)]` |
| Section divider | `flex-1 h-px bg-[var(--border-default)]` |
| Drawer backdrop | `fixed inset-0 bg-[var(--text-primary)]/20 z-40` |
| Drawer panel | `fixed top-0 right-0 h-full w-[400px] bg-[var(--bg-surface)] border-l border-[var(--border-default)] shadow-[-4px_0_24px_rgba(0,0,0,0.08)] z-50 flex flex-col` |
