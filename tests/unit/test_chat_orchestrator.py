"""The Ask the Arena orchestrator (T312/T314) run under Node: parity with Python BM25, refusals."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from arena.agent.retrieval import BM25Index

ROOT = Path(__file__).resolve().parents[2]
CHAT = ROOT / "src" / "arena" / "site" / "static" / "chat.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="needs Node")

PACK = {
    "version": 1, "built": "2026-11-13", "status": "Rehearsal.", "disclaimer": "x",
    "forecasters": {"ml": "ML model", "base_rate": "Base rate"},
    "domains": {"power": "Electricity"},
    "questions": [
        {
            "id": "power-q1", "domain": "power", "template": "mean_gt", "entity": "DE_LU",
            "title": "Electricity above 150 on Sat 14 Nov",
            "text": "Will German electricity average more than 150 EUR/MWh on 14 November 2026?",
            "target": "2026-11-14", "batch": "2026-11-13", "lock": "2026-11-13 09:30 UTC",
            "threshold": 150.0, "unit": "EUR/MWh", "state": "open", "outcome": None,
            "f": {"ml": [0.2, None], "base_rate": [0.5, None]},
        }
    ],
    "boards": [],
    "docs": [
        {"id": "docs/a.md#1", "path": "docs/a.md", "heading": "Brier score",
         "text": "The Brier score is the mean squared error of probabilities against outcomes."},
        {"id": "docs/b.md#1", "path": "docs/b.md", "heading": "Ledger",
         "text": "The ledger is append-only and hash chained, so nothing is rewritten."},
    ],
}  # fmt: skip


def _node(script: str) -> object:
    code = f"const c=require({json.dumps(str(CHAT))});const pack={json.dumps(PACK)};{script}"
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_bm25_scores_equal_the_python_index() -> None:
    docs = [f"{d['heading']} {d['text']}" for d in PACK["docs"]] + ["unrelated words here"]
    query = "brier score probabilities"
    got = _node(
        f"console.log(JSON.stringify(new c.BM25({json.dumps(docs)}).scores({json.dumps(query)})))"
    )
    want = BM25Index(docs).scores(query)
    assert [round(x, 9) for x in got] == [round(float(x), 9) for x in want]  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "text",
    [
        "What will be the price of Google stock on 24 Nov?",
        "Should I buy Tesla shares?",
        "Which ETF should I invest in?",
        "Soll ich Aktien kaufen?",
    ],
)
def test_stock_and_advice_questions_are_refused(text: str) -> None:
    r = _node(f"console.log(JSON.stringify(c.answer({json.dumps(text)}, pack)))")
    assert r["kind"] == "refusal" and "not advice" in r["text"]  # type: ignore[index]


def test_published_question_is_looked_up_and_ml_leads_when_decisive() -> None:
    q = "What is the forecast for electricity above 150 on 2026-11-14?"
    r = _node(f"console.log(JSON.stringify(c.answer({json.dumps(q)}, pack)))")
    assert r["kind"] == "lookup" and r["sources"] == ["question power-q1"]  # type: ignore[index]
    assert "ML model (leads)" in json.dumps(r["rows"])  # type: ignore[index]
    assert "20%" in json.dumps(r["rows"])  # type: ignore[index]


def test_wrong_threshold_is_declined_with_nearest_question() -> None:
    q = "What is the forecast for electricity above 299 on 2026-11-14?"
    r = _node(f"console.log(JSON.stringify(c.answer({json.dumps(q)}, pack)))")
    assert r["kind"] == "decline" and "no locked forecast" in r["text"]  # type: ignore[index]
    assert r["sources"] == ["question power-q1"]  # type: ignore[index]


def test_method_question_is_answered_from_documents_with_a_citation() -> None:
    r = _node("console.log(JSON.stringify(c.answer('How is the Brier score computed?', pack)))")
    assert r["kind"] == "docs" and "[docs/a.md#1]" in r["text"]  # type: ignore[index]


def test_unknown_question_is_declined_not_invented() -> None:
    r = _node("console.log(JSON.stringify(c.answer('Tell me a joke', pack)))")
    assert r["tier"] == -1 and "joke" not in r["text"].lower()  # type: ignore[index]


def test_golden_evaluation_meets_the_stated_floors(tmp_path: Path) -> None:
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import chat_eval  # type: ignore[import-not-found]

    m = chat_eval.measure(chat_eval.fixture_pack(tmp_path))
    cats = {c: v["pct"] for c, v in m["category_pct"].items()}
    assert m["refusal_pct"] == 100 and m["false_refusal_pct"] == 0
    assert m["no_invented_numbers_pct"] == 100
    assert cats["decline"] == 100 and cats["lookup"] >= 95 and cats["result"] >= 95
