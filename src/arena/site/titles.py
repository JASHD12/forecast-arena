"""Plain-language titles for questions (owner request 2026-11-12, DECISIONS.md).

A title is a short, friendly headline computed from the question's template and
parameters at site-build time. It is display only: it is not stored in the ledger, is not
shown to forecasters, and never replaces the exact question text and resolution rule,
which stay the source of truth and are shown next to it. When a template is unknown the
exact text is used.
"""

from __future__ import annotations

from datetime import date

from arena.models import Question

#: Friendly names for forecasters and domains (display only; ids stay in tables and data).
FORECASTER_NAMES = {
    "base_rate": "Base rate",
    "persistence": "Same as last time",
    "ml": "ML model",
    "llm_plain": "AI, question only",
    "llm_context": "AI with data",
    "agent": "AI agent with tools",
    "ensemble": "Ensemble",
    "human_panel": "Human panel",
}
DOMAIN_NAMES = {
    "power": "Electricity",
    "weather": "Weather",
    "attention": "Wikipedia",
    "markets": "Currencies",
    "crypto": "Crypto",
}


def forecaster_name(fid: str) -> str:
    """Friendly forecaster name; the id itself when unknown."""
    return FORECASTER_NAMES.get(fid, fid)


def domain_name(domain: str) -> str:
    """Friendly domain name; the id itself when unknown."""
    return DOMAIN_NAMES.get(domain, domain.title())


CITY = {
    "berlin": "Berlin",
    "frankfurt": "Frankfurt",
    "hamburg": "Hamburg",
    "munich": "Munich",
}
POWER = {
    "mean_gt": "Will German electricity average more than {t} €/MWh {d}?",
    "max_gt": "Will German electricity peak above {t} €/MWh {d}?",
    "min_lt": "Will German electricity drop below {t} €/MWh at some hour {d}?",
    "spread_gt": "Will German power prices swing by more than {t} €/MWh {d}?",
    "evening_gt": "Will the German evening power price (5-8 pm) top {t} €/MWh {d}?",
}


def _num(x: float | None) -> str:
    if x is None:
        return "?"
    s = f"{x:,.2f}".rstrip("0").rstrip(".")  # the exact threshold, never rounded away
    return s


def _when(target: date) -> str:
    """Always the date (a relative "tomorrow" would be wrong on archived pages)."""
    return f"on {target.strftime('%a')} {target.day} {target.strftime('%b')}"


def _city(key: str) -> str:
    return CITY.get(key, key.title())


def _article(q: Question) -> str:
    return str(q.params.get("title", q.entity)).replace("_", " ")


def plain_title(q: Question) -> str:
    """A short headline for the question; the exact text when the template is unknown."""
    d = _when(q.target_date)
    t = q.template
    if q.domain == "power" and t == "up_vs_today":
        ref = q.params.get("reference_mean")
        ref_s = f" than today's {_num(float(ref))} €/MWh" if ref is not None else ""
        return f"Will German electricity be pricier{ref_s} {d}?"
    if q.domain == "power" and t in POWER:
        return POWER[t].format(t=_num(q.threshold), d=d)
    if q.domain == "weather":
        city = _city(q.entity)
        if t == "tmax_gt":
            return f"Will {city} get warmer than {q.threshold:g} °C {d}?"
        if t == "wet_day":
            return f"Will it rain (1 mm or more) in {city} {d}?"
        if t == "frost_day":
            return f"Will {city} drop below freezing {d}?"
        if t == "gust_gt":
            return f"Will wind gusts in {city} top {q.threshold:g} km/h {d}?"
        if t in ("warmer_than", "wetter_than"):
            a = _city(str(q.params.get("city_a", "")))
            b = _city(str(q.params.get("city_b", "")))
            if t == "warmer_than":
                return f"Will {a} be warmer than {b} {d}?"
            return f"Will it rain more in {a} than in {b} {d}?"
    if q.domain == "attention" and t == "views_ge":
        lang = "German" if str(q.params.get("project", "")).startswith("de.") else "English"
        return (
            f"Will the {lang} Wikipedia article “{_article(q)}” get at least "
            f"{_num(q.threshold)} views {d}?"
        )
    if q.domain == "crypto":
        coin = str(q.params.get("coin_name", q.entity))
        if t == "up":
            return f"Will {coin} end the day higher {d}?"
        if t == "bigmove" and q.threshold is not None:
            return f"Will {coin} move more than {q.threshold * 100:.1f}% {d}?"
    if q.domain == "markets":
        ccy = str(q.params.get("currency", ""))
        if t == "up":
            return f"Will the euro be worth more {ccy} at the next ECB fixing?"
        if t == "absmove_gt":
            return f"Will the euro make a big move against the {ccy} at the next ECB fixing?"
    return q.text
