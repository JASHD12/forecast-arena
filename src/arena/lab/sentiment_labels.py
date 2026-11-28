"""Open sentiment model against Claude labels on crypto headlines (T375).

Pre-registered in `lab/prereg/sentiment-labels.md`.

Headlines come from GDELT's article list (titles, outlets, URLs and times; verified against a real
response in tests/fixtures/gdelt/titles). Only the **title** is kept in memory; both raters score
it and it is discarded: no title, URL or outlet is written to a file, a log or a result (S7, S12).
Only counts, agreement numbers and token usage leave this module.
"""

from __future__ import annotations

import json
import random
import re
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from arena.lab.judge import weighted_kappa
from arena.sources import gdelt_tone as G

RUBRIC = (
    "You rate the sentiment of one news headline about a cryptocurrency, as it bears on that "
    "coin's price outlook. Use the headline only; do not use outside knowledge.\n"
    "1 = very negative, 2 = negative, 3 = neutral, mixed, or not about the coin's price, "
    "4 = positive, 5 = very positive.\n"
    'Answer with one JSON object and nothing else: {"rating": <integer 1-5>}.'
)
CATEGORIES = 5
MIN_TITLES = 200
PER_COIN = 100
SEED = 0
MAX_RECORDS = 250


class LabelError(Exception):
    """A response or an answer was malformed."""


def parse_titles(payload: object) -> list[tuple[str, datetime]]:
    """(title, seen time) of each article of a GDELT article-list response; nothing else is kept."""
    try:
        rows = payload["articles"]  # type: ignore[index]
        out = []
        for a in rows:
            title = " ".join(str(a["title"]).split())
            seen = datetime.strptime(str(a["seendate"]), "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
            if title:
                out.append((title, seen))
        return out
    except (KeyError, TypeError, ValueError) as exc:
        raise LabelError(f"malformed article list: {exc}") from exc


def artlist_params(
    coin: str, timespan: str = "7d", maxrecords: int = MAX_RECORDS
) -> dict[str, str]:
    """Request parameters of the article list of `coin`'s fixed query (newest first)."""
    if coin not in G.QUERIES:
        raise LabelError(f"unknown coin {coin!r}")
    return {
        "query": G.QUERIES[coin],
        "mode": "artlist",
        "format": "json",
        "maxrecords": str(maxrecords),
        "sort": "datedesc",
        "timespan": timespan,
    }


RETRY_PAUSES = (60.0, 120.0)


def fetch_titles(
    get: Callable[[Mapping[str, str]], object],
    coins: Sequence[str],
    *,
    pause: float = G.REQUEST_PAUSE,
    retry_pauses: Sequence[float] = RETRY_PAUSES,
    sleep: Callable[[float], None] = lambda _s: None,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
) -> tuple[dict[str, list[str]], list[str]]:
    """Fetch each coin's headline list, waiting and retrying a failed coin (GDELT limits hard).

    `get` takes the request parameters and returns the parsed JSON. A coin is retried after each
    pause in `retry_pauses`; one that still fails is named in the second return value. Only titles
    are kept (S7). Nothing is invented for a coin that failed (I6).
    """
    by_coin: dict[str, list[str]] = {}
    failed: list[str] = []
    for i, coin in enumerate(coins):
        if i:
            sleep(pause)
        last = ""
        for attempt in range(len(retry_pauses) + 1):
            if attempt:
                sleep(retry_pauses[attempt - 1])
            try:
                by_coin[coin] = [t for t, _ in parse_titles(get(artlist_params(coin)))]
                break
            except (LabelError, ValueError, *retry_on) as exc:  # type: ignore[misc]
                last = f"{coin}: {type(exc).__name__}"
        else:
            failed.append(last)
    return by_coin, failed


def sample_titles(
    titles_by_coin: Mapping[str, Sequence[str]], per_coin: int = PER_COIN, seed: int = SEED
) -> list[tuple[str, str]]:
    """(coin, title) pairs: up to `per_coin` distinct titles per coin, sampled with a fixed seed."""
    rng = random.Random(seed)
    out: list[tuple[str, str]] = []
    for coin in sorted(titles_by_coin):
        uniq = sorted(set(titles_by_coin[coin]))
        rng.shuffle(uniq)
        out.extend((coin, t) for t in uniq[:per_coin])
    return out


def open_rating(score: float) -> int:
    """The open model's score in [-1, 1] as a rating 1..5 (fixed bins)."""
    if not -1.0 <= score <= 1.0:
        raise LabelError(f"score {score!r} outside [-1, 1]")
    if score < -0.6:
        return 1
    if score < -0.2:
        return 2
    if score <= 0.2:
        return 3
    if score <= 0.6:
        return 4
    return 5


def user_prompt(coin: str, title: str) -> str:
    """The one user message of a rating request."""
    return f"Coin: {coin}\nHeadline: {title}"


_JSON = re.compile(r"\{[^{}]*\}")


def parse_rating(text: str) -> int | None:
    """The integer rating 1..5 of an answer, or None when it cannot be read."""
    for m in _JSON.finditer(text):
        try:
            obj = json.loads(m.group(0))
        except ValueError:
            continue
        v = obj.get("rating") if isinstance(obj, dict) else None
        if isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= CATEGORIES:
            return v
    return None


def three_class(r: int) -> str:
    """1-2 negative, 3 neutral, 4-5 positive."""
    return "negative" if r <= 2 else "neutral" if r == 3 else "positive"


def compare(pairs: Sequence[tuple[int, int | None]]) -> dict[str, Any]:
    """Agreement of (open, Claude) ratings; unparsed Claude answers are counted, not used."""
    used = [(a, b) for a, b in pairs if b is not None]
    a = [x for x, _ in used]
    b = [y for _, y in used]
    n = len(used)
    kappa = weighted_kappa(a, b, CATEGORIES)
    return {
        "n": n,
        "unparsed": len(pairs) - n,
        "weighted_kappa": None if kappa is None else round(kappa, 4),
        "exact_match_pct": None if n == 0 else round(100 * sum(x == y for x, y in used) / n, 1),
        "three_class_pct": None
        if n == 0
        else round(100 * sum(three_class(x) == three_class(y) for x, y in used) / n, 1),
        "open_distribution": dict(sorted(Counter(a).items())),
        "claude_distribution": dict(sorted(Counter(b).items())),
        "pair_counts": {f"{x}-{y}": c for (x, y), c in sorted(Counter(used).items())},
    }


def rate_with_claude(ask: Callable[[str, str], str], coin: str, title: str) -> int | None:
    """One request, and one repair request when the answer cannot be read."""
    text = ask(RUBRIC, user_prompt(coin, title))
    r = parse_rating(text)
    if r is not None:
        return r
    return parse_rating(
        ask(
            RUBRIC,
            user_prompt(coin, title)
            + '\nYour last answer was not valid. Reply with {"rating": N}.',
        )
    )
