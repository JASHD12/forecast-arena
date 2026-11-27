"""Commands for the LLM layer: the live smoke test and the evaluation harness."""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import click

from arena.cli import (
    Ctx,
    eval_group,
    llm,
)


@llm.command("smoke")
@click.pass_obj
def llm_smoke(obj: Ctx) -> None:
    """Two live calls that report token usage and write nothing (GitHub Actions only)."""
    import os

    from arena.llm.factory import client_from_settings
    from arena.llm.smoke import run_smoke

    if os.environ.get("GITHUB_ACTIONS") != "true":
        click.echo(
            "refused: live LLM calls run only inside GitHub Actions (AGENTS.md S8)", err=True
        )
        sys.exit(2)
    client = client_from_settings(obj.settings)
    if client is None:
        click.echo(
            "model_missing: ARENA_LLM_PROVIDER, ARENA_LLM_MODEL and ARENA_LLM_API_KEY "
            "must all be set",
            err=True,
        )
        sys.exit(1)
    res = run_smoke(client, obj.settings.llm_max_output_tokens)
    for line in res.lines:
        click.echo(line)
    sys.exit(0 if res.ok else 1)


@eval_group.command("build")
@click.option("--first", type=click.DateTime(["%Y-%m-%d"]), default=None)
@click.option("--last", type=click.DateTime(["%Y-%m-%d"]), default=None)
@click.option("--out", type=click.Path(path_type=Path), required=True)
@click.option(
    "--from-ledger",
    is_flag=True,
    help="Freeze live days from the ledger (morning snapshots + resolutions) instead of SMARD.",
)
@click.option("--topics", default="weather,attention", help="With --from-ledger: comma list.")
@click.option(
    "--until",
    type=click.DateTime(["%Y-%m-%d"]),
    default=None,
    help="With --from-ledger: last batch day.",
)
@click.pass_obj
def eval_build(
    obj: Ctx,
    first: object,
    last: object,
    out: Path,
    from_ledger: bool,
    topics: str,
    until: object,
) -> None:
    """Freeze a golden set: power questions from the SMARD cache (ARENA_CACHE_DIR), or, with
    --from-ledger, live days of other topics (labelled "replay of live days", evaluation only)."""
    if from_ledger:
        _build_from_ledger(obj, topics, until, out)
        return
    if first is None or last is None:
        raise click.UsageError("--first and --last are required without --from-ledger")
    from arena.domains.power import PowerDomain
    from arena.domains.power_history import HISTORY_START, PRICE_KEY, PowerHistory
    from arena.evals.golden import build, dump
    from arena.sources.http import HttpClient
    from arena.sources.smard import SmardClient

    f, la = first.date(), last.date()  # type: ignore[attr-defined]
    client = SmardClient(HttpClient(obj.settings.user_agent()), cache_dir=obj.settings.cache_dir)
    store = PowerHistory(client).store([PRICE_KEY], HISTORY_START, la + timedelta(days=3))
    items = build(PowerDomain(store), f, la, obj.clock.now())
    sha = dump(items, out)
    click.echo(f"golden set: {len(items)} items, {f} to {la}, sha256 {sha} -> {out}")


def _build_from_ledger(obj: Ctx, topics: str, until: object, out: Path) -> None:
    import json

    from arena.evals import from_ledger as fl
    from arena.evals.golden import dump

    if until is None:
        raise click.UsageError("--until is required with --from-ledger")
    day = until.date()  # type: ignore[attr-defined]
    names = [t.strip() for t in topics.split(",") if t.strip()]
    build = fl.build_from_ledger(obj.ledger, names, day)
    if not build.items:
        raise click.ClickException("no resolved question with a morning snapshot: nothing frozen")
    sha = dump(build.items, out)
    sidecar = out.with_suffix(".meta.json")
    sidecar.write_text(
        json.dumps(fl.meta(build, names, day, sha, out.name), indent=1) + "\n", encoding="utf-8"
    )
    click.echo(
        f"{fl.LABEL}: {len(build.items)} items, sha256 {sha} -> {out} (dropped: {build.dropped})"
    )


@eval_group.command("ml-probs")
@click.option(
    "--golden",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Frozen golden set.",
)
@click.option("--out", type=click.Path(path_type=Path), required=True)
@click.pass_obj
def eval_ml_probs(obj: Ctx, golden: Path, out: Path) -> None:
    """Replay the production `ml` power model over a golden set (SMARD cache; a replay, I4)."""
    from arena.backtest import power as bt
    from arena.domains.power import PowerDomain
    from arena.domains.power_history import HISTORY_START, PRICE_KEY, PowerHistory
    from arena.evals import ml_probs as mp
    from arena.sources.http import HttpClient
    from arena.sources.smard import SmardClient

    first, last = mp.batch_range(golden)
    client = SmardClient(HttpClient(obj.settings.user_agent()), cache_dir=obj.settings.cache_dir)
    store = PowerHistory(client).store([PRICE_KEY], HISTORY_START, last + timedelta(days=3))
    run_id = f"mlprobs-{first.isoformat()}-{last.isoformat()}"
    res = bt.run(PowerDomain(store), first, last, run_id=run_id)
    note = (
        f"ml probabilities from a walk-forward replay of the production power model over the "
        f"batch days {first} to {last} (data known before each morning, expanding-window "
        f"retraining), for the frozen golden set {golden.name}; replay, not live (I4)"
    )
    payload = mp.build_payload(golden, res.records, note)
    mp.write(payload, out)
    n = len(payload["probabilities"])
    click.echo(
        f"ml probabilities: {n} questions, golden sha256 {payload['golden_sha256']} -> {out}"
    )


