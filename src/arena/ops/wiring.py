"""Build the live domains and forecasters from settings (used by the CLI and workflows)."""

from __future__ import annotations

import importlib.util
from collections.abc import Callable, Sequence
from datetime import date, datetime, timedelta
from functools import partial
from typing import TYPE_CHECKING, Any

from arena.agent.forecaster import AgentForecaster
from arena.agent.tools import GdeltBackend, wikipedia_summary
from arena.clock import Clock, SystemClock
from arena.config import WEATHER_STATIONS, Settings
from arena.domains.attention import AttentionDomain, titles_from_questions
from arena.domains.base import AsOfStore, Domain
from arena.domains.crypto import COINS, crypto_domain_from_prices
from arena.domains.markets import PAIRS, markets_domain_from_rates
from arena.domains.power import PowerDomain
from arena.domains.power_history import PRICE_KEY, berlin_date, to_observations
from arena.domains.weather import WeatherDomain, weather_domain_from_responses
from arena.forecasters.base import Forecaster, LedgerHistory
from arena.forecasters.baselines import BaseRate, Persistence
from arena.forecasters.llm import LLMContext, LLMPlain
from arena.forecasters.replay import CombinedHistory, ReplayHistory
from arena.ledger import Ledger
from arena.llm.budget import BudgetGuard, Caps, GuardedLLM, usage_from_manifests
from arena.llm.client import LLMClient
from arena.llm.factory import client_from_settings
from arena.llm.tracing import Tracer, TracingLLM
from arena.models import Question
from arena.sources.brightsky import BrightSkyClient
from arena.sources.coingecko import CoinGeckoClient
from arena.sources.ecb import EcbClient
from arena.sources.http import HttpClient
from arena.sources.smard import FILTERS, SmardClient, berlin_day_bounds
from arena.sources.wikimedia import WikimediaClient

if TYPE_CHECKING:
    from arena.ops.weekly import TrainerSpec

#: Days of history a live power domain loads: replay window (200) + longest template
#: window (60) + margin.
POWER_HISTORY_DAYS = 280


def power_domain_from_client(
    client: SmardClient,
    now: datetime,
    days: int = POWER_HISTORY_DAYS,
    on_skip: Callable[[str], None] | None = None,
) -> PowerDomain:
    """A power domain with `days` of price history up to D+1, with chunk evidence."""
    today = berlin_date(now)
    start = berlin_day_bounds(today - timedelta(days=days))[0]
    end = berlin_day_bounds(today + timedelta(days=1))[1]
    store = AsOfStore()
    evidence: dict[date, tuple[str, str]] = {}
    for chunk in client.chunks_for(FILTERS[PRICE_KEY], start, end):
        for obs in to_observations(PRICE_KEY, [p for p in chunk.points if start <= p.start < end]):
            store.add(obs)
        for p in chunk.points:
            evidence[berlin_date(p.start)] = (chunk.url, chunk.sha256)
    return PowerDomain(store, evidence=evidence.get, on_skip=on_skip)


#: Calendar days of ECB fixings loaded: 250 returns for the `up` window plus ~200 replayed
#: batches (about 450 publication days, ~650 calendar days).
MARKETS_DAYS = 660
#: Daily crypto prices fetched per coin (the Demo API keeps 365 days).
CRYPTO_DAYS = 365

#: Observation days loaded for weather: morning runs replay ~200 batches (each needing a
#: 90-day window); resolve runs only need the last days within the grace period.
WEATHER_DAYS = {"morning": 300, "resolve": 10}


def weather_domain_live(
    client: BrightSkyClient,
    now: datetime,
    days: int,
    with_forecast: bool,
    on_skip: Callable[[str], None] | None = None,
) -> WeatherDomain:
    """Fetch observations (and tomorrow's MOSMIX forecast) for every station."""
    today = berlin_date(now)
    obs, fc = {}, {}
    for city, (station, _) in WEATHER_STATIONS.items():
        obs[city] = client.weather(station, today - timedelta(days=days), today)
        if with_forecast:
            tomorrow = today + timedelta(days=1)
            fc[city] = client.weather(station, tomorrow, tomorrow)
    return weather_domain_from_responses(WEATHER_STATIONS, obs, fc, now, on_skip=on_skip)


