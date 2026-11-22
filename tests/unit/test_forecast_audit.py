# ruff: noqa: E501  (the CSV rows of the error table are data, kept on one line each)
"""Forecast audit (T320): the golden example, every input error, and the project's scoring rules."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "forecast-audit"
CASES_HEADER = "case_id,group_day,lock_at,outcome_state,outcome\n"
PRED_HEADER = "case_id,model_id,status,probability,issued_at,reason\n"


def _load():
    spec = importlib.util.spec_from_file_location("forecast_audit", EXAMPLE / "forecast_audit.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["forecast_audit"] = mod
    spec.loader.exec_module(mod)
    return mod


fa = _load()


def _write(tmp: Path, cases: str, preds: str) -> tuple[Path, Path]:
    (tmp / "cases.csv").write_text(CASES_HEADER + cases, encoding="utf-8")
    (tmp / "predictions.csv").write_text(PRED_HEADER + preds, encoding="utf-8")
    return tmp / "cases.csv", tmp / "predictions.csv"


def _run(cases: Path, preds: Path, **kw):
    return fa.run(cases, preds, kw.pop("candidate", "a"), kw.pop("baseline", "b"),
                  kw.pop("fa", 1.0), kw.pop("miss", 4.0), **kw)  # fmt: skip


def _cli(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """The real command: isolated interpreter, no project packages, a path with spaces."""
    return subprocess.run(
        [sys.executable, "-I", str(cwd / "report.py"), *args],
        capture_output=True, text=True, cwd=cwd, check=False,
    )  # fmt: skip


# ---- the golden example (README table) -----------------------------------------------------------


def test_golden_example_matches_the_documented_table(tmp_path: Path) -> None:
    where = tmp_path / "a folder with spaces"
    shutil.copytree(EXAMPLE, where)
    out = where / "report out"
    res = _cli(
        where, "--cases", "cases.csv", "--predictions", "predictions.csv", "--candidate", "demo",
        "--baseline", "reference", "--false-alert-cost", "1", "--miss-cost", "4",
        "--on-missing", "no-alert", "--out", str(out),
    )  # fmt: skip
    assert res.returncode == 0, res.stderr
    r = json.loads((out / "report.json").read_text())
    assert r["coverage"]["demo"]["on_time"] == 3 and r["coverage"]["demo"]["absent"] == 1
    assert r["coverage"]["reference"]["on_time"] == 4
    q = r["quality"]
    assert q["shared_cases"] == 3
    assert q["models"]["demo"]["brier"] == pytest.approx(0.213333, abs=1e-6)
    assert q["models"]["demo"]["brier_clipped"] == pytest.approx(0.2134, abs=1e-9)
    assert q["models"]["reference"]["brier"] == pytest.approx(0.28)
    pol = {p["policy"]: p for p in r["decision"]["policies"]}
    assert pol["demo"]["loss_per_case"] == pytest.approx(1.0) and pol["demo"]["misses"] == 1
    assert pol["reference"]["loss_per_case"] == pytest.approx(0.25)
    assert pol["always_alert"]["total_loss"] == 1 and pol["never_alert"]["total_loss"] == 12
    assert pol["demo"]["fallback_used"] == 1  # the absent fourth day
    assert (out / "report.html").read_text().startswith("<!doctype html>")
    assert len((out / "cases-audited.csv").read_text().splitlines()) == 1 + 4 * 2


def test_supplying_the_missing_probability_changes_the_operational_result(tmp_path: Path) -> None:
    cases, preds = _write(
        tmp_path,
        "d1,2026-01-01,2026-01-01T09:30:00+00:00,resolved,0\nd2,2026-01-02,2026-01-02T09:30:00+00:00,resolved,1\n",
        "d1,a,forecast,0,2026-01-01T05:00:00+00:00,\nd2,a,forecast,0.9,2026-01-02T05:00:00+00:00,\n"
        "d1,b,forecast,0.8,2026-01-01T05:00:00+00:00,\nd2,b,forecast,0.8,2026-01-02T05:00:00+00:00,\n",
    )
    report, _, _ = _run(cases, preds)
    pol = {p["policy"]: p for p in report["decision"]["policies"]}
    assert pol["a"]["total_loss"] == 0 and pol["a"]["fallback_used"] == 0


# ---- eligibility, time and states ----------------------------------------------------------------


def test_lock_equality_is_late_and_offsets_are_respected(tmp_path: Path) -> None:
    cases, preds = _write(
        tmp_path,
        "c1,2026-01-01,2026-01-01T09:30:00+00:00,resolved,1\n"
        "c2,2026-01-02,2026-01-02T09:30:00+00:00,resolved,1\n"
        "c3,2026-01-03,2026-01-03T09:30:00+00:00,resolved,1\n",
        "c1,a,forecast,0.5,2026-01-01T09:30:00+00:00,\n"  # equal to the lock: late
        "c2,a,forecast,0.5,2026-01-02T10:29:59+01:00,\n"  # 09:29:59 UTC: on time
        "c3,a,forecast,0.5,2026-01-03T10:30:00+01:00,\n"  # 09:30 UTC: late
        "c1,b,forecast,0.5,2026-01-01T00:00:00+00:00,\nc2,b,forecast,0.5,2026-01-02T00:00:00+00:00,\n"
        "c3,b,forecast,0.5,2026-01-03T00:00:00+00:00,\n",
    )
    report, rows, _ = _run(cases, preds)
    states = {(r["case_id"], r["model_id"]): r["prediction_state"] for r in rows}
    assert states[("c1", "a")] == "late" and states[("c2", "a")] == "on_time"
    assert states[("c3", "a")] == "late"
    assert report["quality"]["shared_cases"] == 1


def test_empty_shared_set_is_undefined_not_zero(tmp_path: Path) -> None:
    cases, preds = _write(
        tmp_path,
        "c1,2026-01-01,2026-01-01T09:30:00+00:00,resolved,1\n",
        "c1,a,skipped,,,model not run\nc1,b,forecast,0.5,2026-01-01T05:00:00+00:00,\n",
    )
    report, _, _ = _run(cases, preds)
    assert report["quality"]["shared_cases"] == 0
    assert report["quality"]["models"]["a"]["brier"] is None
    assert report["coverage"]["a"]["skipped"] == 1


def test_pending_and_void_cases_are_not_scored(tmp_path: Path) -> None:
    cases, preds = _write(
        tmp_path,
        "r,2026-01-01,2026-01-01T09:30:00+00:00,resolved,1\n"
        "p,2026-01-02,2026-01-02T09:30:00+00:00,pending,\n"
        "v,2026-01-03,2026-01-03T09:30:00+00:00,void,\n",
        "".join(
            f"{c},{m},forecast,0.7,2026-01-0{d}T05:00:00+00:00,\n"
            for c, d in (("r", 1), ("p", 2), ("v", 3))
            for m in "ab"
        ),
    )
    report, rows, _ = _run(cases, preds)
    assert report["case_states"] == {"resolved": 1, "pending": 1, "void": 1}
    assert report["quality"]["shared_cases"] == 1
    assert {p["cases"] for p in report["decision"]["policies"]} == {1}
    reasons = {r["case_id"]: r["quality_reason"] for r in rows}
    assert reasons["p"] == "case pending" and reasons["v"] == "case void"


def test_cutoff_ties_alert_and_costs_set_the_cutoff(tmp_path: Path) -> None:
    cases, preds = _write(
        tmp_path,
        "c,2026-01-01,2026-01-01T09:30:00+00:00,resolved,0\n",
        "c,a,forecast,0.2,2026-01-01T05:00:00+00:00,\nc,b,forecast,0.19,2026-01-01T05:00:00+00:00,\n",
    )
    report, _, _ = _run(cases, preds)
    pol = {p["policy"]: p for p in report["decision"]["policies"]}
    assert report["decision"]["cutoff"] == pytest.approx(0.2)
    assert pol["a"]["alerts"] == 1 and pol["b"]["alerts"] == 0  # exactly 0.2 alerts


@pytest.mark.parametrize("mode,alerts", [("no-alert", 0), ("alert", 1), ("baseline", 1)])
def test_missing_prediction_fallbacks(tmp_path: Path, mode: str, alerts: int) -> None:
    cases, preds = _write(
        tmp_path,
        "c,2026-01-01,2026-01-01T09:30:00+00:00,resolved,1\n",
        "c,b,forecast,0.9,2026-01-01T05:00:00+00:00,\nc,x,forecast,0.1,2026-01-01T05:00:00+00:00,\n",
    )
    report, _, _ = _run(cases, preds, candidate="x", on_missing=mode)  # x is on time here; use late
    # make x late instead of on time by re-running with a late issue time
    (tmp_path / "predictions.csv").write_text(
        PRED_HEADER
        + "c,b,forecast,0.9,2026-01-01T05:00:00+00:00,\nc,x,forecast,0.1,2026-01-01T10:00:00+00:00,\n"
    )
    report, _, _ = _run(cases, preds, candidate="x", on_missing=mode)
    pol = {p["policy"]: p for p in report["decision"]["policies"]}
    assert pol["x"]["alerts"] == alerts and pol["x"]["fallback_used"] == 1


def test_sensitivity_ratios_and_policies_are_always_present(tmp_path: Path) -> None:
    report, _, _ = fa.run(
        EXAMPLE / "cases.csv", EXAMPLE / "predictions.csv", "demo", "reference", 1.0, 4.0
    )
    ratios = [s["miss_cost"] / s["false_alert_cost"] for s in report["sensitivity"]]
    assert ratios == [1.0, 9.0]
    assert {p["policy"] for p in report["decision"]["policies"]} >= {"always_alert", "never_alert"}


def test_interval_needs_enough_days_and_is_deterministic(tmp_path: Path) -> None:
    n = 40
    days = [date(2026, 1, 1) + timedelta(days=k) for k in range(n)]
    cases = "".join(
        f"c{i},{d.isoformat()},{d.isoformat()}T09:30:00+00:00,resolved,{i % 2}\n"
        for i, d in enumerate(days)
    )
    preds = "".join(
        f"c{i},{m},forecast,{p},2026-01-01T00:00:00+00:00,\n"
        for i in range(n)
        for m, p in (("a", 0.9 if i % 2 else 0.1), ("b", 0.5))
    )
    c, p = _write(tmp_path, cases, preds)
    r1, _, _ = _run(c, p)
    r2, _, _ = _run(c, p)
    iv = r1["intervals"]["day_block"]
    assert iv["estimated"] and iv["days"] == n and iv["low"] <= iv["mean_difference"] <= iv["high"]
    assert r1["intervals"] == r2["intervals"]
    short, _, _ = fa.run(
        EXAMPLE / "cases.csv", EXAMPLE / "predictions.csv", "demo", "reference", 1, 4
    )
    assert not short["intervals"]["day_block"]["estimated"]


def test_unknown_roster_reports_unknown_coverage(tmp_path: Path) -> None:
    report, _, _ = fa.run(EXAMPLE / "cases.csv", EXAMPLE / "predictions.csv", "demo", "reference",
                          1, 4, roster_known=False)  # fmt: skip
    assert report["roster"] == "unknown"
    assert (
        report["coverage"]["demo"]["scheduled"] is None
        and report["coverage"]["demo"]["absent"] is None
    )


# ---- invalid input: nonzero exit, a field/row message, and no partial report ---------------------

GOOD_CASE = "c1,2026-01-01,2026-01-01T09:30:00+00:00,resolved,1\n"
GOOD_PRED = (
    "c1,a,forecast,0.5,2026-01-01T05:00:00+00:00,\nc1,b,forecast,0.5,2026-01-01T05:00:00+00:00,\n"
)
BAD = [
    ("duplicate case", GOOD_CASE + GOOD_CASE, GOOD_PRED, "row 3: field case_id 'c1' is a duplicate"),
    ("duplicate prediction", GOOD_CASE, GOOD_PRED + GOOD_PRED, "appears twice"),
    ("unknown case id", GOOD_CASE, GOOD_PRED + "zz,a,forecast,0.5,2026-01-01T05:00:00+00:00,\n", "is not in cases.csv"),
    ("naive lock time", "c1,2026-01-01,2026-01-01T09:30:00,resolved,1\n", GOOD_PRED, "field lock_at"),
    ("garbled time", "c1,2026-01-01,tomorrow,resolved,1\n", GOOD_PRED, "field lock_at"),
    ("bad day", "c1,01/02/2026,2026-01-01T09:30:00+00:00,resolved,1\n", GOOD_PRED, "field group_day"),
    ("bad outcome", "c1,2026-01-01,2026-01-01T09:30:00+00:00,resolved,2\n", GOOD_PRED, "field outcome"),
    ("outcome on pending", "c1,2026-01-01,2026-01-01T09:30:00+00:00,pending,1\n", GOOD_PRED, "must be empty"),
    ("bad state", "c1,2026-01-01,2026-01-01T09:30:00+00:00,maybe,\n", GOOD_PRED, "field outcome_state"),
    ("nan probability", GOOD_CASE, "c1,a,forecast,nan,2026-01-01T05:00:00+00:00,\nc1,b,forecast,0.5,2026-01-01T05:00:00+00:00,\n", "field probability"),
    ("inf probability", GOOD_CASE, "c1,a,forecast,inf,2026-01-01T05:00:00+00:00,\nc1,b,forecast,0.5,2026-01-01T05:00:00+00:00,\n", "field probability"),
    ("probability above one", GOOD_CASE, "c1,a,forecast,1.2,2026-01-01T05:00:00+00:00,\nc1,b,forecast,0.5,2026-01-01T05:00:00+00:00,\n", "field probability"),
    ("text probability", GOOD_CASE, "c1,a,forecast,high,2026-01-01T05:00:00+00:00,\nc1,b,forecast,0.5,2026-01-01T05:00:00+00:00,\n", "not a number"),
    ("naive issue time", GOOD_CASE, "c1,a,forecast,0.5,2026-01-01T05:00:00,\nc1,b,forecast,0.5,2026-01-01T05:00:00+00:00,\n", "field issued_at"),
    ("skip without reason", GOOD_CASE, "c1,a,skipped,,,\nc1,b,forecast,0.5,2026-01-01T05:00:00+00:00,\n", "needs a reason"),
    ("bad status", GOOD_CASE, "c1,a,maybe,0.5,2026-01-01T05:00:00+00:00,\nc1,b,forecast,0.5,2026-01-01T05:00:00+00:00,\n", "field status"),
]  # fmt: skip


@pytest.mark.parametrize("name,cases,preds,message", BAD, ids=[b[0] for b in BAD])
def test_invalid_input_stops_with_a_field_message_and_writes_nothing(
    tmp_path: Path, name: str, cases: str, preds: str, message: str
) -> None:
    where = tmp_path / "x y"
    shutil.copytree(EXAMPLE, where)
    _write(where, cases, preds)
    out = where / "out"
    res = _cli(where, "--cases", "cases.csv", "--predictions", "predictions.csv", "--candidate", "a",
               "--baseline", "b", "--out", str(out))  # fmt: skip
    assert res.returncode == 2
    assert message in res.stderr and "no report written" in res.stderr
    assert not out.exists()


def test_missing_columns_and_unknown_models_are_reported(tmp_path: Path) -> None:
    where = tmp_path / "w"
    shutil.copytree(EXAMPLE, where)
    (where / "cases.csv").write_text("case_id,group_day\nc1,2026-01-01\n")
    res = _cli(where, "--cases", "cases.csv", "--predictions", "predictions.csv", "--candidate", "demo",
               "--baseline", "reference", "--out", str(where / "o"))  # fmt: skip
    assert res.returncode == 2 and "missing column" in res.stderr
    shutil.copy(EXAMPLE / "cases.csv", where / "cases.csv")
    res = _cli(where, "--cases", "cases.csv", "--predictions", "predictions.csv", "--candidate", "nobody",
               "--baseline", "reference", "--out", str(where / "o"))  # fmt: skip
    assert res.returncode == 2 and "'nobody'" in res.stderr


def test_costs_must_be_positive(tmp_path: Path) -> None:
    where = tmp_path / "w"
    shutil.copytree(EXAMPLE, where)
    res = _cli(where, "--cases", "cases.csv", "--predictions", "predictions.csv", "--candidate", "demo",
               "--baseline", "reference", "--miss-cost", "0", "--out", str(where / "o"))  # fmt: skip
    assert res.returncode == 2 and "--miss-cost" in res.stderr


# ---- output safety and agreement with the project ------------------------------------------------


def test_html_escapes_text_from_the_input_files(tmp_path: Path) -> None:
    cases, preds = _write(
        tmp_path,
        "c,2026-01-01,2026-01-01T09:30:00+00:00,resolved,1\n",
        "c,<script>alert(1)</script>,forecast,0.5,2026-01-01T05:00:00+00:00,\n"
        "c,b,forecast,0.5,2026-01-01T05:00:00+00:00,\n",
    )
    report, _, inputs = _run(cases, preds, candidate="<script>alert(1)</script>", baseline="b")
    page = fa.render_html({**report, "inputs": inputs}, inputs)
    assert "<script>" not in page and "&lt;script&gt;" in page


def test_scoring_matches_the_arena_scoring_module() -> None:
    from arena.scoring import core

    assert (fa.CLIP[0], fa.CLIP[1]) == (core.CLIP_LOW, core.CLIP_HIGH)
    ps, ys = [0.0, 1.0, 0.2, 0.55], [0, 1, 1, 0]
    assert fa.brier(ps, ys, clip=True) == pytest.approx(core.brier(ps, ys))
    assert fa.brier(ps, ys, clip=False) == pytest.approx(core.brier(ps, ys, clipped=False))
    assert fa.clipped(1.0) == core.clip(1.0) and fa.clipped(0.0) == core.clip(0.0)
