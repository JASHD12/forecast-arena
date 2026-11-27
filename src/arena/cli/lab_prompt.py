"""Prompt-optimisation commands of the lab (SPEC 17)."""

from __future__ import annotations

import json
from pathlib import Path

import click

from arena.cli import Ctx, lab
from arena.lab.dataset import Row


def _po_data() -> tuple[list[Row], list[Row], list[Row]]:
    """(train rows, validation rows, test rows sorted by id) of the frozen splits."""
    from arena.lab import dataset as ds

    base = Path("lab/data/forecast-sft")
    train = ds.read_split(base / "train.jsonl.gz")
    val = ds.read_split(base / "val.jsonl.gz")
    test = sorted(
        [r for n in ("test_oct", "test_nov") for r in ds.read_split(base / f"{n}.jsonl.gz")],
        key=lambda r: r.id,
    )
    return list(train), list(val), list(test)


@lab.command("prompt-score")
@click.option("--phase", type=click.Choice(["search", "final"]), required=True)
@click.option("--shard", "index", type=int, required=True)
@click.option("--of", "count", type=int, required=True)
@click.option("--winner", default=None, help="Candidate id, final phase only.")
@click.option("--cache", type=click.Path(path_type=Path), default=Path("models_cache/po"))
@click.pass_obj
def lab_prompt_score(
    obj: Ctx, phase: str, index: int, count: int, winner: str | None, cache: Path
) -> None:
    """Score one shard of the prompt-optimisation work list with the free local GGUF (T297)."""
    import time

    from arena.lab import ft_gguf as fg
    from arena.lab import prompt_opt as po
    from arena.lab.artefacts import load_artefact
    from arena.lab.ft_runtime import LlamaScorer
    from arena.llm.local import model_path

    art = load_artefact()
    if art is None:
        raise click.ClickException("lab/artefacts/llm_local_ft.json is missing (token ids)")
    train, val, test = _po_data()
    by_id = {c.id: c for c in po.candidates()}
    if phase == "search":
        rows = po.search_rows(val)
        cands = list(by_id.values())
    else:
        if winner not in by_id:
            raise click.ClickException("--winner must be a candidate id such as i2s4")
        rows = test
        cands = [po.BASELINE] + ([by_id[winner]] if winner != po.BASELINE.id else [])
    items = [(c, i) for c in cands for i in range(len(rows))]
    mine = fg.shard(items, index, count)
    scorer = LlamaScorer(
        model_path(cache),
        model="qwen2.5-1.5b-instruct-q4_k_m",
        yes_id=art.yes_id,
        no_id=art.no_id,
        run_budget=5.5 * 3600.0,
    )
    shots = {c.id: po.pick_shots(train, c.shots) for c in cands}
    margins: dict[str, float] = {}
    start = time.monotonic()
    for n, (c, i) in enumerate(mine, 1):
        margins[f"{c.id}:{i}"] = round(scorer.margin(*po.render(rows[i], c, shots[c.id])), 2)
        if n % 10 == 0 or n == len(mine):
            click.echo(
                f"{phase} shard {index}: {n}/{len(mine)} items, {time.monotonic() - start:.0f}s"
            )
    click.echo(f"PO_{phase.upper()}_SHARD_{index}=" + json.dumps(margins, sort_keys=True))


