#!/usr/bin/env python3
"""
agent.py

LLM-powered Q&A agent over the CodeIQ knowledge graph. Wraps four tools --
search_code() (semantic, src/vector_index/query_index.py), and
find_entity_by_id_or_name() / get_related_entities() / (exact lookup + 1-hop
graph traversal) get_transitive_related_entities() (multi-hop BFS, src/
qa_agent/tools.py) -- and drives a bounded tool-calling loop against a
Groq-hosted chat model (model name is a parameter, not hardcoded, so
different Groq models can be compared head-to-head; see eval.py).

Confidence (High/Medium/Low) is computed deterministically from search_code's
relevance scores, not self-reported by the LLM, so it's reproducible and
grading-defensible.

The knowledge-graph tag (which indexed repo snapshot to query) is resolved
once per run from --tag / the ask() argument, never from the LLM: each tool
is wrapped so `tag` is force-injected on every call and hidden from the
tool schema the model sees, so the model can neither omit it nor override it.

Usage:
  python3 agent.py "which hook manages session state?" --model llama-3.3-70b-versatile
  python3 agent.py "what breaks if BookmarksScreen changes?" --model openai/gpt-oss-120b
  python3 agent.py "which hook manages session state?" --tag v2
"""
import argparse
import functools
import inspect
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import groq  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage  # noqa: E402
from langchain_core.tools import tool as as_tool  # noqa: E402
from langchain_groq import ChatGroq  # noqa: E402

from src.clone_raw.clone_raw import TAG  # noqa: E402
from src.vector_index.query_index import search_code  # noqa: E402
from src.qa_agent.tools import (  # noqa: E402
    find_entity_by_id_or_name,
    get_related_entities,
    get_transitive_related_entities,
)
from src.qa_agent.cost_logger import CostLogWriter, classify_prompt_type, estimate_char_shares  # noqa: E402

MODELS = {
    "llama-3.3-70b-versatile": "Groq Llama 3.3 70B -- most tool-calling-tested default",
    "openai/gpt-oss-120b": "Groq-hosted OpenAI gpt-oss 120B -- alternate for reasoning-quality comparison",
}
DEFAULT_MODEL = "openai/gpt-oss-120b"
DEFAULT_TAG = TAG
MAX_TOOL_CALLS = 5
MAX_INVOKE_RETRIES = 2

# Free-tier Groq TPM limits are tight (as low as 8000 tokens/minute for larger
# models). A trimmed tool result still accumulates across every call in the
# loop and gets resent in full on every subsequent turn (Groq's chat API is
# stateless), so two independent levers keep a single request under the cap:
#   1. Hard-clamp search_code's n_results before invoking it (see
#      _clamp_tool_args below) -- more reliable than trusting the system
#      prompt's "prefer n_results=3" hint, since the model can ignore it.
#   2. Truncate the two large free-text fields (snippet, graph_context) in
#      every hit before it goes back into the LLM's context. Full hits
#      (untrimmed) are still kept in `sources_by_id` for citations/eval --
#      this only shrinks what the model has to re-read on later turns.
MAX_SEARCH_RESULTS = 3
MAX_SNIPPET_CHARS_IN_CONTEXT = 150
MAX_GRAPH_CONTEXT_CHARS_IN_CONTEXT = 100
MAX_TRANSITIVE_DEPTH = 3
MAX_TRANSITIVE_RESULTS = 15

# Params that select which indexed repo snapshot a tool reads from. These are
# never exposed to the LLM's tool schema and are force-injected server-side
# (see _bind_tag) -- the model has no way to see, omit, or override them.
_TAG_SCOPED_PARAMS = ("tag", "chroma_dir")

