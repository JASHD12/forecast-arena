"""Commands of the small paid lab runs: LLM judge, routing study, distillation labels.

Owner approval of 2026-11-22 (HUMAN_TODO H27, H31, H36). Every command that calls the model is
refused outside GitHub Actions (S8), runs under hard caps for that run, prints one compact result
line the agent reads back from the job log, and writes nothing to the ledger.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import click

from arena.cli import Ctx, lab

JUDGE_DIR = Path("lab/judge")
DISTILL_N = 1200
DISTILL_PATH = Path("lab/data/distill-labels-v1.json")
FT_MARGINS = Path("lab/artefacts/llm_local_ft.margins.json")


def _refuse_outside_actions() -> None:
    from arena.lab.paid import in_actions

    if not in_actions():
        click.echo(
            "refused: live LLM calls run only inside GitHub Actions (AGENTS.md S8)", err=True
        )
        sys.exit(2)


def _client(obj: Ctx) -> Any:
    from arena.llm.factory import client_from_settings

    client = client_from_settings(obj.settings)
    if client is None:
        click.echo("model_missing: no LLM configured", err=True)
        sys.exit(1)
    return client


# ---- LLM judge (T252b) --------------------------------------------------------------------------


@lab.command("judge-sheet")
@click.option("--out-dir", type=click.Path(path_type=Path), default=JUDGE_DIR)
@click.pass_obj
def lab_judge_sheet(obj: Ctx, out_dir: Path) -> None:
    """Freeze the 100 rationales the judge grades and the 30 the owner labels (T252b, H29)."""
    from arena.lab import judge as jg
    from arena.ledger import layout
    from arena.scoring.core import load

    rec = load(obj.ledger)
    snaps: dict[tuple[str, object], dict[str, Any]] = {}
    cands: list[dict[str, Any]] = []
    for f in rec.forecasts:
        q = rec.questions.get(f.question_id)
        if q is None or not f.rationale:
            continue
        key = (q.domain, q.batch_date)
        if key not in snaps:
            rel = f"{layout.snapshot_dir(q.domain, q.batch_date)}/morning_context.json.gz"
            snaps[key] = (
                json.loads(gzip.decompress(obj.ledger.read_bytes(rel)))
                if obj.ledger.exists(rel)
                else {}
            )
        ctx = snaps[key].get(q.question_id)
        if ctx is None:
            continue
        k = f"{f.forecaster_id}|{f.question_id}"
        cands.append(
            {
                "key": k,
                "id": jg.item_id(k),
                "forecaster_id": f.forecaster_id,
                "question": q.text,
                "rule": q.resolution_rule,
                "context": json.dumps(ctx, sort_keys=True, separators=(",", ":"))[
                    : jg.CONTEXT_CHARS
                ],
                "probability": round(float(f.probability), 4),
                "rationale": f.rationale,
            }
        )
    items = jg.select_items(cands)
    labels = jg.label_subset(items)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "items.json").write_text(
        json.dumps(items, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    with (out_dir / "label-sheet.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "id",
                "question",
                "resolution_rule",
                "data_excerpt",
                "probability_yes",
                "rationale",
                *jg.DIMENSIONS,
            ]
        )
        for it in labels:
            w.writerow(
                [
                    it["id"],
                    it["question"],
                    it["rule"],
                    it["context"][:700],
                    it["probability"],
                    it["rationale"],
                    "",
                    "",
                    "",
                ]
            )
    click.echo(f"{len(items)} items for the judge, {len(labels)} for the owner -> {out_dir}")


@lab.command("judge-run")
@click.option(
    "--items",
    "items_path",
    type=click.Path(exists=True, path_type=Path),
    default=JUDGE_DIR / "items.json",
)
@click.option("--max-tokens", type=int, default=400_000, help="Hard token cap for this run.")
@click.option("--model", default="", help="Judge model id instead of the configured one (T328).")
@click.option(
    "--labels-only", is_flag=True, help="Grade only the 30 items the owner labels (T328)."
)
@click.pass_obj
def lab_judge_run(
    obj: Ctx, items_path: Path, max_tokens: int, model: str, labels_only: bool
) -> None:
    """Grade the frozen rationales with the judge model (Actions only; capped; T252b)."""
    from arena.lab import judge as jg
    from arena.lab.paid import PaidRun
    from arena.llm.budget import BudgetExhausted
    from arena.llm.client import LLMError
    from arena.llm.factory import client_from_settings

    _refuse_outside_actions()
    items = json.loads(items_path.read_text(encoding="utf-8"))
    if labels_only:
        items = jg.label_subset(items)
    if model:
        client = client_from_settings(obj.settings.model_copy(update={"llm_model": model}))
        if client is None:
            click.echo("model_missing: no LLM configured", err=True)
            sys.exit(1)
    else:
        client = _client(obj)
    run = PaidRun(
        client, max_requests=len(items) + 5, max_tokens=max_tokens, max_output_tokens=1000
    )
    scores: dict[str, list[int] | None] = {}
    skips: dict[str, int] = {}
    for it in items:
        try:
            j = jg.parse_judgement(run.ask(jg.RUBRIC, jg.user_prompt(it)).text)
            scores[it["id"]] = [j[d] for d in jg.DIMENSIONS]
        except (jg.JudgeError, LLMError, BudgetExhausted) as exc:
            scores[it["id"]] = None
            skips[type(exc).__name__] = skips.get(type(exc).__name__, 0) + 1
    click.echo("JG_SUMMARY=" + json.dumps({**run.summary(), "skips": skips}, sort_keys=True))
    click.echo("JG_SCORES=" + json.dumps(scores, sort_keys=True))


@lab.command("judge-compare")
@click.argument("scores_a", type=click.Path(exists=True, path_type=Path))
@click.argument("scores_b", type=click.Path(exists=True, path_type=Path))
@click.option("--name-a", default="judge A")
@click.option("--name-b", default="judge B")
@click.option("--cost", type=float, default=0.0, help="US$ of the second judge run (JG_SUMMARY).")
@click.option("--experiment", default="judge-llm", help="Result id; the card is docs/lab/<id>.md.")
@click.option("--title", default="Two LLM judges compared (not human calibration)")
@click.option("--limit", "extra_limits", multiple=True, help="An extra limit to print on the card.")
@click.option(
    "--out", type=click.Path(path_type=Path), default=Path("evals/results/lab-judge-llm.json")
)
@click.pass_obj
def lab_judge_compare(
    obj: Ctx,
    scores_a: Path,
    scores_b: Path,
    name_a: str,
    name_b: str,
    cost: float,
    experiment: str,
    title: str,
    extra_limits: tuple[str, ...],
    out: Path,
) -> None:
    """Agreement between two LLM judges on the items both graded. Not human calibration (T328)."""
    from arena.lab import judge as jg
    from arena.lab.results import LabResult

    a = json.loads(scores_a.read_text(encoding="utf-8"))
    b = json.loads(scores_b.read_text(encoding="utf-8"))
    both = sorted(i for i in a if a[i] is not None and b.get(i) is not None)
    metrics: dict[str, dict[str, float | int | str | None]] = {}
    for k, d in enumerate(jg.DIMENSIONS):
        kappa = jg.weighted_kappa([a[i][k] for i in both], [b[i][k] for i in both])
        exact = sum(a[i][k] == b[i][k] for i in both) / len(both) if both else None
        metrics[f"agreement / {d}"] = {
            "n": len(both),
            "weighted_kappa": None if kappa is None else round(kappa, 3),
            "exact_match_pct": None if exact is None else round(100 * exact, 1),
        }
    result = LabResult(
        experiment=experiment,
        title=title,
        created_at=obj.clock.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        why="Checking a judge against a second, independent model is a cheap sanity check "
        "before (and never instead of) calibrating it against human labels.",
        metrics=metrics,
        cost_usd=cost,
        notes=[
            f"{name_a} against {name_b} on {len(both)} rationales both graded.",
            "Both are language models; this is not agreement with a human.",
        ],
        limits=[
            "Two models can share biases, so agreement does not show either is right.",
            "Only the items both judges graded are compared; the sample is small.",
            *extra_limits,
        ],
        card=f"docs/lab/{experiment}.md",
    )
    out.write_text(result.model_dump_json(indent=1) + "\n", encoding="utf-8")
    for name, value in metrics.items():
        click.echo(f"{name}: {value}")


@lab.command("judge-eval")
@click.argument("scores", type=click.Path(exists=True, path_type=Path))
@click.option("--labels", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--cost", type=float, default=0.0, help="US$ of the judge run (JG_SUMMARY).")
@click.option(
    "--items",
    "items_path",
    type=click.Path(exists=True, path_type=Path),
    default=JUDGE_DIR / "items.json",
)
@click.option(
    "--out", type=click.Path(path_type=Path), default=Path("evals/results/lab-judge.json")
)
@click.pass_obj
def lab_judge_eval(
    obj: Ctx, scores: Path, labels: Path | None, cost: float, items_path: Path, out: Path
) -> None:
    """Judge scores per forecaster and, with the owner's labels, the agreement (T252b)."""
    from arena.lab import judge as jg
    from arena.lab.results import LabResult

    items = {i["id"]: i for i in json.loads(items_path.read_text(encoding="utf-8"))}
    sc = json.loads(scores.read_text(encoding="utf-8"))
    metrics: dict[str, dict[str, float | int | str | None]] = {}
    by_f: dict[str, list[list[int]]] = {}
    for iid, v in sc.items():
        if v is not None:
            by_f.setdefault(items[iid]["forecaster_id"], []).append(v)
    for f, rows in sorted(by_f.items()):
        metrics[f"judge / {f}"] = {
            "n": len(rows),
            **{
                d: round(sum(r[k] for r in rows) / len(rows), 2)
                for k, d in enumerate(jg.DIMENSIONS)
            },
        }
    notes = [f"{sum(v is not None for v in sc.values())} of {len(sc)} rationales were graded."]
    if labels is not None:
        human: dict[str, list[int]] = {}
        with labels.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                try:
                    human[row["id"]] = [int(row[d]) for d in jg.DIMENSIONS]
                except (KeyError, ValueError):
                    continue
        both = [i for i in human if sc.get(i) is not None]
        for k, d in enumerate(jg.DIMENSIONS):
            kappa = jg.weighted_kappa([sc[i][k] for i in both], [human[i][k] for i in both])
            metrics[f"agreement / {d}"] = {
                "n": len(both),
                "weighted_kappa": None if kappa is None else round(kappa, 3),
            }
        notes.append(f"Owner labels used: {len(both)} of {len(human)} rows.")
    result = LabResult(
        experiment="judge",
        title="LLM-as-judge for stored rationales",
        created_at=obj.clock.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        why=(
            "A rubric-based LLM grader, calibrated against a small human-labelled set, is the "
            "standard way teams evaluate open-ended LLM output at scale."
        ),
        metrics=metrics,
        cost_usd=cost,
        notes=notes,
        limits=[
            "The judge model is the same family as the forecasters it grades, so it may favour "
            "their style.",
            "At most 30 human labels: the agreement estimate is rough.",
            "It grades the stated reasoning, not whether the forecast turned out right.",
        ],
        card="docs/lab/judge.md",
    )
    out.write_text(result.model_dump_json(indent=1) + "\n", encoding="utf-8")
    for name, value in metrics.items():
        click.echo(f"{name}: {value}")


