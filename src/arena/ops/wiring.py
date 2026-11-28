"""Build the live domains and forecasters from settings (used by the CLI and workflows)."""

from __future__ import annotations

import importlib.util
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import partial
from typing import TYPE_CHECKING, Any

from arena.agent.forecaster import AgentForecaster
from arena.agent.hybrid import AgentHybrid
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
from arena.forecasters.ml import DomainModel, MLForecaster, ModelLoadFailure
from arena.forecasters.replay import CombinedHistory, ReplayHistory
from arena.ledger import Ledger, layout
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

#: Observation days loaded for weather: morning and evening runs replay ~200 batches (each
#: needing a 90-day window); resolve runs only need the last days within the grace period.
WEATHER_DAYS = {"evening": 300, "morning": 300, "resolve": 10}


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
                    news=gdelt_news(http, now, on_skip) if settings.sentiment else None,
                )
            )
        else:
            raise ValueError(f"domain {name!r} is not available yet")
    return out


#: GDELT days fetched per coin for the morning context (a 15-day window is stored).
GDELT_DAYS = 30


def gdelt_news(
    http: HttpClient,
    now: datetime,
    on_skip: Callable[[str], None] | None = None,
    pause: float | None = None,
) -> Callable[[str, datetime], dict[str, Any] | None]:
    """A (coin, asof) -> GDELT aggregates provider (T373, flag `ARENA_SENTIMENT`).

    Fetches the last 30 days of tone and article counts once per coin; a coin whose request
    fails has no `gdelt` entry today and the reason is recorded (I6). Only aggregate numbers
    are kept, never article text (S7).
    """
    from arena.forecasters.sentiment import gdelt_context, outage_days
    from arena.sources.gdelt_tone import GdeltClient, GdeltError
    from arena.sources.http import HttpError

    skip = on_skip or (lambda m: None)
    client = GdeltClient(http) if pause is None else GdeltClient(http, pause, lambda s: None)
    end = now.date()
    start = end - timedelta(days=GDELT_DAYS - 1)
    covered = {start + timedelta(days=i) for i in range(GDELT_DAYS)}
    fetched: dict[str, Any] = {}
    for coin in COINS:
        try:
            fetched[coin] = client.daily(coin, start, end)
        except (GdeltError, HttpError) as exc:
            skip(f"crypto/gdelt/{coin}: {type(exc).__name__}: {str(exc)[:120]}")

    # a day without counts for every fetched coin is a GDELT outage, not a quiet day (T402)
    outages = outage_days({c: n.count for c, n in fetched.items()}, covered) if fetched else set()

    def provider(coin: str, asof: datetime) -> dict[str, Any] | None:
        news = fetched.get(coin)
        if news is None:
            return None
        return gdelt_context(news.tone, news.count, covered, asof, unknown_days=outages)

    return provider


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


def _ft_forecaster(settings: Settings, n: int) -> Forecaster:
    """`llm_local_ft`: no API cost, so it also runs in dry runs. A missing pin, a failed or
    mismatching download or a load failure give `model_missing` skips with the reason (I6)."""
    from arena.forecasters.llm_ft import LLMLocalFT
    from arena.lab import artefacts
    from arena.lab.ft_runtime import LlamaScorer

    art = artefacts.load_artefact()
    if art is None:
        return LLMLocalFT(None, None, n)
    try:
        path = artefacts.fetch(art, settings.models_dir / "ft", settings.user_agent())
        scorer = LlamaScorer(path, model=art.name, yes_id=art.yes_id, no_id=art.no_id)
    except Exception as exc:  # ImportError, download, hash or load failure
        return LLMLocalFT(
            None, art, n, missing=f"fine-tuned model unavailable: {type(exc).__name__}: {exc}"
        )
    return LLMLocalFT(scorer, art, n)