def build_domains(
    settings: Settings,
    now: datetime,
    on_skip: Callable[[str], None] | None = None,
    job: str = "morning",
    ledger: Ledger | None = None,
) -> list[Domain]:
    """The domains enabled in settings, loaded from the live sources (with the cache)."""
    http = HttpClient(settings.user_agent())
    out: list[Domain] = []
    for name in settings.domains:
        if name == "power":
            client = SmardClient(http, cache_dir=settings.cache_dir)
            out.append(power_domain_from_client(client, now, on_skip=on_skip))
        elif name == "weather":
            out.append(
                weather_domain_live(
                    BrightSkyClient(http), now, WEATHER_DAYS[job], job == "morning", on_skip=on_skip
                )
            )
        elif name == "markets":
            start = berlin_date(now) - timedelta(days=MARKETS_DAYS)
            r = EcbClient(http).rates(list(PAIRS), start)
            out.append(markets_domain_from_rates(r.rates, r.url, r.sha256, on_skip=on_skip))
        elif name == "attention":
            questions = (
                []
                if ledger is None
                else [q for _, q in ledger.iter_family("questions") if isinstance(q, Question)]
            )

            def recent(project: str, batch: date, qs: list[Question] = questions) -> set[str]:
                return titles_from_questions(qs, project, batch)

            out.append(
                AttentionDomain(
                    WikimediaClient(http, cache_dir=settings.cache_dir),
                    recent_titles=recent,
                    on_skip=on_skip,
                )
            )
        elif name == "crypto":
            if settings.coingecko_api_key is None:
                # The keyless API is not meant for scheduled use (docs/SOURCES.md): no key,
                # no crypto questions today, and the run manifest says why.
                (on_skip or (lambda m: None))("crypto: ARENA_COINGECKO_API_KEY is not set")
                continue
            cg = CoinGeckoClient(http, settings.coingecko_api_key.get_secret_value())
            fetched = {coin: cg.daily(coin, CRYPTO_DAYS) for coin in COINS}
            out.append(
                crypto_domain_from_prices(
                    {c: f.prices for c, f in fetched.items()},
                    {c: (f.url, f.sha256) for c, f in fetched.items()},
                    on_skip=on_skip,
                )
            )
        else:
            raise ValueError(f"domain {name!r} is not available yet")
    return out


def _local_forecaster(settings: Settings, n: int, tracer: Tracer, clock: Clock) -> Forecaster:
    """`llm_local` on the CPU: no API cost, so it runs in dry runs too and is never wrapped
    by the API budget guard. If the library or the model cannot be loaded, the forecaster
    has no client and records `model_missing` skips (I6), and the other forecasters run."""
    from arena.forecasters.llm import LLMLocal
    from arena.llm import local

    try:
        backend = local.llama_backend(local.model_path(settings.models_dir / "gguf"))
    except Exception as exc:  # ImportError, download or load failure
        return LLMLocal(None, n, missing=f"local model unavailable: {type(exc).__name__}: {exc}")
    return LLMLocal(TracingLLM(local.LlamaCppLLM(backend), tracer, clock), n)


