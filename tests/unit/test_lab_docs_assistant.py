"""T254: the docs assistant answers with citations or refuses; the question set is honest."""

import json
from pathlib import Path

from arena.lab.docs_assistant import (
    DOC_PATHS,
    DocsIndex,
    ask,
    chunk_markdown,
    evaluate,
    load_chunks,
)

ROOT = Path(__file__).resolve().parents[2]
TEXT = (
    "# Title\nintro line\n\n## Locking\nForecasts lock at 09:30 UTC every morning, and nothing "
    "written after that counts.\n\n## Scoring\nThe Brier score is the mean squared error of "
    "the probabilities.\n"
)


def test_chunks_split_at_headings_and_have_stable_ids() -> None:
    chunks = chunk_markdown("docs/x.md", TEXT)
    assert [c.heading for c in chunks] == ["Title", "Locking", "Scoring"]
    assert chunks[1].chunk_id == "docs/x.md#2" and "09:30" in chunks[1].text


def test_answers_are_cited_sentences_from_the_documents() -> None:
    idx = DocsIndex(chunk_markdown("docs/x.md", TEXT))
    ans = ask(idx, "When do forecasts lock?")
    assert not ans.refused and "09:30" in ans.text and ans.citations == ("docs/x.md#2",)


def test_out_of_scope_questions_are_refused() -> None:
    idx = DocsIndex(chunk_markdown("docs/x.md", TEXT))
    ans = ask(idx, "How do I bake sourdough bread?")
    assert ans.refused and ans.citations == ()


def test_golden_questions_point_at_real_phrases() -> None:
    """Every expected phrase really appears in its expected file (no invented references)."""
    rows = [
        json.loads(x)
        for x in (ROOT / "evals/golden/docs-qa-v1.jsonl").read_text().splitlines()
        if x
    ]
    assert len(rows) >= 26
    for r in rows:
        if r["source"] is not None:
            assert r["source"] in DOC_PATHS
            assert r["must_contain"].lower() in (ROOT / r["source"]).read_text().lower(), r["q"]


def test_evaluation_on_the_real_documents_is_deterministic() -> None:
    rows = [
        json.loads(x)
        for x in (ROOT / "evals/golden/docs-qa-v1.jsonl").read_text().splitlines()
        if x
    ]
    idx = DocsIndex(load_chunks(ROOT, DOC_PATHS))
    first = evaluate(idx, rows)
    assert first == evaluate(idx, rows)
    assert first["hit_pct"] >= 50 and first["correct_refusal_pct"] >= 80
