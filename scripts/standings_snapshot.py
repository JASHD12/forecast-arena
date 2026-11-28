"""Write the README's standings from a real ledger checkout (T390).

    python scripts/standings_snapshot.py LEDGER_DIR

Reads the public ledger (`git archive origin/ledger | tar -x -C LEDGER_DIR`), writes
`docs/data/standings.json` and `docs/img/standings.svg`, then run `scripts/readme_sections.py`.
Run by hand; the live ledger changes every day, so CI only checks the committed files agree.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from arena.ledger import Ledger
from arena.scoring.core import load
from arena.site.shaping import official_start
from arena.site.standings import build_snapshot, render_svg

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str]) -> int:
    if not argv or not (Path(argv[0]) / "chain").exists():
        print(__doc__)
        return 2
    ledger = Ledger(Path(argv[0]))
    rec = load(ledger)
    s = official_start(ledger)
    snap = build_snapshot(
        rec.scored, date.fromisoformat(s) if s else None, datetime.now(UTC).date()
    )
    (ROOT / "docs" / "data").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs" / "data" / "standings.json").write_text(
        json.dumps(snap, indent=1) + "\n", encoding="utf-8"
    )
    (ROOT / "docs" / "img" / "standings.svg").write_text(render_svg(snap), encoding="utf-8")
    print(
        f"standings: {snap['official']['questions']} common questions, "
        f"{snap['official_days']} official days"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
