"""DSPy-based Brain Wiki compiler — production path (non-mock only).

Three modules compile a corpus document into wiki artifacts, mirroring OpenKB:
  - DocSummaryModule   : document → per-doc summary page (+ candidate concepts)
  - ConceptPlanModule  : summary + existing concept briefs → {create, update, related}
  - ConceptPageModule  : topic + document + tree outline → free-form concept page
                         with section-level tree_node_refs into the PageIndex tree

Topics are EMERGENT (not a fixed taxonomy). Pages are free-form prose. Each
concept cites the PageIndex node_ids that ground its claims; the caller
validates those against the real tree (whitelist), like OpenKB's wikilink guard.
"""
import asyncio
import logging
from typing import Literal

import dspy
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


# ── Output models ───────────────────────────────────────────────────────────────

class DocSummaryOut(BaseModel):
    brief: str = Field(description="One sentence (<120 chars) describing the document")
    content_md: str = Field(description="Markdown summary of the document's key content")
    candidate_concepts: list[str] = Field(
        default_factory=list,
        description="Free-form cross-document topic names this document suggests",
    )


class ConceptAction(BaseModel):
    slug: str = Field(description="snake_case, URL-safe concept identifier")
    title: str = Field(description="Human-readable concept title")


class ConceptPlanOut(BaseModel):
    create: list[ConceptAction] = Field(default_factory=list)
    update: list[ConceptAction] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list, description="Existing slugs to cross-link only")


class TreeNodeRefOut(BaseModel):
    node_id: str = Field(description="A node_id from the provided document outline")
    title: str = Field(default="", description="The section title for that node")


class ConceptPageOut(BaseModel):
    brief: str = Field(description="One sentence (<120 chars) defining the concept")
    content_md: str = Field(description="Free-form Markdown knowledge page for this topic")
    related_slugs: list[str] = Field(
        default_factory=list, description="Other concept slugs to cross-link (from whitelist)"
    )
    tree_node_refs: list[TreeNodeRefOut] = Field(
        default_factory=list,
        description="PageIndex node_ids (from the outline) that ground this page's claims",
    )


# ── Signatures ──────────────────────────────────────────────────────────────────

class DocSummarySignature(dspy.Signature):
    """Summarise a software-system document for an application knowledge base.

    Write a clear, faithful summary of what THIS document says about the system —
    its capabilities, behaviours, constraints, integrations, and any non-obvious
    details. Then suggest candidate cross-document topics (free-form themes, not a
    fixed taxonomy) that this document contributes to and that could become shared
    concept pages across the application's corpus.
    """

    app_name: str = dspy.InputField()
    doc_name: str = dspy.InputField()
    source_text: str = dspy.InputField(desc="The document's markdown text or a structured outline of its sections")
    summary: DocSummaryOut = dspy.OutputField()


class ConceptPlanSignature(dspy.Signature):
    """Decide how a new document changes the application's wiki concept pages.

    Concepts are EMERGENT themes that span multiple documents — never a fixed
    category list. Given the new document's summary and the briefs of concepts
    that already exist, return:
      - create:  genuinely new topics no existing concept covers
      - update:  existing concepts this document materially enriches
      - related: existing concepts only tangentially relevant (cross-link, no rewrite)
    Do not duplicate an existing concept with a near-identical new one — prefer update.
    For the first one or two documents, create only 2-4 foundational concepts.
    """

    app_name: str = dspy.InputField()
    doc_summary: str = dspy.InputField()
    existing_concept_briefs: str = dspy.InputField(desc="Lines of '- slug: brief', or '(none yet)'")
    plan: ConceptPlanOut = dspy.OutputField()


