"""Project Copilot — the codebase's first dspy.ReAct agent.

Tools navigate the project's PageIndex trees, wiki concepts, and app facts.
The signature's docstring is the agent's system prompt; keep it precise.
"""
import dspy


class ProjectChatSignature(dspy.Signature):
    """Answer the user's question about THIS project using ONLY the tools and seed_context.

    CRITICAL RULES — follow exactly:
    1. NEVER call any tool with an empty string argument. Every argument must be a
       real non-empty value copied from seed_context or a previous tool result.
    2. Read seed_context first — it already contains the most relevant sections and
       concepts. Use read_section/read_concept to deepen those specific results.
    3. Use EXACT ids from tool output (e.g. 'S:abc123:0007'); never guess or invent.
    4. Cite EVERY claim inline: S:<doc_id>:<node_id> (section), C:<slug> (concept),
       F:<id> (fact). If the knowledge base does not cover the question, say so."""

    project_name: str = dspy.InputField()
    seed_context: str = dspy.InputField(
        desc="Pre-retrieved candidate sections/concepts to verify and expand"
    )
    conversation: str = dspy.InputField(desc="Prior chat turns, or empty string")
    question: str = dspy.InputField()
    answer: str = dspy.OutputField(
        desc="Markdown answer with inline S:/C:/F: citation tokens"
    )


def build_react(tools: list, max_iters: int = 4) -> dspy.ReAct:
    return dspy.ReAct(ProjectChatSignature, tools=tools, max_iters=max_iters)
