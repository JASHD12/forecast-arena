"""The release path: an archive of HEAD holds the tool, and the quickstart runs from it."""

from __future__ import annotations

import io
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NEEDED = (
    "examples/forecast-audit/forecast_audit.py",
    "examples/forecast-audit/report.py",
    "examples/forecast-audit/selfcheck.py",
    "examples/forecast-audit/SCHEMA.md",
    "examples/forecast-audit/README.md",
    "examples/forecast-audit/cases.csv",
    "examples/forecast-audit/predictions.csv",
    "examples/forecast-audit/german-electricity/MANIFEST.json",
    "examples/forecast-audit/german-electricity/DATA_LICENSE.md",
    "examples/forecast-audit/german-electricity/expected/report.json",
    "CONTRIBUTING.md",
    ".github/ISSUE_TEMPLATE/reproducible-example.yml",
)


def _archive() -> tarfile.TarFile:
    out = subprocess.run(
        ["git", "archive", "HEAD", "examples/forecast-audit", "CONTRIBUTING.md", ".github"],
        cwd=ROOT, capture_output=True, check=False,
    )  # fmt: skip
    if out.returncode != 0:
        pytest.skip("not a git checkout")
    return tarfile.open(fileobj=io.BytesIO(out.stdout))


def test_archive_holds_the_tool_and_runs_the_quickstart(tmp_path: Path) -> None:
    tar = _archive()
    names = set(tar.getnames())
    missing = [n for n in NEEDED if n not in names]
    if (
        missing
        and subprocess.run(
            ["git", "status", "--porcelain", "--", *missing],
            cwd=ROOT,
            capture_output=True,
            text=True,
        ).stdout.strip()
    ):
        pytest.skip("files not committed yet")
    assert not missing
    dest = tmp_path / "unpacked dir"  # a path with a space
    dest.mkdir()
    tar.extractall(dest, filter="data")
    ex = dest / "examples" / "forecast-audit"
    for script in (["selfcheck.py"],):
        run = subprocess.run(
            [sys.executable, "-I", str(ex / script[0])], capture_output=True, text=True, check=False
        )
        assert run.returncode == 0, run.stderr
    out = tmp_path / "out"
    run = subprocess.run(
        [
            sys.executable, "-I", str(ex / "report.py"),
            "--cases", str(ex / "cases.csv"), "--predictions", str(ex / "predictions.csv"),
            "--candidate", "demo", "--baseline", "reference",
            "--false-alert-cost", "1", "--miss-cost", "4", "--on-missing", "no-alert",
            "--out", str(out),
        ],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert run.returncode == 0, run.stderr
    assert (out / "report.json").exists() and (out / "report.html").exists()
