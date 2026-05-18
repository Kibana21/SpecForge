---
name: gemini-image-gen
description: >
  Use this skill whenever the user wants to generate, edit, or manipulate images using
  the Google Gemini API (Imagen / Nano Banana models). Triggers include: "generate an image
  with Gemini", "use Gemini image API", "Imagen API", "Nano Banana model", "gemini image
  generation", "text-to-image with Gemini", "edit image with Gemini", "Gemini 3 image",
  "gemini-3.1-flash-image-preview", "gemini-3-pro-image-preview", or any request to write
  code that calls the Gemini API to produce or edit images. Also use when the user asks
  about aspect ratios, resolution (1K/2K/4K), multi-turn image editing, grounding with
  Google Search, or thinking levels in the context of Gemini image generation.
---

# Gemini Image Generation Skill

## Overview

Google's Gemini API provides native image generation (called **Nano Banana**) via three models:

| Model Name | Model ID | Best For |
|---|---|---|
| Nano Banana 2 | `gemini-3.1-flash-image-preview` | Speed, high-volume, 512–4K, image search grounding |
| Nano Banana Pro | `gemini-3-pro-image-preview` | Professional assets, complex reasoning, high-fidelity text |
| Nano Banana (legacy) | `gemini-2.5-flash-image` | High-volume, low-latency tasks |

All generated images include a **SynthID watermark** automatically.

---

## Key Capabilities

- **Text-to-image**: Generate images from text prompts
- **Image editing**: Provide an image + text prompt to modify it
- **Multi-turn editing**: Chat-style iterative refinement
- **Resolutions**: `512`, `1K`, `2K`, `4K` (uppercase K required; `512` has no K)
- **Aspect ratios**: `1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `16:9`, `21:9`
  - Nano Banana 2 also supports: `1:4`, `4:1`, `1:8`, `8:1`
- **Up to 14 reference images** (mix objects + characters for consistency)
- **Google Search grounding**: Generate images based on real-time info
- **Image Search grounding** (Nano Banana 2 only): Use web images as visual context
- **Thinking mode**: Built-in by default; control with `thinkingLevel` (`minimal` | `high`)

---

## SDK Setup & Authentication

```bash
pip install google-genai pillow        # basic
pip install google-genai google-auth pillow  # service account / ADC
```

Three authentication methods are supported — see `references/authentication.md` for full details.

| Method | When to use |
|---|---|
| **API Key** | Local dev, prototyping, no GCP project |
| **Service Account key file** | CI/CD, containers, no `gcloud` available |
| **Application Default Credentials (ADC)** | GCP runtimes (Cloud Run, GKE, Compute Engine) |

### Quick examples

**API Key (simplest)**
```python
from google import genai
client = genai.Client(api_key="YOUR_KEY")  # or set GOOGLE_API_KEY env var
```

**Service Account key file → Vertex AI**
```python
import os
from google import genai
from google.oauth2.service_account import Credentials

credentials = Credentials.from_service_account_file(
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
    scopes=["https://www.googleapis.com/auth/cloud-platform"],
)
client = genai.Client(
    vertexai=True,
    project=os.environ["GCLOUD_PROJECT_ID"],
    location="us-central1",
    credentials=credentials,
)
```

**From dict / secret manager (no file on disk)**
```python
import json
from google.oauth2.service_account import Credentials

sa_info = json.loads(os.environ["SERVICE_ACCOUNT_JSON"])
credentials = Credentials.from_service_account_info(
    sa_info, scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
client = genai.Client(vertexai=True, project=sa_info["project_id"],
                      location="us-central1", credentials=credentials)
```

**ADC (GCP-managed environments)**
```python
import google.auth
from google import genai

credentials, project_id = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
client = genai.Client(vertexai=True, project=project_id,
                      location="us-central1", credentials=credentials)
```

> **Note:** API keys do NOT work with Vertex AI — Vertex requires OAuth/service account credentials.

### JavaScript
```bash
npm install @google/genai
```
```javascript
import { GoogleGenAI } from "@google/genai";
const ai = new GoogleGenAI({});  // Uses GOOGLE_API_KEY env var
```

---

## 1. Text-to-Image (Basic)

### Python
```python
from google import genai
from google.genai import types
from PIL import Image

client = genai.Client()

response = client.models.generate_content(
    model="gemini-3.1-flash-image-preview",
    contents=["Your prompt here"],
)

for part in response.parts:
    if part.text is not None:
        print(part.text)
    elif part.inline_data is not None:
        image = part.as_image()
        image.save("output.png")
```

### JavaScript
```javascript
import { GoogleGenAI } from "@google/genai";
import * as fs from "node:fs";

const ai = new GoogleGenAI({});
const response = await ai.models.generateContent({
  model: "gemini-3.1-flash-image-preview",
  contents: "Your prompt here",
});

for (const part of response.candidates[0].content.parts) {
  if (part.text) {
    console.log(part.text);
  } else if (part.inlineData) {
    fs.writeFileSync("output.png", Buffer.from(part.inlineData.data, "base64"));
  }
}
```

### REST
```bash
curl -s -X POST \
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image-preview:generateContent" \
  -H "x-goog-api-key: $GOOGLE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [{"parts": [{"text": "Your prompt here"}]}]
  }'
```

---

## 2. Image Editing (Text + Image → Image)

Pass a base64-encoded image alongside your text prompt.

### Python
```python
from PIL import Image