def _hybrid_forecasters(
    ledger: Ledger,
    settings: Settings,
    client: LLMClient | None,
    agent: AgentForecaster,
    retriever: Any,
    peers: dict[str, Forecaster],
    classes: Sequence[type[AgentHybrid]],
) -> list[Forecaster]:
    """`agent_hybrid` (and its skills variant) next to `agent`, sharing one retriever and one
    reranker. A missing reranker or retriever is a visible `model_missing` skip, not a failure of
    the whole run (the lock-critical job must go on)."""
    from arena.agent.retrieval import CrossEncoderReranker, FastEmbedder, PastQuestions

    common: dict[str, Any] = {
        "per_domain": settings.llm_questions_per_domain,
        "max_tool_calls": settings.agent_max_tool_calls,
        "peers": peers,
        "news": agent.news,
        "wiki": agent.wiki,
    }
    try:
        cache = settings.cache_dir / "fastembed"
        if retriever is None:
            retriever = PastQuestions.from_ledger(ledger, FastEmbedder(cache_dir=cache))
        rr = CrossEncoderReranker(cache_dir=cache)
    except Exception as exc:  # ImportError, download or load failure
        reason = f"hybrid retrieval unavailable: {type(exc).__name__}: {exc}"
        return [cls(client, missing=reason, **common) for cls in classes]
    return [
        cls(client, retriever=retriever, reranker=rr.score, reranker_name=rr.name, **common)
        for cls in classes
    ]


def _conformal_margins(ledger: Ledger) -> dict[str, dict[str, float]]:
    """CQR margins of the central 80% band per power statistic, from the newest weekly summary
    that has them (T276b). Missing or unreadable summaries simply mean no interval is shown."""
    from arena.ops import weekly

    try:
        for s in weekly.summaries(ledger):
            rows = (s.get("conformal") or {}).get("power") or []
            margins = {r["stat"]: float(r["margin80"]) for r in rows if "margin80" in r}
            if margins:
                return {"power": margins}
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return {}


def live_ml(ledger: Ledger, domains: Sequence[Domain], asof: datetime) -> MLForecaster:
    """Load the visible champions once; one bad artifact only disables its own domain."""
    from arena.forecasters import registry
    from arena.forecasters.ml_crypto import CryptoModel
    from arena.forecasters.ml_markets import MarketsModel
    from arena.forecasters.ml_weather import WeatherRules

    rules: dict[str, Callable[[], DomainModel]] = {
        "weather": WeatherRules,
        "markets": MarketsModel,
        "crypto": CryptoModel,
    }
    models: dict[str, DomainModel] = {}
    errors: dict[str, ModelLoadFailure] = {}
    hashes: dict[str, str] = {}
    for name in sorted({d.name for d in domains}):
        if name in rules:
            models[name] = rules[name]()
            continue
        version = None
        try:
            version = registry.current_version(ledger, name, asof=asof)
            if version is None:
                continue
            info = registry.model_info(ledger, name, version)
            created = datetime.fromisoformat(info.meta["created_at"])
            if created.tzinfo is None or created > asof:
                raise registry.RegistryError("model artifact was not available at forecast time")
            model = registry.load(ledger, name, version)
            train_end = getattr(model, "train_end", None)
            if train_end is not None and train_end > asof.date():
                raise registry.RegistryError("model training cutoff is after forecast time")
            models[name] = model
            hashes[name] = info.sha256
        except Exception as exc:
            errors[name] = ModelLoadFailure(
                version, f"{name} model load failed: {type(exc).__name__}: {exc}"[:300]
            )
    return MLForecaster(
        models, load_errors=errors, artifact_hashes=hashes, conformal=_conformal_margins(ledger)
    )


