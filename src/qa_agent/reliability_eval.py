#!/usr/bin/env python3
"""
reliability_eval.py

Batch runner for reliability.py's evaluate_reliability() over a fixed,
hand-picked subset of the eval questions -- not the full 30, see
reports/reliability-and-cost-testing.md's sequencing note on cost -- with cost
tracking wired in via cost_sink, same pattern as cost_eval.py.

Question selection (10 of 30): spans all three prompt types that actually
occur in the eval questions (discovery, identifier_lookup, transitive_impact
-- see cost_logger.classify_prompt_type) and multiple areas of the codebase,
and deliberately excludes the three already-known, already-diagnosed eval
misses (q10, q25, q29) -- a reliability FAIL/INCONCLUSIVE verdict here
should reflect genuine run-to-run variance, not an already-understood
retrieval gap surfacing again.

Usage:
  python3 -m src.qa_agent.reliability_eval
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv  # noqa: E402

from src.qa_agent.agent import DEFAULT_MODEL, ask  # noqa: E402
from src.qa_agent.cost_logger import (  # noqa: E402
    CostLogWriter,
    aggregate_by_prompt_type,
    aggregate_by_source,
    load_cost_log,
)
from src.qa_agent.eval import DELAY_BETWEEN_CALLS_S, load_questions  # noqa: E402
from src.qa_agent.reliability import evaluate_reliability  # noqa: E402

DEFAULT_QUESTION_SETS = (
    "data/eval/questions.json",
    "data/eval/questions_2.json",
    "data/eval/questions_3.json",
)
SELECTED_QUESTION_IDS = ["q1", "q4", "q5", "q6", "q13", "q15", "q18", "q20", "q24", "q30"]

RESULTS_DIR = Path("data/reliability")
RELIABILITY_RESULTS_PATH = RESULTS_DIR / "reliability_results.json"
RELIABILITY_REPORT_PATH = RESULTS_DIR / "RELIABILITY_REPORT.md"
RELIABILITY_COST_LOG_PATH = Path("data/cost/reliability_cost_log.jsonl")
COST_REPORT_PATH = Path("data/cost/COST_REPORT.md")


def load_selected_questions(ids=SELECTED_QUESTION_IDS, question_paths=DEFAULT_QUESTION_SETS) -> list[dict]:
    by_id = {}
    for path in question_paths:
        for q in load_questions(Path(path)):
            by_id[q["id"]] = q
    return [by_id[qid] for qid in ids]


def run_reliability_pass(
    questions: list[dict], model: str, cost_log_path: Path, results_path: Path,
) -> list[dict]:
    cost_log_path.unlink(missing_ok=True)  # fresh log per run, matches cost_eval.py
    writer = CostLogWriter(cost_log_path)

    results = []
    for i, q in enumerate(questions, 1):
        print(f"[{i}/{len(questions)}] {q['id']}: {q['question']}", flush=True)

        def ask_with_delay(question_text, _qid=q["id"]):
            result = ask(question_text, model=model, cost_sink=writer, question_id=_qid)
            time.sleep(DELAY_BETWEEN_CALLS_S)
            return result

        try:
            result = evaluate_reliability(q["question"], ask_with_delay)
            record = result.to_dict()
            record["question_id"] = q["id"]
            print(
                f"  -> {record['verdict']} ({record['num_samples']} samples, "
                f"agreement={record['agreement_fraction']:.2f})",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001 -- one bad question shouldn't abort the whole pass
            record = {"question_id": q["id"], "question": q["question"], "verdict": "ERROR", "error": str(exc)}
            print(f"  ERROR: {exc}", file=sys.stderr, flush=True)

        results.append(record)
        # Checkpoint after every question, not just at the end -- tonight's
        # failure mode (a mid-run exception losing every prior result because
        # nothing was written until the full loop finished) shouldn't be
        # possible to repeat.
        results_path.write_text(json.dumps(results, indent=2) + "\n")

    return results


def write_reliability_report(results: list[dict], out_path: Path) -> None:
    verdict_counts = {"PASS": 0, "FAIL": 0, "INCONCLUSIVE": 0, "ERROR": 0}
    total_samples = 0
    for r in results:
        verdict_counts[r["verdict"]] = verdict_counts.get(r["verdict"], 0) + 1
        total_samples += r.get("num_samples", 0)

    lines = [
        "# Reliability report",
        "",
        f"Generated from {len(results)} questions, {total_samples} total live samples "
        f"(adaptive 3-then-5 per question, early-stopped on unanimous agreement).",
        "",
        f"**PASS: {verdict_counts['PASS']} / FAIL: {verdict_counts['FAIL']} / "
        f"INCONCLUSIVE: {verdict_counts['INCONCLUSIVE']} / ERROR: {verdict_counts['ERROR']}**",
        "",
        "| Question | Verdict | Samples | Agreement | Tool-trace | Entity-overlap | Confidence-stable |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        if r["verdict"] == "ERROR":
            lines.append(f"| {r['question_id']}: {r['question']} | ERROR | - | - | - | - | {r['error']} |")
            continue
        # recovered_from_stdout entries (a run resumed after a crash lost the
        # fine-grained fingerprint detail, salvaging only what was printed)
        # have verdict/num_samples/agreement_fraction but not the three
        # sub-metrics -- show "-" rather than KeyError.
        note = "recovered from stdout, no fingerprint detail" if r.get("recovered_from_stdout") else ""
        tool_trace = f"{r['tool_trace_agreement']:.2f}" if "tool_trace_agreement" in r else "-"
        entity_overlap = f"{r['entity_overlap_agreement']:.2f}" if "entity_overlap_agreement" in r else "-"
        confidence = f"{r['confidence_stability']:.2f}" if "confidence_stability" in r else note
        lines.append(
            f"| {r['question_id']}: {r['question']} | {r['verdict']} | {r['num_samples']} | "
            f"{r['agreement_fraction']:.2f} | {tool_trace} | {entity_overlap} | {confidence} |"
        )

    out_path.write_text("\n".join(lines) + "\n")


def append_reliability_cost_section(cost_log_path: Path, report_path: Path) -> None:
    """Adds a distinct 'Reliability run' section to the existing cost report,
    computed from the reliability run's own cost log -- kept separate from
    the single-pass run's tables rather than blended into them, since the
    two runs have very different call shapes (1 call/question vs 3-5
    repeated samples/question) and averaging them together would conflate
    two different sampling methods in the same numbers."""
    records = load_cost_log(cost_log_path)
    by_type = aggregate_by_prompt_type(records)
    by_source = aggregate_by_source(records)

    lines = [
        "",
        "---",
        "",
        "## Reliability run (separate from the single-pass profile above)",
        "",
        f"Generated from {len(records)} logged LLM calls across {len(SELECTED_QUESTION_IDS)} questions, "
        "3-5 repeated samples each (adaptive early-stopping). Kept as its own section, not blended into "
        "the tables above, since repeated-sampling calls have a different shape than the single-pass run "
        "and would skew those averages if merged in.",
        "",
        "### Tokens by prompt type",
        "",
        "| Prompt type | Questions | Calls | Prompt tokens | Completion tokens | Avg tokens/question |",
        "|---|---|---|---|---|---|",
    ]
    for ptype, v in by_type.items():
        lines.append(
            f"| {ptype} | {v['num_questions']} | {v['num_calls']} | {v['total_prompt_tokens']} | "
            f"{v['total_completion_tokens']} | {v['avg_tokens_per_question']} |"
        )

    lines += ["", "### Estimated tokens by source", "", "| Source | Estimated tokens | Share of total |", "|---|---|---|"]
    for tag, v in by_source.items():
        lines.append(f"| {tag} | {v['estimated_tokens']} | {v['share_of_total']:.1%} |")

    with open(report_path, "a") as f:
        f.write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser(description="Run the reliability harness over a fixed question subset.")
    ap.add_argument(
        "--ids", nargs="+", default=SELECTED_QUESTION_IDS,
        help="Question ids to run (default: the full 10-question selection). "
             "Use this to resume a partial run without re-spending quota on already-completed questions.",
    )
    ap.add_argument(
        "--cost-log", default=str(RELIABILITY_COST_LOG_PATH),
        help="Where to write this run's cost log (default overwrites the shared one -- "
             "pass a different path when resuming a partial run so it doesn't clobber prior results).",
    )
    args = ap.parse_args()

    load_dotenv()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    questions = load_selected_questions(ids=args.ids)
    results = run_reliability_pass(questions, DEFAULT_MODEL, Path(args.cost_log), RELIABILITY_RESULTS_PATH)

    write_reliability_report(results, RELIABILITY_REPORT_PATH)
    cost_log_path = Path(args.cost_log)
    if cost_log_path.exists() and cost_log_path.stat().st_size > 0:
        append_reliability_cost_section(cost_log_path, COST_REPORT_PATH)

    print(f"\nWrote {RELIABILITY_RESULTS_PATH}, {RELIABILITY_REPORT_PATH}, "
          f"and appended a reliability section to {COST_REPORT_PATH}")


if __name__ == "__main__":
    main()
