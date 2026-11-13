"""Static JSON API (T139)."""

import json
from datetime import UTC, datetime

from factories import B, forecast, question

from arena.clock import FixedClock
from arena.ledger import Ledger, layout
from arena.models import Evidence, Resolution
from arena.site.api import LeaderboardFile, QuestionsFile
from arena.site.build import build_site

NOW = datetime(2026, 11, 20, tzinfo=UTC)


def _site(tmp_path):
    led = Ledger(tmp_path / "led")
    q1, q2 = question(), question(template="max_gt")
    led.append(layout.questions_path(B), [q1, q2])
    led.append(layout.forecasts_path(B), [forecast(q1, "base_rate", 0.5),
                                          forecast(q1, "llm_context", 0.8),
                                          forecast(q2, "base_rate", 0.5)])  # fmt: skip
    ev = Evidence(source_url="https://x", snapshot_sha256="a" * 64, values_used={})
    res = Resolution(question_id=q1.question_id, outcome=1, observed_value=91.0,
                     resolved_at=q1.resolve_after, evidence=ev)  # fmt: skip
    led.append(layout.resolutions_path(B), [res])
    return q1, q2, build_site(led, tmp_path / "site", FixedClock(NOW))


def test_files_validate_against_their_models_and_schemas(tmp_path) -> None:
    q1, q2, res = _site(tmp_path)
    base = res.out_dir / "api" / "v1"
    qs = QuestionsFile.model_validate_json((base / "questions.json").read_text())
    by = {q.question_id: q for q in qs.questions}
    assert by[q1.question_id].status == "resolved" and by[q1.question_id].outcome == 1
    assert by[q2.question_id].status == "open" and by[q2.question_id].outcome is None
    assert {f.forecaster_id for f in by[q1.question_id].forecasts} == {"base_rate", "llm_context"}
    assert all(f.created_at < q.lock_time for q in qs.questions for f in q.forecasts)
    latest = QuestionsFile.model_validate_json((base / "latest.json").read_text())
    assert {q.batch_date for q in latest.questions} == {B}
    lb = LeaderboardFile.model_validate_json((base / "leaderboard.json").read_text())
    assert lb.scope == "rehearsal" and lb.label  # "too early to tell" before 30 official days
    for name in ("questions", "latest", "leaderboard"):
        schema = json.loads((base / "schema" / f"{name}.schema.json").read_text())
        assert schema["type"] == "object" and "properties" in schema
    page = (res.out_dir / "api.html").read_text()
    assert 'href="api/v1/questions.json"' in page and "schema" in page


def test_schema_validation_with_jsonschema_when_available(tmp_path) -> None:
    import pytest

    jsonschema = pytest.importorskip("jsonschema")
    _, _, res = _site(tmp_path)
    base = res.out_dir / "api" / "v1"
    for name in ("questions", "latest", "leaderboard"):
        doc = json.loads((base / f"{name}.json").read_text())
        schema = json.loads((base / "schema" / f"{name}.schema.json").read_text())
        jsonschema.validate(doc, schema)
