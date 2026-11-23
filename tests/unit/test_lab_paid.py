"""T247, T250, T252b: the paid lab runs are capped, refused outside Actions, and deterministic."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from arena.cli import main
from arena.lab import distill as dl
from arena.lab import judge as jg
from arena.lab import routing as rt
from arena.lab.dataset import read_split
from arena.llm.client import FakeLLM

ROOT = Path(__file__).resolve().parents[2]
JUDGE_ANSWER = json.dumps({"reasoning": "ok", "data_use": 4, "direction": 5, "hedging": 3})


def _fake(answer: str) -> FakeLLM:
    return FakeLLM(lambda s, t, tools: answer)


def _live(monkeypatch: pytest.MonkeyPatch, answer: str) -> None:
    monkeypatch.setattr("arena.lab.paid.in_actions", lambda: True)
    monkeypatch.setattr("arena.llm.factory.client_from_settings", lambda s: _fake(answer))


def _run(*args: str, env: dict[str, str] | None = None):
    return CliRunner().invoke(main, list(args), env=env or {}, catch_exceptions=False)


# ---- judge ---------------------------------------------------------------------------------------


def test_parse_judgement_accepts_only_the_contract() -> None:
    assert jg.parse_judgement(JUDGE_ANSWER)["direction"] == 5
    for bad in (
        "no json",
        '{"data_use": 6, "direction": 1, "hedging": 1}',
        '{"data_use": true, "direction": 1, "hedging": 1}',
        '{"data_use": 3}',
    ):
        with pytest.raises(jg.JudgeError):
            jg.parse_judgement(bad)


def test_weighted_kappa_extremes() -> None:
    a = [1, 2, 3, 4, 5, 3, 2]
    assert jg.weighted_kappa(a, a) == pytest.approx(1.0)
    assert jg.weighted_kappa([1, 1, 1], [1, 1, 1]) is None  # no variation: undefined
    assert jg.weighted_kappa(a, [6 - x for x in a]) < 0  # reversed scale disagrees


def test_committed_items_and_label_sheet_are_consistent() -> None:
    items = json.loads((ROOT / "lab/judge/items.json").read_text(encoding="utf-8"))
    assert len(items) == jg.N_ITEMS and len({i["id"] for i in items}) == jg.N_ITEMS
    assert len({i["forecaster_id"] for i in items}) >= 4
    sheet = (ROOT / "lab/judge/label-sheet.csv").read_text(encoding="utf-8")
    header = sheet.splitlines()[0].split(",")
    assert header[0] == "id" and "forecaster_id" not in header  # graders never see the author
    ids = {i["id"] for i in items}
    import csv
    import io

    rows = list(csv.DictReader(io.StringIO(sheet)))
    assert len(rows) == jg.N_LABELS and {r["id"] for r in rows} <= ids
    assert all(not r["data_use"] for r in rows)  # blank until the owner fills it in
    assert all(i["forecaster_id"] not in i["id"] for i in items)


def test_selection_is_seeded_and_spread() -> None:
    cands = [{"key": f"{f}|{n}", "forecaster_id": f} for f in ("a", "b", "c") for n in range(40)]
    one, two = jg.select_items(cands, 30), jg.select_items(cands, 30)
    assert one == two and {c["forecaster_id"] for c in one} == {"a", "b", "c"}
    assert [c["forecaster_id"] for c in one].count("a") == 10


@pytest.mark.parametrize("cmd", ["judge-run", "routing-score", "distill-labels"])
def test_paid_commands_are_refused_outside_actions(
    cmd: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert _run("lab", cmd).exit_code == 2


def test_judge_run_with_a_fake_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _live(monkeypatch, JUDGE_ANSWER)
    items = json.loads((ROOT / "lab/judge/items.json").read_text(encoding="utf-8"))[:3]
    path = tmp_path / "items.json"
    path.write_text(json.dumps(items), encoding="utf-8")
    res = _run("lab", "judge-run", "--items", str(path))
    line = next(x for x in res.output.splitlines() if x.startswith("JG_SCORES="))
    scores = json.loads(line.removeprefix("JG_SCORES="))
    assert list(scores.values()) == [[4, 5, 3]] * 3
    assert "JG_SUMMARY=" in res.output


def test_judge_run_labels_only_grades_the_30_labelled_items_and_takes_a_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _live(monkeypatch, JUDGE_ANSWER)
    seen: list[str | None] = []
    real = __import__("arena.llm.factory", fromlist=["client_from_settings"])

    def fake(settings):  # type: ignore[no-untyped-def]
        seen.append(settings.llm_model)
        return _fake(JUDGE_ANSWER)

    monkeypatch.setattr(real, "client_from_settings", fake)
    res = _run("lab", "judge-run", "--labels-only", "--model", "claude-sonnet-5-5")
    line = next(x for x in res.output.splitlines() if x.startswith("JG_SCORES="))
    scores = json.loads(line.removeprefix("JG_SCORES="))
    items = json.loads((ROOT / "lab/judge/items.json").read_text(encoding="utf-8"))
    assert sorted(scores) == sorted(i["id"] for i in jg.label_subset(items))
    assert len(scores) == 30 and seen == ["claude-sonnet-5-5"]


def test_judge_compare_is_labelled_as_llm_against_llm(tmp_path: Path) -> None:
    a = {f"i{n}": [(n % 5) + 1, 3, 4] for n in range(20)}
    b = {**a, "i0": [5, 3, 4], "i1": None}
    pa, pb, out = tmp_path / "a.json", tmp_path / "b.json", tmp_path / "out.json"
    pa.write_text(json.dumps(a), encoding="utf-8")
    pb.write_text(json.dumps(b), encoding="utf-8")
    res = _run("lab", "judge-compare", str(pa), str(pb), "--out", str(out))
    d = json.loads(out.read_text(encoding="utf-8"))
    m = d["metrics"]["agreement / hedging"]
    assert res.exit_code == 0 and m["n"] == 19 and m["exact_match_pct"] == 100.0
    assert "not agreement with a human" in " ".join(d["notes"]) and d["kind"] == "evaluation"


def test_label_cards_cover_exactly_the_label_sheet_and_prefill_nothing() -> None:
    import csv
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import judge_cards

    ids = [r["id"] for r in csv.DictReader((ROOT / "lab/judge/label-sheet.csv").open())]
    text = judge_cards.OUT.read_text(encoding="utf-8")
    assert text == judge_cards.render()
    assert all(f"`{i}`" in text for i in ids) and text.count("Your line:") == 30
    assert ",_,_,_`" in text and "forecaster_id" not in text


def test_the_second_judge_model_has_a_list_price() -> None:
    from arena.site.llm_obs import price_for

    assert price_for("anthropic", "claude-sonnet-5-5") == (2.00, 10.00)


def test_judge_eval_reports_agreement(tmp_path: Path) -> None:
    items = json.loads((ROOT / "lab/judge/items.json").read_text(encoding="utf-8"))
    scores = {i["id"]: [(n % 5) + 1, 3, 4] for n, i in enumerate(items)}
    sp = tmp_path / "scores.json"
    sp.write_text(json.dumps(scores), encoding="utf-8")
    labels = tmp_path / "labels.csv"
    rows = [
        "id,question,resolution_rule,data_excerpt,probability_yes,rationale,data_use,direction,hedging"
    ]
    for n, i in enumerate(items[:30]):
        rows.append(f"{i['id']},q,r,d,0.5,t,{(n % 5) + 1},{(n % 3) + 1},4")
    labels.write_text("\n".join(rows) + "\n", encoding="utf-8")
    out = tmp_path / "lab-judge.json"
    res = _run("lab", "judge-eval", str(sp), "--labels", str(labels), "--out", str(out))
    d = json.loads(out.read_text(encoding="utf-8"))
    assert d["metrics"]["agreement / data_use"]["weighted_kappa"] == pytest.approx(1.0)
    assert d["metrics"]["agreement / data_use"]["n"] == 30 and res.exit_code == 0


# ---- routing -------------------------------------------------------------------------------------


def _item(n: int, ml: float, ft: float, claude: float, y: int) -> rt.Item:
    return rt.Item(f"q{n}", f"2026-10-{(n % 28) + 1:02d}", y, ml, ft, claude, 0.5)


def test_decide_rules() -> None:
    sure = _item(0, 0.85, 0.80, 0.5, 1)
    assert rt.decide(sure, "pair", 0.15) == (pytest.approx(0.825), False)
    assert rt.decide(_item(1, 0.85, 0.55, 0.4, 1), "pair", 0.15) == (0.4, True)  # ft unsure
    assert rt.decide(_item(2, 0.85, 0.20, 0.4, 1), "pair", 0.15) == (0.4, True)  # disagree
    assert rt.decide(_item(3, 0.85, 0.55, 0.4, 1), "ml_only", 0.15) == (0.85, False)
    with pytest.raises(ValueError):
        rt.decide(sure, "other", 0.1)


def test_study_counts_paid_calls_and_grid_is_monotone() -> None:
    rows = [_item(n, 0.5 + 0.4 * ((n % 5) / 4 - 0.5), 0.5, 0.6, n % 2) for n in range(60)]
    res = rt.study(rows)
    assert res["arms"]["claude (llm_context)"]["paid_calls"] == 60
    ml_only = [c for c in res["curve"] if c["rule"] == "ml_only"]
    avoided = [c["paid_calls_avoided"] for c in ml_only]
    assert avoided == sorted(avoided, reverse=True)  # a higher bar never avoids more
    pair = next(c for c in res["curve"] if c["rule"] == "pair" and c["delta"] == rt.PRIMARY_DELTA)
    assert pair["paid_calls_avoided"] == 0  # ft sits at 0.5: never decisive (hypothesis H-RT2)
    assert {p["b"] for p in res["paired"]} == {"claude (llm_context)", "ml", "base_rate"}


# ---- distillation labels -------------------------------------------------------------------------


def test_distillation_sample_is_train_only_seeded_and_balanced() -> None:
    train = read_split(ROOT / "lab/data/forecast-sft/train.jsonl.gz")
    one, two = dl.sample_rows(train, 120), dl.sample_rows(train, 120)
    assert [r.id for r in one] == [r.id for r in two] and len(one) == 120
    assert {r.split for r in one} == {"train"}
    assert len({r.template for r in one}) >= 5
    val = read_split(ROOT / "lab/data/forecast-sft/val.jsonl.gz")[:1]
    with pytest.raises(ValueError, match="leakage"):
        dl.usable([val[0].id], [0.5], train)
    assert dl.usable([one[0].id, one[1].id], [0.3, None], train) == [(one[0].id, 0.3)]


def test_distill_labels_with_a_fake_teacher(monkeypatch: pytest.MonkeyPatch) -> None:
    _live(monkeypatch, json.dumps({"probability": 0.37, "rationale": "x", "key_factors": []}))
    res = _run("lab", "distill-labels", "--n", "4")
    line = next(x for x in res.output.splitlines() if x.startswith("DL_PROBS="))
    assert json.loads(line.removeprefix("DL_PROBS=")) == [0.37] * 4


# ---- workflows -----------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["lab-judge", "lab-routing", "lab-distill-labels"])
def test_paid_workflows_are_manual_capped_and_read_only(name: str) -> None:
    text = (ROOT / ".github/workflows" / f"{name}.yml").read_text(encoding="utf-8")
    doc = yaml.safe_load(text)
    on = doc.get("on") or doc[True]
    assert list(on) == ["workflow_dispatch"]
    assert doc["permissions"] == {"contents": "read"}
    assert on["workflow_dispatch"]["inputs"]["max_tokens"]["default"].isdigit()
    assert text.count("secrets.") == 1 and "secrets.ARENA_LLM_API_KEY" in text
    assert "COINGECKO" not in text


def test_routing_score_and_study_end_to_end_with_fakes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _live(monkeypatch, json.dumps({"probability": 0.6, "rationale": "x", "key_factors": []}))
    res = _run("lab", "routing-score")
    summary = json.loads(
        next(x for x in res.output.splitlines() if x.startswith("RT_SUMMARY=")).removeprefix(
            "RT_SUMMARY="
        )
    )
    probs = json.loads(
        next(x for x in res.output.splitlines() if x.startswith("RT_PROBS=")).removeprefix(
            "RT_PROBS="
        )
    )
    assert summary["n"] == 276 and len(probs) == 276 and set(probs) == {0.6}
    ids = sorted(
        json.loads(line)["question"]["question_id"]
        for f in ("power-2026-10", "power-2026-11a")
        for line in (ROOT / "evals/golden" / f"{f}.jsonl").read_text().splitlines()
        if line.strip()
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    with (run_dir / "forecasts.jsonl").open("w", encoding="utf-8") as fh:
        for n, i in enumerate(ids):
            row = {"forecaster_id": "ml", "question_id": i, "probability": 0.8 if n % 2 else 0.2}
            fh.write(json.dumps(row) + "\n")
    pf = tmp_path / "probs.json"
    pf.write_text(json.dumps(probs), encoding="utf-8")
    out = tmp_path / "lab-routing.json"
    res2 = _run("lab", "routing", str(pf), "--ml-run", str(run_dir), "--out", str(out))
    d = json.loads(out.read_text(encoding="utf-8"))
    assert d["experiment"] == "routing" and d["metrics"]["ml"]["n"] == 276
    assert res2.exit_code == 0


def test_distill_start_and_merge_cover_the_full_sample(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _live(monkeypatch, json.dumps({"probability": 0.37, "rationale": "x", "key_factors": []}))
    res = _run("lab", "distill-labels", "--n", "6", "--start", "4")
    summary = json.loads(
        next(x for x in res.output.splitlines() if x.startswith("DL_SUMMARY=")).removeprefix(
            "DL_SUMMARY="
        )
    )
    probs = json.loads(
        next(x for x in res.output.splitlines() if x.startswith("DL_PROBS=")).removeprefix(
            "DL_PROBS="
        )
    )
    assert summary["n"] == 2 and summary["start"] == 4 and probs == [0.37, 0.37]


def test_committed_first_label_run_matches_its_recorded_sample() -> None:
    import hashlib

    train = read_split(ROOT / "lab/data/forecast-sft/train.jsonl.gz")
    ids = [r.id for r in dl.sample_rows(train, dl.DISTILL_N if hasattr(dl, "DISTILL_N") else 1200)]
    # the run logged this hash of the full sorted sample (run 45071238970)
    assert (
        hashlib.sha256("\n".join(ids).encode()).hexdigest()
        == "a65f226077d310ef96eb85c9c8727c6bd989d57f94f0be976d9006aea0ea9847"
    )
    part = json.loads((ROOT / "lab/data/distill-run1-probs.json").read_text(encoding="utf-8"))
    assert len(part) == 774 and sum(p is None for p in part) == 1
    assert all(p is None or 0 <= p <= 1 for p in part)
    train_ids = {r.id for r in train}
    assert set(ids[:774]) <= train_ids  # labels belong to training rows only (no leakage)
