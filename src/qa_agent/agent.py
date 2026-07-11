#!/usr/bin/env python3
"""
agent.py

LLM-powered Q&A agent over the CodeIQ knowledge graph. Wraps three tools --
search_code() (semantic, src/vector_index/query_index.py), and
find_entity_by_id_or_name() / get_related_entities() (exact lookup + graph
traversal, src/qa_agent/tools.py) -- and drives a bounded tool-calling loop
against a Groq-hosted chat model (model name is a parameter, not hardcoded,
so different Groq models can be compared head-to-head; see eval.py).

Confidence (High/Medium/Low) is computed deterministically from search_code's
relevance scores, not self-reported by the LLM, so it's reproducible and
grading-defensible.

Usage:
  python3 agent.py "which hook manages session state?" --model llama-3.3-70b-versatile
  python3 agent.py "what breaks if BookmarksScreen changes?" --model openai/gpt-oss-120b
"""
import argparse
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

from src.vector_index.query_index import search_code  # noqa: E402
from src.qa_agent.tools import find_entity_by_id_or_name, get_related_entities  # noqa: E402

MODELS = {
    "llama-3.3-70b-versatile": "Groq Llama 3.3 70B -- most tool-calling-tested default",
    "openai/gpt-oss-120b": "Groq-hosted OpenAI gpt-oss 120B -- alternate for reasoning-quality comparison",
}
DEFAULT_MODEL = "llama-3.3-70b-versatile"
MAX_TOOL_CALLS = 5
MAX_INVOKE_RETRIES = 2

# Free-tier Groq TPM limits are tight (as low as 8000 tokens/minute for larger
# models), and a single search_code call already returns ~2K tokens of full
# snippets. Trim what goes back into the LLM's context; full hits (untrimmed)
# are still kept in `sources_by_id` for citations/eval, this only shrinks what
# the model has to re-read on every subsequent turn.
MAX_SNIPPET_CHARS_IN_CONTEXT = 300
MAX_GRAPH_CONTEXT_CHARS_IN_CONTEXT = 200

SYSTEM_PROMPT = """You are CodeIQ, a code-understanding assistant answering questions about a \
parsed React/React Native codebase (bluesky-social/social-app) via a knowledge graph and \
vector index. You have three tools:

1. search_code -- semantic search over code entities (Files/Components/Hooks/Screens). Start \
here for discovery: "which hook does X", "what renders Y", "where is Z implemented". Prefer \
n_results=3 unless the question genuinely needs broader coverage -- results include full code \
snippets, so requesting more than necessary wastes context.
2. find_entity_by_id_or_name -- exact/near-exact identifier lookup. Prefer this over trusting \
search_code's similarity ranking when the question names a specific identifier directly \
(e.g. a function/component name in backticks or CamelCase) -- semantic similarity can return a \
near-miss instead of the exact entity, especially when multiple entities share a name.
3. get_related_entities -- uncapped graph traversal (renders/calls/depends_on/defines, either \
direction) for one specific entity id you already have. search_code's results include only a \
capped preview (8 names per relation). Use this when a question needs an entity's full \
relationship list, or one hop beyond what a single semantic hit exposes.

Rules:
- Always call at least one tool before answering -- never answer from memory alone.
- Answer only from retrieved evidence. If the tools don't surface a clear answer, say so.
- Cite the file path and line range for every factual claim (e.g. `src/App.tsx:110-145`).
- Keep answers concise and concrete -- prefer real entity/file names over generalities.
"""


def _build_tools():
    return [
        as_tool(search_code),
        as_tool(find_entity_by_id_or_name),
        as_tool(get_related_entities),
    ]


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


def _invoke_with_retry(llm_with_tools, messages, max_retries: int = MAX_INVOKE_RETRIES):
    """Retry a Groq call on tool-call generation glitches and transient rate limits.

    Groq's tool-calling occasionally emits malformed function calls (a known
    flakiness, not specific to our prompt); a 413/429 token-rate error is
    often transient within the same rolling window. Both are worth a bounded
    retry before surfacing as a hard failure.
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return llm_with_tools.invoke(messages)
        except groq.APIStatusError as exc:
            last_exc = exc
            if attempt >= max_retries:
                raise
            time.sleep(15 if exc.status_code in (413, 429) else 2)
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


def ask(question: str, model: str = DEFAULT_MODEL, max_tool_calls: int = MAX_TOOL_CALLS) -> dict:
    llm = ChatGroq(model=model, temperature=0)
    tools = _build_tools()
    tools_by_name = {t.name: t for t in tools}
    llm_with_tools = llm.bind_tools(tools)

    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=question)]
    sources_by_id: dict[str, dict] = {}
    tool_call_trace: list[dict] = []

    start = time.monotonic()
    calls_made = 0
    response: AIMessage = _invoke_with_retry(llm_with_tools, messages)

    while response.tool_calls and calls_made < max_tool_calls:
        messages.append(response)
        for call in response.tool_calls:
            tool_call_trace.append({"tool": call["name"], "args": call["args"]})
            result = tools_by_name[call["name"]].invoke(call["args"])
            for hit in result or []:
                sources_by_id.setdefault(hit["id"], hit)
            messages.append(ToolMessage(content=json.dumps(_trim_for_context(result)), tool_call_id=call["id"]))
            calls_made += 1
            if calls_made >= max_tool_calls:
                break
        response = _invoke_with_retry(llm_with_tools, messages)

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
        "latency_s": latency_s,
        "tool_calls": tool_call_trace,
    }


def main():
    ap = argparse.ArgumentParser(description="Ask the CodeIQ Q&A agent a question.")
    ap.add_argument("question")
    ap.add_argument("--model", default=DEFAULT_MODEL, choices=list(MODELS))
    args = ap.parse_args()

    load_dotenv()
    if not os.environ.get("GROQ_API_KEY"):
        raise SystemExit("GROQ_API_KEY is not set (add it to .env, see .env.example)")

    result = ask(args.question, model=args.model)

    print(f"\nQ: {result['question']}")
    print(f"Model: {result['model']}  |  Latency: {result['latency_s']}s  |  Confidence: {result['confidence']}")
    print(f"Confidence rationale: {result['confidence_rationale']}\n")
    print(f"A: {result['answer']}\n")
    print(f"Sources ({len(result['sources'])}):")
    for s in result["sources"]:
        loc = f"{s['file']}:{s['start_line']}-{s['end_line']}" if s.get("file") else s["id"]
        print(f"  - {s['type']:10s} {s['name']:30s} {loc}")


if __name__ == "__main__":
    main()