class ConceptPageSignature(dspy.Signature):
    """Write or revise a free-form wiki knowledge page for one application topic.

    Synthesise what the source document contributes to this topic into a clear,
    well-structured Markdown page. Use whatever section structure best fits the
    topic — do NOT force a fixed template. Ground every claim in the document.

    IMPORTANT — content_md must read like a clean knowledge article for a human.
    Do NOT begin content_md by repeating the topic title as a heading — the page
    already displays the title and the brief above the body, so start directly with
    the explanatory content (subsection headings within are fine). Keep `brief` a
    crisp one-sentence abstract of the whole page, distinct from the opening
    paragraph (don't just restate it). NEVER write node ids, "(node_id: ...)",
    page numbers, or any internal section identifiers inside content_md. Section
    grounding belongs ONLY in the separate tree_node_refs field: list there the
    node_ids from the provided outline that support this page. Only cross-link related concepts whose slug appears in the
    provided whitelist; never invent slugs or node_ids. If revising existing content,
    integrate the new information
    naturally rather than appending.
    """

    app_name: str = dspy.InputField()
    topic_title: str = dspy.InputField()
    topic_description: str = dspy.InputField()
    doc_name: str = dspy.InputField()
    source_text: str = dspy.InputField(desc="Document markdown or section outline")
    tree_outline: str = dspy.InputField(desc="Lines of '<node_id> · <title> — <summary>' for citing node_ids")
    valid_concept_slugs: str = dspy.InputField(desc="Whitelist of slugs allowed in related_slugs")
    existing_content: str = dspy.InputField(desc="Current page content to revise, or '(new page)'")
    page: ConceptPageOut = dspy.OutputField()


# ── Modules ─────────────────────────────────────────────────────────────────────

class DocSummaryModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(DocSummarySignature)

    def forward(self, app_name: str, doc_name: str, source_text: str) -> dict:
        if not source_text or not source_text.strip():
            return {"brief": "", "content_md": "", "candidate_concepts": []}
        try:
            result = self.predict(app_name=app_name, doc_name=doc_name, source_text=source_text)
            return result.summary.model_dump()
        except Exception as exc:
            log.error("dspy doc_summary failed for %s: %s", doc_name, exc, exc_info=True)
            return {"brief": "", "content_md": "", "candidate_concepts": []}


class ConceptPlanModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(ConceptPlanSignature)

    def forward(self, app_name: str, doc_summary: str, existing_concept_briefs: str) -> dict:
        try:
            result = self.predict(
                app_name=app_name,
                doc_summary=doc_summary,
                existing_concept_briefs=existing_concept_briefs,
            )
            return result.plan.model_dump()
        except Exception as exc:
            log.error("dspy concept_plan failed: %s", exc, exc_info=True)
            return {"create": [], "update": [], "related": []}


class ConceptPageModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(ConceptPageSignature)

    def forward(
        self,
        app_name: str,
        topic_title: str,
        topic_description: str,
        doc_name: str,
        source_text: str,
        tree_outline: str,
        valid_concept_slugs: str,
        existing_content: str,
    ) -> dict:
        try:
            result = self.predict(
                app_name=app_name,
                topic_title=topic_title,
                topic_description=topic_description,
                doc_name=doc_name,
                source_text=source_text,
                tree_outline=tree_outline,
                valid_concept_slugs=valid_concept_slugs,
                existing_content=existing_content,
            )
            return result.page.model_dump()
        except Exception as exc:
            log.error("dspy concept_page failed for %s: %s", topic_title, exc, exc_info=True)
            return {"brief": "", "content_md": "", "related_slugs": [], "tree_node_refs": []}


# ── Public async entrypoints (thread-executor, Celery-safe) ──────────────────────

async def run_doc_summary(app_name: str, doc_name: str, source_text: str) -> dict:
    from app.services.skills.fact_extractor.dspy_extractor import _configure_dspy
    _configure_dspy()
    module = DocSummaryModule()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, module, app_name, doc_name, source_text)


async def run_concept_plan(app_name: str, doc_summary: str, existing_concept_briefs: str) -> dict:
    from app.services.skills.fact_extractor.dspy_extractor import _configure_dspy
    _configure_dspy()
    module = ConceptPlanModule()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, module, app_name, doc_summary, existing_concept_briefs)


