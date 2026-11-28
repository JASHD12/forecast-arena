"""Fine-tuning experiments of the lab (SPEC 17): parity, evaluation, scoring, lineage."""

from __future__ import annotations

import json
from pathlib import Path

import click

from arena.cli import Ctx, lab


def _ft_rows() -> list[object]:
    from arena.lab import dataset as ds
    from arena.lab import ft_gguf as fg

    return [
        r
        for name in fg.SPLITS
        for r in ds.read_split(Path("lab/data/forecast-sft") / f"{name}.jsonl.gz")
    ]


@lab.command("ft-parity")
@click.argument("gguf", type=click.Path(exists=True, path_type=Path))
@click.argument("scores", type=click.Path(exists=True, path_type=Path))
@click.option("--every", type=int, default=9, show_default=True, help="Score every n-th test row.")
@click.option("--out", type=click.Path(path_type=Path), default=Path("/tmp/ft-parity.json"))
def lab_ft_parity(gguf: Path, scores: Path, every: int, out: Path) -> None:
    """Score a subset of the frozen test rows with the GGUF and compare with the Colab scores."""
    import time

    from arena.lab import dataset as ds
    from arena.lab.artefacts import load_artefact
    from arena.lab.ft_parity import colab_margins, compare
    from arena.lab.ft_runtime import LlamaScorer

    art = load_artefact()
    if art is None:
        raise click.ClickException("lab/artefacts/llm_local_ft.json is missing")
    rows = [
        r
        for name in ("test_oct", "test_nov")
        for r in ds.read_split(Path("lab/data/forecast-sft") / f"{name}.jsonl.gz")
    ][:: max(1, every)]
    scorer = LlamaScorer(
        gguf, model=art.name, yes_id=art.yes_id, no_id=art.no_id, run_budget=3 * 3600.0
    )
    margins: dict[str, float] = {}
    start = time.monotonic()
    for i, r in enumerate(rows, 1):
        margins[r.id] = scorer.margin(r.system, r.user)
        click.echo(
            f"{i}/{len(rows)} {r.id} margin {margins[r.id]:.3f} ({time.monotonic() - start:.0f}s)"
        )
    res = compare(margins, colab_margins(scores), art.platt)
    res["seconds_per_question"] = round((time.monotonic() - start) / len(rows), 1)
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    click.echo(json.dumps(res, indent=1))


@lab.command("lineage")
@click.argument("summary", type=click.Path(exists=True, path_type=Path))
@click.option("--out", type=click.Path(path_type=Path), default=Path("docs/lab/runs/qlora-r1.json"))
def lab_lineage(summary: Path, out: Path) -> None:
    """Write the lineage record of the pinned fine-tuned model from the Colab run summary (T248)."""
    from arena.lab import lineage
    from arena.lab.artefacts import load_artefact

    art = load_artefact()
    if art is None:
        raise click.ClickException("lab/artefacts/llm_local_ft.json is missing")
    calibrations = [
        {
            "when": "2026-11-22",
            "fitted_on": "validation margins of the Colab 4-bit model plus adapter (552 rows)",
            "platt": [2.605708652161696, 0.5474124423307355],
            "source": "Colab run_summary.json",
        },
        {
            "when": "2026-11-22",
            "fitted_on": "validation margins of the GGUF itself (552 rows, CPU, 4 shards)",
            "platt": [0.5902640387475047, 0.17304395312180548],
            "source": "lab-eval run 45011720244, arena lab ft-calibrate",
        },
    ]
    record = lineage.build(
        art,
        json.loads(summary.read_text(encoding="utf-8")),
        calibrations,
        "evals/results/lab-qlora-r1.json",
    )
    lineage.write(record, out)
    click.echo(f"lineage -> {out}")


