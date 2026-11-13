"""T188: README badges never overstate what CI measured."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("badges", ROOT / "scripts" / "badges.py")
assert spec and spec.loader
badges = importlib.util.module_from_spec(spec)
spec.loader.exec_module(badges)


def _xml(tmp_path, rate: float, tests: int, failures: int = 0) -> tuple[Path, Path]:
    cov = tmp_path / "coverage.xml"
    cov.write_text(f'<?xml version="1.0"?><coverage line-rate="{rate}"></coverage>')
    junit = tmp_path / "junit.xml"
    junit.write_text(
        f'<testsuites><testsuite tests="{tests}" failures="{failures}" errors="0" '
        f'skipped="0"/></testsuites>'
    )
    return cov, junit


def test_measured_rounds_down_and_counts_only_passing(tmp_path) -> None:
    cov, junit = _xml(tmp_path, 0.88999, 521, failures=2)
    assert badges.measured(cov, junit) == (88, 519)


def test_check_rejects_overstated_and_stale_badges(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(badges, "OUT", tmp_path)
    for name, data in badges.badges(88, 521).items():
        (tmp_path / f"{name}.json").write_text(json.dumps(data))
    assert badges.check(88, 521) == [] and badges.check(90, 600) == []
    assert "says 88%" in badges.check(87, 521)[0]  # CI measured less than the badge claims
    assert "lags" in badges.check(91, 521)[0]
    assert "500+" in badges.check(88, 499)[0]


def test_committed_badges_are_well_formed() -> None:
    for name in ("coverage", "tests"):
        data = json.loads((ROOT / "docs" / "badges" / f"{name}.json").read_text())
        assert data["schemaVersion"] == 1 and data["label"] == name
