# Cost report

Generated from 106 logged LLM calls, made from the 30 eval questions log.

## Tokens by prompt type

| Prompt type | Questions | Calls | Prompt tokens | Completion tokens | Avg tokens/question |
|---|---|---|---|---|---|
| discovery | 17 | 54 | 212679 | 8724 | 13023.7 |
| identifier_lookup | 11 | 45 | 173691 | 6844 | 16412.3 |
| transitive_impact | 2 | 7 | 24792 | 1366 | 13079.0 |

## Estimated tokens by source (system prompt / question / tool / prior turns)

| Source | Estimated tokens | Share of total |
|---|---|---|
| system_prompt | 237316.0 | 57.7% |
| tool:search_code | 126636.0 | 30.8% |
| tool:get_related_entities | 26115.5 | 6.3% |
| tool:find_entity_by_id_or_name | 14975.5 | 3.6% |
| question | 5713.9 | 1.4% |
| budget_exhausted_prompt | 407.5 | 0.1% |
| tool:get_transitive_related_entities | 2.1 | 0.0% |
| assistant_turn | 0.0 | 0.0% |

## Intended prompt type vs. actual first tool used

Mismatches here are tool-selection misses -- the same failure mode fixed in eval set 2 -- and correlate with higher cost.

| Intended type | Actual first tool | Count |
|---|---|---|
| discovery | search_code | 8 |
| discovery | find_entity_by_id_or_name | 9 |
| identifier_lookup | find_entity_by_id_or_name | 11 |
| transitive_impact | find_entity_by_id_or_name | 2 |

---

## Reliability run (separate from the single-pass profile above)

Generated from 141 logged LLM calls across 10 questions, 3-5 repeated samples each (adaptive early-stopping). Kept as its own section, not blended into the tables above, since repeated-sampling calls have a different shape than the single-pass run and would skew those averages if merged in.

### Tokens by prompt type

| Prompt type | Questions | Calls | Prompt tokens | Completion tokens | Avg tokens/question |
|---|---|---|---|---|---|
| discovery | 5 | 71 | 281973 | 11044 | 58603.4 |
| identifier_lookup | 3 | 50 | 178335 | 7072 | 61802.3 |
| transitive_impact | 2 | 20 | 68562 | 4178 | 36370.0 |

### Estimated tokens by source

| Source | Estimated tokens | Share of total |
|---|---|---|
| system_prompt | 319149.6 | 60.4% |
| tool:search_code | 119894.0 | 22.7% |
| tool:get_related_entities | 53696.2 | 10.2% |
| tool:find_entity_by_id_or_name | 27868.6 | 5.3% |
| question | 7758.6 | 1.5% |
| budget_exhausted_prompt | 503.3 | 0.1% |
| assistant_turn | 0.0 | 0.0% |
