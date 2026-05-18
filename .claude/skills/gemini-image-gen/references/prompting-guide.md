# Gemini Image Generation — Prompting Guide

Core principle: **Describe the scene, don't list keywords.** A narrative paragraph beats a keyword list every time.

---

## 1. Photorealistic Scenes

**Template:**
```
A photorealistic [shot type] of [subject], [action/expression], set in [environment].
The scene is illuminated by [lighting], creating a [mood] atmosphere.
Captured with a [camera/lens], emphasizing [key textures/details].
[Aspect ratio or orientation].
```

**Example:**
```
A photorealistic close-up portrait of an elderly Japanese ceramicist with deep,
sun-etched wrinkles and a warm, knowing smile. He is carefully inspecting a freshly
glazed tea bowl in his rustic, sun-drenched workshop. The scene is illuminated by
soft, golden hour light streaming through a window. Captured with an 85mm portrait
lens with soft bokeh. Serene, masterful mood. Vertical portrait orientation.
```

**Tips:** Camera angle, lens type, lighting type, mood keyword, orientation.

---

## 2. Stylized Illustrations & Stickers

**Template:**
```
A [style] sticker of a [subject], featuring [key characteristics] and a [color palette].
The design should have [line style] and [shading style]. The background must be white.
```

**Example:**
```
A kawaii-style sticker of a happy red panda wearing a tiny bamboo hat, munching
on a green bamboo leaf. Bold, clean outlines, simple cel-shading, vibrant colors.
The background must be white.
```

**Tips:** 
- Always say "background must be white" — transparent backgrounds are NOT supported
- Specify art style explicitly: kawaii, flat design, isometric, pixel art, watercolor, etc.

---

## 3. Accurate Text in Images

**Template:**
```
Create a [image type] for [brand/concept] with the text "[text to render]" in a
[font style description]. The design should be [style], with a [color scheme].
```

**Example:**
```
Create a modern, minimalist logo for a coffee shop called 'The Daily Grind'.
Clean, bold sans-serif font. Black and white color scheme. Circular shape.
A coffee bean integrated cleverly into the design.
```

**Tips:**
- Use **Nano Banana Pro** (`gemini-3-pro-image-preview`) for professional text rendering
- Describe font style (e.g. "bold serif", "condensed sans-serif") rather than font names
- Keep text content short and specific

---

## 4. Product Mockups & Commercial Photography

**Template:**
```
A high-resolution, studio-lit product photograph of [product description] on
[background/surface]. Lighting: [setup, e.g., three-point softbox] to [purpose].
Camera angle: [angle] to showcase [feature]. Ultra-realistic, sharp focus on [detail].
[Aspect ratio].
```

**Example:**
```
A high-resolution, studio-lit product photograph of a minimalist ceramic coffee
mug in matte black, on a polished concrete surface. Three-point softbox lighting
for soft, diffused highlights with no harsh shadows. Slightly elevated 45-degree
shot to showcase clean lines. Ultra-realistic, sharp focus on the rising steam.
Square image.
```

---

## 5. Minimalist & Negative Space Design

**Template:**
```
A minimalist composition featuring a single [subject] placed [position] on a
[solid color] background. [Style description]. Vast empty space for text overlay.
[Aspect ratio].
```

**Example:**
```
A minimalist composition featuring a single white origami crane placed in the
lower-left corner of a deep navy blue background. Clean, modern, elegant.
Vast empty space on the right for text overlay. 16:9 landscape.
```

---

## 6. Style Transfer / Mixed Styles

**Template:**
```
A [realistic/photo] scene of [subject and setting] where [style detail 1] and
[style detail 2] coexist. [Specific style mixing instructions].
```

**Example:**
```
A photo of an everyday scene at a busy café serving breakfast.
In the foreground is an anime man with blue hair, one of the people is
a pencil sketch, another is a claymation person. Photorealistic background.
```

---

## 7. Infographics & Data Visualization

Great for grounding-enabled prompts. Works best with Google Search tool enabled.

**Example:**
```
Create a vibrant infographic that explains photosynthesis as if it were a recipe
for a plant's favorite food. Show the "ingredients" (sunlight, water, CO2) and
the "finished dish" (sugar/energy). Style like a colorful kids' cookbook, suitable
for a 4th grader.
```

**With search grounding (weather/news):**
```
Visualize the current 5-day weather forecast for Singapore as a clean, modern
weather chart. Add a visual suggestion of what to wear each day.
```
*(Use `tools=[{"google_search": {}}]` in config)*

---

## 8. High-Fidelity Detail Preservation

For Nano Banana Pro. Best for integrating logos or brand assets into scenes.

**Example:**
```
Put this logo on a high-end ad for a bamboo-scented perfume bottle.
The logo must be perfectly integrated into the bottle's label, preserving
every detail of the original design.
```
*(Pass the logo image as a reference image alongside the prompt)*

---

## General Prompting Dos & Don'ts

| Do | Don't |
|---|---|
| Write full descriptive sentences | List keywords: "sunset, dramatic, orange, moody" |
| Specify lighting setup | Leave lighting implicit |
| Name the aspect ratio or orientation | Let it default when you have a specific need |
| Use `white background` for stickers | Ask for transparent background (unsupported) |
| Use Nano Banana Pro for text-heavy images | Use Flash for professional typography work |
| Control aspect ratio via `image_config` | Try to control it through prompt text alone |
