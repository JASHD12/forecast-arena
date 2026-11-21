"""Commands of the experiments lab (SPEC 17)."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import click

from arena.cli import Ctx, lab


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
