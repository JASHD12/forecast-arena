"""T170: the interview kit exists, its numbers file is current, and the prose quotes no
figure that is not in the generated numbers file (I5)."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "docs" / "interview"
PROSE = (
    "README.md",
    "pitch.md",
    "system-design.md",
    "questions.md",
    "star-stories.md",
    "cv-bullets.md",
)
#: Method parameters, not results: interval level and the coin-flip reference.
METHOD_PERCENTAGES = {"95%", "50%"}
FIGURE = re.compile(r"(?<![\w.])[-+]?\d+\.\d{2,}(?![\w.])|(?<![\w.])\d+(?:\.\d+)?%")


def test_kit_files_exist() -> None:
    for name in (*PROSE, "numbers.md"):
        assert (KIT / name).stat().st_size > 500, name


def test_numbers_file_is_current() -> None:
    r = subprocess.run(
        [sys.executable, "scripts/interview_numbers.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_every_figure_in_the_prose_is_in_numbers_md() -> None:
    numbers = (KIT / "numbers.md").read_text(encoding="utf-8")
    missing = []
    for name in PROSE:
        for fig in FIGURE.findall((KIT / name).read_text(encoding="utf-8")):
            fig = fig.lstrip("+")
            if fig in METHOD_PERCENTAGES:
                continue
            if fig not in numbers and fig.lstrip("-") not in numbers:
                missing.append(f"{name}: {fig}")
    assert not missing, missing