async def run_concept_page(
    app_name: str,
    topic_title: str,
    topic_description: str,
    doc_name: str,
    source_text: str,
    tree_outline: str,
    valid_concept_slugs: str,
    existing_content: str,
) -> dict:
    from app.services.skills.fact_extractor.dspy_extractor import _configure_dspy
    _configure_dspy()
    module = ConceptPageModule()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, module, app_name, topic_title, topic_description, doc_name,
        source_text, tree_outline, valid_concept_slugs, existing_content,
    )


# ── Concept selection (Deep Search retrieval) ───────────────────────────────────

class ConceptSelection(BaseModel):
    concept_slugs: list[str] = Field(default_factory=list)
    doc_ids: list[str] = Field(default_factory=list)


class ConceptSelectSignature(dspy.Signature):
    """Select which compiled knowledge-base pages are relevant to a question.

    Prefer concept pages (they synthesise across documents); add document
    summaries only when a specific document is clearly central. Pick up to 5
    concept slugs and up to 3 doc ids. Use only slugs/ids that appear in the
    inputs — never invent values. Return empty lists when nothing is relevant.
    """

    question: str = dspy.InputField()
    concepts_outline: str = dspy.InputField(desc="lines of 'slug · Title — brief'")
    summaries_outline: str = dspy.InputField(desc="lines of 'doc_id · Name — brief'")
    selection: ConceptSelection = dspy.OutputField()


class ConceptSelectModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.Predict(ConceptSelectSignature)

    def forward(self, question: str, concepts_outline: str, summaries_outline: str) -> dict:
        try:
            result = self.predict(
                question=question,
                concepts_outline=concepts_outline,
                summaries_outline=summaries_outline,
            )
            return result.selection.model_dump()
        except Exception as exc:
            log.error("dspy concept_select failed: %s", exc, exc_info=True)
            return {"concept_slugs": [], "doc_ids": []}


async def run_concept_select(question: str, concepts_outline: str, summaries_outline: str) -> dict:
    from app.config import get_settings
    if get_settings().llm_provider == "mock":
        return {"concept_slugs": [], "doc_ids": []}
    from app.services.skills.fact_extractor.dspy_extractor import _configure_dspy
    _configure_dspy()
    module = ConceptSelectModule()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, module, question, concepts_outline, summaries_outline)


# ── Wiki health lint (contradictions) ───────────────────────────────────────────

class ConceptForLint(BaseModel):
    slug: str
    title: str
    content_md: str


class Contradiction(BaseModel):
    concept_a: str
    concept_b: str
    issue: str = Field(description="One sentence naming both conflicting claims")
    severity: Literal["critical", "warning"] = "warning"


class WikiLintResult(BaseModel):
    contradictions: list[Contradiction] = Field(default_factory=list)


class WikiLintSignature(dspy.Signature):
    """Find contradictions across an application's wiki concept pages.

    A contradiction is a pair of concepts making claims that cannot both be true
    about the same system (e.g. 500 vs 1000 TPS; exactly-once vs at-least-once;
    feature exists vs unsupported). Only report genuine, specific conflicts
    grounded in the text — never invent disagreements or flag mere differences in
    topic. Reference concepts by their exact slug. Return an empty list if none.
    """

    app_name: str = dspy.InputField()
    concepts: list[ConceptForLint] = dspy.InputField()
    result: WikiLintResult = dspy.OutputField()


class WikiLintModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(WikiLintSignature)

    def forward(self, app_name: str, concepts: list[ConceptForLint]) -> dict:
        try:
            result = self.predict(app_name=app_name, concepts=concepts)
            return result.result.model_dump()
        except Exception as exc:
            log.error("dspy wiki_lint failed: %s", exc, exc_info=True)
            return {"contradictions": []}


async def run_wiki_lint(app_name: str, concepts: list[ConceptForLint]) -> dict:
    from app.config import get_settings
    if get_settings().llm_provider == "mock":
        return {"contradictions": []}
    from app.services.skills.fact_extractor.dspy_extractor import _configure_dspy
    _configure_dspy()
    module = WikiLintModule()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, module, app_name, concepts)
