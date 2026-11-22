"""T248: the lineage record agrees with the pin file and the evaluation result."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from arena.lab import lineage
from arena.lab.artefacts import load_artefact

ROOT = Path(__file__).resolve().parents[2]


def _load() -> tuple[dict, dict]:
    record = json.loads((ROOT / "docs/lab/runs/qlora-r1.json").read_text(encoding="utf-8"))
    result = json.loads((ROOT / "evals/results/lab-qlora-r1.json").read_text(encoding="utf-8"))
    return record, result


def test_committed_lineage_matches_pin_and_result() -> None:
    art = load_artefact()
    assert art is not None
    record, result = _load()
    assert lineage.check(record, art, result) == []
    assert len(record["calibrations"]) >= 2  # Colab map first, GGUF map last
    assert record["gguf"]["quantisation"] == "Q4_K_M"


def test_check_flags_a_changed_pin() -> None:
    art = load_artefact()
    assert art is not None
    record, result = _load()
    changed = replace(art, platt=(1.0, 0.0), sha256="0" * 64)
    problems = lineage.check(record, changed, result)
    assert any("GGUF hash" in p for p in problems)
    assert any("Platt" in p for p in problems)
    assert any("different artefacts" in p for p in problems)


def test_write_is_stable(tmp_path: Path) -> None:
    record, _ = _load()
    lineage.write(record, tmp_path / "a.json")
    lineage.write(json.loads((tmp_path / "a.json").read_text()), tmp_path / "b.json")
    assert (tmp_path / "a.json").read_text() == (tmp_path / "b.json").read_text()
