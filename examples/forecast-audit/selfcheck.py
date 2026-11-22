#!/usr/bin/env python3
"""Self-check, standard library only: run the four-case example and compare the documented table.

    python3 examples/forecast-audit/selfcheck.py

Used by CI on a bare Python 3.12 (no `pip install`) and by anyone who wants to see it work.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="forecast audit ") as tmp:
        out = Path(tmp) / "report"
        cmd = [
            sys.executable, "-I", str(HERE / "report.py"),
            "--cases", str(HERE / "cases.csv"), "--predictions", str(HERE / "predictions.csv"),
            "--candidate", "demo", "--baseline", "reference",
            "--false-alert-cost", "1", "--miss-cost", "4", "--on-missing", "no-alert",
            "--out", str(out),
        ]  # fmt: skip
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode != 0:
            print(res.stderr, file=sys.stderr)
            return 1
        r = json.loads((out / "report.json").read_text(encoding="utf-8"))
    q = r["quality"]["models"]
    pol = {p["policy"]: p for p in r["decision"]["policies"]}
    expected = [
        ("candidate predictions on time", r["coverage"]["demo"]["on_time"], 3),
        ("shared days", r["quality"]["shared_cases"], 3),
        ("candidate Brier", round(q["demo"]["brier"], 6), 0.213333),
        ("candidate clipped Brier", round(q["demo"]["brier_clipped"], 6), 0.2134),
        ("reference Brier", round(q["reference"]["brier"], 6), 0.28),
        ("candidate loss per day", pol["demo"]["loss_per_case"], 1.0),
        ("reference loss per day", pol["reference"]["loss_per_case"], 0.25),
    ]
    bad = [(n, got, want) for n, got, want in expected if got != want]
    for n, got, want in expected:
        print(f"{'ok  ' if got == want else 'FAIL'} {n}: {got} (expected {want})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
