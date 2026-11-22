"""CLI commands of the experiments lab that run offline on the committed files (T254, T246b)."""

import json
from pathlib import Path

from click.testing import CliRunner

from arena.cli import main


def run(*args: str, cwd: Path | None = None):
    return CliRunner().invoke(main, list(args), catch_exceptions=False)


def test_ask_answers_with_a_citation_and_refuses_out_of_scope(tmp_path: Path) -> None:
    ok = run("--ledger-dir", str(tmp_path), "lab", "ask", "At what time is the daily lock?")
    assert ok.exit_code == 0 and "docs/" in ok.output and "[" in ok.output
    no = run("--ledger-dir", str(tmp_path), "lab", "ask", "How do I bake sourdough bread?")
    assert no.exit_code == 0 and "Not in the documents" in no.output


def test_docs_eval_writes_a_valid_result_file(tmp_path: Path) -> None:
    out = tmp_path / "lab-docs.json"
    res = run("--ledger-dir", str(tmp_path), "lab", "docs-eval", "--out", str(out))
    assert res.exit_code == 0
    data = json.loads(out.read_text())
    assert data["kind"] == "evaluation" and data["metrics"]["docs_assistant"]["answerable"] >= 20


def test_ft_calibrate_merges_shards_and_fits_platt_on_validation_only(tmp_path: Path) -> None:
    """Synthetic margins for every committed validation and test row; two shards."""
    from arena.lab import dataset as ds
    from arena.lab import ft_gguf as fg

    rows = [
        r
        for name in fg.SPLITS
        for r in ds.read_split(Path("lab/data/forecast-sft") / f"{name}.jsonl.gz")
    ]
    margins = {r.id: (0.5 if r.outcome else -0.5) for r in rows}
    parts = []
    for i in range(2):
        p = tmp_path / f"m{i}.json"
        p.write_text(
            json.dumps(
                fg.shard(sorted(margins.items()), i, 2)
                and dict(fg.shard(sorted(margins.items()), i, 2))
            )
        )
        parts.append(str(p))
    out = tmp_path / "all.json"
    res = run("--ledger-dir", str(tmp_path), "lab", "ft-calibrate", *parts, "--out", str(out))
    assert res.exit_code == 0
    line = next(x for x in res.output.splitlines() if x.startswith("FT_CALIBRATION_JSON="))
    cal = json.loads(line.split("=", 1)[1])
    assert set(cal["splits"]) == {"val", "test_oct", "test_nov"} and cal["platt_new"][0] > 0
    assert len(json.loads(out.read_text())) == len(rows)