SYSTEM_PROMPT = """You are CodeIQ, a code-understanding assistant answering questions about a \
parsed codebase via a knowledge graph and vector index. You have four tools:

1. search_code -- semantic search over code entities (Files/Components/Hooks/Screens). Start \
here for discovery: "which hook does X", "what renders Y", "where is Z implemented". Prefer \
n_results=3 unless the question genuinely needs broader coverage -- results include full code \
snippets, so requesting more than necessary wastes context.
2. find_entity_by_id_or_name -- exact/near-exact identifier lookup. Prefer this over trusting \
search_code's similarity ranking when the question names a specific identifier directly \
(e.g. a function/component name in backticks or CamelCase) -- semantic similarity can return a \
near-miss instead of the exact entity, especially when multiple entities share a name.
3. get_related_entities -- uncapped 1-hop graph traversal (renders/calls/depends_on/defines, \
either direction) for one specific entity id you already have. search_code's results include \
only a capped preview (8 names per relation). Use this when a question needs an entity's full \
direct relationship list, or one hop beyond what a single semantic hit exposes.
4. get_transitive_related_entities -- multi-hop BFS (one relation, one direction) from one \
entity id you already have. Use this specifically for transitive/indirect impact questions -- \
"what breaks if X changes", "what does X transitively depend on/use" -- instead of calling \
get_related_entities repeatedly hop-by-hop. direction="in" over "calls" or "depends_on" answers \
"what transitively uses/depends on X"; direction="out" over "depends_on" answers "what does X \
transitively pull in". Results are capped and ordered by hop count (depth field).

Rules:
- Always call at least one tool before answering -- never answer from memory alone.
- Answer only from retrieved evidence. If the tools don't surface a clear answer, say so.
- Cite the file path and line range for every factual claim (e.g. `src/App.tsx:110-145`).
- Keep answers concise and concrete -- prefer real entity/file names over generalities.
- Only these four tools exist: search_code, find_entity_by_id_or_name, get_related_entities, \
get_transitive_related_entities. Never call any other tool name (e.g. open_file, read_file, \
list_files) -- if you need more of a file's content, call search_code or get_related_entities \
again instead.
- If the question names a code identifier (CamelCase like BookmarksScreen, or a useX hook name), \
your FIRST call must be find_entity_by_id_or_name with that identifier. Only fall back to \
search_code if the exact lookup returns nothing. Many entities share a name (e.g. 57 components \
are named Provider) -- semantic similarity cannot disambiguate them, exact lookup can.
- If the question is explicitly about transitive/indirect impact ("what breaks if...", "what \
does X eventually depend on"), prefer get_transitive_related_entities over chaining multiple \
get_related_entities calls -- it returns the full multi-hop answer in a single call.
- Never repeat a tool call with the same arguments -- it returns identical results. search_code's \
n_results is hard-capped at 3, so raising it changes nothing. If a search missed, change the \
query wording, switch tool, or answer from what you have.
"""


def _bind_tag(fn, tag: str):
    """Wrap fn so any tag-scoped kwarg it accepts (tag, chroma_dir, ...) is
    always set to `tag`/derived-from-`tag` server-side, and is hidden from
    the signature LangChain inspects to build the tool's JSON schema.

    This means the LLM's tool-call arguments can never contain a `tag` --
    it isn't offered the parameter at all -- and even a stray one wouldn't
    survive: it's overwritten unconditionally on every call.
    """
    sig = inspect.signature(fn)
    visible_params = [
        p for name, p in sig.parameters.items() if name not in _TAG_SCOPED_PARAMS
    ]
    visible_sig = sig.replace(parameters=visible_params)
    accepts_tag = "tag" in sig.parameters

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        for scoped in _TAG_SCOPED_PARAMS:
            kwargs.pop(scoped, None)
        if accepts_tag:
            kwargs["tag"] = tag
        return fn(*args, **kwargs)

    wrapper.__signature__ = visible_sig
    return wrapper


def _build_tools(tag: str):
    return [
        as_tool(_bind_tag(search_code, tag)),
        as_tool(_bind_tag(find_entity_by_id_or_name, tag)),
        as_tool(_bind_tag(get_related_entities, tag)),
        as_tool(_bind_tag(get_transitive_related_entities, tag)),
    ]


