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
@click.option("--first", type=click.DateTime(["%Y-%m-%d"]), required=True)
@click.option("--last", type=click.DateTime(["%Y-%m-%d"]), required=True)
@click.option("--out", type=click.Path(path_type=Path), required=True)
@click.pass_obj
def eval_build(obj: Ctx, first: object, last: object, out: Path) -> None:
    """Freeze a golden set of power questions from the SMARD cache (ARENA_CACHE_DIR)."""
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


@eval_group.command("run")
@click.option("--golden", type=click.Path(exists=True, path_type=Path), required=True)
@click.option(
    "--variant",
    "variants",
    multiple=True,
    type=click.Choice(["llm_plain", "llm_context", "llm_local"]),
    default=("llm_plain", "llm_context"),
)
@click.option("--limit", type=int, default=None, help="Stratified seeded sample size.")
@click.option("--fake", is_flag=True, help="FakeLLM answers (the CI gate; no network).")
@click.option("--max-tokens", type=int, default=60_000, help="Hard token cap for this run.")
@click.option("--out", "out_dir", type=click.Path(path_type=Path), default=Path("evals/results"))
@click.pass_obj
def eval_run(
    obj: Ctx,
    golden: Path,
    variants: tuple[str, ...],
    limit: int | None,
    fake: bool,
    max_tokens: int,
    out_dir: Path,
) -> None:
    """Run the variants on the golden set and write `evals/results/<run_id>.json`."""
    import json
    import os

    from arena.evals.golden import load
    from arena.evals.run import EvalCaps, run, sample
    from arena.llm.client import FakeLLM, LLMClient

    items, sha = load(golden)
    items = sample(items, limit)
    clients: dict[str, LLMClient] = {}
    if fake:
        answer = json.dumps({"probability": 0.5, "rationale": "fake", "key_factors": []})
        clients = {v: FakeLLM(lambda s, t, tools: answer) for v in variants}
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
        max_requests=max(1, 2 * len(items) * len(clients)),
        max_tokens=max_tokens,
        max_output_tokens=obj.settings.llm_max_output_tokens,
    )
    res = run(items, clients, obj.clock, golden=golden.name, golden_sha256=sha, caps=caps)
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
