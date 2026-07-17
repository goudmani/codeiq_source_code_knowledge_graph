#!/usr/bin/env python3
"""
cost_logger.py

Token/cost instrumentation for the qa_agent, built as a lower-level layer
that the reliability test (and any other repeated-run tooling) can reuse
rather than duplicating instrumentation. See reports/reliability-and-cost-testing.md
for the design decisions behind this module.

Groq gives us exact prompt_tokens/completion_tokens/total_tokens per LLM
call for free (response.response_metadata["token_usage"], confirmed against
the installed langchain_groq source) -- agent.py captures that directly at
the invocation call site and passes it in here. What Groq does NOT give us:

  - Per-message-source attribution: one combined prompt-token count per
    call, not a breakdown of how many tokens came from the system prompt
    vs. a specific tool's result vs. the question. estimate_char_shares()
    fills this in via each message's share of the turn's total prompt
    characters -- an estimate, not a measurement, but consistent with how
    the codebase already reasons about size (MAX_SNIPPET_CHARS_IN_CONTEXT
    etc.), and good enough for a relative ranking.
  - Prompt-type classification: classify_prompt_type() buckets a question
    into the four categories already implicit in SYSTEM_PROMPT's
    tool-selection rules, so cost can be analyzed by the same taxonomy the
    agent itself reasons with, rather than an invented one.
"""
from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from pathlib import Path

PROMPT_TYPES = ("identifier_lookup", "relationship", "transitive_impact", "discovery")

# Mirrors SYSTEM_PROMPT's own disambiguation rule: CamelCase identifiers or
# useX hook names name a specific entity directly. Same heuristic limitation
# as everywhere else in this codebase that detects identifiers this way --
# an ordinary CamelCase proper noun (e.g. "GitHub") can false-positive.
_IDENTIFIER_RE = re.compile(r"\b([A-Z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*|use[A-Z][a-zA-Z0-9]*)\b")

# \b...\b word-boundary matching, not plain substring -- a naive "in" check
# on the lowercased question would false-positive e.g. "what uses" inside
# "...what useSessionApi does" (lowercased "usesessionapi" contains "uses"
# right after "what ", with no word boundary between "uses" and the rest of
# the hook name). Compiled once at import time.
_TRANSITIVE_HINTS = [
    re.compile(r"\b" + h + r"\b")
    for h in (
        "breaks if", "break if", "transitively", "eventually depend",
        "downstream", "ripple", "cascade", "impact of", "depends on",
    )
]
_RELATIONSHIP_HINTS = [
    re.compile(r"\b" + h + r"\b")
    for h in (
        "who calls", "who renders", "who uses", "what renders", "what calls",
        "callers of", "who depends on", "what uses",
    )
]


def classify_prompt_type(question: str) -> str:
    """Classify a question into one of the four PROMPT_TYPES.

    Order matters: transitive-impact phrasing is checked first since it can
    also contain an identifier name (e.g. "what breaks if BookmarksScreen
    changes") -- the transitive intent should win over the identifier match.
    Relationship phrasing is checked next for the same reason ("who calls
    useSession" names an identifier but is a relationship question).
    """
    q_lower = question.lower()
    if any(hint.search(q_lower) for hint in _TRANSITIVE_HINTS):
        return "transitive_impact"
    if any(hint.search(q_lower) for hint in _RELATIONSHIP_HINTS):
        return "relationship"
    if _IDENTIFIER_RE.search(question):
        return "identifier_lookup"
    return "discovery"


def estimate_char_shares(tagged_texts: list[tuple[str, str]]) -> dict[str, float]:
    """Given [(tag, text), ...] for everything in context at one LLM call,
    estimate each tag's share of that call's prompt tokens via its share of
    total characters. Entries sharing a tag (e.g. two results from the same
    tool) have their shares summed.
    """
    totals: dict[str, int] = defaultdict(int)
    for tag, text in tagged_texts:
        totals[tag] += len(text)
    grand_total = sum(totals.values())
    if grand_total == 0:
        return {}
    return {tag: round(count / grand_total, 4) for tag, count in totals.items()}


