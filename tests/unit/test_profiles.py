"""Forecaster profiles (T132)."""

from datetime import timedelta

from factories import B, forecast, question

from arena.ledger import Ledger, layout
from arena.models import Evidence, Resolution
from arena.scoring.core import load
from arena.site.build import INFORMATION_SETS, version_changelog
from arena.site.llm_obs import UsageRow
from arena.site.profiles import profile
from arena.site.titles import FORECASTER_NAMES


def _rec(tmp_path, days=3, per_day=4):
    led = Ledger(tmp_path)
    templates = ["mean_gt", "max_gt", "min_lt", "spread_gt"][:per_day]
    for i in range(days):
        d = B + timedelta(days=i)
        qs = [question(batch=d, template=t) for t in templates]
        led.append(layout.questions_path(d), qs)
        led.append(
            layout.forecasts_path(d),
            [forecast(q, "base_rate", 0.5) for q in qs]
            + [forecast(q, "llm_context", 0.9 if k % 2 == 0 else 0.2) for k, q in enumerate(qs)],
        )
        led.append(
            layout.resolutions_path(d),
            [
                Resolution(
                    question_id=q.question_id,
                    outcome=1 if k % 2 == 0 else 0,
                    observed_value=1.0,
                    resolved_at=q.resolve_after,
                    evidence=Evidence(
                        source_url="https://x", snapshot_sha256="a" * 64, values_used={}
                    ),
                )
                for k, q in enumerate(qs)
            ],
        )
    return load(led)


def test_profile_scores_calls_versions_and_usage(tmp_path) -> None:
    rec = _rec(tmp_path)
    info = {f: (s, c) for f, s, c in INFORMATION_SETS}
    usage = [UsageRow(B, "llm_context", "m", 3, 0, 1, 900, 120, 1.0, 2.0, 0.001)]
    p = profile("llm_context", rec, FORECASTER_NAMES, version_changelog(rec), usage, info)
    assert p["n"] == 12 and p["brier"] < p["base_brier"] == 0.25
    assert p["calibration"] is not None and p["race"] is not None
    assert set(p["race_rows"]) == {"llm_context", "base_rate"}
    best, worst = p["best"], p["worst"]
    assert len(best) == len(worst) == 5
    assert (best[0].probability - best[0].outcome) ** 2 <= (
        worst[0].probability - worst[0].outcome
    ) ** 2
    assert p["versions"][0]["version"] == "1" and p["usage"]["calls"] == 3
    assert "as-of context" in p["sees"]
    b = profile("base_rate", rec, FORECASTER_NAMES, [], [], info)
    assert "base_brier" not in b and set(b["race_rows"]) == {"base_rate"}


def test_profile_pages_are_built_and_linked(tmp_path) -> None:
    from arena.clock import FixedClock
    from arena.site.build import build_site

    _rec(tmp_path / "led")
    from datetime import UTC, datetime

    res = build_site(
        Ledger(tmp_path / "led"), tmp_path / "site", FixedClock(datetime(2026, 11, 20, tzinfo=UTC))
    )
    page = (res.out_dir / "forecasters" / "llm_context.html").read_text()
    assert "Best calls" in page and "Version history" in page and "Calibration" in page
    board = (res.out_dir / "leaderboard.html").read_text()
    assert 'href="forecasters/llm_context.html"' in board
    assert (res.out_dir / "forecasters" / "index.html").exists()
