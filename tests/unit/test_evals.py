"""LLM evaluation harness (T124): golden set, runner, metrics and the CI gate."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner
from power_fixtures import fixture_domain

from arena.clock import FixedClock
from arena.evals.golden import build, dump, load
from arena.evals.run import KIND, EvalCaps, run, sample
from arena.llm.client import FakeLLM

GOLDEN = Path(__file__).resolve().parents[2] / "evals" / "golden" / "power-2026-10.jsonl"
NOW = datetime(2026, 11, 13, 12, tzinfo=UTC)
GOOD = json.dumps({"probability": 0.7, "rationale": "r", "key_factors": []})


def test_golden_set_round_trip_and_no_open_questions(tmp_path) -> None:
    dom = fixture_domain()
    items = build(dom, date(2026, 10, 24), date(2026, 10, 26), datetime(2026, 10, 28, tzinfo=UTC))
    assert items and all(it.outcome in (0, 1) for it in items)
    assert all(it.asof.date() == it.question.batch_date for it in items)
    # Context is the as-of context: never contains the target day.
    for it in items:
        assert all(r["day"] < it.question.target_date.isoformat() for r in it.context["daily"])
    sha = dump(items, tmp_path / "g.jsonl")
    back, sha2 = load(tmp_path / "g.jsonl")
    assert sha == sha2 and [b.question for b in back] == [i.question for i in items]


def test_sample_is_seeded_and_stratified() -> None:
    items, _ = load(GOLDEN)
    a, b = sample(items, 12), sample(items, 12)
    assert [x.question.question_id for x in a] == [x.question.question_id for x in b]
    assert len({x.question.template for x in a}) >= 5  # spread over templates
    assert sample(items, None) == list(items)


def test_metrics_repairs_and_parse_failures(tmp_path) -> None:
    items, sha = load(GOLDEN)
    items = sample(items, 4)
    calls = {"n": 0}

    def flaky(system, turns, tools):  # first answer of every 2nd question needs a repair
        calls["n"] += 1
        return "oops" if calls["n"] in (2, 5) else GOOD

    res = run(
        items,
        {"llm_context": FakeLLM(flaky), "llm_plain": FakeLLM(lambda *a: "x")},
        FixedClock(NOW),
        golden="g",
        golden_sha256=sha,
    )
    assert res["kind"] == KIND and res["golden_sha256"] == sha
    ctx, plain = res["metrics"]["llm_context"], res["metrics"]["llm_plain"]
    assert ctx["answered"] == 4 and ctx["repair_rate"] == 0.5 and ctx["json_valid_first_try"] == 0.5
    assert ctx["brier"] == pytest.approx(sum((0.7 - it.outcome) ** 2 for it in items) / 4, abs=1e-9)
    assert plain["answered"] == 0 and plain["skips"] == {"parse_failure": 4}
    assert plain["json_valid_first_try"] == 0.0 and res["paired"] == []


def test_caps_hold_during_an_eval() -> None:
    items, sha = load(GOLDEN)
    fake = FakeLLM(lambda *a: GOOD)
    res = run(
        sample(items, 6),
        {"llm_context": fake},
        FixedClock(NOW),
        golden="g",
        golden_sha256=sha,
        caps=EvalCaps(max_requests=3),
    )
    m = res["metrics"]["llm_context"]
    assert len(fake.calls) == 3 and m["answered"] == 3 and m["skips"] == {"budget_exhausted": 3}


def test_ci_gate_fake_run_on_the_frozen_golden_set(tmp_path) -> None:
    from arena.cli import main

    out = CliRunner().invoke(
        main,
        ["eval", "run", "--golden", str(GOLDEN), "--fake", "--limit", "18", "--out", str(tmp_path)],
    )
    assert out.exit_code == 0, out.output
    (path,) = tmp_path.glob("fake-*.json")
    res = json.loads(path.read_text())
    for m in res["metrics"].values():  # the harness gate: every answer parsed and scored
        assert m["answered"] == m["n"] == 18 and m["json_valid_first_try"] == 1.0
        assert m["brier"] == pytest.approx(0.25)
    assert res["paired"][0]["n"] == 18


def test_live_eval_is_refused_outside_github_actions(monkeypatch, tmp_path) -> None:
    from arena.cli import main

    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    out = CliRunner().invoke(main, ["eval", "run", "--golden", str(GOLDEN), "--out", str(tmp_path)])
    assert out.exit_code == 2 and "refused" in out.output


def test_evals_page_shows_committed_runs_only(tmp_path) -> None:
    from arena.ledger import Ledger
    from arena.site.build import build_site

    items, sha = load(GOLDEN)
    res = run(
        sample(items, 6),
        {"llm_context": FakeLLM(lambda *a: GOOD), "llm_plain": FakeLLM(lambda *a: GOOD)},
        FixedClock(NOW),
        golden=GOLDEN.name,
        golden_sha256=sha,
    )
    ev = tmp_path / "evals"
    ev.mkdir()
    (ev / "eval-real.json").write_text(json.dumps({**res, "run_id": "eval-real"}))
    (ev / "fake-eval-x.json").write_text(json.dumps({**res, "run_id": "fake-eval-x"}))
    site = build_site(Ledger(tmp_path / "led"), tmp_path / "site", FixedClock(NOW), evals_dir=ev)
    page = (site.out_dir / "evals.html").read_text()
    assert "EVALUATION" in page and "eval-real" in page and "fake-eval-x" not in page
    assert "interval includes zero" in page  # identical answers: no difference shown


def test_json_validity_ignores_provider_errors() -> None:
    """2026-11-13: a structured run where every call was rejected showed 100% valid JSON."""
    from arena.evals.run import _valid_first_try

    rows = [{"question_id": f"q{i}", "skip": "error"} for i in range(4)]
    assert _valid_first_try(rows, set()) is None
    rows += [
        {"question_id": "a", "skip": None},
        {"question_id": "b", "skip": None},
        {"question_id": "c", "skip": "parse_failure"},
    ]
    assert _valid_first_try(rows, {"b"}) == 1 / 3  # only "a" parsed first time
