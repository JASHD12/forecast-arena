"""One model card per forecaster in one format, generated and current (T392)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
_spec = importlib.util.spec_from_file_location("model_cards", ROOT / "scripts" / "model_cards.py")
assert _spec and _spec.loader
mc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mc)

SECTIONS = ("## Intended use", "## Data", "## Metrics", "## Limits", "## Monitoring")


def test_cards_are_current() -> None:
    res = subprocess.run(
        [sys.executable, "scripts/model_cards.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr


def test_every_forecaster_has_a_card_with_every_section_in_order() -> None:
    from arena.forecasters.catalog import CATALOG

    files = mc.build()
    for e in CATALOG:
        text = files[f"{e.id}.md"]
        positions = [text.index(s) for s in SECTIONS]
        assert positions == sorted(positions), e.id
    assert "DATA_SHEET.md" in files and "README.md" in files


def test_a_forecaster_outside_the_headline_set_shows_no_invented_number() -> None:
    text = mc.build()["agent_committee.md"]
    assert "Not part of the headline set" in text and "| Brier |" not in text


def test_headline_forecasters_show_their_snapshot_numbers_with_intervals() -> None:
    snap = mc._standings()
    ml = next(r for r in snap["official"]["rows"] if r["id"] == "ml")
    text = mc.build()["ml.md"]
    assert f"{ml['brier']:.3f}" in text and f"[{ml['lo']:.3f}, {ml['hi']:.3f}]" in text