def _clamp_tool_args(name: str, args: dict) -> dict:
    """Hard-cap search_code's n_results, and get_transitive_related_entities'
    max_depth/limit, regardless of what the model requested.

    Each hit already carries a full code snippet, so result count is the
    single biggest lever on request size under Groq's per-minute token cap --
    more reliable than trusting the system prompt's hints alone. A transitive
    BFS is the other risk: an uncapped depth/limit on a fan-out-heavy node
    could return far more hits than search_code ever would.
    """
    if name == "search_code" and args.get("n_results", 0) > MAX_SEARCH_RESULTS:
        args = {**args, "n_results": MAX_SEARCH_RESULTS}
    if name == "get_transitive_related_entities":
        if args.get("max_depth", 0) > MAX_TRANSITIVE_DEPTH:
            args = {**args, "max_depth": MAX_TRANSITIVE_DEPTH}
        if args.get("limit", 0) > MAX_TRANSITIVE_RESULTS:
            args = {**args, "limit": MAX_TRANSITIVE_RESULTS}
    return args


def _trim_for_context(hits: list[dict] | None) -> list[dict]:
    """Shrink a tool result before it goes back into the LLM's context.

    Keeps every field but truncates the two large free-text ones (snippet,
    graph_context). The untruncated hit is kept separately for citations --
    this only affects what the model re-reads on subsequent turns.
    """
    trimmed = []
    for hit in hits or []:
        h = dict(hit)
        if len(h.get("snippet") or "") > MAX_SNIPPET_CHARS_IN_CONTEXT:
            h["snippet"] = h["snippet"][:MAX_SNIPPET_CHARS_IN_CONTEXT] + "...(truncated)"
        if len(h.get("graph_context") or "") > MAX_GRAPH_CONTEXT_CHARS_IN_CONTEXT:
            h["graph_context"] = h["graph_context"][:MAX_GRAPH_CONTEXT_CHARS_IN_CONTEXT] + "...(truncated)"
        trimmed.append(h)
    return trimmed


def _load_api_keys() -> list[tuple[str, str]]:
    """Configured Groq API keys in priority order: [(account_label, key), ...].

    GROQ_API_KEY is Account_1; GROQ_API_KEY_2, GROQ_API_KEY_3, ... are
    additional accounts used as fallbacks when the active one hits its rate
    limit -- each Groq account carries its own independent TPM/TPD quota.
    """
    keys = []
    if os.environ.get("GROQ_API_KEY"):
        keys.append(("Account_1", os.environ["GROQ_API_KEY"]))
    n = 2
    while os.environ.get(f"GROQ_API_KEY_{n}"):
        keys.append((f"Account_{n}", os.environ[f"GROQ_API_KEY_{n}"]))
        n += 1
    return keys


# Sticks across calls once rotated, so an account that just exhausted its
# quota isn't pointlessly retried first on every subsequent request.
_active_key_index = 0


def _invoke_with_retry(make_runnable, messages, max_retries: int = MAX_INVOKE_RETRIES):
    """Invoke a Groq call with bounded retries, rotating accounts on rate limits.

    make_runnable(api_key) builds the runnable (with or without tools bound)
    for one account's key. On a 413/429 the next configured account is tried
    immediately -- it has its own fresh TPM/TPD budget, so rotating beats
    sleeping. Only when every account is rate-limited does it sleep 15s for
    the rolling window. Other API glitches (e.g. Groq's occasional malformed
    tool-call 400s) retry the same account after a short pause.
    """
    global _active_key_index
    keys = _load_api_keys()
    if not keys:
        raise SystemExit("No GROQ_API_KEY configured (add it to .env, see .env.example)")

    last_exc = None
    for attempt in range(max_retries + 1):
        for offset in range(len(keys)):
            index = (_active_key_index + offset) % len(keys)
            label, key = keys[index]
            try:
                result = make_runnable(key).invoke(messages)
                if index != _active_key_index:
                    print(f"[groq] rate limit on active account -- switched to {label}", file=sys.stderr)
                    _active_key_index = index
                return result
            except groq.APIStatusError as exc:
                last_exc = exc
                if exc.status_code in (413, 429):
                    continue  # rate-limit-flavored: the next account has its own quota
                if attempt >= max_retries:
                    raise
                time.sleep(2)
                break  # transient non-rate-limit glitch: retry the same account
        else:
            if attempt >= max_retries:
                raise last_exc
            time.sleep(15)  # every account limited: wait out the rolling window
    raise last_exc