def live_ensemble(ledger: Ledger, asof: datetime) -> Forecaster | None:
    """The ensemble (SPEC 8.6) once it is active, else None (inactive is not a failure).

    Needs the official record to have started and at least 300 resolved common-set forecasts
    from it; rehearsal days never train it."""
    import json

    from arena.forecasters.ensemble import EnsembleForecaster, train
    from arena.scoring.core import load

    if not ledger.exists(layout.OFFICIAL_START_PATH):
        return None
    value = json.loads(ledger.read_bytes(layout.OFFICIAL_START_PATH)).get("official_start")
    if not value:
        return None
    model = train(load(ledger).scored, date.fromisoformat(str(value)), asof)
    return EnsembleForecaster(model) if model is not None else None


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
    clk = clock if clock is not None else SystemClock()
    ml = live_ml(ledger, domains, clk.now())
    out: list[Forecaster] = [BaseRate(history), Persistence(history), ml]
    guard = None
    if settings is None:
        return out, None
    client = llm if llm is not None else (None if dry_run else client_from_settings(settings))
    if client is not None and day is not None:
        guard = BudgetGuard(Caps.from_settings(settings), usage_from_manifests(ledger, day))
        client = GuardedLLM(client, guard)
    tracer = Tracer()  # T123: one span per model call, written with the day's traces
    if client is not None:
        client = TracingLLM(client, tracer, clk)
    http = HttpClient(settings.user_agent())
    retriever = None
    if settings.agent_rag and client is not None:
        # No silent fallback: if fastembed is missing this raises and the run fails.
        from arena.agent.retrieval import FastEmbedder, PastQuestions

        embedder = FastEmbedder(cache_dir=settings.cache_dir / "fastembed")
        retriever = PastQuestions.from_ledger(ledger, embedder)
    n = settings.llm_questions_per_domain
    agent = AgentForecaster(
        client,
        per_domain=n,
        max_tool_calls=settings.agent_max_tool_calls,
        peers={"base_rate": out[0], "ml": ml},
        retriever=retriever,
        prompt_version="v2" if retriever is not None else "v1",
        news=None if llm is not None else GdeltBackend(http),
        wiki=None if llm is not None else partial(wikipedia_summary, http),
    )
    b = _Build(ledger, settings, clk, n, client, tracer, out[0], ml, retriever, agent)
    # Registration order matters: forecasters that read peers (`needs_peers`) come last, after
    # everything they read; tests/unit/test_wiring_order.py pins it.
    out += _llm_family(b)
    out += _agent_variants(b)
    out += _open_models(b)
    out += _graph_family(b)
    out += _peer_readers(b)
    for f in out:  # per-call output cap from the settings (thinking counts against it)
        if hasattr(f, "max_output_tokens"):
            f.max_output_tokens = settings.llm_max_output_tokens
    return out, guard


@dataclass
class _Build:
    """What the per-family registration functions share."""

    ledger: Ledger
    settings: Settings
    clk: Clock
    n: int
    client: LLMClient | None
    tracer: Tracer
    base: Forecaster
    ml: Forecaster
    retriever: Any
    agent: AgentForecaster

    @property
    def peers(self) -> dict[str, Forecaster]:
        """What the agent family may read: the base rate and `ml`."""
        return {"base_rate": self.base, "ml": self.ml}


def _llm_family(b: _Build) -> list[Forecaster]:
    """`llm_plain` (retired, off), `llm_context` and `agent`."""
    out: list[Forecaster] = []
    if b.settings.llm_plain:  # retired 2026-11-27: only on if the owner switches it back on
        out.append(LLMPlain(b.client, b.n))
    out += [LLMContext(b.client, b.n), b.agent]
    return out


