"""The analyst and calibration result (T381, T382): built from the stored eval files."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arena.forecasters.llm_context_cal import load_map
from arena.lab import analyst_eval as ae
from arena.lab.results import LabResult, card_markdown

ROOT = Path(__file__).parents[2]
RES = ROOT / "evals/results"


def _read(p: str) -> dict:
    return json.loads((RES / p).read_text("utf-8"))


NOV, OCT, REF = (
    _read("eval-20261128T125938.json"),
    _read("eval-20261128T155637.json"),
    _read("eval-20261126T195707.json"),
)


def _build() -> LabResult:
    ml_n = json.loads((ROOT / "evals/golden/ml-probs-power-11a.json").read_text("utf-8"))
    ml_o = json.loads((ROOT / "evals/golden/ml-probs-power.json").read_text("utf-8"))
    cal = load_map(ROOT / "lab/artefacts/llm_context_cal.json")
    assert cal is not None
    return ae.build(NOV, OCT, REF, ml_n, ml_o, cal, 1.3928, prereg_path=ROOT / ae.PREREG)


def test_the_stored_result_is_what_the_builder_makes_from_the_eval_files() -> None:
    stored = LabResult.model_validate(_read("lab-analyst-and-calibration.json"))
    assert _build().model_dump() == stored.model_dump()
    assert (ROOT / "docs/lab/analyst-and-calibration.md").read_text("utf-8") == card_markdown(
        stored
    )


def test_cost_is_the_recorded_cost_of_both_runs_and_nothing_is_counted_twice() -> None:
    r = _build()
    nov = sum(m["cost_usd"] for m in NOV["metrics"].values())
    oct_ = sum(m["cost_usd"] for m in OCT["metrics"].values())
    assert r.cost_usd == pytest.approx(nov + oct_, abs=1e-6)
    assert r.paired and all(p["split"] in ("November", "October") for p in r.paired)


def test_the_calibrated_arm_is_the_raw_answers_through_the_fixed_map() -> None:
    cal = load_map(ROOT / "lab/artefacts/llm_context_cal.json")
    assert cal is not None and (cal.a, cal.b) == (1.5656, 0.257455)
    raw = [r for r in OCT["rows"] if r["variant"] == "llm_context" and r["probability"] is not None]
    assert len(raw) == 186 and all(0 < cal.apply(r["probability"]) < 1 for r in raw)


def test_rules_are_applied_to_the_stored_numbers() -> None:
    v = {x["rule"]: x for x in ae.verdicts(_build())}
    assert v["H-A1"]["passed"] is True and "entirely below zero" in v["H-A1"]["text"]
    assert v["H-A2"]["passed"] is False and v["H-A3"]["passed"] is True
    assert v["H-C1"]["passed"] is False and v["H-C1 (second test, October)"]["passed"] is False


def test_a_replayed_ml_file_for_another_golden_set_is_refused() -> None:
    ml_n = json.loads((ROOT / "evals/golden/ml-probs-power-11a.json").read_text("utf-8"))
    cal = load_map(ROOT / "lab/artefacts/llm_context_cal.json")
    assert cal is not None
    with pytest.raises(ValueError, match="another golden file"):
        ae.build(NOV, OCT, REF, ml_n, ml_n, cal, 1.0, prereg_path=ROOT / ae.PREREG)
