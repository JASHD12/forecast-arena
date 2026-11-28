"""The Tier C sampler (T406): per topic, seeded, spread over days, with a live ml forecast."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from click.testing import CliRunner

from arena.cli import main
from arena.evals.golden import load
from arena.evals.run import sample_per_topic, topic_of

ROOT = Path(__file__).parents[2]
GOLDEN = ROOT / "evals/golden/replay-weather-attention-2026-11-25.jsonl"
ITEMS, SHA = load(GOLDEN)
PROBS = json.loads(
    (ROOT / "evals/golden/replay-weather-attention-2026-11-25.ml-probs.json").read_text()
)


def _topics(sub) -> Counter:
    return Counter(topic_of(i.question.question_id) for i in sub)


def test_sixty_per_topic_from_the_questions_that_have_a_live_ml_forecast() -> None:
    sub = sample_per_topic(ITEMS, 60, only=set(PROBS["probabilities"]))
    assert _topics(sub) == {"weather": 60, "attention": 60}
    assert all(i.question.question_id in PROBS["probabilities"] for i in sub)
    assert len({i.question.batch_date for i in sub}) >= 8  # spread over the days, not one day


def test_the_draw_is_deterministic_and_the_seed_changes_it() -> None:
    a = sample_per_topic(ITEMS, 60, only=set(PROBS["probabilities"]))
    b = sample_per_topic(ITEMS, 60, only=set(PROBS["probabilities"]))
    c = sample_per_topic(ITEMS, 60, seed=1, only=set(PROBS["probabilities"]))
    ids = lambda s: [i.question.question_id for i in s]  # noqa: E731
    assert ids(a) == ids(b) and ids(a) != ids(c)


def test_a_topic_with_too_few_questions_contributes_all_of_them() -> None:
    sub = sample_per_topic(ITEMS, 1000)
    assert len(sub) == len(ITEMS)


def test_the_replay_ml_file_belongs_to_the_replay_golden_set() -> None:
    assert PROBS["golden_sha256"] == SHA


def test_per_topic_and_limit_are_mutually_exclusive() -> None:
    res = CliRunner().invoke(
        main,
        ["eval", "run", "--golden", str(GOLDEN), "--limit", "10", "--per-topic", "5", "--fake"],
    )
    assert res.exit_code == 2 and "either --limit or --per-topic" in res.output


def test_the_eval_cli_runs_the_tier_c_shape_offline(tmp_path: Path) -> None:
    res = CliRunner().invoke(
        main,
        [
            "eval", "run", "--golden", str(GOLDEN), "--per-topic", "3",
            "--ml-probs", str(PROBS_FILE),
            "--variant", "agent", "--variant", "agent_analyst", "--fake",
            "--max-tokens", "1000000", "--out", str(tmp_path),
        ],
    )  # fmt: skip
    assert res.exit_code == 0, res.output
    (path,) = tmp_path.glob("fake-*.json")
    doc = json.loads(path.read_text())
    assert doc["n_items"] == 6 and set(doc["metrics"]) == {"agent", "agent_analyst"}