@lab.command("ft-eval")
@click.argument("scores", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--ml-run", "ml_runs", multiple=True, type=click.Path(exists=True, path_type=Path))
@click.option("--parity", type=click.Path(exists=True, path_type=Path), default=None)
@click.option(
    "--experiment", type=click.Choice(["qlora-r1", "dpo-r1", "distill-r1"]), default="qlora-r1"
)
@click.option(
    "--summary", "summary_path", type=click.Path(exists=True, path_type=Path), default=None
)
@click.option(
    "--teacher",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="RT_PROBS list: the teacher's probabilities on the 276 test questions (distill-r1).",
)
@click.option(
    "--out", type=click.Path(path_type=Path), default=Path("evals/results/lab-qlora-r1.json")
)
@click.pass_obj
def lab_ft_eval(
    obj: Ctx,
    scores: tuple[Path, ...],
    ml_runs: tuple[Path, ...],
    parity: Path | None,
    experiment: str,
    summary_path: Path | None,
    teacher: Path | None,
    out: Path,
) -> None:
    """Evaluate a Colab run (QLoRA, or DPO / distillation with --experiment) on the frozen test sets
    from its score files (T246)."""
    import hashlib

    from arena.lab import dataset as ds
    from arena.lab import ft_eval as fe
    from arena.lab.artefacts import load_artefact
    from arena.lab.results import LabResult

    art = load_artefact()
    if art is None:
        raise click.ClickException("lab/artefacts/llm_local_ft.json is missing")
    data = Path("lab/data/forecast-sft")
    rows = {
        r.id: {
            "split": name,
            "batch_date": r.batch_date,
            "base_rate": r.base_rate,
            "outcome": r.outcome,
        }
        for name in fe.SPLITS
        for r in ds.read_split(data / f"{name}.jsonl.gz")
    }
    ml: dict[str, float] = {}
    for run in ml_runs:
        ml.update(fe.read_backtest(run))
    dpo = experiment == "dpo-r1"
    distill = experiment == "distill-r1"
    pairs = (
        [
            ("distill_1_5b", "base_1_5b"),
            ("distill_1_5b", "qlora_1_5b"),
            ("distill_1_5b", "claude_teacher"),
            ("distill_1_5b", "base_rate"),
            ("distill_1_5b", "ml"),
            ("claude_teacher", "base_rate"),
            ("claude_teacher", "ml"),
            ("qlora_1_5b", "base_rate"),
            ("ml", "base_rate"),
        ]
        if distill
        else [
            ("dpo_1_5b", "base_1_5b"),
            ("dpo_1_5b", "qlora_1_5b"),
            ("dpo_1_5b", "base_rate"),
            ("dpo_1_5b", "ml"),
            ("qlora_1_5b", "base_rate"),
            ("ml", "base_rate"),
        ]
        if dpo
        else [
            ("qlora_1_5b", "base_1_5b"),
            ("qlora_1_5b", "base_rate"),
            ("qlora_1_5b", "ml"),
            ("lora_0_5b", "base_0_5b"),
            ("lora_0_5b", "base_rate"),
            ("lora_0_5b", "qlora_1_5b"),
            ("ml", "base_rate"),
            ("gguf_q4", "qlora_1_5b"),
            ("gguf_q4", "base_1_5b"),
            ("gguf_q4", "base_rate"),
            ("gguf_q4", "ml"),
        ]
    )
    all_scores = fe.read_scores(list(scores))
    teacher_note = None
    if distill and teacher is not None:
        from arena.cli.lab_paid_cmds import GOLDEN_SETS
        from arena.evals.golden import load as load_golden

        gids = sorted(
            it.question.question_id for path in GOLDEN_SETS for it in load_golden(Path(path))[0]
        )
        tp = dict(zip(gids, json.loads(teacher.read_text(encoding="utf-8")), strict=True))
        all_scores["claude_teacher"] = {
            i: {"id": i, "p": float(p), "margin": None, "outcome": rows[i]["outcome"],
                "split": rows[i]["split"]}
            for i, p in tp.items() if p is not None and i in rows
        }  # fmt: skip

        def gap(arm: str) -> float:
            common = [i for i in all_scores["claude_teacher"] if i in all_scores[arm]]
            return sum(
                abs(all_scores[arm][i]["p"] - all_scores["claude_teacher"][i]["p"]) for i in common
            ) / len(common)

        teacher_note = (
            "Mean absolute difference of probabilities to the teacher (Claude `llm_context`, the "
            f"routing-study answers): student {gap('distill_1_5b'):.4f}, hard-label QLoRA "
            f"{gap('qlora_1_5b'):.4f}, untuned {gap('base_1_5b'):.4f} "
            f"(over {len(all_scores['claude_teacher'])} test questions)."
        )
    metrics, paired = fe.evaluate(all_scores, rows, ml, pairs)
    notes = [
        (
            "All probabilities are the Colab scores (4-bit model plus adapter, Platt map fitted "
            "on the validation split only). The student was trained on Claude's probabilities "
            "for 1,198 training-split questions (soft labels); no GGUF was exported and it is "
            "not a live forecaster. The `claude_teacher` arm is Claude Haiku with the live "
            "prompt on the same test questions (routing study)."
        )
        if distill
        else (
            "All probabilities are the Colab scores (4-bit model plus adapter, Platt map fitted "
            "on the validation split only). No GGUF was exported for this run (the optional "
            "export cell failed on a notebook bug, fixed since), so hypothesis H-DPO3 (export "
            "loss) is not tested, and the DPO model is not a live forecaster."
        )
        if dpo
        else (
            "Probabilities of the Colab arms are the Colab scores (4-bit model plus adapter, "
            "Platt map fitted on the validation split only). The arm `gguf_q4` is the live "
            "model: the Q4_K_M GGUF scored by llama.cpp on CPU, with its own Platt map fitted "
            "on the GGUF's validation margins only."
        ),
        f"Test sets: {sum(1 for r in rows.values() if r['split'] == 'test_oct')} questions "
        f"(October 2026) and {sum(1 for r in rows.values() if r['split'] == 'test_nov')} "
        "(1 to 15 November 2026); the six questions of a day are correlated, so intervals are "
        "day-block bootstrap intervals.",
    ]
    if teacher_note:
        notes.append(teacher_note)
    if ml:
        notes.append(f"The `ml` champion covers {len(ml)} of these questions (backtest rows).")
    if parity is not None:
        par = json.loads(parity.read_text(encoding="utf-8"))
        notes.append(
            f"GGUF parity on {par['n']} test rows: mean absolute margin difference "
            f"{par['margin_mean_abs_diff']}, Brier {par['brier_gguf']} (GGUF) against "
            f"{par['brier_colab']} (Colab), loss {par['brier_loss']:+}; "
            f"{par['seconds_per_question']} s per question on CPU."
        )
    summary_file = summary_path or Path(scores[0]).parent / "run_summary.json"
    summary = json.loads(summary_file.read_text("utf-8"))
    sums = (
        json.loads((summary_file.parent / "SHA256SUMS.json").read_text("utf-8"))
        if dpo or distill
        else {}
    )
    artefacts = (
        {
            "adapter": sums["adapter_distill_1_5b/adapter_model.safetensors"],
            "labels": summary["labels_sha256"],
            "release": "https://github.com/JASHD12/forecast-arena/releases/tag/lab-distill-r1",
        }
        if distill
        else {
            "adapter": sums["adapter_dpo_1_5b/adapter_model.safetensors"],
            "release": "https://github.com/JASHD12/forecast-arena/releases/tag/lab-dpo-r1",
        }
        if dpo
        else {"gguf": art.sha256, "adapter": art.adapter_sha256, "release": art.url}
    )
    prereg = (
        "lab/prereg/distill.md"
        if distill
        else "lab/prereg/dpo-forecast.md"
        if dpo
        else "lab/prereg/qlora-forecast.md"
    )
    result = LabResult(
        experiment=experiment,
        title=(
            "Distillation from Claude into Qwen2.5-1.5B (soft-label QLoRA)"
            if distill
            else "DPO preference tuning of Qwen2.5-1.5B on replayed power questions"
            if dpo
            else "QLoRA fine-tune of Qwen2.5-1.5B on replayed power questions"
        ),
        created_at=obj.clock.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        why=(
            "Distilling a large model's probabilities into a small one is the standard way to cut "
            "inference cost; the comparison with the teacher and a classical model shows what is "
            "kept."
            if distill
            else "Preference tuning (DPO) is the standard follow-up to supervised fine-tuning for "
            "aligning a model with outcomes; comparing it with plain fine-tuning and a classical "
            "model shows what the extra step buys."
            if dpo
            else "Parameter-efficient fine-tuning of a small open model is the standard way "
            "companies adapt an LLM to a narrow task; the comparison with a classical model is "
            "the point."
        ),
        prereg_sha256=hashlib.sha256(Path(prereg).read_bytes()).hexdigest(),
        dataset_sha256={k: v for k, v in summary["dataset_sha256"].items()},
        artefacts=artefacts,
        metrics=metrics,  # type: ignore[arg-type]
        paired=paired,
        notes=notes,
        limits=[
            "Electricity only; 276 test questions from about 45 days; intervals are wide.",
            "One training run, one seed: a different seed could change the ranking of the two "
            "tuned models.",
            "Colab ran transformers "
            f"{summary['packages'].get('transformers')}, not the pinned version.",
            "The untuned arms use their own Platt map fitted on validation, so they are not raw "
            "model probabilities.",
        ],
        card=f"docs/lab/{experiment}.md",
        cost_usd=0.0,
    )
    out.write_text(result.model_dump_json(indent=1) + "\n", encoding="utf-8")
    for k, m in metrics.items():
        click.echo(f"{k}: {m}")
    for p in paired:
        click.echo(p)


@lab.command("ft-score")
@click.option("--shard", "index", type=int, required=True)
@click.option("--of", "count", type=int, required=True)
@click.option("--cache", type=click.Path(path_type=Path), default=Path("models_cache/ft"))
@click.option("--out", type=click.Path(path_type=Path), required=True)
@click.pass_obj
def lab_ft_score(obj: Ctx, index: int, count: int, cache: Path, out: Path) -> None:
    """Score one shard of the validation and test rows with the pinned GGUF (CPU)."""
    import time

    from arena.lab import ft_gguf as fg
    from arena.lab.artefacts import fetch, load_artefact
    from arena.lab.ft_runtime import LlamaScorer

    art = load_artefact()
    if art is None:
        raise click.ClickException("lab/artefacts/llm_local_ft.json is missing")
    path = fetch(art, cache, obj.settings.user_agent())
    rows = fg.shard(_ft_rows(), index, count)
    scorer = LlamaScorer(
        path, model=art.name, yes_id=art.yes_id, no_id=art.no_id, run_budget=6 * 3600.0
    )
    margins: dict[str, float] = {}
    start = time.monotonic()
    for i, r in enumerate(rows, 1):
        margins[r.id] = scorer.margin(r.system, r.user)
        if i % 10 == 0 or i == len(rows):
            click.echo(f"shard {index}: {i}/{len(rows)} rows, {time.monotonic() - start:.0f}s")
    out.write_text(json.dumps(margins, sort_keys=True), encoding="utf-8")
    click.echo(f"shard {index}: wrote {len(margins)} margins to {out}")
    click.echo(
        f"FT_MARGINS_SHARD_{index}="
        + json.dumps({k: round(v, 4) for k, v in sorted(margins.items())})
    )


@lab.command("ft-calibrate")
@click.argument("parts", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--out", type=click.Path(path_type=Path), default=Path("ft-gguf-margins.json"))
def lab_ft_calibrate(parts: tuple[Path, ...], out: Path) -> None:
    """Merge shard margins, refit Platt on validation only, print the comparison (L3)."""
    from arena.lab import ft_gguf as fg
    from arena.lab.artefacts import load_artefact

    art = load_artefact()
    if art is None:
        raise click.ClickException("lab/artefacts/llm_local_ft.json is missing")
    margins = fg.merge([json.loads(p.read_text(encoding="utf-8")) for p in parts])
    rows = {r.id: {"split": r.split, "outcome": r.outcome} for r in _ft_rows()}  # type: ignore[attr-defined]
    res = fg.calibrate(margins, rows, art.platt)
    out.write_text(json.dumps(margins, sort_keys=True), encoding="utf-8")
    click.echo("FT_CALIBRATION_JSON=" + json.dumps(res))
    click.echo(
        "FT_MARGINS_JSON=" + json.dumps({k: round(v, 4) for k, v in sorted(margins.items())})
    )
