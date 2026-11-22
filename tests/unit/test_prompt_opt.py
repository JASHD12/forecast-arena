"""T297: the prompt-optimisation search is deterministic, leak-free and picks honestly."""

from __future__ import annotations

from pathlib import Path

from arena.lab import dataset as ds
from arena.lab import prompt_opt as po

DATA = Path(__file__).resolve().parents[2] / "lab" / "data" / "forecast-sft"


def _rows(name: str) -> list[ds.Row]:
    return ds.read_split(DATA / f"{name}.jsonl.gz")


def test_eight_candidates_baseline_first() -> None:
    cands = po.candidates()
    assert len(cands) == 8 and cands[0] == po.BASELINE
    assert len({c.id for c in cands}) == 8


def test_search_rows_are_validation_only_seeded_and_spread() -> None:
    val = _rows("val")
    a, b = po.search_rows(val), po.search_rows(val)
    assert [r.id for r in a] == [r.id for r in b] and len(a) == po.N_SEARCH_ROWS
    assert {r.split for r in a} == {"val"}
    assert len({r.template for r in a}) >= 4


def test_shots_come_from_train_and_are_balanced() -> None:
    train = _rows("train")
    shots = po.pick_shots(train, po.SHOTS)
    assert len(shots) == 4 and sum(s.outcome for s in shots) == 2
    assert {s.split for s in shots} == {"train"}
    assert po.pick_shots(train, 0) == []
    assert [s.id for s in po.pick_shots(train, 4)] == [s.id for s in shots]


def test_render_changes_only_the_system_text() -> None:
    row = _rows("val")[0]
    shots = po.pick_shots(_rows("train"), 4)
    system, user = po.render(row, po.BASELINE, [])
    assert system == row.system and user == row.user
    system2, user2 = po.render(row, po.Candidate(2, 4), shots)
    assert user2 == row.user
    assert system2.startswith(row.system.rstrip())
    assert "Solved examples" in system2 and system2.count("->") == 4
    assert "base rate" in system2


def test_cross_fitting_prefers_an_informative_margin() -> None:
    y = [0, 0, 1, 1] * 10
    good = [(-1.0 if v == 0 else 1.0) + 0.01 * i for i, v in enumerate(y)]
    flat = [0.0] * 40
    assert po.cross_fitted_brier(good, y) < 0.05
    assert abs(po.cross_fitted_brier(flat, y) - 0.25) < 0.01


def test_choose_keeps_the_baseline_unless_strictly_better() -> None:
    assert po.choose({"i0s0": 0.25, "i1s0": 0.25, "i2s4": 0.26}) == "i0s0"
    assert po.choose({"i0s0": 0.25, "i1s0": 0.24, "i2s4": 0.26}) == "i1s0"


def test_score_candidate_uses_the_injected_scorer() -> None:
    class Fake:
        model = "fake"

        def __init__(self) -> None:
            self.seen: list[tuple[str, str]] = []

        def margin(self, system: str, user: str) -> float:
            self.seen.append((system, user))
            return float(len(self.seen))

    val = po.search_rows(_rows("val"), 3)
    fake = Fake()
    out = po.score_candidate(fake, po.Candidate(1, 4), val, _rows("train"))
    assert out == [1.0, 2.0, 3.0]
    assert all("one word" in s for s, _ in fake.seen)


def test_workflow_has_both_phases_and_no_secret() -> None:
    import yaml

    path = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "lab-prompt-opt.yml"
    text = path.read_text(encoding="utf-8")
    doc = yaml.safe_load(text)
    on = doc.get("on") or doc[True]
    assert on["workflow_dispatch"]["inputs"]["phase"]["options"] == ["search", "final"]
    assert "API_KEY" not in text and "secrets." not in text
    assert doc["permissions"] == {"contents": "read"}
