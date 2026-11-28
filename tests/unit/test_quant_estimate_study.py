"""The `quant-r2` estimate was chosen on October by the pre-registered rule (T399)."""

from __future__ import annotations

import sys
from pathlib import Path

from arena.evals.golden import load
from arena.lab import quant_estimate as qe

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import quant_estimate_study as study  # noqa: E402

OCT, _ = load(ROOT / "evals/golden/power-2026-10.jsonl")


def test_card_is_current() -> None:
    assert study.OUT.read_text(encoding="utf-8") == study.render()


def test_the_served_estimate_is_the_lowest_october_candidate_by_the_registered_rule() -> None:
    sel = qe.selection(OCT)
    thr = [t for t in sel if t != "up_vs_today"]
    mean = {n: sum(sel[t][n] for t in thr) / len(thr) for n in qe.CANDIDATES_THRESHOLD}
    assert min(mean, key=mean.get) == "persistence, normal error (r2)"
    up = sel["up_vs_today"]
    assert min(up, key=up.get) == "same-weekday change, normal tail (r2)"


def test_the_candidate_functions_are_what_the_tool_serves() -> None:
    for it in OCT[:60]:
        q = it.question
        cand = (
            qe.CANDIDATES_UP["same-weekday change, normal tail (r2)"]
            if q.template == "up_vs_today"
            else qe.CANDIDATES_THRESHOLD["persistence, normal error (r2)"]
        )
        assert abs(qe.r2_estimate(q, it.context) - cand(q, it.context)) < 1e-3  # tool rounds


def test_the_frozen_r1_copy_reproduces_the_r1_estimates_november_brier() -> None:
    nov, _ = load(ROOT / "evals/golden/power-2026-11a.jsonl")
    brier = sum((qe.r1_estimate(i.question, i.context) - i.outcome) ** 2 for i in nov) / len(nov)
    assert round(brier, 4) == 0.1438  # the r1 estimate, computed from the stored contexts
