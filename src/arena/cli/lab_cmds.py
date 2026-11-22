"""Commands of the experiments lab (SPEC 17)."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import click

from arena.cli import Ctx, lab
from arena.lab.docs_assistant import DOC_PATHS, DocsIndex, ask, evaluate, load_chunks


@lab.group("dataset")
def dataset_group() -> None:
    """Leak-free supervised datasets for the fine-tuning experiments."""


@dataset_group.command("build")
@click.option("--out", type=click.Path(path_type=Path), default=Path("lab/data/forecast-sft"))
@click.option("--max-train-rows", type=int, default=6000, show_default=True)
@click.option("--seed", type=int, default=0, show_default=True)
@click.option(
    "--card", type=click.Path(path_type=Path), default=None, help="Write the data card here."
)
@click.pass_obj
def dataset_build(obj: Ctx, out: Path, max_train_rows: int, seed: int, card: Path | None) -> None:
    """Build the power splits from the SMARD cache (ARENA_CACHE_DIR) and write hashes."""
    from arena.domains.power import PowerDomain
    from arena.domains.power_history import HISTORY_START, PRICE_KEY, PowerHistory
    from arena.lab import dataset as ds
    from arena.sources.http import HttpClient
    from arena.sources.smard import SmardClient

    ds.check_windows()
    last = max(w[1] for w in ds.SPLITS.values())
    client = SmardClient(HttpClient(obj.settings.user_agent()), cache_dir=obj.settings.cache_dir)
    store = PowerHistory(client).store([PRICE_KEY], HISTORY_START, last + timedelta(days=3))
    domain = PowerDomain(store)
    rows = {name: ds.build_split(domain, name) for name in ds.SPLITS}
    rows["train"] = ds.subsample(rows["train"], max_train_rows, seed)
    ds.assert_no_overlap(rows)
    manifest: dict[str, object] = {"domain": "power", "seed": seed, "splits": {}}
    for name, r in rows.items():
        sha = ds.write_split(r, out / f"{name}.jsonl.gz")
        manifest["splits"][name] = {  # type: ignore[index]
            "sha256": sha,
            "window": [d.isoformat() for d in ds.SPLITS[name]],
            **ds.summary(r),
        }
        click.echo(f"{name}: {len(r)} rows, sha256 {sha}")
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    if card is not None:
        card.parent.mkdir(parents=True, exist_ok=True)
        card.write_text(ds.data_card(manifest), encoding="utf-8")
        click.echo(f"data card -> {card}")


@lab.group("retrieval")
def retrieval_group() -> None:
    """Dense vs BM25 vs hybrid retrieval with reranking (T251)."""


@retrieval_group.command("build")
@click.option("--corpus-first", default="2025-11-01", show_default=True)
@click.option("--corpus-last", default="2026-09-30", show_default=True)
@click.option("--query-first", default="2026-10-01", show_default=True)
@click.option("--query-last", default="2026-10-31", show_default=True)
@click.option(
    "--out", type=click.Path(path_type=Path), default=Path("evals/golden/retrieval-v1.jsonl")
)
@click.pass_obj
def retrieval_build(
    obj: Ctx, corpus_first: str, corpus_last: str, query_first: str, query_last: str, out: Path
) -> None:
    """Freeze the graded retrieval eval set from replayed power questions (SMARD cache)."""
    from datetime import UTC, date, datetime

    from arena.domains.power import PowerDomain
    from arena.domains.power_history import HISTORY_START, PRICE_KEY, PowerHistory
    from arena.evals.golden import build
    from arena.lab import retrieval_eval as re_
    from arena.sources.http import HttpClient
    from arena.sources.smard import SmardClient

    cf, cl = date.fromisoformat(corpus_first), date.fromisoformat(corpus_last)
    qf, ql = date.fromisoformat(query_first), date.fromisoformat(query_last)
    client = SmardClient(HttpClient(obj.settings.user_agent()), cache_dir=obj.settings.cache_dir)
    store = PowerHistory(client).store([PRICE_KEY], HISTORY_START, ql + timedelta(days=3))
    domain = PowerDomain(store)
    resolve_at = datetime.combine(ql + timedelta(days=3), datetime.min.time(), tzinfo=UTC)
    docs, queries = re_.build_set(
        build(domain, cf, cl, resolve_at), build(domain, qf, ql, resolve_at)
    )
    sha = re_.write_set(docs, queries, out)
    click.echo(
        f"retrieval set: {len(docs)} documents, {len(queries)} queries, sha256 {sha} -> {out}"
    )


@retrieval_group.command("eval")
@click.option("--set", "set_path", type=click.Path(exists=True, path_type=Path),
              default=Path("evals/golden/retrieval-v1.jsonl"))  # fmt: skip
@click.option("--rerank/--no-rerank", default=True, show_default=True)
@click.option(
    "--out",
    type=click.Path(path_type=Path),
    default=Path("evals/results/lab-retrieval-hybrid.json"),
)
@click.pass_obj
def retrieval_eval_cmd(obj: Ctx, set_path: Path, rerank: bool, out: Path) -> None:
    """Score the four retrieval arms on the frozen set and write the lab result."""
    from arena.agent.retrieval import CrossEncoderReranker, FastEmbedder
    from arena.lab import retrieval_eval as re_
    from arena.lab.results import LabResult

    docs, queries, sha = re_.read_set(set_path)
    cache = obj.settings.cache_dir / "fastembed"
    index = re_.index_of(docs, FastEmbedder(cache_dir=cache))
    reranker = CrossEncoderReranker(cache_dir=cache) if rerank else None
    metrics = re_.evaluate(
        index, queries, re_.arms_for(index, reranker.score if reranker else None)
    )
    result = LabResult(
        experiment="retrieval-hybrid",
        title="Retrieval: dense vs BM25 vs hybrid with reranking",
        created_at=obj.clock.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        why=(
            "Hybrid search with reranking is the standard retrieval stack of production RAG "
            "(docs/SOURCES.md, lab sources)."
        ),
        dataset_sha256={"retrieval-v1": sha},
        metrics=metrics,  # type: ignore[arg-type]
        notes=[
            f"{len(docs)} resolved power questions as documents, {len(queries)} October 2026 "
            "queries; relevance is graded from template, entity, date and threshold (see the "
            "module docstring), never by hand.",
            "The live agent keeps its dense retriever; nothing here changes a live forecast.",
        ],
        limits=[
            "Relevance is graded from question metadata, so it rewards matching template, "
            "entity and a similar threshold; it says nothing about whether the retrieved "
            "questions improve a forecast.",
            "One domain (electricity), one month of queries; queries on the same day are "
            "correlated and the differences between arms were not tested for significance.",
            "Cross-encoder latency is measured on a shared 2-core CPU and varies between runs.",
        ],
        card="docs/lab/retrieval-hybrid.md",
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result.model_dump_json(indent=1) + "\n", encoding="utf-8")
    for name, m in metrics.items():
        click.echo(f"{name}: {m}")


@lab.command("card")
@click.argument("result", type=click.Path(exists=True, path_type=Path))
def lab_card_cmd(result: Path) -> None:
    """Write the experiment card (docs/lab/<experiment>.md) from a lab result file."""
    import json

    from arena.lab.results import LabResult, card_markdown

    r = LabResult.model_validate(json.loads(result.read_text(encoding="utf-8")))
    out = Path(r.card) if r.card else Path("docs/lab") / f"{r.experiment}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(card_markdown(r), encoding="utf-8")
    click.echo(f"card -> {out}")


@lab.command("grounding")
@click.option(
    "--out", type=click.Path(path_type=Path), default=Path("evals/results/lab-grounding.json")
)
@click.pass_obj
def lab_grounding(obj: Ctx, out: Path) -> None:
    """Check every stored live rationale for numbers that are not in its prompt (T252a)."""
    from arena.lab import grounding as gr
    from arena.lab.results import LabResult
    from arena.scoring.core import load

    rec = load(obj.ledger)
    per = gr.rationale_checks(obj.ledger, rec)
    metrics = {fid: gr.summarize(items) for fid, items in sorted(per.items())}
    result = LabResult(
        experiment="grounding",
        title="Numeric grounding of model rationales",
        created_at=obj.clock.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        why=(
            "Checking generated answers against their source data is the cheapest first line of "
            "LLM evaluation, before any LLM-as-judge (docs/SOURCES.md, lab sources)."
        ),
        metrics=metrics,  # type: ignore[arg-type]
        notes=[
            "Every stored live rationale and key factor with a stored morning context "
            f"({sum(m['n'] for m in metrics.values())} rationales; "
            f"{len(rec.forecasts)} forecasts in the ledger).",
            "Trivial numbers (small integers, years, dates) are ignored. A number counts as in "
            "the prompt if it equals one in the question, the rule or the context within its "
            "rounding or 1%.",
        ],
        limits=[
            "Not in the prompt is an upper bound on invented figures: a model can compute "
            "things (a weekly mean of seven values, for example) that are legitimate but not "
            "literally in the prompt.",
            "The agents also read tool results (series, base rates, retrieval) that are not part "
            "of the stored morning context, so their share is overstated here.",
            "It does not judge whether the reasoning is good, only whether the figures it "
            "quotes can be traced.",
            "Small sample: the live record is a few days old; the numbers will move.",
        ],
        card="docs/lab/grounding.md",
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result.model_dump_json(indent=1) + "\n", encoding="utf-8")
    for fid, m in metrics.items():
        click.echo(f"{fid}: {m}")


@lab.command("redteam")
@click.option(
    "--cases", type=click.Path(exists=True, path_type=Path), default=Path("lab/redteam/cases.json")
)
@click.option(
    "--out", type=click.Path(path_type=Path), default=Path("evals/results/lab-guardrails.json")
)
@click.pass_obj
def lab_redteam(obj: Ctx, cases: Path, out: Path) -> None:
    """Run the guards over the red-team set and write the lab result (no model, no cost)."""
    import hashlib

    from arena.lab import redteam
    from arena.lab.results import LabResult

    metrics = redteam.run(redteam.load_cases(cases))
    result = LabResult(
        experiment="guardrails",
        title="Guardrails and red-team suite for untrusted tool and news text",
        created_at=obj.clock.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        why=(
            "Layered input and output guards around an LLM agent, tested with a red-team "
            "set, are standard for production agents (docs/SOURCES.md, lab sources)."
        ),
        dataset_sha256={"redteam-cases": hashlib.sha256(cases.read_bytes()).hexdigest()},
        metrics=metrics,  # type: ignore[arg-type]
        notes=[
            "Detection means the guard flagged the text (injection pattern, markup, link, "
            "code fence or length); an instruction-like text is replaced before it reaches "
            "the model.",
            "The evasion category (paraphrase, spacing, other languages, base64) is expected "
            "to get past the regex guards; its misses are the honest limit of this layer.",
            "Report-only: the live agent is unchanged (its defences are the data labelling "
            "and the harness limits).",
        ],
        limits=[
            "Synthetic attacks written by the project; a determined attacker is not bounded "
            "by them. The patterns were refined once after a first run on this same set "
            "(three misses and one false positive), so the detection rate is optimistic.",
            "Regex guards cannot understand meaning; a classifier or a second model would "
            "be the next layer.",
            "No model was attacked here, so this measures detection, not attack success "
            "against an LLM.",
        ],
        card="docs/lab/guardrails.md",
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result.model_dump_json(indent=1) + "\n", encoding="utf-8")
    for name, m in metrics.items():
        click.echo(f"{name}: {m}")


@lab.command("calibration")
@click.option(
    "--run",
    "run_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
    help="A stored power backtest run (backtests/power-...).",
)
@click.option(
    "--out", type=click.Path(path_type=Path), default=Path("evals/results/lab-calibration.json")
)
@click.pass_obj
def lab_calibration(obj: Ctx, run_dir: Path, out: Path) -> None:
    """Compare re-calibration methods on the `ml` probabilities of a stored backtest."""
    from arena.lab import calibration_study as cs
    from arena.lab.results import LabResult

    rows = cs.load_rows(run_dir)
    preds = cs.walk_forward(rows, cs.default_methods())
    metrics, paired = cs.summarize(preds)
    first, last = min(preds["identity"]["day"]), max(preds["identity"]["day"])
    result = LabResult(
        experiment="calibration",
        title="Calibration methods compared: identity, Platt, isotonic, beta",
        created_at=obj.clock.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        why=(
            "Probabilistic forecasts are only useful if they are calibrated; production teams "
            "monitor and re-calibrate them (docs/SOURCES.md, lab sources)."
        ),
        metrics=metrics,  # type: ignore[arg-type]
        paired=paired,
        notes=[
            f"The `ml` backtest probabilities of run {run_dir.name}, re-calibrated day by day on "
            f"earlier days only (batch days {first} to {last}, 120 warm-up days, weekly refit).",
            "Identity is the power champion as it is (it is already Platt-calibrated "
            "inside its own training).",
        ],
        limits=[
            "A backtest, not live: one market, one year, six strongly correlated questions a day.",
            "Re-calibrating already calibrated probabilities can only add noise unless the "
            "model drifted; no live change follows from this study (rule I8).",
        ],
        card="docs/lab/calibration.md",
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result.model_dump_json(indent=1) + "\n", encoding="utf-8")
    for name, m in metrics.items():
        click.echo(f"{name}: {m}")
    for p in paired:
        click.echo(f"{p['a']} - {p['b']}: {p['diff']:+.4f} [{p['lo']:+.4f}, {p['hi']:+.4f}]")


def _docs_index() -> DocsIndex:
    return DocsIndex(load_chunks(Path("."), DOC_PATHS))


@lab.command("ask")
@click.argument("question")
def lab_ask(question: str) -> None:
    """Ask the project documents a question (extractive, cited, offline; T254)."""
    click.echo(ask(_docs_index(), question).text)


@lab.command("docs-eval")
@click.option(
    "--out", type=click.Path(path_type=Path), default=Path("evals/results/lab-docs-assistant.json")
)
@click.pass_obj
def lab_docs_eval(obj: Ctx, out: Path) -> None:
    """Score the docs assistant on the hand-written question set (T254)."""
    from arena.lab.dataset import plain_sha256
    from arena.lab.results import LabResult

    golden = Path("evals/golden/docs-qa-v1.jsonl")
    pairs = [json.loads(line) for line in golden.read_text(encoding="utf-8").splitlines() if line]
    metrics = {"docs_assistant": evaluate(_docs_index(), pairs)}
    result = LabResult(
        experiment="docs-assistant",
        title="Ask the project: cited answers over the project documents",
        created_at=obj.clock.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        why=(
            "Retrieval-grounded assistants with citations and refusals are the standard "
            "internal-knowledge pattern."
        ),
        dataset_sha256={golden.name: plain_sha256(golden)},
        metrics=metrics,  # type: ignore[arg-type]
        notes=[f"{len(pairs)} hand-written questions; answers are extractive sentences."],
        limits=[
            "The method was changed once after seeing the first score (stop words removed from "
            "the query; a hit no longer needs the expected file; the first run scored 25.0% "
            "hits), so the final figure is optimistic.",
            "Small, hand-written question set whose expected phrases come from the same documents.",
            "A hit means a cited chunk contains the expected phrase, not that the answer reads "
            "well.",
            "Refusal uses a fixed word-coverage threshold chosen once, not tuned per question.",
        ],
        card="docs/lab/docs-assistant.md",
    )
    out.write_text(result.model_dump_json(indent=1) + "\n", encoding="utf-8")
    click.echo(metrics)


@lab.command("conformal")
@click.option("--first", default="2026-04-01", show_default=True)
@click.option("--last", default="2026-10-31", show_default=True)
@click.option(
    "--out", type=click.Path(path_type=Path), default=Path("evals/results/lab-conformal.json")
)
@click.pass_obj
def lab_conformal(obj: Ctx, first: str, last: str, out: Path) -> None:
    """Walk-forward coverage of the central 80% and 90% price bands, raw and conformal (T257)."""
    from datetime import date

    from arena.domains.power import PowerDomain
    from arena.domains.power_history import HISTORY_START, PRICE_KEY, PowerHistory
    from arena.lab import conformal_study as cs
    from arena.lab.results import LabResult
    from arena.sources.http import HttpClient
    from arena.sources.smard import SmardClient

    f, la = date.fromisoformat(first), date.fromisoformat(last)
    client = SmardClient(HttpClient(obj.settings.user_agent()), cache_dir=obj.settings.cache_dir)
    store = PowerHistory(client).store([PRICE_KEY], HISTORY_START, la + timedelta(days=3))
    rows = cs.coverage_rows(PowerDomain(store), cs.month_windows(f, la))
    metrics = cs.summarise(rows)
    result = LabResult(
        experiment="conformal",
        title="Conformal price bands: coverage by month",
        created_at=obj.clock.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        why="Calibrated uncertainty intervals are what planning teams ask of a forecasting model.",
        metrics=metrics,
        notes=[
            f"{len(rows)} month-statistic rows from {first} to {last}; targets 80% and 90%.",
            "Each month: model trained before a 30-day calibration window, CQR margin fitted on "
            "that window, bands scored on the month.",
        ],
        limits=[
            "Seven months only; coverage in one month moves with the market regime.",
            "Conformal guarantees assume exchangeable days, which price series are not.",
            "Backtest of the production recipe on replayed days; not a live score.",
        ],
        card="docs/lab/conformal.md",
    )
    out.write_text(result.model_dump_json(indent=1) + "\n", encoding="utf-8")
    for stat, m in metrics.items():
        click.echo(f"{stat}: {m}")


@lab.command("explain")
@click.option("--cut", default="2026-11-01", show_default=True, help="Train on days before this.")
@click.option("--day", default="2026-11-10", show_default=True, help="Batch day to explain.")
@click.option("--out", type=click.Path(path_type=Path), default=Path("docs/lab/explanations.md"))
@click.pass_obj
def lab_explain(obj: Ctx, cut: str, day: str, out: Path) -> None:
    """Top-3 feature effects for three replayed questions (backtest; T260)."""
    from datetime import UTC, date, datetime, time

    from arena.domains.power import PowerDomain
    from arena.domains.power_history import HISTORY_START, PRICE_KEY, PowerHistory
    from arena.forecasters.ml_power import train
    from arena.lab.explanations import example_rows
    from arena.sources.http import HttpClient
    from arena.sources.smard import SmardClient

    c, b = date.fromisoformat(cut), date.fromisoformat(day)
    client = SmardClient(HttpClient(obj.settings.user_agent()), cache_dir=obj.settings.cache_dir)
    store = PowerHistory(client).store([PRICE_KEY], HISTORY_START, b + timedelta(days=3))
    dom = PowerDomain(store)
    model = train(dom, c, folds=2, max_iter=60)  # lighter than live: this is an illustration
    asof = datetime.combine(b, time(5, 30), tzinfo=UTC)
    rows = example_rows(model, dom, b, asof)
    lines = [
        "# Per-forecast explanations (backtest, not the live record)",
        "",
        f"Model `{model.version}` (reduced training settings, for illustration) replayed on "
        f"{day}. For each question the input features are "
        "replaced one group at a time by their typical value (median of the last week of "
        "inputs); the change in the probability, in percentage points, is the effect. The three "
        "largest are shown. This describes what the model reacts to, not why the market moves.",
        "",
    ]
    for r in rows:
        lines.append(f"**{r['question']}**  P(YES) = {100 * r['probability']:.1f}%")
        lines.append("")
        lines += [f"- {t['feature']}: {t['effect_points']:+.1f} points" for t in r["top"]]
        lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    click.echo(f"explanations -> {out}")


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


@lab.command("ft-eval")
@click.argument("scores", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--ml-run", "ml_runs", multiple=True, type=click.Path(exists=True, path_type=Path))
@click.option("--parity", type=click.Path(exists=True, path_type=Path), default=None)
@click.option(
    "--out", type=click.Path(path_type=Path), default=Path("evals/results/lab-qlora-r1.json")
)
@click.pass_obj
def lab_ft_eval(
    obj: Ctx, scores: tuple[Path, ...], ml_runs: tuple[Path, ...], parity: Path | None, out: Path
) -> None:
    """Evaluate the QLoRA run on the frozen test sets from its Colab score files (T246)."""
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
    pairs = [
        ("qlora_1_5b", "base_1_5b"),
        ("qlora_1_5b", "base_rate"),
        ("qlora_1_5b", "ml"),
        ("lora_0_5b", "base_0_5b"),
        ("lora_0_5b", "base_rate"),
        ("lora_0_5b", "qlora_1_5b"),
        ("ml", "base_rate"),
    ]
    metrics, paired = fe.evaluate(fe.read_scores(list(scores)), rows, ml, pairs)
    notes = [
        "Probabilities are the Colab scores (4-bit model plus adapter, Platt map fitted on the "
        "validation split only); the live model is the Q4_K_M GGUF of the merged adapter.",
        f"Test sets: {sum(1 for r in rows.values() if r['split'] == 'test_oct')} questions "
        f"(October 2026) and {sum(1 for r in rows.values() if r['split'] == 'test_nov')} "
        "(1 to 15 November 2026); the six questions of a day are correlated, so intervals are "
        "day-block bootstrap intervals.",
    ]
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
    summary = json.loads((Path(scores[0]).parent / "run_summary.json").read_text("utf-8"))
    result = LabResult(
        experiment="qlora-r1",
        title="QLoRA fine-tune of Qwen2.5-1.5B on replayed power questions",
        created_at=obj.clock.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        why=(
            "Parameter-efficient fine-tuning of a small open model is the standard way companies "
            "adapt an LLM to a narrow task; the comparison with a classical model is the point."
        ),
        prereg_sha256=hashlib.sha256(Path("lab/prereg/qlora-forecast.md").read_bytes()).hexdigest(),
        dataset_sha256={k: v for k, v in summary["dataset_sha256"].items()},
        artefacts={"gguf": art.sha256, "adapter": art.adapter_sha256, "release": art.url},
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
        card="docs/lab/qlora-r1.md",
    )
    out.write_text(result.model_dump_json(indent=1) + "\n", encoding="utf-8")
    for k, m in metrics.items():
        click.echo(f"{k}: {m}")
    for p in paired:
        click.echo(p)


def _ft_rows() -> list[object]:
    from arena.lab import dataset as ds
    from arena.lab import ft_gguf as fg

    return [
        r
        for name in fg.SPLITS
        for r in ds.read_split(Path("lab/data/forecast-sft") / f"{name}.jsonl.gz")
    ]


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


@lab.command("bandit")
@click.option(
    "--out", type=click.Path(path_type=Path), default=Path("evals/results/lab-bandit.json")
)
@click.pass_obj
def lab_bandit(obj: Ctx, out: Path) -> None:
    """Replay the Hedge forecaster on the live record (walk-forward, no leakage; T293)."""
    from arena.lab import bandit_study as bs
    from arena.lab.results import LabResult
    from arena.scoring.core import load

    rec = load(obj.ledger)
    rep = bs.replay(rec.scored)
    if not rep["y"]:
        raise click.ClickException("no questions answered by two experts in the ledger")
    metrics, paired = bs.summarise(rep)
    result = LabResult(
        experiment="bandit",
        title="Online learning of which forecaster to trust (Hedge and Thompson sampling)",
        created_at=obj.clock.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        why=(
            "Expert-advice and bandit methods are the production form of reinforcement learning "
            "for choosing between models from delayed feedback."
        ),
        metrics=metrics,  # type: ignore[arg-type]
        paired=paired,
        notes=[
            f"{len(rep['y'])} live questions answered by at least two experts over "
            f"{len(set(rep['days']))} batch days (the live rehearsal record, replayed "
            "walk-forward with a two-day outcome lag).",
            "The best expert in hindsight is "
            + min((e for e in metrics if e in bs.bd.EXPERTS), key=lambda e: metrics[e]["brier"])
            + ".",
        ],
        limits=[
            "The live record is only a few days long: the weights barely move and every "
            "interval is wide. This is a mechanism check, not evidence that the blend helps.",
            "The best expert in hindsight is a reference, not something that could be played.",
        ],
        card="docs/lab/bandit.md",
    )
    out.write_text(result.model_dump_json(indent=1) + "\n", encoding="utf-8")
    for k, m in metrics.items():
        click.echo(f"{k}: {m}")
    for p in paired:
        click.echo(p)


@lab.command("anomaly")
@click.option(
    "--out", type=click.Path(path_type=Path), default=Path("evals/results/lab-anomaly.json")
)
@click.pass_obj
def lab_anomaly(obj: Ctx, out: Path) -> None:
    """Isolation Forest against a robust z-score on injected faults in real price windows."""
    from datetime import date

    from arena.domains.power import PowerDomain
    from arena.domains.power_history import HISTORY_START, PRICE_KEY, PowerHistory
    from arena.lab import anomaly_study as st
    from arena.lab.results import LabResult
    from arena.sources.http import HttpClient
    from arena.sources.smard import SmardClient

    train, test = (date(2019, 1, 1), date(2024, 12, 31)), (date(2025, 11, 1), date(2026, 10, 31))
    client = SmardClient(HttpClient(obj.settings.user_agent()), cache_dir=obj.settings.cache_dir)
    store = PowerHistory(client).store([PRICE_KEY], HISTORY_START, test[1] + timedelta(days=3))
    res = st.run(PowerDomain(store).all_days(), train, test)
    result = LabResult(
        experiment="anomaly",
        title="Unsupervised data-anomaly detection on price windows (Isolation Forest)",
        created_at=obj.clock.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        why=(
            "Label-free anomaly detection on incoming data is how production ML teams catch broken "
            "feeds before a model silently uses them."
        ),
        metrics=res["metrics"],
        notes=[
            f"{res['n_windows']} real 28-day windows from {test[0]} to {test[1]} (every third "
            f"day); thresholds from clean windows of {train[0]} to {train[1]} for about 5% false "
            f"alarms: {{k: round(v, 3) for k, v in res['threshold'].items()}}.".replace(
                "{{k: round(v, 3) for k, v in res['threshold'].items()}}",
                str({k: round(v, 3) for k, v in res["threshold"].items()}),
            ),
            "Faults are injected into the latest day only: a spike (one hour times 8), a unit "
            "error (prices divided by 1000), a flat feed and a repeated day.",
        ],
        limits=[
            "Injected faults are synthetic; real feed failures can look different.",
            "A window of 28 days is short; a repeated day is hard for any detector that only "
            "looks at daily statistics.",
        ],
        card="docs/lab/anomaly.md",
    )
    out.write_text(result.model_dump_json(indent=1) + "\n", encoding="utf-8")
    click.echo(json.dumps(res, indent=1))


@lab.command("regimes")
@click.option(
    "--out", type=click.Path(path_type=Path), default=Path("evals/results/lab-regimes.json")
)
@click.pass_obj
def lab_regimes(obj: Ctx, out: Path) -> None:
    """Cluster daily price shapes (k-means) and test the regime as a feature (T294)."""
    from datetime import date

    from arena.domains.power import PowerDomain
    from arena.domains.power_history import HISTORY_START, PRICE_KEY, PowerHistory
    from arena.lab import regimes as rg
    from arena.lab.results import LabResult
    from arena.sources.http import HttpClient
    from arena.sources.smard import SmardClient

    train, test = (date(2019, 1, 1), date(2025, 10, 31)), (date(2025, 11, 1), date(2026, 10, 31))
    client = SmardClient(HttpClient(obj.settings.user_agent()), cache_dir=obj.settings.cache_dir)
    store = PowerHistory(client).store([PRICE_KEY], HISTORY_START, test[1] + timedelta(days=3))
    res = rg.run(PowerDomain(store).all_days(), train, test)
    p = res["paired"]
    result = LabResult(
        experiment="regimes",
        title="Price-regime clustering (k-means) as a feature for the next day's mean price",
        created_at=obj.clock.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        why=(
            "Unsupervised structure (clusters of daily shapes) is a standard source of features "
            "and of operational monitoring in energy forecasting."
        ),
        metrics=res["metrics"],
        paired=[{"a": "with_regime", "b": "without_regime", "split": "test", **p}],
        notes=[
            f"k = {res['info']['k']} chosen by silhouette on {train[0]} to {train[1]} "
            f"(silhouette by k: {res['info']['silhouette_by_k']}); share of training days per "
            f"regime in percent: {res['regime_share_pct']}.",
            "Pinball loss averaged over the 10%, 50% and 90% quantiles of the next day's mean "
            f"price, test year {test[0]} to {test[1]}; the regime is that of the last known day.",
        ],
        limits=[
            "One market, one year of test days; the interval is a day-block bootstrap.",
            "Backtest-only: nothing changes in the live `ml` forecaster.",
        ],
        card="docs/lab/regimes.md",
    )
    out.write_text(result.model_dump_json(indent=1) + "\n", encoding="utf-8")
    click.echo(json.dumps(res, indent=1))
