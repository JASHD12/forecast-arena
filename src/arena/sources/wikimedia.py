"""Wikimedia pageviews and Wikidata person check (SPEC 7.3).

Verified on 2026-11-12 (docs/SOURCES.md):
- top list: ``{BASE}/metrics/pageviews/top/{project}/{access}/{YYYY}/{MM}/{DD}`` ->
  ``{"items": [{"articles": [{"article", "views", "rank"}...]}]}`` (1000 articles);
  404 until the day is published (the list for day X was available at 11:30 UTC on X+1).
- per article: ``{BASE}/metrics/pageviews/per-article/{project}/{access}/{agent}/{title}/
  daily/{YYYYMMDD}/{YYYYMMDD}`` -> ``{"items": [{"timestamp": "YYYYMMDD00", "views"}...]}``;
  404 when there is no data (e.g. a deleted article).
- Titles use underscores for spaces and must be percent-encoded, including ``/``.
- Rate limits: 200 requests/min for clients with a compliant User-Agent (contact URL or
  email); at most 3 concurrent requests; honour ``Retry-After`` on 429 (HttpClient does).
- Wikidata ``wbgetentities`` with ``sites=<dbname>&titles=a|b`` (max 50) returns the
  item's claims; instance of (P31) human (Q5) marks a person article.
"""

from __future__ import annotations

import json
import urllib.parse
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

from arena.sources.http import HttpClient, HttpError

BASE = "https://wikimedia.org/api/rest_v1"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
ATTRIBUTION = "Wikimedia Foundation pageview statistics (wikimedia.org REST API)"
ACCESS = "all-access"
AGENT = "user"
HUMAN = "Q5"
WIKIDATA_BATCH = 50
#: Conservative availability: the pageviews of UTC day X count as known from X+2 00:00 UTC.
PAGEVIEWS_LAG = timedelta(days=2)
SITE_IDS = {"de.wikipedia": "dewiki", "en.wikipedia": "enwiki"}


class WikimediaError(Exception):
    """A response was missing or malformed."""


@dataclass(frozen=True)
class TopArticle:
    """One entry of a daily top list."""

    article: str
    views: int
    rank: int


def encode_title(title: str) -> str:
    """Percent-encode an article title for a REST path (spaces become underscores)."""
    return urllib.parse.quote(title.replace(" ", "_"), safe="")


def pageviews_available_at(day: date) -> datetime:
    """When the pageviews of a UTC day are treated as known (historical replays)."""
    return datetime.combine(day, time(0), tzinfo=UTC) + PAGEVIEWS_LAG


def parse_top(payload: object) -> list[TopArticle]:
    """Validate a top-list document."""
    try:
        items = payload["items"]  # type: ignore[index]
        arts = items[0]["articles"]
        return [TopArticle(str(a["article"]), int(a["views"]), int(a["rank"])) for a in arts]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise WikimediaError(f"malformed top list: {exc}") from exc


def parse_per_article(payload: object) -> dict[date, int]:
    """Validate a per-article document -> {UTC day: views}."""
    try:
        out = {}
        for it in payload["items"]:  # type: ignore[index]
            ts = str(it["timestamp"])
            out[date(int(ts[:4]), int(ts[4:6]), int(ts[6:8]))] = int(it["views"])
        return out
    except (KeyError, TypeError, ValueError) as exc:
        raise WikimediaError(f"malformed per-article series: {exc}") from exc


def instance_of(payload: object) -> dict[str, set[str] | None]:
    """{title (spaces): set of P31 ids} from a wbgetentities document; None if missing."""
    try:
        entities = payload["entities"]  # type: ignore[index]
    except (KeyError, TypeError) as exc:
        raise WikimediaError(f"malformed wikidata response: {exc}") from exc
    out: dict[str, set[str] | None] = {}
    for e in entities.values():
        if "missing" in e:
            title = e.get("title")
            if title:
                out[str(title).replace("_", " ")] = None
            continue
        ids = set()
        for c in e.get("claims", {}).get("P31", []):
            v = c.get("mainsnak", {}).get("datavalue", {}).get("value", {})
            if isinstance(v, dict) and "id" in v:
                ids.add(str(v["id"]))
        for link in e.get("sitelinks", {}).values():
            out[str(link["title"]).replace("_", " ")] = ids
    return out