# ---- Routing study (T250) -----------------------------------------------------------------------

GOLDEN_SETS = ("evals/golden/power-2026-10.jsonl", "evals/golden/power-2026-11a.jsonl")


@lab.command("routing-score")
@click.option("--max-tokens", type=int, default=700_000, help="Hard token cap for this run.")
@click.pass_obj
def lab_routing_score(obj: Ctx, max_tokens: int) -> None:
    """`llm_context` probabilities on all 276 frozen test questions (Actions only; T250)."""
    from arena.evals.golden import load
    from arena.evals.run import EvalCaps, run

    _refuse_outside_actions()
    api = _client(obj)
    probs: dict[str, float | None] = {}
    cost_in = cost_out = 0
    costs: list[float | None] = []
    for path in GOLDEN_SETS:
        items, sha = load(Path(path))
        res = run(
            items,
            {"llm_context": api},
            obj.clock,
            golden=Path(path).name,
            golden_sha256=sha,
            caps=EvalCaps(
                max_requests=len(items) * 2 + 4,
                max_tokens=max_tokens,
                max_output_tokens=obj.settings.llm_max_output_tokens,
            ),
        )
        for r in res["rows"]:
            probs[r["question_id"]] = r["probability"]
        m = res["metrics"]["llm_context"]
        cost_in += m["input_tokens"]
        cost_out += m["output_tokens"]
        costs.append(m["cost_usd"])
    ids = sorted(probs)
    click.echo(
        "RT_SUMMARY="
        + json.dumps(
            {
                "n": len(ids),
                "answered": sum(probs[i] is not None for i in ids),
                "ids_sha256": hashlib.sha256("\n".join(ids).encode()).hexdigest(),
                "input_tokens": cost_in,
                "output_tokens": cost_out,
                "cost_usd": None if None in costs else round(sum(c for c in costs if c), 4),
            }
        )
    )
    rounded = [None if (p := probs[i]) is None else round(p, 3) for i in ids]
    click.echo("RT_PROBS=" + json.dumps(rounded))


