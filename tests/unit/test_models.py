import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from factories import forecast, question, resolution, skip
from pydantic import ValidationError

from arena.models import (
    ALL_MODELS,
    BatchSeal,
    DaySeal,
    RunManifest,
    Void,
    canonical_json,
    export_schemas,
    parse_record,
)

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "docs" / "schemas"
T = datetime(2026, 11, 12, 6, tzinfo=UTC)


def all_examples():
    q = question()
    return [
        q,
        forecast(q),
        skip(q),
        resolution(q),
        Void(question_id=q.question_id, reason_code="source_missing", voided_at=T),
        RunManifest(
            run_id="2026-11-12-morning-1",
            job="morning",
            batch_date=q.batch_date,
            status="ok",
            code_sha="abc",
            started_at=T,
            ended_at=T,
        ),
        BatchSeal(batch_date=q.batch_date, sealed_at=T, files={"questions/x": "0" * 64}),
        DaySeal(
            day=q.batch_date,
            sealed_at=T,
            files={},
            prev_chain_sha256="0" * 64,
            chain_sha256="1" * 64,
        ),
    ]


@pytest.mark.parametrize("rec", all_examples(), ids=lambda r: r.kind)
def test_round_trip_is_identical(rec) -> None:
    line = canonical_json(rec)
    assert line.endswith("\n") and line.count("\n") == 1
    back = parse_record(line)
    assert back == rec
    assert canonical_json(back) == line


def test_canonical_json_sorted_and_utf8() -> None:
    q = question()
    q2 = q.model_copy(update={"text": "Wird der Preis über 80 € liegen? (Europe/Berlin)"})
    line = canonical_json(q2)
    assert "über" in line and "€" in line
    keys = list(json.loads(line).keys())
    assert keys == sorted(keys)
    assert '"created_at":"2026-11-12T05:30:00Z"' in line


def test_question_id_must_match_fields() -> None:
    q = question()
    data = q.model_dump()
    data["question_id"] = "power-mean_gt-DE_LU-2099-01-01-v1"
    with pytest.raises(ValidationError, match="question_id must be"):
        type(q)(**data)


def test_question_time_order() -> None:
    data = question().model_dump()
    data["lock_time"] = data["created_at"] - timedelta(minutes=1)
    with pytest.raises(ValidationError):
        type(question())(**data)


def test_probability_bounds_and_nan() -> None:
    q = question()
    for bad in (-0.01, 1.01, float("nan")):
        with pytest.raises(ValidationError):
            forecast(q, p=bad)


def test_rationale_word_limit() -> None:
    f = forecast(question())
    with pytest.raises(ValidationError, match="80 words"):
        f.model_validate({**f.model_dump(), "rationale": "word " * 81})


def test_naive_datetimes_refused() -> None:
    data = question().model_dump()
    data["created_at"] = datetime(2026, 11, 12, 5)
    with pytest.raises(ValidationError):
        type(question())(**data)


def test_unknown_fields_refused() -> None:
    line = canonical_json(question()).replace('{"base_rate_hint"', '{"bogus":1,"base_rate_hint"')
    with pytest.raises(ValidationError):
        parse_record(line)


def test_skip_and_forecast_share_id_space() -> None:
    q = question()
    assert skip(q, "base_rate").record_id == forecast(q, "base_rate").record_id


def test_schemas_up_to_date(tmp_path: Path) -> None:
    export_schemas(tmp_path)
    for model in ALL_MODELS:
        name = f"{model.__name__}.schema.json"
        committed = SCHEMA_DIR / name
        assert committed.exists(), f"missing {name}: run `make schemas`"
        assert committed.read_text() == (tmp_path / name).read_text(), (
            f"{name} drifted from arena.models: run `make schemas` and commit"
        )
