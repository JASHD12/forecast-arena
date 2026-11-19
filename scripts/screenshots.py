"""Regenerate the README's home screenshot from a real ledger checkout (P4, T213).

    python scripts/screenshots.py LEDGER_DIR [--date YYYY-MM-DD]

Builds the site from the ledger (no network), screenshots the home page with Playwright
(Node, from tools/a11y) to docs/img/home.png and rewrites the caption under it in README.md
with the date. Run by hand after pulling the `ledger` branch; it is not part of
`make check` because the live ledger changes every day. The ledger is public data and the
site shows no personal data (S12).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPTION_RE = re.compile(r"^\*Screenshot of .*?\*$", re.M)


def caption(day: str) -> str:
    """The README line under the screenshot."""
    return (
        f"*Screenshot of the site built from the public ledger on {day}. "
        "Research project, not advice.*"
    )


def update_readme(text: str, day: str) -> str:
    """Replace the screenshot caption; raises when the README has none."""
    if not CAPTION_RE.search(text):
        raise SystemExit("README has no '*Screenshot of ...*' caption line")
    return CAPTION_RE.sub(lambda _m: caption(day), text, count=1)


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    if not args or not (Path(args[0]) / "chain").exists():
        print(__doc__)
        return 2
    day = datetime.now(UTC).date().isoformat()
    if "--date" in argv:
        day = argv[argv.index("--date") + 1]
        args = [a for a in args if a != day]
    with tempfile.TemporaryDirectory() as tmp:
        site = Path(tmp) / "site"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "arena.cli",
                "--ledger-dir",
                args[0],
                "site",
                "build",
                "--out",
                str(site),
            ],
            check=True,
            cwd=ROOT,
        )
        env = {**os.environ, "NODE_PATH": str(ROOT / "tools/a11y/node_modules")}
        subprocess.run(
            ["node", "tools/a11y/shot.js", str(site), "index.html", "docs/img/home.png"],
            check=True,
            cwd=ROOT,
            env=env,
        )
    readme = ROOT / "README.md"
    readme.write_text(update_readme(readme.read_text(encoding="utf-8"), day), encoding="utf-8")
    print(f"docs/img/home.png and the README caption updated ({day})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