@lab.command("prompt-search")
@click.argument("parts", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
def lab_prompt_search(parts: tuple[Path, ...]) -> None:
    """Merge search shards, cross-fitted Brier per candidate, print the winner (T297)."""
    from arena.lab import ft_gguf as fg
    from arena.lab import prompt_opt as po

    _, val, _ = _po_data()
    rows = po.search_rows(val)
    y = [int(r.outcome) for r in rows]
    margins = fg.merge([json.loads(p.read_text(encoding="utf-8")) for p in parts])
    scores: dict[str, float] = {}
    for c in po.candidates():
        ms = [margins[f"{c.id}:{i}"] for i in range(len(rows))]
        scores[c.id] = round(po.cross_fitted_brier(ms, y), 4)
    best = po.choose(scores)
    click.echo("PO_SEARCH_JSON=" + json.dumps({"scores": scores, "winner": best}))


@lab.command("prompt-final")
@click.argument("parts", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.option(
    "--search",
    "search_parts",
    multiple=True,
    required=True,
    type=click.Path(exists=True, path_type=Path),
)
@click.option("--winner", required=True)
@click.option("--ml-run", "ml_runs", multiple=True, type=click.Path(exists=True, path_type=Path))
@click.option(
    "--out", type=click.Path(path_type=Path), default=Path("evals/results/lab-prompt-opt.json")
)
@click.pass_obj
def lab_prompt_final(
    obj: Ctx,
    parts: tuple[Path, ...],
    search_parts: tuple[Path, ...],
    winner: str,
    ml_runs: tuple[Path, ...],
    out: Path,
) -> None:
    """Evaluate the baseline and the winning prompt on the frozen test sets (T297)."""
    import hashlib

    from arena.lab import ft_eval as fe
    from arena.lab import ft_gguf as fg
    from arena.lab import prompt_opt as po
    from arena.lab.results import LabResult

    _, val, test = _po_data()
    vrows = po.search_rows(val)
    vy = [int(r.outcome) for r in vrows]
    smargins = fg.merge([json.loads(p.read_text(encoding="utf-8")) for p in search_parts])
    fmargins = fg.merge([json.loads(p.read_text(encoding="utf-8")) for p in parts])
    arms = {"baseline": po.BASELINE.id, "winner": winner}
    scores: dict[str, dict[str, dict[str, object]]] = {}
    platts: dict[str, tuple[float, float]] = {}
    for arm, cid in arms.items():
        platts[arm] = po.fit_platt([smargins[f"{cid}:{i}"] for i in range(len(vrows))], vy)
        scores[arm] = {
            r.id: {"p": po.apply_platt(fmargins[f"{cid}:{i}"], platts[arm])}
            for i, r in enumerate(test)
        }
    rows = {
        r.id: {
            "split": r.split,
            "batch_date": r.batch_date,
            "base_rate": r.base_rate,
            "outcome": r.outcome,
        }
        for r in test
    }
    ml: dict[str, float] = {}
    for run in ml_runs:
        ml.update(fe.read_backtest(run))
    pairs = [("winner", "baseline"), ("winner", "base_rate")] + ([("winner", "ml")] if ml else [])
    metrics, paired = fe.evaluate(scores, rows, ml, pairs)
    log = {
        c.id: round(
            po.cross_fitted_brier([smargins[f"{c.id}:{i}"] for i in range(len(vrows))], vy), 4
        )
        for c in po.candidates()
    }
    notes = [
        f"Winner of the search: {winner} (baseline {po.BASELINE.id}). Search log, cross-fitted "
        "Brier on the 48 validation questions per candidate (i = instruction variant, s = "
        "solved examples): " + ", ".join(f"{k} {v}" for k, v in log.items()) + ".",
        "Platt maps are fitted on the 48 validation margins of each prompt; the test sets are "
        "scored once.",
    ]
    result = LabResult(
        experiment="prompt-opt",
        title="Offline prompt optimisation for the free local model",
        created_at=obj.clock.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        why=(
            "Prompt engineering evaluated against a baseline on a time-split set is the standard "
            "way to improve an LLM feature without training."
        ),
        prereg_sha256=hashlib.sha256(Path("lab/prereg/prompt-opt.md").read_bytes()).hexdigest(),
        metrics=metrics,  # type: ignore[arg-type]
        paired=paired,
        notes=notes,
        limits=[
            "Electricity only; 276 test questions from 46 days; intervals are wide.",
            "Eight candidates only, searched on 48 validation questions: a small search.",
            "One model (Qwen2.5-1.5B-Instruct Q4_K_M); the result does not transfer to Claude.",
        ],
        card="docs/lab/prompt-opt.md",
    )
    out.write_text(result.model_dump_json(indent=1) + "\n", encoding="utf-8")
    for k, m in metrics.items():
        click.echo(f"{k}: {m}")
    for p in paired:
        click.echo(p)
