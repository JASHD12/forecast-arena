#!/usr/bin/env python3
"""Tick a task in docs/project/TASKS.md: `python scripts/tick.py T001`."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    """Replace `- [ ] Txxx ·` with `- [x] Txxx ·` for each id given."""
    path = ROOT / "docs/project/TASKS.md"
    text = path.read_text(encoding="utf-8")
    for tid in sys.argv[1:]:
        old = f"- [ ] {tid} ·"
        if old not in text:
            print(f"not open: {tid}", file=sys.stderr)
            return 1
        text = text.replace(old, f"- [x] {tid} ·", 1)
    path.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