@lab.command("routing")
@click.argument("probs", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--ml-run",
    "ml_runs",
    multiple=True,
    required=True,
    type=click.Path(exists=True, path_type=Path),
)
@click.option("--cost", type=float, default=0.0, help="US$ of the routing-score run.")
@click.option(
    "--out", type=click.Path(path_type=Path), default=Path("evals/results/lab-routing.json")
)
@click.pass_obj
def lab_routing(obj: Ctx, probs: Path, ml_runs: tuple[Path, ...], cost: float, out: Path) -> None:
    """Cost-quality study of a cascade over stored forecasts (offline; T250)."""
    from arena.evals.golden import load
    from arena.lab import dataset as ds
    from arena.lab import ft_eval as fe
    from arena.lab import routing as rt
    from arena.lab.finetune import train as tr
    from arena.lab.results import LabResult

    items: dict[str, Any] = {}
    for path in GOLDEN_SETS:
        for it in load(Path(path))[0]:
            items[it.question.question_id] = it
    ids = sorted(items)
    claude = dict(zip(ids, json.loads(probs.read_text(encoding="utf-8")), strict=True))
    ml: dict[str, float] = {}
    for run_dir in ml_runs:
        ml.update(fe.read_backtest(run_dir))
    pin = json.loads(Path("lab/artefacts/llm_local_ft.json").read_text(encoding="utf-8"))
    a, b = pin["platt"]
    margins = json.loads(FT_MARGINS.read_text(encoding="utf-8"))
    ft = {i: tr.apply_platt(margins[i], a, b) for i in ids if i in margins}
    base = {
        r.id: r.base_rate
        for n in fe.SPLITS
        for r in ds.read_split(Path("lab/data/forecast-sft") / f"{n}.jsonl.gz")
        if r.base_rate is not None
    }
    rows = [
        rt.Item(
            i,
            items[i].question.batch_date.isoformat(),
            int(items[i].outcome),
            ml[i],
            ft[i],
            claude[i],
            base[i],
        )
        for i in ids
        if i in ml and i in ft and i in base and claude.get(i) is not None
    ]
    res = rt.study(rows)
    metrics: dict[str, dict[str, float | int | str | None]] = {}
    for name, m in res["arms"].items():
        metrics[name] = m
    for row in res["curve"]:
        metrics[f"curve / {row['rule']} delta {row['delta']:.2f}"] = row
    result = LabResult(
        experiment="routing",
        title="Cost routing: a cheap pair first, the paid model only when they are unsure",
        created_at=obj.clock.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        why=(
            "Routing easy cases to cheap models and escalating the rest is the standard way to cut "
            "LLM cost without losing quality."
        ),
        prereg_sha256=hashlib.sha256(Path("lab/prereg/routing.md").read_bytes()).hexdigest(),
        metrics=metrics,
        paired=res["paired"],
        cost_usd=cost,
        notes=res["notes"],
        limits=[
            "Electricity only; the cheap pair is the `ml` backtest and the GGUF model, on 276 test "
            "questions from 46 days.",
            "The rule was fixed before the Claude answers existed; the grid is descriptive.",
            "The saving is counted in paid calls avoided on the shared sample, not measured live.",
        ],
        card="docs/lab/routing.md",
    )
    out.write_text(result.model_dump_json(indent=1) + "\n", encoding="utf-8")
    for k, m in metrics.items():
        if not k.startswith("curve"):
            click.echo(f"{k}: {m}")


