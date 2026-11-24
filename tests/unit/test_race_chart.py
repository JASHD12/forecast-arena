"""The home 'race' chart: readable on a phone, labels inside the picture, honest with few days."""

import re
from datetime import date, timedelta

from arena.site.charts import RACE_MIN_DAYS, RACE_NARROW, RACE_WIDE, race_highlights, race_svg
from arena.site.titles import FORECASTER_NAMES


def _series(days: int):
    ds = [(date(2026, 11, 16) + timedelta(days=i)).isoformat() for i in range(days)]
    final = {
        "ml": 0.10, "base_rate": 0.28, "persistence": 0.235, "llm_plain": 0.22,
        "llm_context": 0.145, "agent": 0.13, "agent_graph": 0.14, "llm_local": 0.36,
    }  # fmt: skip
    series = {
        f: [(d, v * (1 + 0.1 * (days - i) / days)) for i, d in enumerate(ds)]
        for f, v in final.items()
    }
    return series, ds


def test_too_few_days_show_a_note_not_a_chart() -> None:
    series, ds = _series(RACE_MIN_DAYS - 1)
    out = race_svg(series, FORECASTER_NAMES, ds)
    assert (
        "<svg" not in out and f"after {RACE_MIN_DAYS} days" in out and "so far there are 6" in out
    )


def test_chart_has_two_layouts_a_sorted_legend_and_a_coin_reference() -> None:
    series, ds = _series(8)
    out = race_svg(series, FORECASTER_NAMES, ds)
    assert out.count("<svg") == 2 and "race-wide" in out and "race-narrow" in out
    assert "always 50% = 0.25" in out
    legend = re.findall(r'<span class="lg-name">([^<]+)</span> <span class="lg-val">([\d.]+)', out)
    vals = [float(v) for _, v in legend]
    assert next(n for n, _ in legend) == "ML model" and vals == sorted(vals)
    assert len(legend) == len(series)  # every forecaster is in the list, none only on the lines
    assert "<title>ML model: " in out  # tooltips kept


def test_every_forecaster_keeps_its_own_colour_and_the_important_ones_are_thicker() -> None:
    series, ds = _series(8)
    assert race_highlights(series) == {"ml", "base_rate", "agent"}  # best AI = lowest final Brier
    out = race_svg(series, FORECASTER_NAMES, ds)
    assert "s-muted" not in out  # nothing is greyed out any more
    classes = re.findall(r'<path class="line (s-[a-z0-9]+)( thin)?"', out)
    wide = classes[: len(classes) // 2]
    assert len({c for c, _ in wide}) == len(series)  # one distinct colour class per forecaster
    assert sum(1 for _, t in wide if t) == len(series) - 3  # only the three others are thinner
    assert out.count('class="endlabel') == len(series)  # every line labelled (wide layout only)


def test_end_labels_fit_inside_the_wide_viewbox_and_the_phone_layout_has_none() -> None:
    series, ds = _series(8)
    names = {**FORECASTER_NAMES, "agent": "A very long forecaster name for an agent with tools"}
    out = race_svg(series, names, ds)
    wide_w = RACE_WIDE[0]
    labels = re.findall(r'<text class="endlabel[^"]*" x="([\d.]+)"[^>]*>([^<]+)</text>', out)
    assert len(labels) == len(series)  # every line is labelled at its end (wide layout)
    for x, text in labels:
        # 13px bold text is about 7.6 viewBox units per character; it must end inside the box
        assert float(x) + 7.6 * len(text) <= wide_w, text
    assert any(t.startswith("A very long forecaster") is False and "…" in t for _, t in labels)
    narrow = out.split("race-narrow")[1]
    assert "endlabel" not in narrow.split("</svg>")[0]
    assert RACE_NARROW[2][2] >= 30  # room for the day labels


def test_days_axis_shows_several_days_not_just_two() -> None:
    series, ds = _series(10)
    wide = race_svg(series, FORECASTER_NAMES, ds).split("race-narrow")[0]
    day_labels = re.findall(
        r'class="tick" x="[\d.]+" y="\d+" text-anchor="\w+">(\d\d-\d\d)</text>', wide
    )
    assert 5 <= len(day_labels) <= 8 and day_labels[0] == "11-16" and day_labels[-1] == "11-25"


def test_every_day_is_labelled_and_the_coin_label_sits_in_the_margin() -> None:
    series, ds = _series(7)
    out = race_svg(series, FORECASTER_NAMES, ds)
    wide, narrow = out.split("race-narrow")[0], "race-narrow" + out.split("race-narrow")[1]
    for d in ds:  # no gap in the axis, on either layout
        assert wide.count(f">{d[5:]}</text>") == 1 and narrow.count(f">{d[5:]}</text>") == 1
    left, right = RACE_WIDE[2][3], RACE_WIDE[2][1]
    m = re.search(r'class="tick coin coin-margin" x="([\d.]+)" y="([\d.]+)"', wide)
    assert m and float(m.group(1)) >= RACE_WIDE[0] - right  # in the right margin, off the lines
    assert "coin-margin" not in narrow  # phones keep it over the plot (with a halo)
    ends = [float(y) for y in re.findall(r'class="endlabel [^"]*" x="[\d.]+" y="([\d.]+)"', wide)]
    assert all(abs(float(m.group(2)) - e) >= 14 for e in ends)  # never on top of an end label
    assert left > 0
