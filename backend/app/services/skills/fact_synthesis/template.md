Application: {{ app_name }}
Fact category: {{ kind }}

## Source Facts to Synthesize

{{ facts_json }}

Synthesize the above {{ kind }} facts for {{ app_name }}. Merge duplicates, preserve distinct facts, and return a JSON object with a "facts" array. Each fact must include source_fact_ids listing which input fact IDs contributed to it.
