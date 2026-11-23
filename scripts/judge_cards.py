#!/usr/bin/env python3
"""Write the readable labelling cards for the owner's 30 judge labels (H29).

    python scripts/judge_cards.py          # writes lab/judge/label-cards.md
    python scripts/judge_cards.py --check  # fails if the file is stale

The 30 items are the frozen label subset of `lab/judge/items.json` (same ids as `label-sheet.csv`).
No forecaster name is shown, and nothing is pre-filled: the labels are the owner's.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arena.lab import judge as jg  # noqa: E402

OUT = ROOT / "lab" / "judge" / "label-cards.md"


def render() -> str:
    """The cards text."""
    items = json.loads((ROOT / "lab" / "judge" / "items.json").read_text(encoding="utf-8"))
    return jg.cards_markdown(jg.label_subset(items)) + "\n"


def main() -> int:
    """Write, or with --check compare."""
    text = render()
    if "--check" in sys.argv:
        ok = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print(
            "label cards up to date" if ok else "label cards are stale: run scripts/judge_cards.py"
        )
        return 0 if ok else 1
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
