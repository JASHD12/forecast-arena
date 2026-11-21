"""T241: lab dataset rows are the live prompt, deterministic, and never leak across splits."""

from datetime import UTC, date, datetime

import pytest
from power_fixtures import fixture_domain

from arena.forecasters.llm import LLMContext
from arena.lab import dataset as ds
from arena.llm import prompts

SPLITS = {
    "train": (date(2026, 1, 1), date(2026, 1, 20)),
    "val": (date(2026, 1, 21), date(2026, 1, 31)),
    "test_oct": (date(2026, 2, 1), date(2026, 2, 10)),
    "test_nov": (date(2026, 2, 11), date(2026, 2, 20)),
}


def _rows():
    domain = fixture_domain()
    return {n: ds.build_split(domain, n, SPLITS) for n in SPLITS}


def test_default_windows_are_ordered_and_checked() -> None:
    ds.check_windows()
    bad = {**ds.SPLITS, "val": (date(2026, 6, 30), date(2026, 9, 30))}
    with pytest.raises(ValueError):
        ds.check_windows(bad)
    inverted = {**ds.SPLITS, "val": (date(2026, 9, 30), date(2026, 7, 1))}
    with pytest.raises(ValueError):
        ds.check_windows(inverted)


def test_splits_do_not_share_a_batch_day_and_are_ordered() -> None:
    rows = _rows()
    ds.assert_no_overlap(rows)
    last = {n: max(r.batch_date for r in rs) for n, rs in rows.items() if rs}
    first = {n: min(r.batch_date for r in rs) for n, rs in rows.items() if rs}
    assert last["train"] < first["val"] < first["test_oct"] <= last["test_oct"] < first["test_nov"]
    glued = {"a": rows["train"], "b": rows["train"]}
    with pytest.raises(ValueError):
        ds.assert_no_overlap(glued)


def test_row_input_is_the_exact_live_prompt() -> None:
    domain = fixture_domain()
    from arena.evals.golden import build

    items = build(domain, date(2026, 1, 5), date(2026, 1, 5), datetime(2026, 1, 9, tzinfo=UTC))
    assert items
    it = items[0]
    row = ds.to_row(it, "train")
    f = LLMContext(None)
    assert row.user == f.user_prompt(it.question, it.context, it.asof)
    assert row.system == prompts.load("system", f.prompt_version)
    assert row.outcome in (0, 1) and row.id == it.question.question_id


def test_output_is_deterministic_and_round_trips(tmp_path) -> None:
    a, b = _rows()["train"], _rows()["train"]
    assert [r.as_json() for r in a] == [r.as_json() for r in b]
    sha1 = ds.write_split(a, tmp_path / "a.jsonl.gz")
    sha2 = ds.write_split(b, tmp_path / "b.jsonl.gz")
    assert sha1 == sha2 == ds.plain_sha256(tmp_path / "a.jsonl.gz")
    assert (tmp_path / "a.jsonl.gz").read_bytes() == (tmp_path / "b.jsonl.gz").read_bytes()
    assert ds.read_split(tmp_path / "a.jsonl.gz") == a
    assert ds.write_split(a, tmp_path / "plain.jsonl") == sha1
    assert ds.read_split(tmp_path / "plain.jsonl") == a


def test_subsample_is_seeded_template_proportional_and_stable() -> None:
    rows = _rows()["train"]
    assert len(rows) > 12
    s1 = ds.subsample(rows, 12, seed=1)
    assert s1 == ds.subsample(rows, 12, seed=1)
    assert {r.template for r in s1} == {r.template for r in rows}
    assert ds.subsample(rows, 10_000) == rows
    assert s1 != ds.subsample(rows, 12, seed=2)


def test_data_card_copies_the_manifest_numbers() -> None:
    rows = _rows()
    manifest = {
        "seed": 0,
        "splits": {
            n: {"sha256": "a" * 64, "window": [d.isoformat() for d in SPLITS[n]], **ds.summary(r)}
            for n, r in rows.items()
        },
    }
    card = ds.data_card(manifest)
    assert f"| {len(rows['train'])} |" in card and "not the live record" in card


def test_committed_splits_match_the_manifest_and_do_not_leak() -> None:
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "lab" / "data" / "forecast-sft"
    if not (root / "manifest.json").is_file():
        pytest.skip("lab data not committed in this checkout")
    manifest = json.loads((root / "manifest.json").read_text())
    rows = {}
    for name, info in manifest["splits"].items():
        assert ds.plain_sha256(root / f"{name}.jsonl.gz") == info["sha256"], name
        rows[name] = ds.read_split(root / f"{name}.jsonl.gz")
        assert len(rows[name]) == info["rows"]
    ds.assert_no_overlap(rows)
    assert max(r.batch_date for r in rows["train"]) <= ds.SPLITS["train"][1].isoformat()
    assert min(r.batch_date for r in rows["test_nov"]) >= ds.SPLITS["test_nov"][0].isoformat()
