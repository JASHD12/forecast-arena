"""Commands of the experiments lab (SPEC 17)."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import click

from arena.cli import Ctx, lab
from arena.lab.dataset import Row
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


@lab.command("vectordb")
@click.option("--set", "set_path", type=click.Path(exists=True, path_type=Path),
              default=Path("evals/golden/retrieval-v1.jsonl"))  # fmt: skip
@click.option("--location", default=":memory:", show_default=True, help="Qdrant location or URL.")
@click.option(
    "--out", type=click.Path(path_type=Path), default=Path("evals/results/lab-vectordb.json")
)
@click.pass_obj
def lab_vectordb(obj: Ctx, set_path: Path, location: str, out: Path) -> None:
    """Qdrant against brute-force dense search on the frozen retrieval set (T291)."""
    from datetime import datetime

    from arena.agent.retrieval import FastEmbedder
    from arena.agent.vectorstore import QdrantIndex
    from arena.lab import retrieval_eval as re_
    from arena.lab.results import LabResult

    docs, queries, sha = re_.read_set(set_path)
    emb = FastEmbedder(cache_dir=obj.settings.cache_dir / "fastembed")
    index = re_.index_of(docs, emb)
    qd = QdrantIndex(index.items, emb, location)

    def brute(text: str, asof: datetime, qid: str) -> list[str]:
        return [p.question_id for p, _ in index.search(text, asof, k=10, exclude=qid)]

    def qdrant(text: str, asof: datetime, qid: str) -> list[str]:
        return [p.question_id for p, _ in qd.search(text, asof, k=10, exclude=qid)]

    metrics = re_.evaluate(index, queries, {"dense_numpy": brute, "dense_qdrant": qdrant})
    usable = [q for q in queries if any(g == 2 for g in q["grades"].values())]
    same = [
        set(brute(q["text"], datetime.fromisoformat(q["asof"]), q["id"])[:5])
        == set(qdrant(q["text"], datetime.fromisoformat(q["asof"]), q["id"])[:5])
        for q in usable
    ]
    metrics["dense_qdrant"]["top5_same_set_pct"] = round(100 * sum(same) / len(same), 1)
    result = LabResult(
        experiment="vectordb",
        title="Vector database: Qdrant against brute-force dense search",
        created_at=obj.clock.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        why="A vector database is the standard retrieval store of production RAG systems.",
        dataset_sha256={"retrieval-v1": sha},
        metrics=metrics,  # type: ignore[arg-type]
        notes=[
            f"{len(docs)} documents and {len(usable)} queries of the frozen retrieval set, the "
            f"same embedder for both arms; Qdrant location `{location}` (local mode, no server).",
            "The forecast-time rule (a document must have resolved before the query's as-of "
            "time) is a payload filter inside Qdrant and is covered by unit tests.",
        ],
        limits=[
            "Local mode scans vectors like brute force, so its latency says nothing about a "
            "server with an HNSW index; the CI job `vectordb` runs the same tests against a Qdrant "
            "server container.",
            "Two thousand documents are far below the size where an approximate index matters.",
        ],
        card="docs/lab/vectordb.md",
    )
    out.write_text(result.model_dump_json(indent=1) + "\n", encoding="utf-8")
    for k, m in metrics.items():
        click.echo(f"{k}: {m}")


@lab.command("stacking")
@click.option(
    "--out", type=click.Path(path_type=Path), default=Path("evals/results/lab-stacking.json")
)
@click.pass_obj
def lab_stacking(obj: Ctx, out: Path) -> None:
    """Replay a pandas + scikit-learn Pipeline stacker on the live record (T301)."""
    from arena.lab import stacking_study as st
    from arena.lab.results import LabResult
    from arena.scoring import stats
    from arena.scoring.core import load

    rep = st.replay(load(obj.ledger).scored)
    n_days = len(set(rep["days"]))
    if n_days < 5:
        raise click.ClickException(
            f"only {len(rep['y'])} stacked questions over {n_days} test day(s); need 5 days"
        )
    y = rep["y"]
    metrics = {
        k: {"n": len(v), "brier": round(float(sum(stats.brier_terms(v, y)) / len(v)), 4)}
        for k, v in rep["arms"].items()
    }
    paired = []
    for a, b in (("stacking", "equal_mean"), ("stacking", "ml")):
        iv = stats.paired_brier_difference(rep["days"], rep["arms"][a], rep["arms"][b], y)
        paired.append(
            {
                "a": a,
                "b": b,
                "diff": iv.estimate,
                "lo": iv.low,
                "hi": iv.high,
                "n": iv.n,
                "days": iv.days,
            }
        )
    result = LabResult(
        experiment="stacking",
        title="Stacking with a scikit-learn Pipeline on pandas DataFrames",
        created_at=obj.clock.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        why=(
            "pandas DataFrames feeding scikit-learn Pipelines and ColumnTransformers are the "
            "everyday modelling stack of most data science teams."
        ),
        metrics=metrics,  # type: ignore[arg-type]
        paired=paired,
        notes=[
            f"{len(y)} live questions answered by every peer ({', '.join(st.PEERS)}), replayed "
            "walk-forward with a two-day outcome lag; refitted each batch day."
        ],
        limits=[
            "Only a few live days: the stacker has little to learn from; intervals are wide.",
            "A mechanism check of the DataFrame stack, not a proposal for a new forecaster.",
        ],
        card="docs/lab/stacking.md",
    )
    out.write_text(result.model_dump_json(indent=1) + "\n", encoding="utf-8")
    for k, m in metrics.items():
        click.echo(f"{k}: {m}")
    for p in paired:
        click.echo(p)
