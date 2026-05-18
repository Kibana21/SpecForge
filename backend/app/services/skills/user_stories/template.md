Generate Jira-ready User Stories for "{{ project_name }}" from the Functional Specification below.

Functional Specification:
---
{{ functional_spec }}
---

Extracted Requirements (for context):
---
{{ extracted_requirements }}
---

Return a JSON object with key "stories" containing an array. Each story must have:
- id: string (e.g., "US-001")
- title: string — short imperative title
- description: string — "As a [persona], I want [action] so that [benefit]."
- acceptance_criteria: array of strings (testable, present tense)
- story_points: integer — Fibonacci (1, 2, 3, 5, 8, 13)
- labels: array of lowercase hyphen-separated strings
