"""Replayed ml probabilities for a golden set (T380): coverage, labelling, the real files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from arena.evals import ml_probs as mp
from arena.evals.golden import load

GOLDEN = Path(__file__).parents[2] / "evals" / "golden"


@dataclass
class Rec:
    question_id: str
    forecaster_id: str
    probability: float


def _ids(name: str) -> list[str]:
    items, _ = load(GOLDEN / name)
    return [it.question.question_id for it in items]


def test_payload_takes_only_ml_rows_of_the_golden_questions(tmp_path: Path) -> None:
    ids = _ids("power-2026-11a.jsonl")
    recs = [Rec(i, "ml", 0.4) for i in ids] + [Rec(i, "base_rate", 0.9) for i in ids]
    recs.append(Rec("other-question", "ml", 0.1))
    p = mp.build_payload(GOLDEN / "power-2026-11a.jsonl", recs, "note")
    assert set(p["probabilities"]) == set(ids) and set(p["probabilities"].values()) == {0.4}
    assert p["kind"] == "replay" and p["golden"] == "power-2026-11a.jsonl"
    out = tmp_path / "x.json"
    mp.write(p, out)
    assert json.loads(out.read_text())["golden_sha256"] == p["golden_sha256"]


def test_missing_questions_are_an_error_not_a_filler() -> None:
    ids = _ids("power-2026-11a.jsonl")
    with pytest.raises(mp.ReplayError, match="1 golden questions"):
        mp.build_payload(GOLDEN / "power-2026-11a.jsonl", [Rec(i, "ml", 0.5) for i in ids[1:]], "n")


def test_batch_range_of_the_november_set() -> None:
    first, last = mp.batch_range(GOLDEN / "power-2026-11a.jsonl")
    assert first.isoformat() == "2026-11-01" and last.isoformat() == "2026-11-15"


@pytest.mark.parametrize(
    ("golden", "probs"),
    [
        ("power-2026-10.jsonl", "ml-probs-power.json"),
        ("power-2026-11a.jsonl", "ml-probs-power-11a.json"),
    ],
)
def test_committed_replay_files_match_their_golden_set(golden: str, probs: str) -> None:
    path = GOLDEN / probs
    if not path.is_file():
        pytest.skip(f"{probs} is not built yet")
    d = json.loads(path.read_text())
    _, sha = load(GOLDEN / golden)
    assert d["golden_sha256"] == sha and d["kind"] == "replay"
    assert set(d["probabilities"]) == set(_ids(golden))
    assert all(0.0 < p < 1.0 for p in d["probabilities"].values())
