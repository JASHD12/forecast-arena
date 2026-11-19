"""Write the power slice card from a stored backtest run (T220).

    python scripts/slices.py backtests/power-2025-11-01-2026-10-31-20261113T0954

Writes docs/models/power-slices.md (picked up by the Backtests page). Re-run it whenever
the power card is regenerated from a new run.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arena.backtest.harness import BacktestStore  # noqa: E402
from arena.backtest.slices import markdown  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    run = Path(argv[0]).resolve()
    records = BacktestStore(run.parent).read(run.name)
    out = ROOT / "docs" / "models" / "power-slices.md"
    out.write_text(markdown(records, run.name), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} from {len(records)} records")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