# ---- Distillation labels (T247) -----------------------------------------------------------------


@lab.command("distill-labels")
@click.option("--n", "n_rows", type=int, default=DISTILL_N)
@click.option("--start", type=int, default=0, help="Skip the first rows of the (sorted) sample.")
@click.option("--max-tokens", type=int, default=3_600_000, help="Hard token cap for this run.")
@click.pass_obj
def lab_distill_labels(obj: Ctx, n_rows: int, start: int, max_tokens: int) -> None:
    """The teacher's probability for a seeded sample of training questions (Actions only; T247)."""
    from arena.lab import dataset as ds
    from arena.lab import distill as dl
    from arena.lab.paid import PaidRun
    from arena.llm.budget import BudgetExhausted
    from arena.llm.client import LLMError
    from arena.llm.parse import ParseError, parse_answer

    _refuse_outside_actions()
    train = ds.read_split(Path("lab/data/forecast-sft/train.jsonl.gz"))
    sample = dl.sample_rows(train, n_rows)
    rows = sample[start:]
    run = PaidRun(
        _client(obj),
        max_requests=len(rows) + 100,
        max_tokens=max_tokens,
        max_output_tokens=obj.settings.llm_max_output_tokens,
    )
    probs: list[float | None] = []
    skips: dict[str, int] = {}
    for r in rows:
        try:
            probs.append(round(parse_answer(run.ask(r.system, r.user).text).probability, 3))
        except (ParseError, LLMError, BudgetExhausted) as exc:
            probs.append(None)
            skips[type(exc).__name__] = skips.get(type(exc).__name__, 0) + 1
    ids = [r.id for r in sample]
    click.echo(
        "DL_SUMMARY="
        + json.dumps(
            {
                **run.summary(),
                "skips": skips,
                "n": len(rows),
                "start": start,
                "ids_sha256": hashlib.sha256("\n".join(ids).encode()).hexdigest(),
            },
            sort_keys=True,
        )
    )
    click.echo("DL_PROBS=" + json.dumps(probs))