class CostLogWriter:
    """Appends one JSONL record per LLM call to a cost log file."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log_call(self, record: dict) -> None:
        with open(self.path, "a") as f:
            f.write(json.dumps(record) + "\n")


def load_cost_log(path: str | Path) -> list[dict]:
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def aggregate_by_prompt_type(records: list[dict]) -> dict[str, dict]:
    """Total/avg tokens per prompt-type bucket, across all turns of all
    questions labeled with that bucket."""
    by_type: dict[str, dict] = defaultdict(
        lambda: {"questions": set(), "prompt_tokens": 0, "completion_tokens": 0, "calls": 0}
    )
    for r in records:
        bucket = by_type[r["prompt_type"]]
        bucket["questions"].add(r["question_id"])
        bucket["prompt_tokens"] += r["prompt_tokens"]
        bucket["completion_tokens"] += r["completion_tokens"]
        bucket["calls"] += 1
    return {
        ptype: {
            "num_questions": len(v["questions"]),
            "num_calls": v["calls"],
            "total_prompt_tokens": v["prompt_tokens"],
            "total_completion_tokens": v["completion_tokens"],
            "avg_tokens_per_question": round(
                (v["prompt_tokens"] + v["completion_tokens"]) / max(len(v["questions"]), 1), 1
            ),
        }
        for ptype, v in sorted(by_type.items(), key=lambda kv: -(kv[1]["prompt_tokens"] + kv[1]["completion_tokens"]))
    }


def aggregate_by_source(records: list[dict]) -> dict[str, dict]:
    """Estimated prompt-token contribution per message source (system
    prompt / question / a specific tool / prior assistant turns), summed
    across all calls, via each record's message_breakdown shares. This is
    what answers both "which tool uses the most tokens" (tool:<name> tags)
    and "which part of the process uses the most tokens" (all tags)."""
    by_tag: dict[str, float] = defaultdict(float)
    for r in records:
        for tag, share in r.get("message_breakdown", {}).items():
            by_tag[tag] += share * r["prompt_tokens"]
    total = sum(by_tag.values()) or 1
    return {
        tag: {"estimated_tokens": round(tok, 1), "share_of_total": round(tok / total, 4)}
        for tag, tok in sorted(by_tag.items(), key=lambda kv: -kv[1])
    }


def cross_tab_intended_vs_actual(records: list[dict]) -> dict[str, dict[str, int]]:
    """intended prompt_type -> actual first tool used -> count of questions,
    restricted to each question's first logged call (turn == 1). A mismatch
    (e.g. "identifier_lookup" questions that actually used search_code
    first) is the same tool-selection failure mode fixed once already in
    eval set 2 (commit f21ed7f), and correlates with higher cost -- more
    tool calls, more re-sent context."""
    cross_tab: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in records:
        if r["turn"] != 1:
            continue
        tool = r["first_tool_used"] or "(none -- answered without a tool call)"
        cross_tab[r["prompt_type"]][tool] += 1
    return {ptype: dict(tools) for ptype, tools in cross_tab.items()}


def write_cost_report(records: list[dict], out_path: str | Path) -> None:
    by_type = aggregate_by_prompt_type(records)
    by_source = aggregate_by_source(records)
    cross_tab = cross_tab_intended_vs_actual(records)

    lines = ["# Cost report", "", f"Generated from {len(records)} logged LLM calls.", ""]

    lines += ["## Tokens by prompt type", "", "| Prompt type | Questions | Calls | Prompt tokens | Completion tokens | Avg tokens/question |", "|---|---|---|---|---|---|"]
    for ptype, v in by_type.items():
        lines.append(
            f"| {ptype} | {v['num_questions']} | {v['num_calls']} | {v['total_prompt_tokens']} | "
            f"{v['total_completion_tokens']} | {v['avg_tokens_per_question']} |"
        )

    lines += ["", "## Estimated tokens by source (system prompt / question / tool / prior turns)", "",
              "| Source | Estimated tokens | Share of total |", "|---|---|---|"]
    for tag, v in by_source.items():
        lines.append(f"| {tag} | {v['estimated_tokens']} | {v['share_of_total']:.1%} |")

    lines += ["", "## Intended prompt type vs. actual first tool used", "",
              "Mismatches here are tool-selection misses -- the same failure mode fixed in eval set 2 -- "
              "and correlate with higher cost.", "",
              "| Intended type | Actual first tool | Count |", "|---|---|---|"]
    for ptype, tools in cross_tab.items():
        for tool, count in tools.items():
            lines.append(f"| {ptype} | {tool} | {count} |")

    Path(out_path).write_text("\n".join(lines) + "\n")
