import os
import re
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import pytest
from attention_fixtures import FixtureSource

from arena.domains.attention import (
    AttentionDomain,
    blocked,
    entity_for,
    is_article,
    load_blocklist,
    round_k,
    titles_from_questions,
)
from arena.models import Question, Resolution, Void, canonical_json

GOLDEN = Path(__file__).parents[1] / "fixtures" / "golden" / "attention"
BATCHES = {"resolvable": date(2026, 11, 8), "latest": date(2026, 11, 12)}


def asof(b: date) -> datetime:
    return datetime.combine(b, time(5, 30), tzinfo=UTC)


def gen(b: date, **kw) -> list[Question]:
    return AttentionDomain(FixtureSource(), **kw).generate_questions(b, asof(b))


@pytest.mark.parametrize("name", sorted(BATCHES))
def test_golden(name: str) -> None:
    got = "".join(canonical_json(q) for q in gen(BATCHES[name]))
    path = GOLDEN / f"{name}.jsonl"
    if os.environ.get("UPDATE_GOLDEN") == "1":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(got, encoding="utf-8")
    assert got == path.read_text(encoding="utf-8")


def test_four_per_project_deterministic_and_reference_day() -> None:
    qs = gen(date(2026, 11, 12))
    assert [canonical_json(q) for q in qs] == [canonical_json(q) for q in gen(date(2026, 11, 12))]
    for project in ("de.wikipedia", "en.wikipedia"):
        mine = [q for q in qs if q.params["project"] == project]
        assert len(mine) == 4
        assert sum(q.params["reference_rank"] <= 50 for q in mine) == 2
        assert all(5 <= q.params["reference_rank"] <= 200 for q in mine)
        assert {q.params["reference_day"] for q in mine} == {"2026-11-10"}  # B-2


def test_persons_blocklist_and_non_articles_never_selected() -> None:
    src = FixtureSource()
    patterns = load_blocklist()
    for b in BATCHES.values():
        for q in AttentionDomain(src).generate_questions(b, asof(b)):
            project, title = q.params["project"], q.params["title"]
            p31 = src.p31.get(f"{project}|{title}")
            assert p31 is not None and "Q5" not in p31, title
            assert not blocked(title, patterns) and is_article(project, title)


def test_blocklisted_title_is_dropped() -> None:
    first = gen(date(2026, 11, 12))
    title = first[0].params["title"]
    custom = [*load_blocklist(), re.compile(re.escape(title.replace("_", " ")), re.IGNORECASE)]
    again = gen(date(2026, 11, 12), blocklist=custom)
    assert title not in {q.params["title"] for q in again}


def test_recent_batches_excluded() -> None:
    first = gen(date(2026, 11, 12))
    used = {q.params["title"] for q in first}
    again = gen(date(2026, 11, 12), recent_titles=lambda project, batch: used)
    assert used.isdisjoint({q.params["title"] for q in again})
    later = [q.model_copy(update={"batch_date": date(2026, 11, 11)}) for q in first]
    assert titles_from_questions(later, "de.wikipedia", date(2026, 11, 12)) == {
        q.params["title"] for q in first if q.params["project"] == "de.wikipedia"
    }
    assert titles_from_questions(later, "de.wikipedia", date(2026, 11, 16)) == set()


def test_resolution_and_void() -> None:
    dom = AttentionDomain(FixtureSource())
    qs = gen(date(2026, 11, 8))
    q = qs[0]
    assert dom.resolve(q, q.resolve_after - timedelta(minutes=1)) is None
    r = dom.resolve(q, q.resolve_after)
    assert isinstance(r, Resolution)
    assert r.outcome == int(r.observed_value >= q.threshold)
    missing = q.model_copy(update={"params": {**q.params, "title": "Nope_404"}})
    assert dom.resolve(missing, q.resolve_after) is None
    v = dom.resolve(missing, q.resolve_after + timedelta(hours=96))
    assert isinstance(v, Void) and v.reason_code == "source_missing"


def test_context_only_available_days() -> None:
    dom = AttentionDomain(FixtureSource())
    q = gen(date(2026, 11, 12))[0]
    ctx = dom.context(q, asof(date(2026, 11, 12)))
    assert ctx["daily_views"] and max(d["day"] for d in ctx["daily_views"]) <= "2026-11-10"


def test_helpers() -> None:
    assert round_k(43_700 * 0.6) == 26_000 and round_k(87) == 87 and round_k(0.2) == 1
    assert not is_article("de.wikipedia", "Spezial:Suche")
    assert not is_article("en.wikipedia", "Main_Page")
    assert is_article("en.wikipedia", "Star_Wars:_Episode_IV")
    assert entity_for("de.wikipedia", "Rhein-Main") == "dewiki.Rhein%2DMain"
    assert blocked("Deaths_in_2026", load_blocklist())
