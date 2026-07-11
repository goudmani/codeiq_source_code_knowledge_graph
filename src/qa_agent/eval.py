#!/usr/bin/env python3
"""
eval.py

Runs the 10 self-generated questions in data/eval/questions.json against the
Q&A agent (agent.py) for every model in MODELS -- head-to-head, not just one
-- and writes the results as both raw JSON and a human-readable comparison
report. This is the harness used *while building* the agent (per the brief:
write the eval set before building, then measure quality as you iterate), not
just a final report.

Sequential (not parallel) to stay under Groq free-tier rate limits; a failed
question is recorded as an error and does not abort the run.

Usage:
  python3 eval.py
  python3 eval.py --questions data/eval/questions.json --out-dir data/eval
"""
import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv  # noqa: E402

from src.qa_agent.agent import MODELS, ask  # noqa: E402

DEFAULT_QUESTIONS_PATH = "data/eval/questions.json"
DEFAULT_OUT_DIR = "data/eval"
DELAY_BETWEEN_CALLS_S = 2


def load_questions(path: Path) -> list[dict]:
    return json.loads(path.read_text())


def run_eval(questions: list[dict], models: list[str]) -> list[dict]:
    runs = []
    total = len(questions) * len(models)
    n = 0

    for model in models:
        for q in questions:
            n += 1
            print(f"[{n}/{total}] {model} :: {q['id']}", flush=True)
            try:
                result = ask(q["question"], model=model)
                cited_ids = {s["id"] for s in result["sources"]}
                entity_hit = bool(cited_ids & set(q["expected_entities"]))
                runs.append(
                    {
                        "question_id": q["id"],
                        "question": q["question"],
                        "expected_answer": q["expected_answer"],
                        "expected_entities": q["expected_entities"],
                        "entity_hit": entity_hit,
                        "error": None,
                        **result,
                    }
                )
            except Exception as exc:  # noqa: BLE001 -- eval must survive a single bad run
                runs.append(
                    {
                        "question_id": q["id"],
                        "question": q["question"],
                        "expected_answer": q["expected_answer"],
                        "expected_entities": q["expected_entities"],
                        "entity_hit": False,
                        "error": str(exc),
                        "answer": None,
                        "confidence": None,
                        "confidence_rationale": None,
                        "sources": [],
                        "model": model,
                        "latency_s": None,
                        "tool_calls": [],
                    }
                )
            time.sleep(DELAY_BETWEEN_CALLS_S)

    return runs


def summarize(runs: list[dict], models: list[str]) -> dict:
    summary = {}
    for model in models:
        model_runs = [r for r in runs if r["model"] == model]
        ok_runs = [r for r in model_runs if r["error"] is None]
        latencies = [r["latency_s"] for r in ok_runs if r["latency_s"] is not None]
        confidence_counts = defaultdict(int)
        for r in ok_runs:
            confidence_counts[r["confidence"]] += 1

        summary[model] = {
            "total": len(model_runs),
            "errors": len(model_runs) - len(ok_runs),
            "entity_hit_rate": round(sum(r["entity_hit"] for r in model_runs) / len(model_runs), 2) if model_runs else 0,
            "avg_latency_s": round(sum(latencies) / len(latencies), 2) if latencies else None,
            "confidence_counts": dict(confidence_counts),
        }
    return summary


def write_markdown_report(runs: list[dict], summary: dict, models: list[str], out_path: Path):
    by_question = defaultdict(dict)
    for r in runs:
        by_question[r["question_id"]][r["model"]] = r

    lines = ["# CodeIQ Q&A Agent -- Eval Results", ""]
    lines.append(f"{len(by_question)} questions x {len(models)} models = {len(runs)} runs.")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Model | Entity-hit rate | Avg latency (s) | Errors | Confidence (H/M/L) |")
    lines.append("|---|---|---|---|---|")
    for model in models:
        s = summary[model]
        conf = s["confidence_counts"]
        conf_str = f"{conf.get('High', 0)}/{conf.get('Medium', 0)}/{conf.get('Low', 0)}"
        lines.append(f"| `{model}` | {s['entity_hit_rate']} | {s['avg_latency_s']} | {s['errors']} | {conf_str} |")
    lines.append("")

    lines.append("## Per-question comparison")
    lines.append("")
    for qid, by_model in by_question.items():
        first = next(iter(by_model.values()))
        lines.append(f"### {qid}: {first['question']}")
        lines.append("")
        lines.append(f"_Expected: {first['expected_answer']}_")
        lines.append("")
        for model in models:
            r = by_model.get(model)
            if not r:
                continue
            lines.append(f"**`{model}`** -- confidence: {r['confidence']} ({r['confidence_rationale']}) -- "
                         f"entity hit: {'yes' if r['entity_hit'] else 'no'} -- latency: {r['latency_s']}s")
            if r["error"]:
                lines.append(f"> ERROR: {r['error']}")
            else:
                lines.append(f"> {r['answer']}")
            lines.append("")
        lines.append("---")
        lines.append("")

    out_path.write_text("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description="Run the eval question set against every configured model.")
    ap.add_argument("--questions", default=DEFAULT_QUESTIONS_PATH)
    ap.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    ap.add_argument("--models", nargs="+", default=list(MODELS), choices=list(MODELS))
    args = ap.parse_args()

    load_dotenv()

    questions = load_questions(Path(args.questions))
    runs = run_eval(questions, args.models)
    summary = summarize(runs, args.models)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(json.dumps({"runs": runs, "summary": summary}, indent=2))
    write_markdown_report(runs, summary, args.models, out_dir / "RESULTS.md")

    print(f"\nWrote {out_dir / 'results.json'} and {out_dir / 'RESULTS.md'}")
    for model, s in summary.items():
        print(f"  {model}: hit_rate={s['entity_hit_rate']} avg_latency={s['avg_latency_s']}s errors={s['errors']}")


if __name__ == "__main__":
    main()
