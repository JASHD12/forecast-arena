"""Leaderboard matrices (T134)."""

from datetime import date, timedelta

from arena.scoring.core import Scored
from arena.site.matrices import MIN_N, head_to_head, heatmap, tone

D0 = date(2026, 11, 1)


def scored(fid, p, n=30, domain="power", y=lambda i: i % 2):
    return [
        Scored(f"{domain}-q{i}", fid, "1", domain, D0 + timedelta(days=i // 3), p(i), y(i))
        for i in range(n)
    ]


def test_tone_bins_and_sign() -> None:
    assert tone(None) == tone(0.01) == "hm-n"
    assert tone(0.05) == "hm-b1" and tone(0.10) == "hm-b2" and tone(0.3) == "hm-b3"
    assert tone(-0.05) == "hm-r1" and tone(-0.2) == "hm-r3"
    assert tone(-0.1, better_when_positive=False) == "hm-b2"


def test_heatmap_skill_and_few() -> None:
    good = scored("ml", lambda i: 0.8 if i % 2 else 0.2)
    base = scored("base_rate", lambda i: 0.5)
    few = scored("llm_plain", lambda i: 0.9 if i % 2 else 0.1, n=MIN_N - 1)
    h = heatmap(good + base + few, ["base_rate", "llm_plain", "ml"], ["power", "weather"])
    assert h["fids"] == ["llm_plain", "ml"]  # base_rate is the yardstick, not a row
    ml = h["cells"]["ml"]["power"]
    assert ml["skill"] > 0.5 and ml["tone"] == "hm-b3" and not ml["few"]
    assert (
        h["cells"]["llm_plain"]["power"]["few"]
        and h["cells"]["llm_plain"]["power"]["tone"] == "hm-n"
    )
    assert h["cells"]["ml"]["weather"]["skill"] is None


def test_head_to_head_is_antisymmetric_and_marks_clear_gaps() -> None:
    good = scored("ml", lambda i: 0.9 if i % 2 else 0.1, n=60)
    base = scored("base_rate", lambda i: 0.5, n=60)
    tiny = scored("agent", lambda i: 0.5, n=MIN_N - 2)
    m = head_to_head(good + base + tiny, ["base_rate", "ml", "agent"])
    ab, ba = m["cells"]["ml"]["base_rate"], m["cells"]["base_rate"]["ml"]
    assert ab["diff"] < 0 and abs(ab["diff"] + ba["diff"]) < 1e-12
    assert ab["excludes_zero"] and ab["tone"] == "hm-b2" and ba["tone"] == "hm-r2"
    assert m["cells"]["ml"]["ml"] is None
    assert m["cells"]["agent"]["ml"]["diff"] is None  # too few shared questions
