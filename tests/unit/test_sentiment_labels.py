"""Open model against Claude labels (T375): parser on the real response, rubric, agreement."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from arena.cli import main
from arena.lab import sentiment_labels as sl

FIX = Path(__file__).parents[1] / "fixtures" / "gdelt" / "titles"
ART = FIX / "bitcoin_artlist_20261120.json"


def test_fixture_matches_its_provenance_hash() -> None:
    prov = json.loads((FIX / "provenance.json").read_text("utf-8"))[0]
    assert hashlib.sha256(ART.read_bytes()).hexdigest() == prov["sha256"]


def test_parse_titles_real_response_keeps_only_titles_and_times() -> None:
    rows = sl.parse_titles(json.loads(ART.read_text("utf-8")))
    assert len(rows) == 20
    title, seen = rows[1]
    assert title.startswith("Bitcoin Breaks Below $60")
    assert seen.tzinfo is UTC and seen.date() == datetime(2026, 11, 20, tzinfo=UTC).date()
    assert all(isinstance(t, str) and isinstance(s, datetime) for t, s in rows)


@pytest.mark.parametrize("bad", [None, {}, {"articles": [{"title": "x"}]}, {"articles": 3}])
def test_malformed_article_lists_raise(bad: object) -> None:
    with pytest.raises(sl.LabelError):
        sl.parse_titles(bad)


def test_open_rating_bins_are_the_preregistered_ones() -> None:
    cases = [(-1, 1), (-0.61, 1), (-0.6, 2), (-0.21, 2), (-0.2, 3), (0, 3), (0.2, 3), (0.21, 4)]
    cases += [(0.6, 4), (0.61, 5), (1, 5)]
    for score, rating in cases:
        assert sl.open_rating(score) == rating, score
    with pytest.raises(sl.LabelError):
        sl.open_rating(1.5)


def test_parse_rating_accepts_json_and_rejects_the_rest() -> None:
    assert sl.parse_rating('{"rating": 4}') == 4
    assert sl.parse_rating('Sure.\n```json\n{"rating": 2}\n```') == 2
    for bad in ("", "no", '{"rating": 6}', '{"rating": "4"}', '{"rating": true}', "[4]"):
        assert sl.parse_rating(bad) is None


def test_rate_with_claude_repairs_once_then_gives_up() -> None:
    calls: list[str] = []

    def flaky(system: str, user: str) -> str:
        calls.append(user)
        return "hmm" if len(calls) == 1 else '{"rating": 5}'

    assert sl.rate_with_claude(flaky, "bitcoin", "Bitcoin surges") == 5 and len(calls) == 2
    n = {"c": 0}

    def never(system: str, user: str) -> str:
        n["c"] += 1
        return "no"

    assert sl.rate_with_claude(never, "bitcoin", "x") is None and n["c"] == 2


def test_compare_counts_agreement_and_excludes_unparsed() -> None:
    pairs = [(1, 1), (3, 3), (5, 4), (2, 2), (3, None), (4, 5)]
    r = sl.compare(pairs)
    assert r["n"] == 5 and r["unparsed"] == 1
    assert r["exact_match_pct"] == 60.0 and r["three_class_pct"] == 100.0
    assert 0.8 < r["weighted_kappa"] < 1.0
    assert r["pair_counts"]["5-4"] == 1 and sum(r["claude_distribution"].values()) == 5
    assert sl.compare([])["weighted_kappa"] is None


def test_sample_is_seeded_distinct_and_capped_per_coin() -> None:
    titles = {"bitcoin": [f"t{i}" for i in range(300)] + ["t1"], "ripple": ["a", "b"]}
    a = sl.sample_titles(titles, per_coin=100)
    assert a == sl.sample_titles(titles, per_coin=100)
    assert sum(c == "bitcoin" for c, _ in a) == 100 and sum(c == "ripple" for c, _ in a) == 2
    assert len({t for c, t in a if c == "bitcoin"}) == 100


def test_artlist_params_use_the_fixed_queries() -> None:
    p = sl.artlist_params("solana")
    assert p["query"] == "solana crypto sourcelang:english" and p["mode"] == "artlist"
    with pytest.raises(sl.LabelError):
        sl.artlist_params("dogecoin")


def test_the_paid_command_is_refused_outside_actions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    res = CliRunner().invoke(main, ["lab", "sentiment-labels-run", "--model-dir", str(tmp_path)])
    assert res.exit_code == 2
