"""Project Copilot — the codebase's first dspy.ReAct agent.

Tools navigate the project's PageIndex trees, wiki concepts, and app facts.
The signature's docstring is the agent's system prompt; keep it precise.
"""
import dspy


class ProjectChatSignature(dspy.Signature):
    """Answer the user's question about THIS project using ONLY the tools provided and
    the pre-retrieved seed_context. Verify and expand the seed: open sections with
    read_section, pull concepts with read_concept, check systems with lookup_facts.
    Prefer specific leaf sections over broad summaries. Ground EVERY claim with an
    inline citation token — S:<doc_id>:<node_id> for a source section, C:<slug> for
    a wiki concept, F:<id> for an app fact. Copy ids verbatim from tool output; never
    invent ids or tokens. If the knowledge base does not cover the question, say so
    plainly and do not guess."""

    project_name: str = dspy.InputField()
    seed_context: str = dspy.InputField(
        desc="Pre-retrieved candidate sections/concepts to verify and expand"
    )
    conversation: str = dspy.InputField(desc="Prior chat turns, or empty string")
    question: str = dspy.InputField()
    answer: str = dspy.OutputField(
        desc="Markdown answer with inline S:/C:/F: citation tokens"
    )


def build_react(tools: list, max_iters: int = 6) -> dspy.ReAct:
    return dspy.ReAct(ProjectChatSignature, tools=tools, max_iters=max_iters)
