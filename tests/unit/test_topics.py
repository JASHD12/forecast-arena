"""Topic pages (T133)."""

from datetime import UTC, datetime

from factories import B, forecast, question

from arena.clock import FixedClock
from arena.ledger import Ledger, layout
from arena.scoring.core import load
from arena.site.build import build_site
from arena.site.topics import TOPIC_INFO, topic


def test_topic_kinds_counts_and_sources(tmp_path) -> None:
    led = Ledger(tmp_path)
    qs = [question(), question(template="max_gt"), question(entity="DE_LU", template="min_lt")]
    led.append(layout.questions_path(B), qs)
    led.append(layout.forecasts_path(B), [forecast(q) for q in qs])
    t = topic("power", load(led))
    assert t["n_questions"] == 3 and [k["template"] for k in t["kinds"]] == [
        "max_gt",
        "mean_gt",
        "min_lt",
    ]
    assert "SMARD" in t["source"] and "CC BY 4.0" in t["terms"]
    assert "not verified" in TOPIC_INFO["attention"][2]  # no licence claimed without a source
    res = build_site(led, tmp_path / "site", FixedClock(datetime(2026, 11, 13, tzinfo=UTC)))
    page = (res.out_dir / "topics" / "power.html").read_text()
    assert "The kinds of question" in page and "Who forecasts this topic best" in page
    assert 'href="topics/power.html"' in (res.out_dir / "index.html").read_text()
