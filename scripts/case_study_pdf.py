"""Print the one-page case study to `docs/case-study.pdf` from a real ledger checkout (T391).

    python scripts/case_study_pdf.py LEDGER_DIR

Builds the site from the ledger (no network), prints `case-study.html` with Playwright (Node, from
tools/a11y) and writes the PDF. Run by hand after pulling the `ledger` branch, like
`scripts/screenshots.py`; the numbers on the page are computed from the ledger and the committed
lab results (I5). Recruiters forward PDFs internally.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str]) -> int:
    if not argv or not (Path(argv[0]) / "chain").exists():
        print(__doc__)
        return 2
    with tempfile.TemporaryDirectory() as tmp:
        site = Path(tmp) / "site"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "arena.cli",
                "--ledger-dir",
                argv[0],
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
            ["node", "tools/a11y/pdf.js", str(site), "case-study.html", "docs/case-study.pdf"],
            check=True,
            cwd=ROOT,
            env=env,
        )
    print("docs/case-study.pdf written")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
