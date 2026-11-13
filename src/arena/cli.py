"""`arena` command-line interface.

Common options go before the group: `arena --ledger-dir _ledger --date 2026-11-12 ledger verify`.
Commands whose task is not built yet say so and exit with status 2.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import click

from arena.clock import Clock, SystemClock
from arena.config import Settings
from arena.ledger import Ledger, layout
from arena.models import Question


@dataclass
class Ctx:
    """Shared state handed to every command."""

    settings: Settings
    ledger: Ledger
    day: date
    dry_run: bool
    clock: Clock


def _not_yet(task: str) -> None:
    click.echo(f"not implemented yet (see {task} in TASKS.md)", err=True)
    sys.exit(2)


@click.group()
@click.option("--ledger-dir", type=click.Path(path_type=Path), default=None,
              help="Ledger checkout (default: ARENA_LEDGER_DIR or ./_ledger).")  # fmt: skip
@click.option("--date", "day", type=click.DateTime(["%Y-%m-%d"]), default=None,
              help="Batch or target date (UTC). Default: today.")  # fmt: skip
@click.option("--dry-run", is_flag=True, help="Do everything except write or push.")
@click.version_option(package_name="forecast-arena")
@click.pass_context
def main(ctx: click.Context, ledger_dir: Path | None, day: object, dry_run: bool) -> None:
    """Forecast Arena: questions, forecasts, resolutions, scores and the public site."""
    settings = Settings.from_env()
    clock = SystemClock()
    the_day = day.date() if day is not None else clock.now().date()  # type: ignore[attr-defined]
    ctx.obj = Ctx(
        settings=settings,
        ledger=Ledger(ledger_dir or settings.ledger_dir),
        day=the_day,
        dry_run=dry_run,
        clock=clock,
    )


# ----- ledger --------------------------------------------------------------------------
@main.group()
def ledger() -> None:
    """Inspect, seal and verify the append-only ledger."""


@main.group()
def health() -> None:
    """Health checks after every job and the incident issue (SPEC 12)."""


@health.command("check")
@click.option("--job", required=True, type=click.Choice(["morning", "resolve", "weekly"]))
@click.option("--report", "report_path", type=click.Path(path_type=Path), default=None,
              help="Also write the report as JSON here.")  # fmt: skip
@click.option("--force-fail", is_flag=True, help="Add a failing check (dry-run tests only).")
@click.option("--record", is_flag=True, help="Also write the report to the ledger (health/).")
@click.pass_obj
def health_check(
    obj: Ctx, job: str, report_path: Path | None, force_fail: bool, record: bool
) -> None:
    """Run the health checks against the ledger; exit 1 if any fails."""
    from arena.ops.health import run_checks
    from arena.ops.official import record_health

    now = obj.clock.now()
    rep = run_checks(obj.ledger, job, now, force_fail=force_fail)
    click.echo(rep.markdown())
    if report_path is not None:
        report_path.write_text(rep.to_json(), encoding="utf-8")
    if record:
        click.echo(f"recorded: {record_health(obj.ledger, rep.to_json(), job, now.date())}")
    sys.exit(0 if rep.ok else 1)


@main.group()
def official() -> None:
    """The pre-registered official start (SPEC 2.9)."""


@official.command("update")
@click.option("--push", is_flag=True, help="Commit and push the ledger afterwards.")
@click.pass_obj
def official_update(obj: Ctx, push: bool) -> None:
    """Evaluate the clean-day rule; write meta/official_start.json once when due."""
    from arena.ops.official import update_official_start

    now = obj.clock.now()
    dec = update_official_start(obj.ledger, now, obj.settings.official_start_not_before)
    for st in dec.statuses[-7:]:
        click.echo(f"{st.day}: {'clean' if st.clean else '; '.join(st.reasons)}")
    click.echo(dec.summary())
    if push and obj.settings.ledger_remote and not obj.dry_run:
        _push(obj, obj.settings.ledger_remote, "health", now.date())


@health.command("incident")
@click.option("--report", "report_path", type=click.Path(path_type=Path), required=True)
@click.option("--job-status", required=True, help="The workflow's job status.")
@click.option("--run-url", required=True)
@click.option("--repo", default=None, help="owner/name (default: the current repository).")
def health_incident(report_path: Path, job_status: str, run_url: str, repo: str | None) -> None:
    """Open, update or close the single `incident` issue (needs `gh` and a token)."""
    import json as _json

    from arena.ops.health import incident_body, sync_incident

    report = _json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else None
    healthy = job_status == "success" and report is not None and bool(report.get("ok"))
    click.echo(sync_incident(healthy, incident_body(report, job_status, run_url), repo=repo))


@ledger.command("verify")
@click.option("--git", "with_git", is_flag=True, help="Also check commit times from history.")
@click.pass_obj
def ledger_verify(obj: Ctx, with_git: bool) -> None:
    """Recompute seals and the chain; check every forecast precedes its lock."""
    from arena.ledger.verify import verify

    rep = verify(obj.ledger)
    if with_git:
        from arena.ledger.gitcheck import verify_git

        rep.errors.extend(verify_git(obj.ledger))
    click.echo(rep.summary())
    sys.exit(0 if rep.ok else 1)


@ledger.command("seal-batch")
@click.pass_obj
def ledger_seal_batch(obj: Ctx) -> None:
    """Write the batch seal for --date (idempotent)."""
    from arena.ledger.seal import seal_batch

    if obj.dry_run:
        click.echo(f"dry run: would seal batch {obj.day}")
        return
    seal = seal_batch(obj.ledger, obj.day, obj.clock)
    click.echo(f"batch {seal.batch_date} sealed: {len(seal.files)} files")


@ledger.command("seal-days")
@click.pass_obj
def ledger_seal_days(obj: Ctx) -> None:
    """Seal every finished, unsealed day in order (idempotent)."""
    from arena.ledger.seal import seal_pending_days

    if obj.dry_run:
        click.echo("dry run: would seal pending days")
        return
    for seal in seal_pending_days(obj.ledger, obj.clock):
        click.echo(f"day {seal.day} sealed: chain {seal.chain_sha256[:12]}")


# ----- questions -----------------------------------------------------------------------
@main.group()
def questions() -> None:
    """Generate and list questions."""


@questions.command("list")
@click.pass_obj
def questions_list(obj: Ctx) -> None:
    """List the questions of the batch --date."""
    for rec in obj.ledger.read(layout.questions_path(obj.day)):
        if isinstance(rec, Question):
            click.echo(f"{rec.question_id}\t{rec.text}")


@questions.command("generate")
def questions_generate() -> None:
    """Generate questions for --date (built in T024/T027)."""
    _not_yet("T027")


# ----- data ----------------------------------------------------------------------------
@main.group()
def data() -> None:
    """Fetch and cache source data (git-ignored cache, ARENA_CACHE_DIR)."""


@data.command("backfill")
@click.option("--series", "keys", multiple=True, default=["price_de_lu"], show_default=True,
              help="SMARD series key(s) to backfill.")  # fmt: skip
@click.pass_obj
def data_backfill(obj: Ctx, keys: tuple[str, ...]) -> None:
    """Fetch the full SMARD history into the cache and print a summary."""
    from arena.domains.power_history import backfill
    from arena.sources.http import HttpClient
    from arena.sources.smard import SmardClient

    client = SmardClient(HttpClient(obj.settings.user_agent()), cache_dir=obj.settings.cache_dir)
    for key in keys:
        click.echo(backfill(client, key, until=obj.clock.now()).line())


# ----- the other groups ----------------------------------------------------------------
@main.group()
def forecast() -> None:
    """Run forecasters."""


@forecast.command("run")
def forecast_run() -> None:
    """Run all forecasters for the batch --date (built in T027)."""
    _not_yet("T027")


@main.group()
def resolve() -> None:
    """Resolve questions whose answers are available."""


@resolve.command("run")
def resolve_run() -> None:
    """Resolve whatever is resolvable now (built in T027)."""
    _not_yet("T027")


@main.group()
def score() -> None:
    """Compute scores from the ledger."""


@score.command("show")
@click.pass_obj
def score_show(obj: Ctx) -> None:
    """Print the leaderboard and record counts computed from the ledger."""
    from arena.scoring.core import counts, format_table, leaderboard, load

    rec = load(obj.ledger)
    c = counts(rec)
    click.echo(format_table(leaderboard(rec.scored)))
    click.echo(f"questions={c.questions} resolved={c.resolved} open={c.open} "
               f"voided={c.voided} forecasts={c.forecasts} skips={c.skips}")  # fmt: skip


@main.group()
def site() -> None:
    """Build the static site."""


@site.command("build")
@click.option("--out", "out_dir", type=click.Path(path_type=Path), default=Path("site"),
              show_default=True, help="Output directory.")  # fmt: skip
@click.option("--check-links/--no-check-links", default=True, show_default=True)
@click.pass_obj
def site_build(obj: Ctx, out_dir: Path, check_links: bool) -> None:
    """Build the static site from the ledger, then check internal links."""
    from arena.site.build import build_site
    from arena.site.linkcheck import check_site

    res = build_site(
        obj.ledger,
        out_dir,
        obj.clock,
        site_url=obj.settings.site_url,
        llm_token_cap=obj.settings.llm_max_tokens_per_day,
        evals_dir=Path("evals/results"),
        golden_path=Path("evals/golden/power-2026-10.jsonl"),
        models_dir=Path("docs/models"),
    )
    click.echo(f"site built: {len(res.pages)} pages in {res.out_dir}")
    if check_links:
        errors = check_site(res.out_dir)
        for e in errors:
            click.echo(e, err=True)
        click.echo(f"link check: {'FAIL' if errors else 'PASS'}")
        sys.exit(1 if errors else 0)


@main.group()
def daily() -> None:
    """The scheduled jobs."""


def _sync(obj: Ctx, push: bool) -> str | None:
    """Check out the ledger branch when pushing; returns the remote to push to.

    A dry run with --push still checks the branch out (so it sees the real state) but
    returns None: nothing is pushed, and the job itself works on a throwaway copy."""
    if not push:
        return None
    from arena.ledger.gitsync import ensure_checkout

    remote = obj.settings.ledger_remote
    if not remote:
        raise click.UsageError("--push needs ARENA_LEDGER_REMOTE")
    click.echo(f"ledger checkout: {ensure_checkout(remote, obj.ledger.root)}")
    return None if obj.dry_run else remote


def _push(obj: Ctx, remote: str | None, job: str, day: date) -> None:
    if remote is None:
        return
    from arena.ledger.gitsync import commit_and_push

    sha = commit_and_push(obj.ledger.root, job, day)
    click.echo(f"ledger pushed: {sha}" if sha else "ledger: nothing to push")


@daily.command("morning")
@click.option("--push", is_flag=True, help="Sync with and push to the ledger branch.")
@click.pass_obj
def daily_morning(obj: Ctx, push: bool) -> None:
    """Questions, forecasts, snapshot and batch seal for --date (idempotent)."""
    from arena.ops.jobs import morning
    from arena.ops.wiring import build_domains, build_forecasters

    remote = _sync(obj, push)
    domains = build_domains(obj.settings, obj.clock.now(), ledger=obj.ledger)
    forecasters, guard = build_forecasters(
        obj.ledger, domains, obj.settings, obj.day, dry_run=obj.dry_run, clock=obj.clock
    )

    def attach(rec: object) -> None:
        if guard is not None:
            guard.recorder = rec  # type: ignore[assignment]

    result = morning(obj.ledger, obj.day, obj.clock, domains, forecasters,
                     dry_run=obj.dry_run, on_record=attach)  # fmt: skip
    click.echo(result.line())
    for w in result.warnings:
        click.echo(f"warning: {w}")
    _push(obj, remote, "morning", obj.day)


@daily.command("resolve")
@click.option("--push", is_flag=True, help="Sync with and push to the ledger branch.")
@click.pass_obj
def daily_resolve(obj: Ctx, push: bool) -> None:
    """Resolve what is resolvable now, record revisions, seal finished days."""
    from arena.ops.jobs import resolve
    from arena.ops.wiring import build_domains

    remote = _sync(obj, push)
    now = obj.clock.now()
    domains = build_domains(obj.settings, now, job="resolve", ledger=obj.ledger)
    result = resolve(obj.ledger, obj.clock, domains, dry_run=obj.dry_run)
    click.echo(result.line())
    for w in result.warnings:
        click.echo(f"warning: {w}")
    _push(obj, remote, "resolve", now.date())


@main.group()
def weekly() -> None:
    """The weekly job: retrain, compare, promote by rule."""


@weekly.command("run")
@click.option("--push", is_flag=True, help="Sync with and push to the ledger branch.")
@click.option("--domain", "only", multiple=True, help="Limit to these domains.")
@click.pass_obj
def weekly_run(obj: Ctx, push: bool, only: tuple[str, ...]) -> None:
    """Retrain the power and attention models and promote them by the documented rule."""
    from arena.ops.weekly import weekly as run_weekly
    from arena.ops.wiring import weekly_setup

    remote = _sync(obj, push)
    domains, trainers, cards = weekly_setup(obj.settings, obj.clock.now(), only)
    res = run_weekly(
        obj.ledger,
        obj.clock,
        domains,
        trainers,
        cards=cards,
        dry_run=obj.dry_run,
        mlruns=Path("mlruns"),
    )
    for line in res.lines():
        click.echo(line)
    _push(obj, remote, "weekly", obj.clock.now().date())


@main.group()
def report() -> None:
    """Reports computed from the public record."""


@report.command("backtest-power")
@click.option("--challenger", "challengers", multiple=True,
              type=click.Choice(["lgbm", "mlp", "ets", "sarimax", "chronos"]),
              help="Add a challenger (ml/torch/ts requirements files).")  # fmt: skip
@click.option("--card-type", type=click.Choice(["champion", "lgbm", "mlp", "ts"]),
              default="champion", help="Which model card text to write with --card.")  # fmt: skip
@click.option("--first", type=click.DateTime(["%Y-%m-%d"]), required=True)
@click.option("--last", type=click.DateTime(["%Y-%m-%d"]), required=True)
@click.option("--out", "out_dir", type=click.Path(path_type=Path), default=Path("backtests"))
@click.option(
    "--card",
    type=click.Path(path_type=Path),
    default=None,
    help="Also write the model card (Markdown) here.",
)
@click.pass_obj
def report_backtest_power(
    obj: Ctx,
    first: object,
    last: object,
    out_dir: Path,
    card: Path | None,
    challengers: tuple[str, ...] = (),
    card_type: str = "champion",
) -> None:
    """Walk-forward power backtest from the SMARD cache (ARENA_CACHE_DIR); labelled backtest."""
    from arena.backtest import power as bt
    from arena.backtest.harness import BacktestStore
    from arena.backtest.report import markdown
    from arena.domains.power import PowerDomain
    from arena.domains.power_history import HISTORY_START, PRICE_KEY, PowerHistory
    from arena.sources.http import HttpClient
    from arena.sources.smard import SmardClient

    f, la = first.date(), last.date()  # type: ignore[attr-defined]
    client = SmardClient(HttpClient(obj.settings.user_agent()), cache_dir=obj.settings.cache_dir)
    store = PowerHistory(client).store([PRICE_KEY], HISTORY_START, la + timedelta(days=2))
    run_id = f"power-{f.isoformat()}-{la.isoformat()}-{obj.clock.now():%Y%m%dT%H%M}"
    res = bt.run(PowerDomain(store), f, la, run_id=run_id, challengers=challengers)
    ids = [bt.CHALLENGER_IDS[c] for c in challengers]
    names = ["base_rate", "persistence", "ml", *ids]
    comps = [("ml", "base_rate"), ("ml", "persistence"), ("persistence", "base_rate")]
    comps += [(c, "ml") for c in ids]
    comps += [(c, "base_rate") for c in ids]
    text = markdown(f"Power backtest {f} to {la}", res.records, names, comps, bt.NOTES)
    path = BacktestStore(out_dir).write(
        run_id, res.records, {"domain": "power", "first": f, "last": la}
    )
    (path / "report.md").write_text(text, encoding="utf-8")
    click.echo(text)
    if card is not None:
        from arena.backtest import cards

        make = {"champion": cards.power_card, "lgbm": cards.power_lgbm_card,
                "mlp": cards.power_mlp_card, "ts": cards.power_ts_card}[card_type]  # fmt: skip
        card.parent.mkdir(parents=True, exist_ok=True)
        card.write_text(make(text, run_id), encoding="utf-8")
        click.echo(f"model card written: {card}")


@report.command("backtest-markets")
@click.option("--first", type=click.DateTime(["%Y-%m-%d"]), required=True)
@click.option("--last", type=click.DateTime(["%Y-%m-%d"]), required=True)
@click.option("--out", "out_dir", type=click.Path(path_type=Path), default=Path("backtests"))
@click.option("--card", type=click.Path(path_type=Path), default=None)
@click.pass_obj
def report_backtest_markets(
    obj: Ctx, first: object, last: object, out_dir: Path, card: Path | None
) -> None:
    """Walk-forward markets backtest on ECB fixings since 2019; labelled backtest."""
    from arena.backtest import markets as bt
    from arena.backtest.cards import markets_card
    from arena.backtest.harness import BacktestStore
    from arena.backtest.report import markdown
    from arena.domains.markets import PAIRS, markets_domain_from_rates
    from arena.sources.ecb import EcbClient
    from arena.sources.http import HttpClient

    f, la = first.date(), last.date()  # type: ignore[attr-defined]
    r = EcbClient(HttpClient(obj.settings.user_agent())).rates(
        list(PAIRS), date(2019, 1, 1), la + timedelta(days=10)
    )
    run_id = f"markets-{f.isoformat()}-{la.isoformat()}-{obj.clock.now():%Y%m%dT%H%M}"
    res = bt.run(markets_domain_from_rates(r.rates, r.url, r.sha256), f, la, run_id=run_id)
    text = markdown(
        f"Markets backtest {f} to {la}",
        res.records,
        ["base_rate", "persistence", "ml"],
        [("ml", "base_rate"), ("ml", "persistence"), ("persistence", "base_rate")],
        bt.NOTES,
    )
    path = BacktestStore(out_dir).write(
        run_id, res.records, {"domain": "markets", "first": f, "last": la}
    )
    (path / "report.md").write_text(text, encoding="utf-8")
    click.echo(text)
    if card is not None:
        card.parent.mkdir(parents=True, exist_ok=True)
        card.write_text(markets_card(text, run_id), encoding="utf-8")
        click.echo(f"model card written: {card}")


@report.command("backtest-attention")
@click.option("--first", type=click.DateTime(["%Y-%m-%d"]), required=True)
@click.option("--last", type=click.DateTime(["%Y-%m-%d"]), required=True)
@click.option("--out", "out_dir", type=click.Path(path_type=Path), default=Path("backtests"))
@click.option("--card", type=click.Path(path_type=Path), default=None)
@click.pass_obj
def report_backtest_attention(
    obj: Ctx, first: object, last: object, out_dir: Path, card: Path | None
) -> None:
    """Walk-forward attention backtest (top lists from the cache; live per-article calls)."""
    from arena.backtest import attention as bt
    from arena.backtest.cards import attention_card
    from arena.backtest.harness import BacktestStore
    from arena.backtest.report import markdown
    from arena.domains.attention import AttentionDomain
    from arena.sources.http import HttpClient
    from arena.sources.wikimedia import WikimediaClient

    f, la = first.date(), last.date()  # type: ignore[attr-defined]
    http = HttpClient(obj.settings.user_agent(), backoff=4.0, retries=4)
    dom = AttentionDomain(WikimediaClient(http, cache_dir=obj.settings.cache_dir))
    run_id = f"attention-{f.isoformat()}-{la.isoformat()}-{obj.clock.now():%Y%m%dT%H%M}"
    res = bt.run(dom, f, la, run_id=run_id)
    text = markdown(
        f"Attention backtest {f} to {la}",
        res.records,
        ["base_rate", "persistence", "ml"],
        [("ml", "base_rate"), ("ml", "persistence")],
        bt.NOTES,
    )
    path = BacktestStore(out_dir).write(
        run_id, res.records, {"domain": "attention", "first": f, "last": la}
    )
    (path / "report.md").write_text(text, encoding="utf-8")
    click.echo(text)
    if card is not None:
        card.parent.mkdir(parents=True, exist_ok=True)
        card.write_text(attention_card(text, run_id), encoding="utf-8")
        click.echo(f"model card written: {card}")


@report.command("cv")
@click.pass_obj
def report_cv(obj: Ctx) -> None:
    """Headline numbers for a CV, from the ledger only."""
    from arena.scoring.cv import cv_lines

    for line in cv_lines(obj.ledger):
        click.echo(line)


# ----- llm -----------------------------------------------------------------------------
@main.group()
def llm() -> None:
    """Checks of the configured LLM provider."""


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
        click.echo("model_missing: ARENA_LLM_PROVIDER, ARENA_LLM_MODEL and ARENA_LLM_API_KEY "
                   "must all be set", err=True)  # fmt: skip
        sys.exit(1)
    res = run_smoke(client, obj.settings.llm_max_output_tokens)
    for line in res.lines:
        click.echo(line)
    sys.exit(0 if res.ok else 1)


@main.group("eval")
def eval_group() -> None:
    """LLM evaluation on a frozen golden set (T124; never part of the live record)."""


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
@click.option("--variant", "variants", multiple=True,
              type=click.Choice(["llm_plain", "llm_context", "llm_local"]),
              default=("llm_plain", "llm_context"))  # fmt: skip
@click.option("--limit", type=int, default=None, help="Stratified seeded sample size.")
@click.option("--fake", is_flag=True, help="FakeLLM answers (the CI gate; no network).")
@click.option("--max-tokens", type=int, default=60_000, help="Hard token cap for this run.")
@click.option("--out", "out_dir", type=click.Path(path_type=Path), default=Path("evals/results"))
@click.pass_obj
def eval_run(
    obj: Ctx, golden: Path, variants: tuple[str, ...], limit: int | None, fake: bool,
    max_tokens: int, out_dir: Path,
) -> None:  # fmt: skip
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
            click.echo("refused: live LLM calls run only inside GitHub Actions (AGENTS.md S8)",
                       err=True)  # fmt: skip
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
    caps = EvalCaps(max_requests=max(1, 2 * len(items) * len(clients)), max_tokens=max_tokens,
                    max_output_tokens=obj.settings.llm_max_output_tokens)  # fmt: skip
    res = run(items, clients, obj.clock, golden=golden.name, golden_sha256=sha, caps=caps)
    if fake:
        res["run_id"] = "fake-" + res["run_id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{res['run_id']}.json"
    path.write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    for name, m in res["metrics"].items():
        click.echo(f"{name}: answered {m['answered']}/{m['n']}, brier {m['brier']}, "
                   f"json-valid {m['json_valid_first_try']}, tokens "
                   f"{m['input_tokens'] + m['output_tokens']}, cost {m['cost_usd']}, "
                   f"skips {m['skips']}, stop reasons {m['stop_reasons']}")  # fmt: skip
    click.echo(f"written: {path}")


@main.command("mcp")
@click.pass_obj
def mcp_command(obj: Ctx) -> None:
    """Serve the ledger read-only over MCP on stdio (needs requirements-mcp.txt)."""
    from arena.mcp_server import build_server

    build_server(obj.ledger).run("stdio")


if __name__ == "__main__":
    main()
