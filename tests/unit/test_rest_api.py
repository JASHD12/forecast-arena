"""REST API (T150), with FastAPI's TestClient."""

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from factories import B, forecast, question
from fastapi.testclient import TestClient

from arena.api.app import create_app
from arena.ledger import Ledger, layout
from arena.models import Evidence, Resolution


@pytest.fixture
def client(tmp_path):
    led = Ledger(tmp_path)
    q1, q2 = question(), question(template="max_gt")
    led.append(layout.questions_path(B), [q1, q2])
    led.append(layout.forecasts_path(B), [forecast(q1, "base_rate", 0.5),
                                          forecast(q1, "llm_context", 0.8),
                                          forecast(q2, "base_rate", 0.5)])  # fmt: skip
    ev = Evidence(source_url="https://x", snapshot_sha256="a" * 64, values_used={})
    led.append(layout.resolutions_path(B), [Resolution(
        question_id=q1.question_id, outcome=1, observed_value=91.0,
        resolved_at=q1.resolve_after, evidence=ev)])  # fmt: skip
    return TestClient(create_app(led)), q1, q2


def test_health_questions_and_one_question(client) -> None:
    c, q1, q2 = client
    assert c.get("/health").json() == {"status": "ok", "questions": 2, "forecasts": 3}
    rows = c.get("/questions", params={"status": "resolved"}).json()
    assert [r["question_id"] for r in rows] == [q1.question_id] and rows[0]["outcome"] == 1
    assert len(c.get("/questions", params={"limit": 1}).json()) == 1
    assert c.get("/questions", params={"domain": "weather"}).json() == []
    one = c.get(f"/questions/{q2.question_id}").json()
    assert one["status"] == "open" and one["forecasts"][0]["forecaster_id"] == "base_rate"
    assert c.get("/questions/nope").status_code == 404
    assert c.get("/questions", params={"limit": 0}).status_code == 422  # validated input


def test_leaderboard_and_read_only_sql(client) -> None:
    c, _, _ = client
    lb = c.get("/leaderboard").json()
    assert lb["scope"] == "rehearsal" and lb["label"]
    ok = c.get("/sql", params={"q": "SELECT count(*) AS n FROM forecasts"}).json()
    assert ok["rows"] == [[3]] and ok["columns"] == ["n"]
    for bad in ("DELETE FROM forecasts", "SELECT 1; DROP TABLE skips",
                "SELECT * FROM read_csv('/etc/passwd')"):  # fmt: skip
        assert c.get("/sql", params={"q": bad}).status_code == 400
    assert c.get("/openapi.json").json()["info"]["title"] == "Forecast Arena API"
