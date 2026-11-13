"""README badges for coverage and test count (T188), checked by CI so they never overstate.

    python scripts/badges.py COVERAGE_XML JUNIT_XML           # write docs/badges/*.json
    python scripts/badges.py --check COVERAGE_XML JUNIT_XML   # CI: fail if a badge is wrong

The files are shields.io "endpoint" JSON. The coverage badge shows whole percent rounded
down; the check fails when the badge claims more than CI measured, or lags it by more
than two points. The test badge shows the passing count rounded down to a multiple of 50
("500+"), so adding tests does not break CI, and must not exceed the measured count.
"""

from __future__ import annotations

import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "badges"
TESTS_STEP = 50
COVERAGE_LAG = 2


def measured(coverage_xml: Path, junit_xml: Path) -> tuple[int, int]:
    """(coverage percent rounded down, number of passing tests)."""
    rate = float(ET.parse(coverage_xml).getroot().get("line-rate", "0"))
    root = ET.parse(junit_xml).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    passing = 0
    for s in suites:
        n = int(s.get("tests", 0))
        bad = sum(int(s.get(k, 0)) for k in ("failures", "errors", "skipped"))
        passing += n - bad
    return math.floor(rate * 100 + 1e-9), passing


def badge(label: str, message: str, color: str) -> dict[str, object]:
    return {"schemaVersion": 1, "label": label, "message": message, "color": color}


def badges(cov: int, tests: int) -> dict[str, dict[str, object]]:
    color = "brightgreen" if cov >= 85 else "green" if cov >= 75 else "yellow"
    shown = tests // TESTS_STEP * TESTS_STEP
    return {
        "coverage": badge("coverage", f"{cov}%", color),
        "tests": badge("tests", f"{shown}+ passing", "brightgreen"),
    }


def check(cov: int, tests: int) -> list[str]:
    errors = []
    try:
        c = json.loads((OUT / "coverage.json").read_text(encoding="utf-8"))
        t = json.loads((OUT / "tests.json").read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        return [f"missing badge file: {exc.filename}"]
    shown_cov = int(str(c["message"]).rstrip("%"))
    if shown_cov > cov:
        errors.append(f"coverage badge says {shown_cov}% but CI measured {cov}%")
    elif cov - shown_cov > COVERAGE_LAG:
        errors.append(f"coverage badge {shown_cov}% lags the measured {cov}%; regenerate it")
    shown_tests = int(str(t["message"]).split("+")[0])
    if shown_tests > tests:
        errors.append(f"tests badge says {shown_tests}+ but only {tests} passed")
    return errors


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 2:
        print(__doc__)
        return 2
    cov, tests = measured(Path(args[0]), Path(args[1]))
    if "--check" in argv:
        errors = check(cov, tests)
        for e in errors:
            print(f"badges: {e}")
        if not errors:
            print(f"badges: ok (coverage {cov}%, {tests} tests passing)")
        return 1 if errors else 0
    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in badges(cov, tests).items():
        (OUT / f"{name}.json").write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    print(f"badges written: coverage {cov}%, {tests} tests passing")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
