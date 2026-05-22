## Query
{{ query }}

## Document Section Outline
{{ outline }}

Pick the {{ top_k }} sections most relevant to the Query. Respond with a JSON object:
{"selections":[{"doc":"D0","node_id":"<id from the outline>","reason":"why relevant"}]}
