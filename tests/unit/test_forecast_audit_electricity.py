"""Forecast audit, German electricity example (T321): the table, provenance, SQL agreement."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[2]
EX = ROOT / "examples" / "forecast-audit" / "german-electricity"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


fa = _load("forecast_audit", EX.parent / "forecast_audit.py")
build = _load("build_case", EX / "build_case.py")


def _report() -> dict:
    return json.loads((EX / "expected" / "report.json").read_text(encoding="utf-8"))


def test_46_evening_cases_29_yes_17_no_and_only_derived_columns() -> None:
    rows = list(csv.DictReader((EX / "cases.csv").read_text(encoding="utf-8").splitlines()))
    assert len(rows) == len({r["case_id"] for r in rows}) == 46
    assert (
        sum(r["outcome"] == "1" for r in rows) == 29
        and sum(r["outcome"] == "0" for r in rows) == 17
    )
    assert all("evening_gt-DE_LU" in r["case_id"] for r in rows)
    assert list(rows[0]) == list(fa.CASE_COLUMNS)  # no price columns are shipped
    preds = list(csv.DictReader((EX / "predictions.csv").read_text(encoding="utf-8").splitlines()))
    assert list(preds[0]) == list(fa.PREDICTION_COLUMNS) and len(preds) == 92
    by = {
        m: [float(p["probability"]) for p in preds if p["model_id"] == m]
        for m in ("base_rate", "fine_tuned_gguf")
    }
    assert (min(by["base_rate"]), max(by["base_rate"])) == pytest.approx((0.609, 0.696), abs=1e-3)
    assert (min(by["fine_tuned_gguf"]), max(by["fine_tuned_gguf"])) == pytest.approx(
        (0.457, 0.573), abs=1e-3
    )


def test_reproduces_the_planning_table() -> None:
    r = _report()
    assert r["timing_label"] == "replayed" and r["time_scope"]["cases"] == 46
    q = r["quality"]["models"]
    assert (
        round(q["base_rate"]["brier"], 4) == 0.2337
        and round(q["fine_tuned_gguf"]["brier"], 4) == 0.2499
    )
    pol = {p["policy"]: p for p in r["decision"]["policies"]}
    for name in ("base_rate", "fine_tuned_gguf", "always_alert"):
        assert (pol[name]["alerts"], pol[name]["false_alerts"], pol[name]["misses"]) == (46, 17, 0)
        assert pol[name]["total_loss"] == 17
    assert (
        pol["never_alert"]["alerts"],
        pol["never_alert"]["misses"],
        pol["never_alert"]["total_loss"],
    ) == (0, 29, 116)
    # both models made exactly the same 46 decisions
    audited = list(csv.DictReader((EX / "expected" / "cases-audited.csv").read_text().splitlines()))
    by_model = {
        m: [r["alert"] for r in audited if r["model_id"] == m]
        for m in ("base_rate", "fine_tuned_gguf")
    }
    assert by_model["base_rate"] == by_model["fine_tuned_gguf"] == ["yes"] * 46


def test_shipped_files_are_current_and_match_the_manifest() -> None:
    res = subprocess.run([sys.executable, "-I", str(EX / "build_case.py"), "--check"],
                         capture_output=True, text=True, check=False)  # fmt: skip
    assert res.returncode == 0, (
        res.stderr + "\nre-run build_case.py after changing the golden sets or the pin"
    )
    manifest = json.loads((EX / "MANIFEST.json").read_text(encoding="utf-8"))
    for item in manifest["inputs_in_repository"]:
        assert hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest() == item["sha256"]
    for name, digest in manifest["shipped_files"].items():
        if name != "MANIFEST.json":
            assert hashlib.sha256((EX / name).read_bytes()).hexdigest() == digest
    assert manifest["data_source"]["attribution"] == "Bundesnetzagentur | SMARD.de"
    assert "HEDWIG" in manifest["data_source"]["terms_checked"]


def test_duckdb_agrees_with_the_python_report() -> None:
    con = duckdb.connect()
    cwd = Path.cwd()
    try:
        import os

        os.chdir(EX)
        rows = con.execute((EX / "audit.sql").read_text(encoding="utf-8")).fetchall()
    finally:
        os.chdir(cwd)
    sql = {r[0]: r for r in rows}
    pol = {p["policy"]: p for p in _report()["decision"]["policies"]}
    assert set(sql) == set(pol)
    for name, p in pol.items():
        _, cases, alerts, false_alerts, misses, loss, _brier = sql[name]
        assert (cases, alerts, false_alerts, misses) == (
            p["cases"],
            p["alerts"],
            p["false_alerts"],
            p["misses"],
        )
        assert loss == pytest.approx(p["total_loss"], abs=1e-12)
    for name, v in _report()["quality"]["models"].items():
        assert sql[name][6] == pytest.approx(v["brier"], abs=1e-9)


def test_probabilities_use_the_projects_calibration_and_clipping() -> None:
    from arena.lab.ft_runtime import calibrated

    a, b = json.loads((ROOT / "lab/artefacts/llm_local_ft.json").read_text())["platt"]
    for m in (-3.0, -0.4, 0.0, 0.7, 9.0):
        assert build.platt(m, a, b) == pytest.approx(calibrated(m, (a, b)))


def test_sensitivity_shows_the_model_loses_at_equal_costs() -> None:
    s1 = next(s for s in _report()["sensitivity"] if s["miss_cost"] == 1.0)
    pol = {p["policy"]: p for p in s1["policies"]}
    assert pol["fine_tuned_gguf"]["total_loss"] > pol["always_alert"]["total_loss"]
