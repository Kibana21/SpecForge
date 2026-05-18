Analyse the following extracted requirements and identify missing or ambiguous information that must be clarified before generating specifications.

Extracted requirements:
---
{{ extracted_requirements }}
---

Return a JSON object with key "gaps" containing an array. Each gap must have:
- id: unique string (e.g., "GAP-1")
- question: the clarifying question (plain language)
- category: one of scope | data | security | integration | ux
- severity: one of blocker | major | minor

If there are no gaps, return {"gaps": []}.
