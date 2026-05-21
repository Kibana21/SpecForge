---
name: langchain-gemini
description: >
  LangChain + LangGraph + Google Gemini via Vertex AI (service account auth). Use when writing
  code that calls ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings, or LangGraph agents/workflows
  in this project. Covers: service account credential setup, LLM invocation, streaming, structured
  output, tool/function calling, embedding, and LangGraph state-machine agents. Triggers on:
  "use langchain gemini", "ChatGoogleGenerativeAI", "LangGraph", "LangChain agent", "Gemini tool calling",
  "Vertex AI with service account", "GoogleGenerativeAIEmbeddings", "add a new LangChain skill",
  "build a LangGraph workflow".
---

# LangChain + LangGraph + Gemini (Vertex AI)

## Project conventions

- **Package**: `langchain-google-genai` (not `langchain-google-vertexai` — deprecated)
- **Credentials**: always use `app.core.google_credentials.get_google_credentials()` — never load service account files directly in feature code
- **LLM**: `ChatGoogleGenerativeAI`, accessed via `app.services.llm.get_provider()` which returns `GeminiProvider` in production and `MockProvider` in tests
- **Embeddings**: `GoogleGenerativeAIEmbeddings`, accessed via `app.services.embeddings.get_embedding_provider()`
- **Model**: `gemini-2.5-flash` (from `settings.gemini_model`)
- **Backend**: passing `credentials=` to `ChatGoogleGenerativeAI` automatically routes to Vertex AI — no extra flags needed

## Reference files

Load the relevant file for the task at hand:

| Task | File |
|---|---|
| Service account setup, credential factory | [references/auth.md](references/auth.md) |
| LLM invocation, streaming, tool calling, structured output | [references/chat.md](references/chat.md) |
| Text embeddings | [references/embeddings.md](references/embeddings.md) |
| LangGraph agents and multi-step workflows | [references/langgraph.md](references/langgraph.md) |

## Quick decision guide

- Adding a new skill (prompt template → LLM call → parsed response)? → read `references/chat.md`, follow existing `SkillEngine` pattern in `app/services/skills/`
- Building a multi-step agent that loops, calls tools, or has conditional branches? → read `references/langgraph.md`
- Adding a new embedding use case? → read `references/embeddings.md`
- Credential or auth questions? → read `references/auth.md`
