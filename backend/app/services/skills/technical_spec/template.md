Generate a Technical Specification for "{{ project_name }}" based on the Functional Specification and requirements below.

Functional Specification:
---
{{ functional_spec }}
---

Extracted Requirements:
---
{{ extracted_requirements }}
---

Return a JSON object with:
- architecture_overview: string
- components: array of {name, description}
- data_models: array of {name, description}
- api_endpoints: array of {method, path, description}
- tech_stack: object with keys: frontend, backend, database, and any other relevant keys
- risks: array of {risk, mitigation}
