"""Offline studies of the lab (SPEC 17): bandit, anomaly, regimes, vector database, stacking."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import click

from arena.cli import Ctx, lab


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
