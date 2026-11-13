"""Commands that publish: the static site build and the backtest and CV reports."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import click

from arena.cli import (
    Ctx,
    report,
    site,
)


@site.command("build")
@click.option(
    "--out",
    "out_dir",
    type=click.Path(path_type=Path),
    default=Path("site"),
    show_default=True,
    help="Output directory.",
)
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
        dashboard_url=obj.settings.dashboard_url,
        marts_dir=Path("analytics/dbt/models/marts"),
    )
    click.echo(f"site built: {len(res.pages)} pages in {res.out_dir}")
    if check_links:
        errors = check_site(res.out_dir)
        for e in errors:
            click.echo(e, err=True)
        click.echo(f"link check: {'FAIL' if errors else 'PASS'}")
        sys.exit(1 if errors else 0)


@report.command("backtest-power")
@click.option(
    "--challenger",
    "challengers",
    multiple=True,
    type=click.Choice(["lgbm", "mlp", "ets", "sarimax", "chronos"]),
    help="Add a challenger (ml/torch/ts requirements files).",
)
@click.option(
    "--card-type",
    type=click.Choice(["champion", "lgbm", "mlp", "ts"]),
    default="champion",
    help="Which model card text to write with --card.",
)
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

        make = {
            "champion": cards.power_card,
            "lgbm": cards.power_lgbm_card,
            "mlp": cards.power_mlp_card,
            "ts": cards.power_ts_card,
        }[card_type]
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
