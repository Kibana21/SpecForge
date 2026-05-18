Extract all requirements from the following document for the project "{{ project_name }}".

Document text:
---
{{ document_text }}
---

Return a JSON object with these keys:
- functional_requirements: array of functional requirements
- non_functional_requirements: array of non-functional requirements (performance, security, scalability, etc.)
- constraints: array of constraints (technology, legal, budget, time)
- assumptions: array of assumptions made
- stakeholders: array of stakeholder roles/groups identified

Each item in all arrays must have: id, text, source_reference (string or null), confidence (high|medium|low).