def _agent_variants(b: _Build) -> list[Forecaster]:
    """Experimental variants of `agent`: hybrid retrieval, quant, analyst and skills."""
    s = b.settings
    out: list[Forecaster] = []
    hybrids: list[type[AgentHybrid]] = []
    if s.agent_hybrid:
        hybrids.append(AgentHybrid)
    if s.agent_hybrid_skills:  # T358: the same retriever and reranker as agent_hybrid
        from arena.agent.quant import AgentHybridSkills

        hybrids.append(AgentHybridSkills)
    if hybrids:
        out += _hybrid_forecasters(b.ledger, s, b.client, b.agent, b.retriever, b.peers, hybrids)
    for flag, cls in (
        (s.agent_quant, "AgentQuant"),
        (s.agent_analyst, "AgentAnalyst"),
        (s.agent_skills, "AgentSkills"),
    ):
        if flag:  # T342/T343/T353: experimental variants of `agent`, same sample, caps and peers
            from arena.agent import quant as quant_mod

            out.append(
                getattr(quant_mod, cls)(
                    b.client,
                    per_domain=b.n,
                    max_tool_calls=s.agent_max_tool_calls,
                    peers=b.peers,
                    retriever=b.retriever,
                    prompt_version="v2" if b.retriever is not None else "v1",
                    news=b.agent.news,
                    wiki=b.agent.wiki,
                )
            )
    return out


def _open_models(b: _Build) -> list[Forecaster]:
    """The open models on the runner's CPU: `llm_local` and the fine-tuned `llm_local_ft`."""
    out: list[Forecaster] = []
    if b.settings.llm_local:
        out.append(_local_forecaster(b.settings, b.n, b.tracer, b.clk))
    if b.settings.llm_local_ft:
        out.append(_ft_forecaster(b.settings, b.n))
    return out


def _graph_family(b: _Build) -> list[Forecaster]:
    """The LangGraph agent, its skills variant and the A2A committee."""
    s = b.settings
    out: list[Forecaster] = []
    if s.agent_graph:
        # No silent fallback: if langgraph is missing this raises and the run fails.
        from arena.agent.graph import GraphAgentForecaster

        out.append(
            GraphAgentForecaster(
                b.client,
                max_tool_calls=s.agent_max_tool_calls,
                peers=b.peers,
                news=b.agent.news,
                wiki=b.agent.wiki,
                retriever=b.retriever,
            )
        )
    if s.agent_graph_skills:  # T357: same peers, news, wiki and retriever as agent_graph
        from arena.agent.quant import AgentGraphSkills

        out.append(
            AgentGraphSkills(
                b.client,
                max_tool_calls=s.agent_max_tool_calls,
                peers=b.peers,
                news=b.agent.news,
                wiki=b.agent.wiki,
                retriever=b.retriever,
            )
        )
    if s.agent_committee:  # T363: needs requirements/a2a.txt; a missing SDK fails the run
        from arena.agent.committee import AgentCommittee

        out.append(
            AgentCommittee(
                b.client,
                per_domain=b.n,
                peers={"base_rate": b.base},  # members get the base rate, never `ml`
                news=b.agent.news,
                wiki=b.agent.wiki,
                retriever=b.retriever,
            )
        )
    return out


def _peer_readers(b: _Build) -> list[Forecaster]:
    """Forecasters that read the others' forecasts of the same question: listed last."""
    from arena.forecasters import router as router_mod

    out: list[Forecaster] = []
    rp = router_mod.load_params()
    if rp is not None:  # not registered until frozen
        out.append(router_mod.RouterForecaster(rp))
    if b.settings.llm_context_cal:  # T382: reads `llm_context`'s answer
        from arena.forecasters.llm_context_cal import LLMContextCal, load_map

        cal = load_map()
        if cal is not None:  # no artefact, no forecaster (never a guessed map)
            out.append(LLMContextCal(cal))
    if b.settings.bandit:  # T293: reads the peers' forecasts like the ensemble
        from arena.forecasters import bandit as bandit_mod
        from arena.scoring.core import load as load_record

        out.append(
            bandit_mod.BanditForecaster(bandit_mod.train(load_record(b.ledger).scored, b.clk.now()))
        )
    ens = live_ensemble(b.ledger, b.clk.now())
    if ens is not None:  # listed last: it combines the forecasts the others just wrote
        out.append(ens)
    return out


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
            from arena.forecasters import ml_power_global

            fams["glgbm"] = lambda cut: ml_power_global.train_global(pdom, cut, folds=2)
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
