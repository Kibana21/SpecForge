Generate a Functional Specification for the project "{{ project_name }}".

Extracted requirements:
---
{{ extracted_requirements }}
---

Resolved gap answers (incorporate these into the spec where relevant):
---
{{ resolved_gap_answers }}
---

Return a JSON object with:
- overview: string — 2-3 sentence project summary
- objectives: array of strings — measurable goals
- scope: string — what is and is not included
- features: array of objects, each with:
  - name: string
  - description: string
  - acceptance_criteria: array of strings (testable criteria)