def _score_confidence(sources: list[dict]) -> tuple[str, str]:
    relevances = sorted((s["relevance"] for s in sources if "relevance" in s), reverse=True)
    if not relevances:
        return "Low", "No semantically-scored evidence was retrieved for this answer."

    top = relevances[0]
    strong_support = sum(1 for r in relevances if r >= 0.6)

    if top >= 0.75 and strong_support >= 2:
        level = "High"
    elif top >= 0.5:
        level = "Medium"
    else:
        level = "Low"

    rationale = (
        f"{strong_support} of {len(relevances)} retrieved entities scored >=0.6 relevance; "
        f"top match scored {top:.2f}."
    )
    return level, rationale


def ask(
    question: str,
    model: str = DEFAULT_MODEL,
    max_tool_calls: int = MAX_TOOL_CALLS,
    tag: str = DEFAULT_TAG,
    cost_sink: CostLogWriter | None = None,
    question_id: str | None = None,
) -> dict:
    tools = _build_tools(tag)
    tools_by_name = {t.name: t for t in tools}

    # Built per-key (not once) so _invoke_with_retry can rotate to another
    # account's key mid-question when the active one hits its rate limit.
    def make_llm(api_key: str):
        return ChatGroq(model=model, temperature=0, api_key=api_key)

    def make_llm_with_tools(api_key: str):
        return make_llm(api_key).bind_tools(tools)

    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=question)]
    # Parallel to `messages` -- (source_tag, text) for everything currently
    # in context, so cost_sink can estimate each source's token share. Kept
    # up to date alongside every `messages.append()` below. Cheap to
    # maintain even when cost_sink is None, so no branching at each append
    # site is needed.
    message_tags: list[tuple[str, str]] = [("system_prompt", SYSTEM_PROMPT), ("question", question)]
    sources_by_id: dict[str, dict] = {}
    tool_call_trace: list[dict] = []
    seen_calls: set[tuple] = set()

    prompt_type = classify_prompt_type(question) if cost_sink else None
    turn = 0
    first_tool_used: str | None = None

    def log_turn(resp: AIMessage, tags: list[tuple[str, str]]) -> None:
        nonlocal turn, first_tool_used
        turn += 1
        if cost_sink is None:
            return
        if turn == 1 and resp.tool_calls:
            first_tool_used = resp.tool_calls[0]["name"]
        usage = getattr(resp, "response_metadata", {}).get("token_usage", {})
        cost_sink.log_call({
            "question_id": question_id,
            "question": question,
            "tag": tag,
            "model": model,
            "prompt_type": prompt_type,
            "first_tool_used": first_tool_used,
            "turn": turn,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "message_breakdown": estimate_char_shares(tags),
            "timestamp": time.time(),
        })

    start = time.monotonic()
    calls_made = 0
    budget_exhausted_mid_turn = False
    response: AIMessage = _invoke_with_retry(make_llm_with_tools, messages)
    log_turn(response, message_tags)

    while response.tool_calls and calls_made < max_tool_calls:
        messages.append(response)
        message_tags.append(("assistant_turn", response.content or ""))
        for call in response.tool_calls:
            clamped_args = _clamp_tool_args(call["name"], call["args"])
            # Dedupe on the CLAMPED args: raising n_results past the cap
            # produces a byte-identical request, so e.g. n_results 10/20/50
            # all collapse to the same key as the n_results=3 call.
            dedupe_key = (call["name"], json.dumps(clamped_args, sort_keys=True, default=str))
            duplicate = dedupe_key in seen_calls
            tool_call_trace.append({"tool": call["name"], "args": call["args"], "duplicate": duplicate})
            if duplicate:
                # Don't re-execute or resend the same payload -- nudge the
                # model to change strategy. Still counts against the budget
                # so a stubborn model can't loop forever.
                dup_content = json.dumps({"note": "Duplicate call: identical arguments were already "
                                          "used above and would return the same results. Change the "
                                          "query wording, switch tool, or answer now."})
                messages.append(ToolMessage(content=dup_content, tool_call_id=call["id"]))
                message_tags.append((f"tool:{call['name']}", dup_content))
                calls_made += 1
                if calls_made >= max_tool_calls:
                    budget_exhausted_mid_turn = True
                    break
                continue
            seen_calls.add(dedupe_key)
            result = tools_by_name[call["name"]].invoke(clamped_args)
            for hit in result or []:
                sources_by_id.setdefault(hit["id"], hit)
            tool_content = json.dumps(_trim_for_context(result))
            messages.append(ToolMessage(content=tool_content, tool_call_id=call["id"]))
            message_tags.append((f"tool:{call['name']}", tool_content))
            calls_made += 1
            if calls_made >= max_tool_calls:
                budget_exhausted_mid_turn = True
                break
        if budget_exhausted_mid_turn:
            break
        response = _invoke_with_retry(make_llm_with_tools, messages)
        log_turn(response, message_tags)

    if budget_exhausted_mid_turn or response.tool_calls or not response.content:
        # Either the tool-call budget ran out mid-turn (every tool_call in the
        # last AI turn was executed and paired with a ToolMessage -- `messages`
        # is well-formed at this point), or the model still wants to call a
        # tool it has no budget left for. Either way, re-invoke WITHOUT tools
        # bound -- the model can't ask for another call, and must answer in
        # text using only the evidence already gathered above. (Without this,
        # the loop would exit holding a tool_calls-only response, which
        # carries no text content, producing a blank final answer.)
        try:
            budget_notice = ("You have used all available tool calls. Answer now, in text, "
                              "using only the evidence already retrieved above. Do not emit any "
                              "tool call -- respond with plain prose only.")
            response = _invoke_with_retry(
                make_llm,
                messages + [HumanMessage(content=budget_notice)],
            )
            log_turn(response, message_tags + [("budget_exhausted_prompt", budget_notice)])
        except groq.APIStatusError as exc:
            # gpt-oss-120b sometimes emits tool-call syntax even on this
            # tools-unbound call, which Groq rejects with a 400 ("Tool choice
            # is none, but model called a tool"). The evidence is already
            # gathered at this point -- degrade to a stub answer pointing at
            # the cited sources instead of failing the whole question.
            if exc.status_code != 400:
                raise
            response = AIMessage(
                content="The model exhausted its tool-call budget before producing a final "
                "synthesis. The cited sources below were still retrieved and are valid "
                "evidence for this question."
            )

    latency_s = round(time.monotonic() - start, 2)
    sources = list(sources_by_id.values())
    confidence, confidence_rationale = _score_confidence(sources)

    return {
        "question": question,
        "answer": response.content,
        "confidence": confidence,
        "confidence_rationale": confidence_rationale,
        "sources": sources,
        "model": model,
        "tag": tag,
        "latency_s": latency_s,
        "tool_calls": tool_call_trace,
    }


def main():
    ap = argparse.ArgumentParser(description="Ask the CodeIQ Q&A agent a question.")
    ap.add_argument("question")
    ap.add_argument("--model", default=DEFAULT_MODEL, choices=list(MODELS))
    ap.add_argument("--tag", default=DEFAULT_TAG, help="indexed repo tag to query (data/processed/<tag>)")
    args = ap.parse_args()

    load_dotenv()
    if not os.environ.get("GROQ_API_KEY"):
        raise SystemExit("GROQ_API_KEY is not set (add it to .env, see .env.example)")

    result = ask(args.question, model=args.model, tag=args.tag)

    print(f"\nQ: {result['question']}")
    print(f"Model: {result['model']}  |  Tag: {result['tag']}  |  Latency: {result['latency_s']}s  |  Confidence: {result['confidence']}")
    print(f"Confidence rationale: {result['confidence_rationale']}\n")
    print(f"A: {result['answer']}\n")
    print(f"Sources ({len(result['sources'])}):")
    for s in result["sources"]:
        loc = f"{s['file']}:{s['start_line']}-{s['end_line']}" if s.get("file") else s["id"]
        print(f"  - {s['type']:10s} {s['name']:30s} {loc}")


if __name__ == "__main__":
    main()