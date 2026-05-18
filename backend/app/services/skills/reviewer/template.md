Review the following specifications for "{{ project_name }}" and return actionable feedback.

Functional Specification:
---
{{ functional_spec }}
---

Technical Specification:
---
{{ technical_spec }}
---

User Stories:
---
{{ user_stories }}
---

Extracted Requirements (source of truth):
---
{{ extracted_requirements }}
---

Return a JSON object with key "comments" containing an array. Each comment must have:
- id: string (e.g., "REV-1")
- section: string — the specific section being referenced
- comment: string — actionable feedback
- severity: one of critical | warning | suggestion
- category: one of completeness | ambiguity | security | data | implementation