@lab.command("distill-merge")
@click.option(
    "--part",
    "parts",
    nargs=2,
    multiple=True,
    required=True,
    type=(int, click.Path(exists=True, path_type=Path)),
    help="START and the file with that run's DL_PROBS list (repeat for each run).",
)
@click.option("--cost", type=float, required=True, help="Total US$ of all label runs.")
@click.option("--model", default="claude-haiku-5-5")
@click.option("--out", type=click.Path(path_type=Path), default=DISTILL_PATH)
def lab_distill_merge(
    parts: tuple[tuple[int, Path], ...], cost: float, model: str, out: Path
) -> None:
    """Assemble the committed teacher-label file from one or more label runs (T247)."""
    from arena.lab import dataset as ds
    from arena.lab import distill as dl

    train = ds.read_split(Path("lab/data/forecast-sft/train.jsonl.gz"))
    sample = dl.sample_rows(train, DISTILL_N)
    probs: list[float | None] = [None] * len(sample)
    for start, path in parts:
        for k, v in enumerate(json.loads(path.read_text(encoding="utf-8"))):
            i = start + k
            if i >= len(sample):
                raise click.ClickException(f"part at {start} runs past the sample")
            if v is not None:
                if probs[i] is not None:
                    raise click.ClickException(f"row {i} is labelled twice")
                probs[i] = float(v)
    ids = [r.id for r in sample]
    usable = dl.usable(ids, probs, train)  # raises if a label is not a training row
    summary: dict[str, object] = {
        "model": model,
        "cost_usd": cost,
        "labelled": len(usable),
        "sample": len(ids),
        "note": "probabilities only; the teacher's rationale text is not stored",
    }
    dl.write_labels(out, dl.labels_file(ids, probs, summary))
    click.echo(f"{len(usable)} of {len(ids)} rows labelled -> {out}")
