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
- **"Which type of prompts use the most tokens"**: needs some bucketing
  scheme for questions — candidates: by which tool the question triggers
  first (mirrors the existing identifier-first system-prompt rule), or by
  how many tool calls it took to answer. Not decided yet.
- **Sequencing recommendation**: build this before the reliability test.
  It's the lower-level primitive — the reliability test's own cost tracking
  can just reuse it rather than duplicating instrumentation. It's also
  independently useful immediately: a single (non-repeated) pass over the
  existing `questions.json`/`questions_2.json`/`questions_3.json` sets would
  already produce a first cost profile, at a fraction of the quota cost of
  any 3–5x repeated reliability run.

## Open questions for next round

- Question-bucketing scheme for "which prompt types cost the most."
- Exact fingerprint-equality rule for entity-overlap (a hard threshold, e.g.
  ≥80% Jaccard overlap counts as "same"?).
- Where results get written (mirror `eval.py`'s `results.json`/`RESULTS.md`
  pattern, or a new format).
