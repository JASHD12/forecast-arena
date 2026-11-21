"""T272: the experimental forecasters are named, coloured and kept out of the headline boards."""

from arena.scoring.boards import COMMON_GROUP
from arena.site import charts, content, titles

IDS = ("llm_local_ft", "llm_router", "agent_hybrid")


def test_names_say_experimental_and_colours_are_distinct() -> None:
    for fid in IDS:
        assert titles.forecaster_name(fid).endswith("(experimental)")
        assert charts.series_class(fid) in {"s-9", "s-10", "s-11"}
    assert len({charts.series_class(f) for f in IDS}) == 3
    assert "s-8" != charts.series_class("llm_local_ft")  # not the fallback slot


def test_they_are_ai_forecasters_and_not_in_the_common_group_or_the_ensemble() -> None:
    from arena.forecasters.ensemble import MEMBERS

    for fid in IDS:
        assert fid in content.AI_FORECASTERS and fid in content.EXPERIMENTAL_FORECASTERS
        assert fid not in COMMON_GROUP and fid not in MEMBERS


def test_methods_information_set_table_has_a_row_for_each() -> None:
    assert set(IDS) <= {r[0] for r in content.INFORMATION_SETS}


def test_health_roster_includes_the_fine_tuned_model_only_when_switched_on() -> None:
    from arena.config import Settings
    from arena.ops.health import expected_forecasters

    assert "llm_local_ft" not in expected_forecasters(Settings.from_env({}))
    assert "llm_local_ft" in expected_forecasters(Settings.from_env({"ARENA_LLM_LOCAL_FT": "1"}))


def test_experimental_live_lists_only_forecasters_that_have_published() -> None:
    from datetime import UTC, datetime
    from types import SimpleNamespace as NS

    from arena.site.shaping import experimental_live

    def fc(fid: str, day: int) -> NS:
        return NS(forecaster_id=fid, created_at=datetime(2026, 11, day, 7, tzinfo=UTC))

    rec = NS(forecasts=[fc("llm_local_ft", 24), fc("llm_local_ft", 23), fc("ml", 23)])
    out = experimental_live(rec, titles.FORECASTER_NAMES)
    assert out == [
        {
            "fid": "llm_local_ft",
            "name": "Fine-tuned open model (experimental)",
            "n": 2,
            "first_day": "2026-11-23",
        }  # fmt: skip
    ]
    assert experimental_live(NS(forecasts=[]), {}) == []
