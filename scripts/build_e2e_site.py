#!/usr/bin/env python3
"""Build the static site from the offline e2e schedule (fixture data), for checks in CI.

Usage: python scripts/build_e2e_site.py <out_dir>
"""

from __future__ import annotations

import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests" / "unit"), str(ROOT / "tests" / "e2e")]

from test_e2e import run_schedule  # noqa: E402

from arena.clock import FixedClock  # noqa: E402
from arena.site.build import build_site  # noqa: E402


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "site")
    with tempfile.TemporaryDirectory() as tmp:
        led = run_schedule(Path(tmp) / "ledger")
        res = build_site(
            led,
            out.resolve(),
            FixedClock(datetime(2026, 10, 27, tzinfo=UTC)),
            site_url=out.resolve().as_uri() + "/",  # offline: the 404 page's <base> is local
            golden_path=Path(__file__).resolve().parents[1] / "evals/golden/power-2026-10.jsonl",
        )
    print(f"built {len(res.pages)} pages into {res.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
