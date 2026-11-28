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


@lab.command("analyst-eval")
@click.argument("november_run", type=click.Path(exists=True, path_type=Path))
@click.argument("october_run", type=click.Path(exists=True, path_type=Path))
@click.option("--reference-run", type=click.Path(exists=True, path_type=Path), required=True)
@click.option(
    "--ml-probs-november",
    type=click.Path(exists=True, path_type=Path),
    default=Path("evals/golden/ml-probs-power-11a.json"),
)
@click.option(
    "--ml-probs-october",
    type=click.Path(exists=True, path_type=Path),
    default=Path("evals/golden/ml-probs-power.json"),
)
@click.option(
    "--skills-result",
    type=click.Path(exists=True, path_type=Path),
    default=Path("evals/results/lab-agent-skills.json"),
    help="The agent_skills r1 result whose cost per answered question H-A3 compares with.",
)
@click.option("--out", type=click.Path(path_type=Path), default=None)
def lab_analyst_eval(
    november_run: Path,
    october_run: Path,
    reference_run: Path,
    ml_probs_november: Path,
    ml_probs_october: Path,
    skills_result: Path,
    out: Path | None,
) -> None:
    """Lab result of agent_analyst and the calibrated llm_context from three stored eval files."""
    import json

    from arena.forecasters.llm_context_cal import load_map
    from arena.lab import analyst_eval as ae

    def read(p: Path) -> dict:
        return json.loads(p.read_text(encoding="utf-8"))

    cal = load_map()
    if cal is None:
        raise click.ClickException("the calibration map artefact is missing")
    skills = read(skills_result)["metrics"]["agent_skills / eval"]
    r = ae.build(
        read(november_run),
        read(october_run),
        read(reference_run),
        read(ml_probs_november),
        read(ml_probs_october),
        cal,
        float(skills.get("cost_usd_per_1k_answered") or skills["cost_usd_per_1k"]),
    )
    path = out or Path("evals/results/lab-analyst-and-calibration.json")
    path.write_text(r.model_dump_json(indent=2) + "\n", encoding="utf-8")
    click.echo(f"wrote {path}")
    for v in ae.verdicts(r):
        state = "PASS" if v["passed"] else "NOT MET"
        click.echo(f"{v['rule']}: {state} - {v['text']}")


@lab.command("agent-eval")
@click.argument("eval_run", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--experiment",
    type=click.Choice(
        [
            "agent-skills",
            "agent-committee",
            "agent-committee-r2",
            "agent-quant-r2",
            "agent-skills-r2",
            "agent-committee-r3",
        ]
    ),
    required=True,
)
@click.option(
    "--reference-run",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="An earlier run on the same golden file whose agent_skills arm is reused.",
)
@click.option("--out", type=click.Path(path_type=Path), default=None)
def lab_agent_eval(
    eval_run: Path, experiment: str, reference_run: Path | None, out: Path | None
) -> None:
    """Turn one `arena eval run` file into the lab result of the skills or committee experiment."""
    import json

    from arena.lab import agent_eval as ae

    res = json.loads(eval_run.read_text(encoding="utf-8"))
    if reference_run is not None:
        ref = json.loads(reference_run.read_text(encoding="utf-8"))
        res = ae.merge_reference(res, ref, "agent_skills")
    r = ae.build(res, experiment)
    path = out or Path("evals/results") / f"lab-{experiment}.json"
    path.write_text(r.model_dump_json(indent=2) + "\n", encoding="utf-8")
    click.echo(f"wrote {path}")
    for v in ae.verdicts(r):
        state = "PASS" if v["passed"] else "NOT MET" if v["passed"] is False else "n/a"
        click.echo(f"{v['rule']}: {state} - {v['text']}")


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