class WikimediaClient:
    """Pageviews (with an on-disk cache for published top lists) and the person check."""

    def __init__(self, http: HttpClient, cache_dir: Path | None = None,
                 base: str = BASE, wikidata: str = WIKIDATA_API) -> None:  # fmt: skip
        self.http = http
        self.cache_dir = cache_dir
        self.base = base.rstrip("/")
        self.wikidata = wikidata
        self._mem: dict[tuple[str, date], list[TopArticle]] = {}

    def top_url(self, project: str, day: date) -> str:
        """URL of a daily top list."""
        return f"{self.base}/metrics/pageviews/top/{project}/{ACCESS}/{day:%Y/%m/%d}"

    def top(self, project: str, day: date) -> list[TopArticle] | None:
        """The top list of a UTC day, or None if it is not published yet."""
        if (project, day) in self._mem:
            return self._mem[(project, day)]
        cache = self._cache(project, day)
        if cache is not None and cache.exists():
            arts = parse_top(json.loads(cache.read_text(encoding="utf-8")))
            self._mem[(project, day)] = arts
            return arts
        try:
            resp = self.http.get(self.top_url(project, day))
        except HttpError as exc:
            if exc.status == 404:
                return None
            raise
        arts = parse_top(resp.json())
        self._mem[(project, day)] = arts
        if cache is not None:
            cache.parent.mkdir(parents=True, exist_ok=True)
            tmp = cache.with_suffix(".tmp")
            tmp.write_bytes(resp.body)
            tmp.replace(cache)
        return arts

    def _cache(self, project: str, day: date) -> Path | None:
        if self.cache_dir is None:
            return None
        return self.cache_dir / "wikimedia" / "top" / project / f"{day.isoformat()}.json"

    def per_article_url(self, project: str, title: str, first: date, last: date) -> str:
        """URL of a daily per-article series."""
        return (f"{self.base}/metrics/pageviews/per-article/{project}/{ACCESS}/{AGENT}/"
                f"{encode_title(title)}/daily/{first:%Y%m%d}/{last:%Y%m%d}")  # fmt: skip

    def per_article(self, project: str, title: str, first: date, last: date
                    ) -> tuple[str, str, dict[date, int]]:  # fmt: skip
        """(url, sha256, {day: views}); an empty dict when the API has no data (404)."""
        url = self.per_article_url(project, title, first, last)
        try:
            resp = self.http.get(url)
        except HttpError as exc:
            if exc.status == 404:
                return url, "0" * 64, {}
            raise
        return url, resp.sha256, parse_per_article(resp.json())

    def instance_of(self, project: str, titles: Sequence[str]) -> dict[str, set[str] | None]:
        """P31 ids per title (spaces as separators); titles not found map to None."""
        site = SITE_IDS[project]
        out: dict[str, set[str] | None] = {}
        for i in range(0, len(titles), WIKIDATA_BATCH):
            batch = [t.replace("_", " ") for t in titles[i : i + WIKIDATA_BATCH]]
            params = {
                "action": "wbgetentities",
                "sites": site,
                "titles": "|".join(batch),
                "props": "claims|sitelinks",
                "sitefilter": site,
                "format": "json",
            }
            out.update(instance_of(self.http.get(self.wikidata, params).json()))
        return out


def person_titles(titles: Iterable[str], p31: dict[str, set[str] | None]) -> set[str]:
    """Titles to exclude as person articles. A failed or missing lookup counts as a person
    (fail closed, SPEC 7.3)."""
    out = set()
    for t in titles:
        ids = p31.get(t.replace("_", " "))
        if ids is None or HUMAN in ids:
            out.add(t)
    return out
