# Gemini API Authentication Guide

There are three ways to authenticate with `google-genai`, depending on your deployment context.

---

## Method 1 — API Key (Simplest, Google AI Studio route)

Best for: local dev, prototyping, non-GCP environments.

```bash
pip install google-genai
```

```python
import os
from google import genai

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
```

Or set the env var and the client picks it up automatically:
```bash
export GOOGLE_API_KEY="your-key-here"
```
```python
client = genai.Client()  # auto-reads GOOGLE_API_KEY
```

**Note:** API keys do NOT work with Vertex AI endpoints — they require OAuth/service account credentials.

---

## Method 2 — Service Account Key File (Production, no gcloud required)

Best for: production apps, CI/CD pipelines, containers, anywhere `gcloud` isn't installed.

```bash
pip install google-genai google-auth
```

### Via Vertex AI (recommended for enterprise/GCP)

```python
import os
from google import genai
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

credentials = Credentials.from_service_account_file(
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"],  # path to your JSON key file
    scopes=SCOPES,
)

client = genai.Client(
    vertexai=True,
    project=os.environ["GCLOUD_PROJECT_ID"],
    location=os.environ.get("GCLOUD_LOCATION", "us-central1"),
    credentials=credentials,
)
```

### Via Google AI Studio (Gemini API, non-Vertex)

```python
import os
from google import genai
from google.oauth2 import service_account

SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/generative-language.retriever",
]

credentials = service_account.Credentials.from_service_account_file(
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
    scopes=SCOPES,
)

client = genai.Client(credentials=credentials)
```

### From a dict / secret manager (no file on disk)

```python
import json
from google.oauth2.service_account import Credentials

# Load from env var, secret manager, or vault — not from a file
sa_info = json.loads(os.environ["SERVICE_ACCOUNT_JSON"])

credentials = Credentials.from_service_account_info(
    sa_info,
    scopes=["https://www.googleapis.com/auth/cloud-platform"],
)

client = genai.Client(
    vertexai=True,
    project=sa_info["project_id"],
    location="us-central1",
    credentials=credentials,
)
```

**Important:** Google discourages long-lived service account key files due to security risk. Prefer Workload Identity or ADC in GCP-managed environments.

---

## Method 3 — Application Default Credentials (ADC)

Best for: GCP-managed environments (Cloud Run, GKE, Cloud Functions, Compute Engine, Cloud Shell). No key file needed — the runtime identity is used automatically.

```bash
pip install google-genai google-auth
```

```python
import google.auth
from google import genai

# ADC is resolved automatically from the environment:
# - GCP runtimes: uses the attached service account
# - Local: uses credentials set by `gcloud auth application-default login`
credentials, project_id = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)

client = genai.Client(
    vertexai=True,
    project=project_id,
    location="us-central1",
    credentials=credentials,
)
```

**On GCP runtimes (Cloud Run, GKE, etc.)**, you don't even need the explicit credentials call — just:

```python
client = genai.Client(
    vertexai=True,
    project="your-project-id",
    location="us-central1",
    # credentials auto-resolved from attached service account
)
```

### Local dev with ADC

```bash
gcloud auth application-default login \
  --scopes="https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/generative-language.retriever"
```

Then in code:
```python
client = genai.Client(vertexai=True, project="your-project-id", location="us-central1")
```

---

## Token Refresh (long-running processes)

Service account tokens expire after 1 hour. For long-running apps, use `google.auth.transport.requests.Request` to refresh:

```python
from google.auth.transport.requests import Request

def get_refreshed_client():
    credentials = Credentials.from_service_account_file(
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    # Force a refresh to get a valid token
    credentials.refresh(Request())
    return genai.Client(
        vertexai=True,
        project=os.environ["GCLOUD_PROJECT_ID"],
        location="us-central1",
        credentials=credentials,
    )
```

---

## Required IAM Roles

For the service account to call Gemini image generation, it needs one of:

| Role | Use Case |
|---|---|
| `roles/aiplatform.user` | Vertex AI route (recommended minimum) |
| `roles/ml.developer` | Broader ML access |
| `roles/generativelanguage.user` | Google AI Studio / Gemini API route |

Grant via:
```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_SA@YOUR_PROJECT.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

---

## Which Method to Use?

| Environment | Recommended |
|---|---|
| Local development / prototyping | API Key or ADC (`gcloud auth application-default login`) |
| CI/CD pipeline (GitHub Actions, etc.) | Service account key file (stored as secret) |
| Cloud Run / GKE / Compute Engine | ADC (attach service account to the resource) |
| Container without GCP runtime | Service account key from secret manager |
| AIA / enterprise GCP project | ADC with attached service account (no key file) |

---

## OAuth Scopes Reference

| Scope | When Required |
|---|---|
| `https://www.googleapis.com/auth/cloud-platform` | Vertex AI route (always required) |
| `https://www.googleapis.com/auth/generative-language.retriever` | Google AI Studio route, fine-tuning, semantic retrieval |
