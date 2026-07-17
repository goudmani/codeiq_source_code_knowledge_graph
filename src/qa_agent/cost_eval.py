#!/usr/bin/env python3
"""
cost_eval.py

Runs a single, non-repeated pass over the eval question sets (default:
data/eval/questions.json, questions_2.json, questions_3.json) against the
Q&A agent with cost_sink wired in, producing a first token/cost profile.
See docs/reliability-and-cost-testing.md for the design behind this.

This intentionally does NOT repeat questions the way the reliability harness
does -- a single pass over the existing 30 questions already gives a cost
profile at a fraction of the quota cost of any 3-5x repeated run, per the
design doc's sequencing note.

Each run starts from a fresh cost log (any existing one at --cost-log is
overwritten, not appended to), so results.json/RESULTS.md never mix records
from separate runs.

Usage:
  python3 -m src.qa_agent.cost_eval
  python3 -m src.qa_agent.cost_eval --questions data/eval/questions.json
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv  # noqa: E402

from src.qa_agent.agent import DEFAULT_MODEL, MODELS, ask  # noqa: E402
from src.qa_agent.cost_logger import CostLogWriter, load_cost_log, write_cost_report  # noqa: E402
from src.qa_agent.eval import DELAY_BETWEEN_CALLS_S, load_questions  # noqa: E402

DEFAULT_QUESTION_SETS = (
    "data/eval/questions.json",
    "data/eval/questions_2.json",
    "data/eval/questions_3.json",
)
DEFAULT_COST_LOG_PATH = "data/cost/cost_log.jsonl"
DEFAULT_COST_REPORT_PATH = "data/cost/COST_REPORT.md"


def run_cost_pass(question_paths: list[str], model: str, cost_log_path: str) -> None:
    log_path = Path(cost_log_path)
    log_path.unlink(missing_ok=True)  # fresh log per run, not an append across runs
    writer = CostLogWriter(log_path)

    question_sets = [(p, load_questions(Path(p))) for p in question_paths]
    total = sum(len(qs) for _, qs in question_sets)
    n = 0
    for path, questions in question_sets:
        for q in questions:
            n += 1
            print(f"[{n}/{total}] {model} :: {q['id']} ({path})", flush=True)
            try:
                ask(q["question"], model=model, cost_sink=writer, question_id=q["id"])
            except Exception as exc:  # noqa: BLE001 -- one bad question shouldn't abort the cost pass
                print(f"  ERROR: {exc}", file=sys.stderr)
            time.sleep(DELAY_BETWEEN_CALLS_S)


def main():
    ap = argparse.ArgumentParser(
        description="Single non-repeated pass over the eval question sets, with cost tracking, "
                     "to produce a first token/cost profile."
    )
    ap.add_argument("--questions", nargs="+", default=list(DEFAULT_QUESTION_SETS))
    ap.add_argument("--model", default=DEFAULT_MODEL, choices=list(MODELS))
    ap.add_argument("--cost-log", default=DEFAULT_COST_LOG_PATH)
    ap.add_argument("--report", default=DEFAULT_COST_REPORT_PATH)
    args = ap.parse_args()

    load_dotenv()

    run_cost_pass(args.questions, args.model, args.cost_log)

    records = load_cost_log(args.cost_log)
    write_cost_report(records, args.report)
    print(f"\nWrote {args.cost_log} ({len(records)} records) and {args.report}")


if __name__ == "__main__":
    main()
