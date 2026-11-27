"""The forecaster catalog (T383): every derived list equals the pre-refactor snapshot."""

from __future__ import annotations

import json
import re
from pathlib import Path

from arena.config import Settings
from arena.forecasters import catalog as C

ROOT = Path(__file__).parents[2]
SNAP = json.loads((ROOT / "tests/fixtures/forecaster_catalog_snapshot.json").read_text("utf-8"))


def test_names_slots_and_information_sets_equal_the_snapshot() -> None:
    assert C.FORECASTER_NAMES == dict(SNAP["names"])
    assert C.SERIES_SLOTS == dict(SNAP["slots"])
    assert [list(x) for x in C.INFORMATION_SETS] == SNAP["information_sets"]


def test_label_sets_and_orders_equal_the_snapshot() -> None:
    assert sorted(C.AI_FORECASTERS) == SNAP["ai"]
    assert sorted(C.RETIRED_FORECASTERS) == SNAP["retired"]
    assert sorted(C.EXPERIMENTAL_FORECASTERS) == SNAP["experimental"]
    assert sorted(C.CORE_FORECASTERS) == SNAP["core"]
    assert list(C.DISPLAY_ORDER) == SNAP["display_order"]
    assert list(C.RACE_AI) == SNAP["charts_ai"]


def test_the_rosters_of_every_flag_equal_the_snapshot() -> None:
    assert sorted(C.expected_roster(Settings.from_env({}))) == SNAP["roster_base"]
    for flag, ids in SNAP["flag_roster"].items():
        got = C.expected_roster(Settings.from_env({"ARENA_" + flag.upper(): "1"}))
        assert sorted(got - set(SNAP["roster_base"])) == ids


def test_modules_use_the_catalog_not_their_own_copies() -> None:
    from arena.ops import health
    from arena.site import charts, content, shaping, titles

    assert titles.FORECASTER_NAMES is C.FORECASTER_NAMES
    assert content.INFORMATION_SETS is C.INFORMATION_SETS
    assert content.AI_FORECASTERS is C.AI_FORECASTERS
    assert content.EXPERIMENTAL_FORECASTERS is C.EXPERIMENTAL_FORECASTERS
    assert charts.SERIES_SLOTS is C.SERIES_SLOTS and charts.AI_FORECASTERS is C.RACE_AI
    assert (
        shaping.DISPLAY_ORDER is C.DISPLAY_ORDER and health.CORE_FORECASTERS is C.CORE_FORECASTERS
    )


def test_every_flag_is_a_settings_field_and_ids_are_unique() -> None:
    assert all(f in Settings.model_fields for f in C.FLAGS.values())
    ids = [e.id for e in C.CATALOG]
    assert len(ids) == len(set(ids)) == len(C.BY_ID)
    shared = {}
    for e in C.CATALOG:
        if e.slot is not None:
            shared.setdefault(e.slot, []).append(e.id)
    # `llm_local` shares the ensemble's colour until a validated extra colour exists (DECISIONS)
    assert [sorted(v) for v in shared.values() if len(v) > 1] == [["ensemble", "llm_local"]]


def test_every_colour_slot_has_css_in_light_and_both_dark_blocks() -> None:
    css = (ROOT / "src/arena/site/static/style.css").read_text("utf-8")
    slots = set(C.SERIES_SLOTS.values())
    assert max(slots) <= 20
    for n in slots:
        assert len(re.findall(rf"--s{n}:", css)) == 3, f"--s{n} must be defined in three blocks"
        assert re.search(rf"\.s-{n}\s*\{{\s*--c:\s*var\(--s{n}\)", css), f".s-{n} class missing"
