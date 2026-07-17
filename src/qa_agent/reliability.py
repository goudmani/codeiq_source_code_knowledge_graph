#!/usr/bin/env python3
"""
reliability.py

Self-consistency / test-retest reliability testing for the qa_agent: ask the
same question multiple times and check the agent's *decisions* agree across
runs. See reports/reliability-and-cost-testing.md for the full design reasoning.

LLM output isn't deterministic even at temperature 0 (batched GPU
floating-point execution varies run to run), so "consistent" can't mean
exact answer-text match. Everything here compares structured decisions
instead: which tool was called first, which entities got cited, what
confidence level was reported. Two runs' decisions "agree" if:
  - same first tool called, AND
  - same confidence level, AND
  - cited-entity-set Jaccard overlap >= ENTITY_JACCARD_THRESHOLD

Borrowed from AgentAssay (arXiv:2603.02601):
  - Behavioral fingerprinting: reduce one run to the three decisions above,
    so two runs can be compared in one step instead of three.
  - Adaptive/early-stopping sampling: run 3 first; only spend the extra 2
    (5 total) if the first 3 don't all agree.
  - Three-valued verdict (PASS/FAIL/INCONCLUSIVE) instead of a forced binary
    pass/fail -- with a handful of samples, partial agreement is a real,
    distinct outcome, not just "not passing."
"""
from __future__ import annotations

from dataclasses import dataclass

ENTITY_JACCARD_THRESHOLD = 0.7  # starting default, see design doc -- not yet
                                 # empirically tuned against real variance data
INITIAL_SAMPLES = 3
MAX_SAMPLES = 5
PASS_FRACTION = 4 / 5   # >=4/5 samples agreeing with the reference -> PASS
FAIL_FRACTION = 1 / 5   # <=1/5 agreeing -> FAIL; between the two -> INCONCLUSIVE


@dataclass(frozen=True)
class Fingerprint:
    """One run's key decisions, reduced to a single comparable object --
    literally just the tool-trace-agreement, entity-overlap, and
    confidence-stability signals bundled together, not new complexity on
    top of them."""
    first_tool_used: str | None
    cited_entity_ids: frozenset[str]
    confidence: str


def build_fingerprint(ask_result: dict) -> Fingerprint:
    """Build a Fingerprint from one ask()-shaped result dict."""
    first_tool = ask_result["tool_calls"][0]["tool"] if ask_result["tool_calls"] else None
    entity_ids = frozenset(s["id"] for s in ask_result.get("sources", []))
    return Fingerprint(
        first_tool_used=first_tool,
        cited_entity_ids=entity_ids,
        confidence=ask_result["confidence"],
    )


def jaccard(a: frozenset, b: frozenset) -> float:
    """Jaccard overlap of two sets. Two empty sets count as fully agreeing
    (both retrieved nothing -- that's itself a form of agreement), which
    matches how set operations naturally fall out (union of two empty sets
    is empty) if handled explicitly rather than dividing by zero."""
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def fingerprints_agree(a: Fingerprint, b: Fingerprint, threshold: float = ENTITY_JACCARD_THRESHOLD) -> bool:
    """Two fingerprints agree if they picked the same first tool, reported
    the same confidence level, and their cited-entity sets overlap at least
    `threshold` (Jaccard)."""
    return (
        a.first_tool_used == b.first_tool_used
        and a.confidence == b.confidence
        and jaccard(a.cited_entity_ids, b.cited_entity_ids) >= threshold
    )


def tool_trace_agreement(fingerprints: list[Fingerprint]) -> float:
    """Fraction of fingerprints whose first_tool_used matches the first
    fingerprint's (the reference sample)."""
    if not fingerprints:
        return 0.0
    ref = fingerprints[0].first_tool_used
    return sum(1 for fp in fingerprints if fp.first_tool_used == ref) / len(fingerprints)


def entity_overlap_agreement(fingerprints: list[Fingerprint], threshold: float = ENTITY_JACCARD_THRESHOLD) -> float:
    """Fraction of fingerprints whose cited-entity set overlaps the
    reference sample's at least `threshold` (Jaccard)."""
    if not fingerprints:
        return 0.0
    ref = fingerprints[0].cited_entity_ids
    return sum(1 for fp in fingerprints if jaccard(ref, fp.cited_entity_ids) >= threshold) / len(fingerprints)


