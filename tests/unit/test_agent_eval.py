# ruff: noqa: E501
"""T355/T365: lab results of the skills and committee evaluations, and the page that shows them."""

import json
from pathlib import Path

from click.testing import CliRunner

from arena.cli import main
from arena.lab import agent_eval as ae
from arena.lab.results import LabResult
from arena.site import llm_engineering as le


def _arm(brier: float, cost: float, n: int = 90) -> dict:
    return {
        "n": n, "answered": n, "brier": brier, "log_score": 0.6, "ece": 0.05,
        "base_rate_brier_same_items": 0.24, "cost_usd": cost, "skips": {},
    }  # fmt: skip


def _run(committee_diff: float = -0.01, committee_cost: float = 0.3) -> dict:
    return {
        "run_id": "eval-x", "created_at": "2026-11-27T00:00:00+00:00", "golden": "power-2026-11a.jsonl",
        "golden_sha256": "a" * 64, "n_items": 90,
        "metrics": {
            "agent": _arm(0.2, 0.05), "agent_quant": _arm(0.18, 0.08), "agent_skills": _arm(0.17, 0.1),
            "agent_committee": _arm(0.17 + committee_diff, committee_cost),
        },
        "versions": {k: f"v-{k}" for k in ("agent", "agent_quant", "agent_skills", "agent_committee")},
        "paired": [
            {"a": "agent_quant", "b": "agent_skills", "diff": 0.01, "lo": 0.002, "hi": 0.018, "n": 90, "days": 15},
            {"a": "agent_skills", "b": "agent_committee", "diff": -committee_diff, "lo": -committee_diff - 0.01, "hi": -committee_diff + 0.01, "n": 90, "days": 15},
        ],
    }  # fmt: skip


def test_skills_result_flips_the_pair_and_applies_the_rules() -> None:
    r = ae.build(_run(), "agent-skills")
    assert isinstance(r, LabResult) and r.experiment == "agent-skills"
    (p,) = r.paired
    assert (p["a"], p["b"]) == ("agent_skills", "agent_quant") and p["diff"] == -0.01
    assert p["lo"] == -0.018 and p["hi"] == -0.002
    h1, h2 = ae.verdicts(r)
    assert h1["passed"] is True  # whole interval below zero
    assert h2["passed"] is True  # 0.1 / 0.08 = 1.25 <= 1.3
    assert r.cost_usd == 0.23
    assert "agent_skills" in ae.decision_sentence(r) or "pre-registered" in ae.decision_sentence(r)


def test_committee_rules_pass_fail_or_cannot_be_applied() -> None:
    run = _run(committee_diff=-0.02, committee_cost=0.2)  # interval -0.03..-0.01, cost 2.0x
    r = ae.build(run, "agent-committee")
    assert [v["passed"] for v in ae.verdicts(r)] == [True, True]
    assert "dry run" in ae.decision_sentence(r)
    pricey = ae.build(_run(committee_diff=-0.02, committee_cost=0.3), "agent-committee")
    assert [v["passed"] for v in ae.verdicts(pricey)] == [True, False]  # 3.0x > 2.5x
    assert "stays off" in ae.decision_sentence(pricey)
    run = _run(committee_diff=0.0)
    assert (
        ae.verdicts(ae.build(run, "agent-committee"))[0]["passed"] is False
    )  # interval spans zero
    no_pair = _run()
    no_pair["paired"] = []
    nr = ae.build(no_pair, "agent-committee")
    assert ae.verdicts(nr)[0]["passed"] is None and "cannot be applied" in ae.decision_sentence(nr)


def test_a_run_without_the_arms_is_refused() -> None:
    run = _run()
    del run["metrics"]["agent_committee"]
    try:
        ae.build(run, "agent-committee")
    except ValueError as exc:
        assert "agent_committee" in str(exc)
    else:
        raise AssertionError("expected a refusal")


def test_cli_writes_a_valid_result_and_the_page_shows_rows_and_the_flow(tmp_path: Path) -> None:
    run = tmp_path / "eval-x.json"
    run.write_text(json.dumps(_run(committee_diff=-0.02, committee_cost=0.2)))
    for exp in ("agent-skills", "agent-committee"):
        out = tmp_path / f"lab-{exp}.json"
        res = CliRunner().invoke(
            main, ["lab", "agent-eval", str(run), "--experiment", exp, "--out", str(out)]
        )
        assert res.exit_code == 0, res.output
        LabResult.model_validate(json.loads(out.read_text()))
        assert "H-" in res.output
    rows = le._agent_rows(tmp_path)
    assert [r["key"] for r in rows] == ["agent-skills", "agent-committee"]
    assert (
        "0.1500" in rows[1]["result"]
        and "0.1700" in rows[1]["result"]
        and "0.2400" in rows[1]["result"]
    )
    c = le._committee(tmp_path)
    assert c is not None and "<svg" in str(c["svg"]) and "Scout" in str(c["svg"])
    assert [v["rule"] for v in c["verdicts"]] == ["H-C1", "H-C2"]


def test_without_result_files_there_is_no_row_and_no_committee_section(tmp_path: Path) -> None:
    assert le._agent_rows(tmp_path) == [] and le._committee(tmp_path) is None


def test_the_flow_diagram_has_no_figures_and_readable_text() -> None:
    svg = str(le.committee_flow_svg())
    assert "Chair" in svg and "Skeptic" in svg and "critique" in svg
    import re

    assert not re.search(r"\d\.\d", svg.replace("1.5", ""))


def test_same_items_brier_and_cost_per_answered_question_are_generated() -> None:
    run = _run()
    run["metrics"]["agent_committee"] = {**_arm(0.17, 0.2), "answered": 2, "n": 4}
    run["metrics"]["agent_skills"] = {**_arm(0.1, 0.1), "n": 4, "answered": 4}
    run["rows"] = [
        {"variant": "agent_committee", "question_id": "a", "probability": 0.8, "outcome": 1},
        {"variant": "agent_committee", "question_id": "b", "probability": 0.2, "outcome": 0},
        {"variant": "agent_committee", "question_id": "c", "probability": None, "outcome": 1},
        {"variant": "agent_skills", "question_id": "a", "probability": 0.6, "outcome": 1},
        {"variant": "agent_skills", "question_id": "b", "probability": 0.4, "outcome": 0},
        {"variant": "agent_skills", "question_id": "c", "probability": 0.9, "outcome": 1},
    ]
    r = ae.build(run, "agent-committee")
    same = r.metrics["agent_skills / same items as agent_committee"]
    assert same == {"n": 2, "brier": 0.16}  # (0.16 + 0.16) / 2
    assert any("answered 2 of 4" in n and "100.00 US$ per 1,000" in n for n in r.notes)
    assert r.cost_usd == 0.2  # only the committee arm; agent_skills is counted in the skills result


def test_the_committed_results_validate_and_their_verdicts_are_reproducible() -> None:
    root = Path("evals/results")
    run = root / "eval-20261126T195707.json"
    if not run.is_file():
        return
    res = json.loads(run.read_text())
    for exp in ("agent-skills", "agent-committee"):
        built = ae.build(res, exp)
        stored = LabResult.model_validate(json.loads((root / f"lab-{exp}.json").read_text()))
        assert stored == built
