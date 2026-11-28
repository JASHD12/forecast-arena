"""Per-topic and cost-per-answered-question reporting in eval results (T382)."""

from __future__ import annotations

from arena.evals.run import _by_topic, paired_by_topic, topic_of
from arena.lab import agent_eval as ae


def _row(variant: str, qid: str, p: float | None, y: int, day: str) -> dict:
    return {
        "variant": variant,
        "question_id": qid,
        "day": day,
        "outcome": y,
        "probability": p,
        "skip": None,
    }


def test_topic_is_the_first_part_of_the_question_id() -> None:
    assert topic_of("power-mean_gt-DE_LU-2026-11-02-v1") == "power"
    assert topic_of("weather-x") == "weather"


def test_by_topic_counts_answers_and_scores_each_topic() -> None:
    rows = [
        _row("a", "power-1", 0.9, 1, "d1"),
        _row("a", "power-2", None, 0, "d1"),
        _row("a", "weather-1", 0.2, 0, "d1"),
    ]
    r = _by_topic(rows, {"power-1": 0.5, "weather-1": 0.5, "power-2": 0.5})
    assert r["power"]["n"] == 2 and r["power"]["answered"] == 1
    assert (
        round(r["power"]["brier"], 4) == 0.01 and r["power"]["base_rate_brier_same_items"] == 0.25
    )
    assert r["weather"]["answered"] == 1


def test_paired_by_topic_only_with_more_than_one_topic() -> None:
    one = [_row(v, f"power-{i}", 0.6, i % 2, f"d{i}") for v in ("a", "b") for i in range(4)]
    assert paired_by_topic(one, ["a", "b"]) == []
    two = one + [_row(v, f"weather-{i}", 0.4, i % 2, f"d{i}") for v in ("a", "b") for i in range(4)]
    out = paired_by_topic(two, ["a", "b"])
    assert {p["topic"] for p in out} == {"power", "weather"} and all(p["a"] == "a" for p in out)


def _metrics(brier: float, cost: float | None) -> dict:
    topics = {
        "power": {"n": 4, "answered": 4, "brier": brier, "base_rate_brier_same_items": 0.25},
        "weather": {
            "n": 4,
            "answered": 3,
            "brier": brier + 0.1,
            "base_rate_brier_same_items": 0.24,
        },
    }
    return {
        "n": 8,
        "answered": 7,
        "brier": brier,
        "log_score": 0.5,
        "ece": None,
        "base_rate_brier_same_items": 0.245,
        "skips": {},
        "cost_usd": cost,
        "cost_usd_per_answered": None if cost is None else cost / 7,
        "by_topic": topics,
    }


def test_lab_result_gets_per_topic_rows_pairs_and_cost_per_answered() -> None:
    res = {
        "created_at": "2026-12-01T00:00:00+00:00",
        "run_id": "r",
        "golden": "g.jsonl",
        "n_items": 8,
        "golden_sha256": "0" * 64,
        "versions": {"agent_skills": "v1", "agent_committee": "v2"},
        "metrics": {"agent_skills": _metrics(0.2, 0.07), "agent_committee": _metrics(0.18, 0.14)},
        "paired": [
            {
                "a": "agent_committee",
                "b": "agent_skills",
                "n": 7,
                "diff": -0.02,
                "lo": -0.05,
                "hi": 0.01,
                "days": 3,
            }
        ],
        "paired_by_topic": [
            {
                "a": "agent_skills",
                "b": "agent_committee",
                "topic": "power",
                "n": 4,
                "diff": 0.03,
                "lo": 0.0,
                "hi": 0.06,
                "days": 2,
            },
        ],
        "rows": [],
    }
    r = ae.build(res, "agent-committee")
    assert r.metrics["agent_committee / power"]["brier"] == 0.18
    assert r.metrics["agent_committee / weather"]["asked"] == 4
    assert r.metrics["base_rate / weather"]["brier"] == 0.24
    assert r.metrics["agent_committee / eval"]["cost_usd_per_1k_answered"] == 20.0
    by = {p["split"]: p for p in r.paired}
    assert by["power"]["diff"] == -0.03 and by["power"]["lo"] == -0.06 and by["power"]["hi"] == 0.0