def build_forecasters(
    ledger: Ledger,
    domains: Sequence[Domain],
    settings: Settings | None = None,
    day: date | None = None,
    *,
    dry_run: bool = False,
    llm: LLMClient | None = None,
    clock: Clock | None = None,
) -> tuple[list[Forecaster], BudgetGuard | None]:
    """Baselines over live history (filled with replayed history, SPEC 8.1) and the LLM
    forecasters behind the daily budget guard. Dry runs get no LLM client: their manifests
    never reach the ledger, so their usage could not be counted against the caps."""
    replays = [ReplayHistory(d) for d in domains if getattr(d, "replayable", True)]
    history = CombinedHistory(LedgerHistory(ledger), replays)
    out: list[Forecaster] = [BaseRate(history), Persistence(history)]
    guard = None
    if settings is None:
        return out, None
    client = llm if llm is not None else (None if dry_run else client_from_settings(settings))
    if client is not None and day is not None:
        guard = BudgetGuard(Caps.from_settings(settings), usage_from_manifests(ledger, day))
        client = GuardedLLM(client, guard)
    tracer = Tracer()  # T123: one span per model call, written with the day's traces
    clk = clock if clock is not None else SystemClock()
    if client is not None:
        client = TracingLLM(client, tracer, clk)
    n = settings.llm_questions_per_domain
    http = HttpClient(settings.user_agent())
    retriever = None
    if settings.agent_rag and client is not None:
        # No silent fallback: if fastembed is missing this raises and the run fails.
        from arena.agent.retrieval import FastEmbedder, PastQuestions

        embedder = FastEmbedder(cache_dir=settings.cache_dir / "fastembed")
        retriever = PastQuestions.from_ledger(ledger, embedder)
    agent = AgentForecaster(
        client,
        per_domain=n,
        max_tool_calls=settings.agent_max_tool_calls,
        peers={"base_rate": out[0]},
        retriever=retriever,
        prompt_version="v2" if retriever is not None else "v1",
        news=None if llm is not None else GdeltBackend(http),
        wiki=None if llm is not None else partial(wikipedia_summary, http),
    )
    out += [LLMPlain(client, n), LLMContext(client, n), agent]
    if settings.llm_local:
        out.append(_local_forecaster(settings, n, tracer, clk))
    if settings.agent_graph:
        # No silent fallback: if langgraph is missing this raises and the run fails.
        from arena.agent.graph import GraphAgentForecaster

        out.append(
            GraphAgentForecaster(
                client,
                max_tool_calls=settings.agent_max_tool_calls,
                peers={"base_rate": out[0]},
                news=agent.news,
                wiki=agent.wiki,
                retriever=retriever,
            )
        )
    for f in out:  # per-call output cap from the settings (thinking counts against it)
        if hasattr(f, "max_output_tokens"):
            f.max_output_tokens = settings.llm_max_output_tokens
    return out, guard


def weekly_setup(
    settings: Settings, now: datetime, only: Sequence[str] = ()
) -> tuple[dict[str, Domain], dict[str, TrainerSpec], dict[str, Callable[[Any], str]]]:
    """Domains, trainers and card writers for the weekly job (power and attention)."""
    from arena.backtest.cards import ATTENTION_CARD, POWER_CARD
    from arena.domains.power_history import HISTORY_START, PowerHistory
    from arena.forecasters import ml_attention, ml_power

    http = HttpClient(settings.user_agent())
    domains: dict[str, Domain] = {}
    trainers: dict[str, TrainerSpec] = {}
    today = berlin_date(now)
    if not only or "power" in only:
        client = SmardClient(http, cache_dir=settings.cache_dir)
        pdom = PowerDomain(
            PowerHistory(client).store([PRICE_KEY], HISTORY_START, today + timedelta(days=1))
        )
        domains["power"] = pdom
        fams: dict[str, Callable[[date], Any]] = {
            "hgb": lambda cut: ml_power.train(pdom, cut, folds=2, max_iter=100)
        }
        if importlib.util.find_spec("lightgbm") and importlib.util.find_spec("optuna"):
            from arena.forecasters import ml_power_lgbm

            fams["lgbm"] = lambda cut: ml_power_lgbm.train_lgbm(pdom, cut, n_trials=20, folds=2)
        if importlib.util.find_spec("torch"):
            from arena.forecasters import ml_power_torch

            fams["mlp"] = lambda cut: ml_power_torch.train_torch(pdom, cut, folds=2)
        trainers["power"] = fams
    if not only or "attention" in only:
        adom = AttentionDomain(WikimediaClient(http, cache_dir=settings.cache_dir))
        domains["attention"] = adom
        afams: dict[str, Callable[[date], Any]] = {
            "hgb": lambda cut: ml_attention.train(
                adom, cut - timedelta(days=65), cut - timedelta(days=5)
            )
        }
        if importlib.util.find_spec("lightgbm"):
            afams["lgbm"] = lambda cut: ml_attention.train_lgbm(
                adom, cut - timedelta(days=65), cut - timedelta(days=5)
            )
        trainers["attention"] = afams

    def card(text: str) -> Callable[[Any], str]:
        return lambda d: (
            text + "\n## Weekly evaluation\n\n"
            f"Window {d.window_first} to {d.window_last}, {d.n} questions; "
            f"candidate Brier {d.brier_candidate}, current {d.brier_current}.\n"
        )

    return domains, trainers, {"power": card(POWER_CARD), "attention": card(ATTENTION_CARD)}