def confidence_stability(fingerprints: list[Fingerprint]) -> float:
    """Fraction of fingerprints reporting the same confidence level as the
    reference sample."""
    if not fingerprints:
        return 0.0
    ref = fingerprints[0].confidence
    return sum(1 for fp in fingerprints if fp.confidence == ref) / len(fingerprints)


@dataclass
class ReliabilityResult:
    question: str
    verdict: str  # "PASS" | "FAIL" | "INCONCLUSIVE"
    num_samples: int
    agreement_fraction: float
    tool_trace_agreement: float
    entity_overlap_agreement: float
    confidence_stability: float
    fingerprints: list[Fingerprint]

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "verdict": self.verdict,
            "num_samples": self.num_samples,
            "agreement_fraction": round(self.agreement_fraction, 4),
            "tool_trace_agreement": round(self.tool_trace_agreement, 4),
            "entity_overlap_agreement": round(self.entity_overlap_agreement, 4),
            "confidence_stability": round(self.confidence_stability, 4),
            "fingerprints": [
                {
                    "first_tool_used": fp.first_tool_used,
                    "cited_entity_ids": sorted(fp.cited_entity_ids),
                    "confidence": fp.confidence,
                }
                for fp in self.fingerprints
            ],
        }


def _agreement_fraction(fingerprints: list[Fingerprint], threshold: float) -> float:
    ref = fingerprints[0]
    return sum(1 for fp in fingerprints if fingerprints_agree(ref, fp, threshold)) / len(fingerprints)


def _verdict_from_fraction(fraction: float) -> str:
    if fraction >= PASS_FRACTION:
        return "PASS"
    if fraction <= FAIL_FRACTION:
        return "FAIL"
    return "INCONCLUSIVE"


def evaluate_reliability(
    question: str,
    ask_fn,
    threshold: float = ENTITY_JACCARD_THRESHOLD,
) -> ReliabilityResult:
    """Run `question` through ask_fn (agent.ask, or a partial with
    model/tag/cost_sink pre-bound) 3 times; if all 3 agree with the first
    sample, stop early (PASS). Otherwise run 2 more (5 total) and verdict on
    the full agreement fraction: >=4/5 PASS, 2-3/5 INCONCLUSIVE, <=1/5 FAIL.
    """
    fingerprints = [build_fingerprint(ask_fn(question)) for _ in range(INITIAL_SAMPLES)]
    fraction = _agreement_fraction(fingerprints, threshold)

    if fraction == 1.0:
        verdict = "PASS"
    else:
        fingerprints += [build_fingerprint(ask_fn(question)) for _ in range(MAX_SAMPLES - INITIAL_SAMPLES)]
        fraction = _agreement_fraction(fingerprints, threshold)
        verdict = _verdict_from_fraction(fraction)

    return ReliabilityResult(
        question=question,
        verdict=verdict,
        num_samples=len(fingerprints),
        agreement_fraction=fraction,
        tool_trace_agreement=tool_trace_agreement(fingerprints),
        entity_overlap_agreement=entity_overlap_agreement(fingerprints, threshold),
        confidence_stability=confidence_stability(fingerprints),
        fingerprints=fingerprints,
    )


# Entities in the bluesky-social/social-app index with no LLM-generated
# `description` field (7/3820, see reports/reliability-and-cost-testing.md).
# Ready-to-run scenario: does the agent stay grounded in the code snippet
# when asked about one of these, or does it hallucinate a plausible-sounding
# description across repeated runs? A per-entity question, not a general
# reliability check -- run through evaluate_reliability() same as any other
# question, on tag="bluesky-social_social-app_main".
MISSING_DESCRIPTION_ENTITIES = [
    "src/alf/fonts.ts",
    "src/geolocation/types.ts",
    "src/components/Dialog/types.ts",
    "src/components/dms/ActionsWrapper.web.tsx#ActionsWrapper",
    "src/components/icons/CircleCheck.tsx",
    "src/components/icons/Message.tsx",
    "src/components/PolicyUpdateOverlay/logger.ts",
]


def missing_description_question(entity_id: str) -> str:
    """A natural-language question that should surface `entity_id` as a
    cited source, for probing the missing-description scenario above.

    File entities (no "#" in the id -- the id is just the file path) are
    asked about by full path, not basename: two of the seven entities here
    share the basename "types.ts" (src/geolocation/types.ts and
    src/components/Dialog/types.ts), so a bare-basename question would be
    ambiguous about which one is meant.
    """
    if "#" in entity_id:
        return f"What does {entity_id.split('#')[-1]} do, and what is it for?"
    return f"What does the file {entity_id} do, and what is it for?"
