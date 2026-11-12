from datetime import UTC, date, datetime, time

from weather_fixtures import fixture_weather

from arena.site.titles import plain_title


def test_every_weather_question_gets_a_short_title() -> None:
    b = date(2026, 11, 9)
    qs = fixture_weather().generate_questions(b, datetime.combine(b, time(5, 30), tzinfo=UTC))
    titles = {q.template: plain_title(q) for q in qs}
    assert set(titles) == {"tmax_gt", "wet_day", "frost_day", "gust_gt", "warmer_than",
                           "wetter_than"}  # fmt: skip
    for q in qs:
        t = plain_title(q)
        assert t != q.text and t.endswith("?") and len(t) < len(q.text)
        assert "Tue 10 Nov" in t  # always the date, never a relative "tomorrow"
    assert titles["warmer_than"] == "Will Berlin be warmer than Munich on Tue 10 Nov?"


def test_unknown_template_falls_back_to_exact_text() -> None:
    b = date(2026, 11, 9)
    q = fixture_weather().generate_questions(b, datetime.combine(b, time(5, 30), tzinfo=UTC))[0]
    odd = q.model_copy(update={"template": "something_new"})
    assert plain_title(odd) == q.text


def test_power_attention_markets_titles() -> None:
    from factories import question

    from arena.site.titles import POWER

    for t in POWER:
        q = question("DE_LU", date(2026, 11, 12), template=t)
        assert "German" in plain_title(q) and "Fri 13 Nov" in plain_title(q)
    base = question("DE_LU", date(2026, 11, 12))
    params = {"project": "en.wikipedia", "title": "Mount_Etna"}
    att = base.model_copy(
        update={"domain": "attention", "template": "views_ge", "threshold": 52000.0,
                "params": params}
    )  # fmt: skip
    assert plain_title(att) == (
        "Will the English Wikipedia article “Mount Etna” get at least 52,000 views on Fri 13 Nov?"
    )
    up = base.model_copy(update={"domain": "markets", "template": "up",
                                 "params": {"currency": "USD"}})  # fmt: skip
    assert plain_title(up) == "Will the euro be worth more USD at the next ECB fixing?"


def test_threshold_is_never_rounded_in_a_title() -> None:
    from factories import question

    q = question("DE_LU", date(2026, 11, 12)).model_copy(update={"threshold": 224.37})
    assert "224.37 €/MWh" in plain_title(q)
    assert "80 €/MWh" in plain_title(question("DE_LU", date(2026, 11, 12)))
