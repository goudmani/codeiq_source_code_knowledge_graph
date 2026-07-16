# Reliability & cost testing — design notes

Branch: `feat/reducancy_and_cost`. Two pieces of work: (1) a repeated-sampling
reliability test for the Q&A agent, (2) a token/cost instrumentation layer.
This doc tracks the decisions made so far and the open questions, so the
reasoning behind the approach is visible, not just the final code.

## Why build a custom harness instead of adopting a framework

We looked at three widely-used open-source LLM eval tools before deciding to
extend our existing `eval.py` harness instead of adopting one:

- **RAGAS** — purpose-built for RAG quality metrics (faithfulness, context
  precision). No native "run the same input N times and compare" primitive,
  and our agent is a tool-calling agent, not a plain retrieve-then-generate
  pipeline.
- **DeepEval** — pytest-style, one assertion per test case. Good for CI
  quality gates on individual answers, not naturally shaped for comparing N
  repeated runs of the same input against each other.
- **Promptfoo** — strongest at red-teaming and multi-model comparison, not
  at repeated-sampling consistency.

None of them has a first-class "sample the same input N times and measure
agreement" concept, which is the actual thing we need. Adopting one would
mean bending our tool-calling architecture to fit someone else's primitives.
We already have a working harness (`agent.ask()` → structured result dict,
`eval.py`'s `summarize()`/`write_markdown_report()`) that's a closer match,
so we're extending that instead of introducing a new dependency.

## Reliability test

This is a **self-consistency / test-retest reliability test**: ask the same
question multiple times and check the agent's decisions agree across runs.

**Important constraint:** LLM output isn't deterministic even at
temperature 0 (batched GPU floating-point execution varies run to run), so
"consistent" can't mean exact text match. Every signal below compares
*structured decisions*, not prose.

### What we compare across runs (building #1–4; #5 deferred)

1. **Tool-call trace agreement** — did the runs call the same first tool /
   same tool sequence for the same question? Cheapest, most stable signal;
   already logged as `tool_calls` on every `ask()` result.
2. **Cited-entity overlap** — how much do the sets of entity ids cited as
   sources overlap across runs (pairwise Jaccard overlap)? Reuses the same
   idea as the existing `entity_hit` eval metric, just comparing runs to
   each other instead of to a fixed expected-answer list.
3. **Confidence-level stability** — is the reported High/Medium/Low
   confidence the same across runs? Already computed deterministically by
   `_score_confidence`, cheap to compare.
4. **Answer semantic similarity** — embedding cosine similarity between the
   answer texts (using the same local embedding model Chroma already uses,
   no extra API cost).
5. *(deferred)* LLM-as-judge equivalence — an extra LLM call to judge
   whether answers are materially consistent. More expensive, more
   semantically aware; revisit after 1–4 are working.

### Borrowed from AgentAssay ([arXiv:2603.02601](https://arxiv.org/abs/2603.02601))

- **Three-valued verdict** (PASS / FAIL / INCONCLUSIVE) instead of a forced
  binary pass/fail — with a handful of samples, "not enough signal to call
  it" is sometimes the honest answer.
- **Adaptive / early-stopping sampling** — don't always spend the full
  sample budget.
- **Behavioral fingerprinting** — decided to adopt this too. What it means
  in plain terms: reduce one run down to its key decisions — first tool
  called, cited entity ids, confidence level — into one comparable object,
  instead of comparing paragraphs of prose word for word. This is not new
  complexity on top of signals 1–3 above; it's exactly signals 1–3 combined
  into a single object so two runs can be compared in one step. Framed this
  way it should be easy to explain to reviewers, since it's the same three
  already-explained ideas, just packaged together.

### Adaptive sampling rule (decided)

- Run 3 samples first.
- If all 3 agree (by fingerprint comparison) → **PASS**, stop early (saves
  2 of 5 calls — this is the cost saving).
- If they don't all agree, run the remaining 2 (full 5 samples), then:
  - ≥4/5 agree → **PASS**
  - 2–3/5 agree → **INCONCLUSIVE**
  - ≤1/5 agree → **FAIL**

## Cost / token instrumentation — still being ideated, not decided yet

Notes so far, to pick back up next round:

- **Ground truth is free**: `langchain_groq`'s `ChatGroq` returns exact
  `prompt_tokens` / `completion_tokens` / `total_tokens` per LLM call via
  `response_metadata["token_usage"]` (or `usage_metadata` for the
  unified LangChain fields). This can be captured directly at the existing
  LLM-invocation call site in `agent.py`'s loop — no extra API calls needed.
- **The hard part is attribution, not measurement.** Groq (like other
  providers) returns one combined prompt-token count per call — it does
  *not* tell you how many of those tokens came from the system prompt vs.
  a specific tool's result vs. the original question. To answer "which tool
  uses the most tokens," we have to estimate that split ourselves.
  - Leaning towards a character-count-based estimate (each message's share
    of a turn's total prompt characters) rather than a separate tokenizer
    dependency, since the codebase already reasons about size in
    characters (`MAX_SNIPPET_CHARS_IN_CONTEXT`, `MAX_GRAPH_CONTEXT_CHARS_IN_CONTEXT`)
    — consistent with the existing trimming logic, and good enough for a
    relative ranking ("tool X's results are typically 3x tool Y's") even
    if not byte-exact.
- **"Which part of the process uses tokens"**: tag each message when it's
  appended in `ask()`'s loop (system prompt / question / a specific tool's
  result / final answer), then sum estimated tokens by tag per question.
- **Sequencing recommendation**: design the bucketing schema before writing
  the logger (see below), then build the logger. Reasoning: the only truly
  new raw data the logger adds is per-call token usage — everything else it
  attaches to already exists in `ask()`'s return value. The one-shot,
  hard-to-redo decision is what fields each log record needs to carry so
  bucketing can be computed from the log afterward without re-running live
  (quota-costing) Groq calls. Actual bucketing/aggregation code can be
  iterated on cheaply after the fact, same as `eval.py`'s `summarize()`
  re-aggregates `results.json` — that part doesn't need to exist yet.
  Once the logger is built, it should also come before the reliability
  test — the reliability test's own cost tracking can just reuse it rather
  than duplicating instrumentation, and a single non-repeated pass over the
  existing `questions.json`/`questions_2.json`/`questions_3.json` sets
  already gives a first cost profile at a fraction of the quota cost of any
  3–5x repeated reliability run.

### Prompt-type bucketing scheme (decided)

For "which type of prompts cost the most," reuse the four question
categories already implicit in `SYSTEM_PROMPT`'s tool-selection rules,
rather than inventing a new taxonomy:

1. **Identifier lookup** — question names a specific entity directly
   (CamelCase name, `useX` hook) → should trigger `find_entity_by_id_or_name` first.
2. **Discovery / semantic** — open-ended ("which hook does X", "where is Y
   implemented") → should trigger `search_code` first.
3. **Relationship** — "who calls X", "what does X render" → `get_related_entities`.
4. **Transitive impact** — "what breaks if X changes" → `get_transitive_related_entities`.

Reusing this taxonomy is free — no new classification scheme, just labeling
each question by which of the four patterns it matches. It also gives a
bonus signal beyond cost: since the tool-call trace records which tool was
*actually* used first, we get a free "intended category vs. actual tool
used" cross-tab. A mismatch (e.g. a question labeled "identifier lookup"
that actually triggered `search_code` first) is the same tool-selection
failure mode already fixed once in eval set 2 (commit `f21ed7f`) — and those
mismatches are exactly the cases likely to cost more (extra tool calls, more
turns, more re-sent context). So this bucketing doubles as a cheap
correctness check, not just a cost one.

## Fingerprint-equality threshold (decided)

Two runs' cited-entity sets count as "the same" if their Jaccard overlap is
**≥ 0.7**. Chosen as a starting default, not empirically tuned yet — we
don't have real repeated-run data to calibrate against until the live
testing round. Kept as a single named constant so it's a one-line change to
recalibrate once we see real variance. Combined with exact equality on
first-tool-called and confidence level for the overall fingerprint match
(all three must agree for two runs to count as "the same run").

## Output file format (decided)

Mirrors `eval.py`'s existing `results.json` / `RESULTS.md` pattern for
consistency with the rest of the project:

- `data/cost/cost_log.jsonl` — one raw record per LLM call (the schema from
  the section above).
- `data/cost/COST_REPORT.md` — human-readable aggregated report (tokens by
  prompt-type bucket, by tool, by process stage, plus the intended-vs-actual
  tool cross-tab).
- `data/reliability/reliability_results.json` — one record per question
  tested: the fingerprints from each sample, the verdict (PASS/FAIL/INCONCLUSIVE),
  and how many samples were actually used (3 or 5).
- `data/reliability/RELIABILITY_REPORT.md` — human-readable summary.

## Noted for later: missing-description handling

Not every entity in `entities_with_desc.jsonl` has a `description` (7/3820
bluesky entities, 0/24 raysk4ever). The code never fails on this -- it always
falls back to an empty string -- but there's no explicit system-prompt
instruction telling the model this is expected, and the tool docstrings are
inconsistent about it (`find_entity_by_id_or_name`/`get_related_entities`
document "empty string if none"; `get_transitive_related_entities` doesn't
mention it at all; `search_code`'s docstring frames it as an index-wide
condition rather than a per-entity one, which could mislead the model into
assuming descriptions are always present in this index). Simple test for
later: ask about one of the entities below a few times and check whether the
agent stays grounded in the code snippet vs. hallucinates a plausible-sounding
description.

Entities with no description (bluesky-social/social-app):
- `src/alf/fonts.ts` (File)
- `src/geolocation/types.ts` (File)
- `src/components/Dialog/types.ts` (File)
- `src/components/dms/ActionsWrapper.web.tsx#ActionsWrapper` (Component)
- `src/components/icons/CircleCheck.tsx` (File)
- `src/components/icons/Message.tsx` (File)
- `src/components/PolicyUpdateOverlay/logger.ts` (File)
