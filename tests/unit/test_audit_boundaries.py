"""Regressions for malformed numbers and CTE-prefixed SQL mutations."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from arena.domains.base import AsOfStore, Observation
from arena.mcp_server import SqlRefused, check_sql
from arena.models import Evidence, Resolution, canonical_json
from arena.sources.smard import SmardError, parse_chunk


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), True])
def test_invalid_observations_are_rejected(value):
    with pytest.raises(SmardError):
        parse_chunk({"series": [[0, value]]})
    now = datetime(2026, 11, 16, tzinfo=UTC)
    with pytest.raises(ValueError):
        AsOfStore([Observation(now, now, "price", value)])


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_invalid_resolution_and_nested_json_are_rejected(value):
    with pytest.raises(ValidationError):
        Resolution(
            question_id="x",
            outcome=0,
            observed_value=value,
            resolved_at=datetime(2026, 11, 16, tzinfo=UTC),
            evidence=Evidence(source_url="https://example.com", snapshot_sha256="a" * 64),
        )
    with pytest.raises(ValueError):
        canonical_json(
            Evidence(
                source_url="https://example.com",
                snapshot_sha256="a" * 64,
                values_used={"bad": value},
            )
        )


@pytest.mark.parametrize(
    "query",
    [
        "WITH x AS (SELECT 1) DELETE FROM forecasts RETURNING *",
        "WITH x AS (SELECT 1) UPDATE forecasts SET probability=0 RETURNING *",
        "WITH x AS (SELECT 1) INSERT INTO forecasts SELECT * FROM forecasts",
        "SELECT 1; DELETE FROM forecasts",
    ],
)
def test_cte_mutations_are_refused(query):
    with pytest.raises(SqlRefused):
        check_sql(query)


def test_real_cte_and_string_semicolons_remain_valid():
    assert check_sql("WITH x AS (SELECT ';' AS a) SELECT * FROM x")
