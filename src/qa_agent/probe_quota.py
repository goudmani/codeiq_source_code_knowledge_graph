#!/usr/bin/env python3
"""
probe_quota.py

Cheap Groq quota probe: sends a 1-token request per model and reports
whether the account currently has quota for it. Costs ~1-2 tokens per
model -- run this before a full eval so an exhausted daily (TPD) budget
is discovered for pennies instead of by burning a real agent question
(~2500-3500 tokens each).

Limit of the probe: a 1-token "OK" only proves quota isn't fully
exhausted -- it does NOT prove a full agent question will fit (observed
live: probe passed while only ~2.5K daily tokens remained, then the real
run failed). Treat "OK" as "worth trying," not a guarantee.

Usage:
  python -m src.qa_agent.probe_quota
  python -m src.qa_agent.probe_quota --models openai/gpt-oss-120b
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import groq  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from src.qa_agent.agent import MODELS, _load_api_keys  # noqa: E402


def probe(models: list[str]) -> dict[str, str]:
    status = {}
    for label, key in _load_api_keys():
        client = groq.Groq(api_key=key)
        for model in models:
            try:
                client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "hi"}],
                    max_completion_tokens=1,
                )
                status[f"{label} / {model}"] = "OK -- not rate limited"
            except groq.RateLimitError as exc:
                status[f"{label} / {model}"] = f"RATE LIMITED -- {str(exc)[:300]}"
            except groq.AuthenticationError as exc:
                status[f"{label} / {model}"] = f"BAD KEY -- {str(exc)[:200]}"
    return status


def main():
    ap = argparse.ArgumentParser(description="Probe Groq quota with a 1-token request per model.")
    ap.add_argument("--models", nargs="+", default=list(MODELS), choices=list(MODELS))
    args = ap.parse_args()

    load_dotenv()
    if not os.environ.get("GROQ_API_KEY"):
        raise SystemExit("GROQ_API_KEY is not set (add it to .env, see .env.example)")

    for model, result in probe(args.models).items():
        print(f"{model}: {result}")


if __name__ == "__main__":
    main()