@eval_group.command("run")
@click.option("--golden", type=click.Path(exists=True, path_type=Path), required=True)
@click.option(
    "--variant",
    "variants",
    multiple=True,
    type=click.Choice(
        [
            "llm_plain",
            "llm_context",
            "llm_local",
            "agent",
            "agent_quant",
            "agent_analyst",
            "agent_skills",
            "agent_committee",
            "llm_context_sc5",
        ]
    ),
    default=("llm_plain", "llm_context"),
)
@click.option("--limit", type=int, default=None, help="Stratified seeded sample size.")
@click.option(
    "--ml-probs",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Replayed ml probabilities (evals/golden/ml-probs-power.json); needed by agent_analyst.",
)
@click.option("--fake", is_flag=True, help="FakeLLM answers (the CI gate; no network).")
@click.option("--max-tokens", type=int, default=60_000, help="Hard token cap for this run.")
@click.option("--out", "out_dir", type=click.Path(path_type=Path), default=Path("evals/results"))
@click.pass_obj
def eval_run(
    obj: Ctx,
    golden: Path,
    variants: tuple[str, ...],
    limit: int | None,
    ml_probs: Path | None,
    fake: bool,
    max_tokens: int,
    out_dir: Path,
) -> None:
    """Run the variants on the golden set and write `evals/results/<run_id>.json`."""
    import json
    import os

    from arena.evals.golden import load
    from arena.evals.run import (
        AGENT_REQUESTS_PER_QUESTION,
        AGENT_VARIANTS,
        COMMITTEE_REQUESTS_PER_QUESTION,
        EvalCaps,
        run,
        sample,
    )
    from arena.forecasters.selfconsistency import K as SC_K
    from arena.llm.client import FakeLLM, LLMClient

    items, sha = load(golden)
    items = sample(items, limit)
    probs: dict[str, float] | None = None
    if ml_probs is not None:
        doc = json.loads(ml_probs.read_text(encoding="utf-8"))
        if doc.get("golden_sha256") != sha:
            click.echo("refused: the ml probabilities were built for another golden set", err=True)
            sys.exit(2)
        probs = {k: float(v) for k, v in doc["probabilities"].items()}
    if "agent_analyst" in variants and probs is None:
        click.echo("refused: agent_analyst needs --ml-probs (replayed ml probabilities)", err=True)
        sys.exit(2)
    clients: dict[str, LLMClient] = {}
    if fake:
        answer = json.dumps({"probability": 0.5, "rationale": "fake", "key_factors": []})
        critique = json.dumps({"severity": "none", "issues": [], "direction": "none"})
        clients = {
            v: FakeLLM(lambda s, t, tools: critique if "skeptic of" in s else answer)
            for v in variants
        }
    else:
        if os.environ.get("GITHUB_ACTIONS") != "true":
            click.echo(
                "refused: live LLM calls run only inside GitHub Actions (AGENTS.md S8)", err=True
            )
            sys.exit(2)
        from arena.llm.factory import client_from_settings

        api = client_from_settings(obj.settings)
        for v in variants:
            if v == "llm_local":
                from arena.llm import local

                path = local.model_path(obj.settings.models_dir / "gguf")
                clients[v] = local.LlamaCppLLM(local.llama_backend(path))
            elif api is not None:
                clients[v] = api
        if not clients:
            click.echo("model_missing: no LLM configured", err=True)
            sys.exit(1)
    caps = EvalCaps(
        max_requests=max(
            1,
            len(items)
            * sum(
                COMMITTEE_REQUESTS_PER_QUESTION
                if v == "agent_committee"
                else AGENT_REQUESTS_PER_QUESTION
                + (2 if v == "agent_skills" else 0)  # + skill loads
                if v in AGENT_VARIANTS
                else 2 * SC_K
                if v.endswith("_sc5")
                else 2
                for v in clients
            ),
        ),
        max_tokens=max_tokens,
        max_output_tokens=obj.settings.llm_max_output_tokens,
    )
    res = run(
        items, clients, obj.clock, golden=golden.name, golden_sha256=sha, caps=caps, ml_probs=probs
    )
    if fake:
        res["run_id"] = "fake-" + res["run_id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{res['run_id']}.json"
    path.write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    for name, m in res["metrics"].items():
        click.echo(
            f"{name}: answered {m['answered']}/{m['n']}, brier {m['brier']}, "
            f"json-valid {m['json_valid_first_try']}, tokens "
            f"{m['input_tokens'] + m['output_tokens']}, cost {m['cost_usd']}, "
            f"skips {m['skips']}, stop reasons {m['stop_reasons']}"
        )
    click.echo(f"written: {path}")
