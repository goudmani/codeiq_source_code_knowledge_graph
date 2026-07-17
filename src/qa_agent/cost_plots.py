#!/usr/bin/env python3
"""
cost_plots.py

Renders the three tables in data/cost/COST_REPORT.md as PNG charts for the
presentation, reusing cost_logger.py's aggregation functions directly rather
than recomputing them. Pure-stdlib + matplotlib -- does not need the codeiq
conda env (no langchain/chromadb dependency), just `pip install matplotlib`.

Usage:
  python3 -m src.qa_agent.cost_plots
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402

from src.qa_agent.cost_logger import (  # noqa: E402
    aggregate_by_prompt_type,
    aggregate_by_source,
    load_cost_log,
)

DEFAULT_COST_LOG_PATH = "data/cost/cost_log.jsonl"
DEFAULT_OUT_DIR = "data/cost/plots"

# Reference palette (see the dataviz skill's palette.md) -- fixed categorical
# slot order, validated CVD-safe for a 2-series adjacent pair.
BLUE = "#2a78d6"
GREEN = "#008300"
SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "text.color": INK_PRIMARY,
    "axes.edgecolor": BASELINE,
    "axes.labelcolor": INK_SECONDARY,
    "xtick.color": INK_MUTED,
    "ytick.color": INK_MUTED,
})


def _clean_axes(ax, hide_y_spine=True):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if hide_y_spine:
        ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.tick_params(length=0)


def plot_tokens_by_prompt_type(records: list[dict], out_path: Path) -> None:
    by_type = aggregate_by_prompt_type(records)
    # Normalize by question count -- the raw totals are dominated by how many
    # questions fell into each bucket (17 discovery vs 2 transitive_impact),
    # not by how expensive that type of question actually is. Average tokens
    # per question is the fair per-type comparison; re-sort by it since
    # aggregate_by_prompt_type sorts by raw total.
    types = sorted(
        by_type.keys(),
        key=lambda t: -(by_type[t]["total_prompt_tokens"] + by_type[t]["total_completion_tokens"])
        / by_type[t]["num_questions"],
    )
    avg_prompt = [by_type[t]["total_prompt_tokens"] / by_type[t]["num_questions"] for t in types]
    avg_completion = [by_type[t]["total_completion_tokens"] / by_type[t]["num_questions"] for t in types]

    fig, ax = plt.subplots(figsize=(7.5, 5))
    x = range(len(types))
    bar_w = 0.42
    ax.bar(x, avg_prompt, bar_w, color=BLUE, label="Avg prompt tokens / question")
    ax.bar(x, avg_completion, bar_w, bottom=avg_prompt, color=GREEN, label="Avg completion tokens / question")

    for i, t in enumerate(types):
        avg_total = avg_prompt[i] + avg_completion[i]
        n = by_type[t]["num_questions"]
        ax.annotate(
            f"{avg_total:,.0f}\n({n} questions)",
            (i, avg_total), xytext=(0, 6), textcoords="offset points",
            ha="center", va="bottom", fontsize=9, color=INK_SECONDARY,
        )

    ax.set_xticks(list(x))
    ax.set_xticklabels([t.replace("_", " ") for t in types], fontsize=10)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.set_ylabel("Avg tokens per question")
    ax.set_title("Average tokens per question, by prompt type", fontsize=13, fontweight="bold", loc="left", pad=14)
    ax.grid(axis="y", color=GRIDLINE, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    _clean_axes(ax)
    ax.margins(y=0.15)
    ax.legend(frameon=False, loc="upper right", fontsize=9)

    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def plot_tokens_by_source(records: list[dict], out_path: Path) -> None:
    by_source = aggregate_by_source(records)
    items = list(by_source.items())[::-1]  # reverse: barh draws bottom-up, want largest on top
    labels = [tag.replace("tool:", "").replace("_", " ") for tag, _ in items]
    values = [v["estimated_tokens"] for _, v in items]
    shares = [v["share_of_total"] for _, v in items]

    fig, ax = plt.subplots(figsize=(7.5, 5))
    y = range(len(labels))
    ax.barh(y, values, color=BLUE, height=0.6)

    max_v = max(values) if values else 1
    for i, (v, s) in enumerate(zip(values, shares)):
        ax.annotate(
            f"{s:.1%}", (v, i), xytext=(6, 0), textcoords="offset points",
            ha="left", va="center", fontsize=9, color=INK_SECONDARY,
        )

    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_xlim(0, max_v * 1.18)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.set_xlabel("Estimated tokens (share of total, direct-labeled)")
    ax.set_title("Estimated tokens by source", fontsize=13, fontweight="bold", loc="left", pad=14)
    ax.grid(axis="x", color=GRIDLINE, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    _clean_axes(ax)

    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def main():
    log_path = Path(DEFAULT_COST_LOG_PATH)
    out_dir = Path(DEFAULT_OUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    records = load_cost_log(log_path)
    if not records:
        raise SystemExit(f"No records found in {log_path}")

    plot_tokens_by_prompt_type(records, out_dir / "tokens_by_prompt_type.png")
    plot_tokens_by_source(records, out_dir / "tokens_by_source.png")

    print(f"Wrote 2 charts to {out_dir}/")


if __name__ == "__main__":
    main()