image = Image.open("input.png")
response = client.models.generate_content(
    model="gemini-3.1-flash-image-preview",
    contents=["Edit this image: remove the background", image],
)
```

### JavaScript
```javascript
const base64Image = fs.readFileSync("input.png").toString("base64");
const response = await ai.models.generateContent({
  model: "gemini-3.1-flash-image-preview",
  contents: [
    { text: "Edit this image: remove the background" },
    { inlineData: { mimeType: "image/png", data: base64Image } },
  ],
});
```

---

## 3. Multi-turn (Chat) Editing

Recommended approach for iterative image creation.

### Python
```python
from google.genai import types

chat = client.chats.create(
    model="gemini-3.1-flash-image-preview",
    config=types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
    )
)

response = chat.send_message("Create a logo for AcmeCorp in blue tones")
# Then iterate:
response2 = chat.send_message("Make the font bolder and add a rocket icon")

for part in response2.parts:
    if part.text: print(part.text)
    elif image := part.as_image(): image.save("logo_v2.png")
```

---

## 4. Resolution & Aspect Ratio

```python
response = client.models.generate_content(
    model="gemini-3.1-flash-image-preview",
    contents=["A wide cinematic landscape"],
    config=types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
        image_config=types.ImageConfig(
            aspect_ratio="16:9",   # See supported list above
            image_size="2K"        # "512", "1K", "2K", "4K" — uppercase K required
        ),
    )
)
```

**Important**: Use uppercase `K` — `"1k"` will be rejected. `"512"` has no K suffix.

---

## 5. Google Search Grounding

Generate images based on real-time information (weather, news, stock data, etc.).

```python
response = client.models.generate_content(
    model="gemini-3.1-flash-image-preview",
    contents=["Visualize today's weather in Singapore as a chart with outfit suggestions"],
    config=types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
        image_config=types.ImageConfig(aspect_ratio="16:9"),
        tools=[{"google_search": {}}]
    )
)
```

The response includes `groundingMetadata` with `searchEntryPoint` (HTML to render search chips) and `groundingChunks` (top 3 web sources).

---

## 6. Image Search Grounding (Nano Banana 2 Only)

Lets the model use web images as visual reference context.

```python
response = client.models.generate_content(
    model="gemini-3.1-flash-image-preview",
    contents=["A detailed painting of a resplendent quetzal bird"],
    config=types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        tools=[
            types.Tool(google_search=types.GoogleSearch(
                search_types=types.SearchTypes(
                    web_search=types.WebSearch(),
                    image_search=types.ImageSearch()
                )
            ))
        ]
    )
)
```

**Display requirements when using image search grounding:**
- Must provide a clickable link to the *containing webpage* (not direct image URL)
- Must provide single-click navigation from source image to its webpage
- No intermediate image viewers allowed

---

## 7. Multiple Reference Images (Up to 14)

| Model | Max Objects (high-fidelity) | Max Characters (consistent) |
|---|---|---|
| Nano Banana 2 | 10 | 4 |
| Nano Banana Pro | 6 | 5 |

```python
response = client.models.generate_content(
    model="gemini-3.1-flash-image-preview",
    contents=[
        "An office group photo, everyone is making funny faces.",
        Image.open("person1.png"),
        Image.open("person2.png"),
        Image.open("person3.png"),
    ],
    config=types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
        image_config=types.ImageConfig(aspect_ratio="5:4", image_size="2K"),
    )
)
```

---

## 8. Thinking Mode Control

Thinking is **always on** by default and always billed. You can control level and visibility.

```python
response = client.models.generate_content(
    model="gemini-3.1-flash-image-preview",
    contents=["A futuristic city inside a giant glass bottle in space"],
    config=types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        thinking_config=types.ThinkingConfig(
            thinking_level="High",       # "minimal" (default, low latency) or "High"
            include_thoughts=True        # whether to return thought images in response
        ),
    )
)

for part in response.parts:
    if part.thought:
        continue  # Skip thought images if not needed
    elif image := part.as_image():
        image.save("output.png")
```

**Note**: `thinking_level` is only available on Nano Banana 2 (`gemini-3.1-flash-image-preview`).

---

## 9. Thought Signatures (Multi-turn with Thinking)

When using thinking models in multi-turn conversations, always pass thought signatures back:

- All `inline_data` image parts in responses have a `thought_signature` field
- The first non-thought text part also has a signature
- Pass them back unchanged in conversation history
- If using the official Google Gen AI SDK chat feature, this is handled **automatically**

---

## Prompting Best Practices

See `references/prompting-guide.md` for detailed templates. Core principle:

> **Describe the scene narratively — don't just list keywords.** A descriptive paragraph produces far better results than a comma-separated list of adjectives.

Quick templates by use case:
- **Photorealistic**: mention shot type, lens, lighting, mood, orientation
- **Stickers/icons**: specify style, outlines, shading, "white background" (no transparent bg support)
- **Text in images**: specify font style descriptively, overall design, color scheme
- **Product shots**: lighting setup (e.g. three-point softbox), camera angle, key detail
- **Logos**: shape, color scheme, font style, any symbolic element

---

## Common Errors & Fixes

| Issue | Fix |
|---|---|
| `"1k" rejected` | Use uppercase: `"1K"`, `"2K"`, `"4K"` |
| No image in response | Ensure `response_modalities` includes `"IMAGE"` |
| Thought signatures error in multi-turn | Pass full response object back to chat history (SDK handles auto) |
| Image search grounding not working | Only available on `gemini-3.1-flash-image-preview` |
| Transparent background requested | Not supported — use white background instead |

---

## Reference Files

- `references/authentication.md` — Service account, ADC, API key setup; IAM roles; token refresh; scope reference
- `references/prompting-guide.md` — Detailed prompt templates for 8 image styles
