# Authentication — Vertex AI via Service Account

## Project credential factory

All Google API clients must use the singleton factory instead of loading keys directly:

```python
# app/core/google_credentials.py  (already exists — do not recreate)
from functools import lru_cache
from google.oauth2 import service_account

_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

@lru_cache(maxsize=1)
def get_google_credentials() -> service_account.Credentials:
    from app.config import get_settings
    settings = get_settings()
    return service_account.Credentials.from_service_account_file(
        settings.google_service_account_path,
        scopes=_SCOPES,
    )
```

Config key: `GOOGLE_SERVICE_ACCOUNT_PATH` → `settings.google_service_account_path`  
Key file: `video-key.json` at repo root (set in `.env`)

## Using credentials in a new client

```python
from app.core.google_credentials import get_google_credentials

creds = get_google_credentials()

# LLM
from langchain_google_genai import ChatGoogleGenerativeAI
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", credentials=creds, project="...")

# Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
embedder = GoogleGenerativeAIEmbeddings(model="text-embedding-004", credentials=creds)
```

## Backend selection logic

`langchain-google-genai` automatically selects Vertex AI when **either** `credentials=` **or** `project=` is provided. No separate `vertexai=True` flag is needed.

## Environment variables (for reference only — set in .env)

| Variable | Purpose |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_PATH` | Path to service account JSON key |
| `GEMINI_PROJECT_ID` | GCP project ID |
| `GEMINI_LOCATION` | GCP region (default `us-central1`) |
| `GEMINI_MODEL` | Model name (default `gemini-2.5-flash`) |
| `LLM_PROVIDER` | `gemini` or `mock` |
