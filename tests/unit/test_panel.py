from datetime import UTC, datetime
from pathlib import Path

import pytest
from factories import question

from arena.forecasters.panel import (
    HumanPanel,
    latest_by_member,
    parse_panel_csv,
    pseudonym,
    token_hash,
)
from arena.models import Forecast, Skip

CSV = (Path(__file__).parents[1] / "fixtures" / "panel" / "submissions.csv").read_text()
ASOF = datetime(2026, 11, 12, 9, 29, tzinfo=UTC)


def test_bad_rows_counted_not_guessed() -> None:
    intake = parse_panel_csv(CSV)
    assert intake.rejected == {"bad_token": 1, "bad_probability": 1, "bad_value": 1}
    assert all(r.member.startswith("panel-") and len(r.member) == 14 for r in intake.rows)
    assert "alpha-token-0001" not in repr(intake)


def test_late_rows_ignored_and_latest_wins() -> None:
    q = question()  # mean_gt, lock 2026-11-12 09:30 UTC
    rows = latest_by_member(parse_panel_csv(CSV).rows, q)
    assert rows[pseudonym("alpha-token-0001")].probability == 0.55  # latest valid
    assert rows[pseudonym("gamma-token-0003")].probability == 0.20  # 09:31 is after lock
    assert pseudonym("delta-token-0004") not in rows  # submitted after lock
    assert len(rows) == 3


def test_median_with_three_or_more() -> None:
    out = HumanPanel(parse_panel_csv(CSV)).forecast(question(), {}, ASOF)
    assert isinstance(out, Forecast) and out.probability == 0.55  # median of .55 .70 .20
    assert out.meta["n"] == 3 and all(m.startswith("panel-") for m in out.meta["members"])


def test_fewer_than_three_answers_is_a_skip() -> None:
    out = HumanPanel(parse_panel_csv(CSV)).forecast(question(template="max_gt"), {}, ASOF)
    assert isinstance(out, Skip) and out.reason_code == "not_sampled" and "2 panel" in out.detail
    none = HumanPanel(None).forecast(question(), {}, ASOF)
    assert isinstance(none, Skip) and none.reason_code == "model_missing"


def test_allowlist_and_header() -> None:
    allow = {token_hash("alpha-token-0001"), token_hash("beta-token-00002")}
    intake = parse_panel_csv(CSV, allowlist=allow)
    assert {r.member for r in intake.rows} == {
        pseudonym("alpha-token-0001"),
        pseudonym("beta-token-00002"),
    }
    assert intake.rejected["unknown_token"] >= 5
    with pytest.raises(ValueError):
        parse_panel_csv("name,email\nx,y\n")
