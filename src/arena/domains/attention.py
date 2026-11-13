"""Attention domain (SPEC 7.3): will a Wikipedia article get at least K views on D?

Reference day R = the latest fully published day at batch time (normally B-2).
Target day D = B+1 (UTC). Lock B 09:30 UTC. Resolve after D+1 12:00 UTC. Grace 96 h.
Per project (de, en): candidates are ranks 5-200 of R's top list minus non-articles,
person articles (Wikidata P31 = Q5; a failed lookup also excludes), blocklisted titles
and articles used in the previous 3 batches. A seeded sample takes 2 from ranks 5-50 and
2 from ranks 51-200.

K = views on R x the median ratio views(t+3)/views(t) over the top-200 articles of the
90 days before, from top lists only (see docs/project/DECISIONS.md "Attention threshold").
An article missing from the top list of t+3 gets that list's lowest view count as an upper bound.
"""

from __future__ import annotations

import random
import re
import statistics
import urllib.parse
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from importlib import resources
from typing import Any, Protocol

from arena.domains.base import is_degenerate, template_version_for, trailing_frequency
from arena.models import Evidence, Question, Resolution, Void, question_id_for
from arena.sources.wikimedia import (
    ATTRIBUTION,
    TopArticle,
    pageviews_available_at,
    person_titles,
)

DOMAIN = "attention"
TEMPLATE = "views_ge"
#: Template versions: 1 = published on the batch morning, 2 = the evening before (T160).
PROJECTS = ("de.wikipedia", "en.wikipedia")
LOCK = time(9, 30)
RESOLVE_AFTER = time(12, 0)
GRACE = timedelta(hours=96)
WINDOW = 90
HORIZON = 3  # D = R + 3
TOP_RANK, MID_RANK, LOW_RANK = 5, 50, 200
PER_BAND = 2
RECENT_BATCHES = 3
TRAJECTORY_DAYS = 7
SOURCE = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"

_NAMESPACES = {
    "de.wikipedia": ["Wikipedia", "Spezial", "Datei", "Portal", "Kategorie", "Hilfe",
                     "Benutzer", "Benutzerin", "Vorlage", "Diskussion", "Modul", "MediaWiki",
                     "Benutzer Diskussion", "Wikipedia Diskussion", "Special", "File",
                     "Category", "Help", "User", "Template", "Talk", "Module"],
    "en.wikipedia": ["Wikipedia", "Special", "File", "Portal", "Category", "Help", "User",
                     "Template", "Talk", "Draft", "Module", "MediaWiki", "User talk",
                     "Wikipedia talk", "TimedText", "Book"],
}  # fmt: skip
_MAIN_PAGES = {"Main_Page", "Hauptseite", "Wikipedia:Hauptseite", "-", "Special:Search"}


class PageviewSource(Protocol):
    """What the domain needs from the Wikimedia client."""

    def top(self, project: str, day: date) -> list[TopArticle] | None: ...

    def per_article(
        self, project: str, title: str, first: date, last: date
    ) -> tuple[str, str, dict[date, int]]: ...

    def instance_of(self, project: str, titles: Sequence[str]) -> dict[str, set[str] | None]: ...


def load_blocklist(text: str | None = None) -> list[re.Pattern[str]]:
    """Compile the blocklist (package file by default)."""
    if text is None:
        text = resources.files("arena.domains").joinpath("attention_blocklist.txt").read_text(
            encoding="utf-8")  # fmt: skip
    return [re.compile(line.strip(), re.IGNORECASE) for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")]  # fmt: skip


def is_article(project: str, title: str) -> bool:
    """False for the main page, search, special pages and other namespaces."""
    if title in _MAIN_PAGES:
        return False
    if ":" in title:
        prefix = title.split(":", 1)[0].replace("_", " ")
        if prefix in _NAMESPACES.get(project, []):
            return False
    return True


def blocked(title: str, patterns: Sequence[re.Pattern[str]]) -> bool:
    """True if any blocklist pattern matches the title."""
    text = title.replace("_", " ")
    return any(p.search(text) for p in patterns)


def entity_for(project: str, title: str) -> str:
    """URL-safe entity id: `<wiki>.<percent-encoded title>` (hyphens encoded too)."""
    wiki = project.split(".")[0] + "wiki"
    return f"{wiki}." + urllib.parse.quote(title, safe="").replace("-", "%2D")


def round_k(x: float) -> int:
    """K rounded to two significant figures (natural units for view counts), at least 1."""
    if x < 1:
        return 1
    digits = len(str(int(x))) - 2
    step = 10 ** max(digits, 0)
    return max(1, int((x + step / 2) // step * step))


@dataclass(frozen=True)
class Candidate:
    """An eligible article on the reference day."""

    title: str
    rank: int
    views: int


class AttentionDomain:
    """Wikipedia attention questions; all pageview data filtered by availability."""

    name = DOMAIN
    #: Base rates are per article, which rarely repeats: replaying history cannot give the
    #: 10 instances base_rate needs, so it is not replayed (base_rate answers 0.5).
    replayable = False

    def __init__(
        self,
        source: PageviewSource,
        recent_titles: Callable[[str, date], set[str]] | None = None,
        blocklist: Sequence[re.Pattern[str]] | None = None,
        on_skip: Callable[[str], None] | None = None,
    ) -> None:
        self.source = source
        self.recent_titles = recent_titles or (lambda project, batch: set())
        self.blocklist = list(blocklist) if blocklist is not None else load_blocklist()
        self.on_skip = on_skip or (lambda msg: None)

    # ----- reference day and ratios ------------------------------------------------
    def reference_day(self, project: str, asof: datetime) -> date | None:
        """Latest day whose pageviews are available at `asof` and whose list exists."""
        day = asof.date() - timedelta(days=1)
        for _ in range(4):
            if pageviews_available_at(day) <= asof and self.source.top(project, day):
                return day
            day -= timedelta(days=1)
        return None

    def ratios(self, project: str, ref: date) -> list[tuple[date, float]]:
        """(t, views(t+3)/views(t)) for top-200 articles, t+3 <= R, over 90 days."""
        out = []
        for back in range(WINDOW + HORIZON - 1, HORIZON - 1, -1):
            t = ref - timedelta(days=back)
            a, b = self.source.top(project, t), self.source.top(project, t + timedelta(HORIZON))
            if not a or not b:
                continue
            later = {x.article: x.views for x in b}
            floor = min(later.values())
            for x in a:
                if TOP_RANK <= x.rank <= LOW_RANK and is_article(project, x.article):
                    out.append((t, later.get(x.article, floor) / x.views))
        return out

    # ----- generation --------------------------------------------------------------
    def generate_questions(self, batch_date: date, asof: datetime) -> list[Question]:
        """Four questions per project, deterministic for the batch date and data."""
        target = batch_date + timedelta(days=1)
        lock = datetime.combine(batch_date, LOCK, tzinfo=UTC)
        created = min(asof, lock)
        out: list[Question] = []
        for project in PROJECTS:
            ref = self.reference_day(project, created)
            if ref is None:
                self.on_skip(f"attention/{project}: no published reference day")
                continue
            ratios = self.ratios(project, ref)
            days_seen = {t for t, _ in ratios}
            if len(days_seen) < WINDOW * 0.9:
                self.on_skip(f"attention/{project}: only {len(days_seen)} days of ratios")
                continue
            median = statistics.median(r for _, r in ratios)
            freq = trailing_frequency([int(r >= median) for _, r in ratios])
            if is_degenerate(freq):
                self.on_skip(f"attention/{project}: degenerate ({freq})")
                continue
            for c in self.select(project, ref, batch_date):
                k = round_k(c.views * median)
                out.append(self._question(project, c, ref, k, median, freq, batch_date,
                                          target, created, lock))  # fmt: skip
        return out

    def select(self, project: str, ref: date, batch_date: date) -> list[Candidate]:
        """Seeded sample of 2 + 2 eligible articles from R's top list."""
        top = self.source.top(project, ref) or []
        recent = self.recent_titles(project, batch_date)
        pool = [Candidate(x.article, x.rank, x.views) for x in top
                if TOP_RANK <= x.rank <= LOW_RANK and is_article(project, x.article)
                and not blocked(x.article, self.blocklist) and x.article not in recent]  # fmt: skip
        if not pool:
            return []
        try:
            p31 = self.source.instance_of(project, [c.title for c in pool])
        except Exception as exc:
            self.on_skip(f"attention/{project}: person lookup failed ({exc}); all excluded")
            return []
        persons = person_titles([c.title for c in pool], p31)
        eligible = [c for c in pool if c.title not in persons]
        rng = random.Random(f"{DOMAIN}-{project}-{batch_date.isoformat()}")
        high = [c for c in eligible if c.rank <= MID_RANK]
        low = [c for c in eligible if c.rank > MID_RANK]
        chosen = rng.sample(high, min(PER_BAND, len(high)))
        chosen += rng.sample(low, min(PER_BAND, len(low)))
        return sorted(chosen, key=lambda c: c.rank)

    def _question(self, project: str, c: Candidate, ref: date, k: int, median: float,
                  freq: float | None, batch_date: date, target: date, created: datetime,
                  lock: datetime) -> Question:  # fmt: skip
        title = c.title.replace("_", " ")
        text = (f"Will the {project.split('.')[0]}.wikipedia.org article \"{title}\" get at "
                f"least {k:,} views on {target.isoformat()} (UTC day, all access methods, "
                f"human users only)?")  # fmt: skip
        rule = (
            "Daily views of the article on D from the Wikimedia per-article pageviews API "
            "(all-access, agent=user); YES if greater than or equal to K. Void if the "
            "article is deleted or moved or the day is missing 96 hours after "
            "resolve_after."
        )
        version = template_version_for(batch_date, created)
        return Question(
            question_id=question_id_for(
                DOMAIN, TEMPLATE, entity_for(project, c.title), target, version
            ),
            domain=DOMAIN,
            template=TEMPLATE,
            template_version=version,
            entity=entity_for(project, c.title),
            text=text,
            batch_date=batch_date,
            target_date=target,
            created_at=created,
            lock_time=lock,
            resolve_after=datetime.combine(target + timedelta(days=1), RESOLVE_AFTER, tzinfo=UTC),
            resolution_source=f"{SOURCE}/{project}/all-access/user/<title>/daily",
            resolution_rule=rule,
            threshold=float(k),
            unit="views",
            comparator="ge",
            params={
                "project": project,
                "title": c.title,
                "reference_day": ref.isoformat(),
                "reference_rank": c.rank,
                "reference_views": c.views,
                "median_ratio_t_plus_3": round(median, 6),
                "window_days": WINDOW,
            },
            base_rate_hint=None if freq is None else round(freq, 4),
            tags=["news-driven", "attention"],
        )

    # ----- context -----------------------------------------------------------------
    def context(self, question: Question, asof: datetime) -> dict[str, Any]:
        """The article's daily views of the last 30 available days, rank and weekday."""
        project, title = question.params["project"], question.params["title"]
        last = asof.date()
        _, _, series = self.source.per_article(project, title, last - timedelta(days=32), last)
        known = {d: v for d, v in series.items() if pageviews_available_at(d) <= asof}
        return {
            "domain": DOMAIN,
            "asof": asof.isoformat(),
            "attribution": ATTRIBUTION,
            "project": project,
            "title": title,
            "reference_day": question.params["reference_day"],
            "reference_rank": question.params["reference_rank"],
            "target_weekday": question.target_date.strftime("%A"),
            "daily_views": [{"day": d.isoformat(), "views": v} for d, v in sorted(known.items())],
            "top_trajectory": top_trajectory(
                self.source, project, title, date.fromisoformat(question.params["reference_day"])
            ),
        }

    # ----- resolution --------------------------------------------------------------
    def resolve(self, question: Question, now: datetime) -> Resolution | Void | None:
        """Views on D from the per-article API; Void when still missing after grace."""
        if now < question.resolve_after:
            return None
        project, title = question.params["project"], question.params["title"]
        d = question.target_date
        url, sha, series = self.source.per_article(project, title, d, d)
        if d not in series:
            if now >= question.resolve_after + GRACE:
                return Void(question_id=question.question_id, reason_code="source_missing",
                            detail="article deleted, moved or day missing at end of grace",
                            voided_at=now)  # fmt: skip
            return None
        views = series[d]
        assert question.threshold is not None
        return Resolution(
            question_id=question.question_id,
            outcome=int(views >= question.threshold),  # type: ignore[arg-type]
            observed_value=float(views),
            resolved_at=now,
            evidence=Evidence(source_url=url, snapshot_sha256=sha,
                              values_used={"day": d.isoformat(), "views": views,
                                           "threshold": question.threshold}),
        )  # fmt: skip

    def revised(self, question: Question, first: Resolution) -> bool:
        """True if the API now reports a different view count for D."""
        project, title = question.params["project"], question.params["title"]
        d = question.target_date
        _, _, series = self.source.per_article(project, title, d, d)
        return d in series and series[d] != first.evidence.values_used.get("views")


_INDEX: dict[tuple[int, str, date], tuple[dict[str, TopArticle], int | None]] = {}


def _top_index(
    source: PageviewSource, project: str, day: date
) -> tuple[dict[str, TopArticle], int | None]:
    """Title index of a top list. Only published (non-empty) lists are memoised, so a
    transient 'not published' answer is retried rather than remembered."""
    key = (id(source), project, day)
    if key in _INDEX:
        return _INDEX[key]
    top = source.top(project, day) or []
    out = {x.article: x for x in top}, min((x.views for x in top), default=None)
    if top:
        if len(_INDEX) > 16384:
            _INDEX.clear()
        _INDEX[key] = out
    return out


def top_trajectory(
    source: PageviewSource, project: str, title: str, ref: date, days: int = TRAJECTORY_DAYS
) -> list[dict[str, Any]]:
    """The article's views on R-days+1 .. R from the daily top lists. Where it is absent,
    `views` is None and `floor` (the list's lowest count) bounds it from above. Only days
    up to R are used (as-of: R is the latest published day)."""
    out = []
    for back in range(days - 1, -1, -1):
        d = ref - timedelta(days=back)
        index, floor = _top_index(source, project, d)
        hit = index.get(title)
        out.append(
            {
                "day": d.isoformat(),
                "views": hit.views if hit else None,
                "rank": hit.rank if hit else None,
                "floor": floor,
            }
        )
    return out


def titles_from_questions(questions: Iterable[Question], project: str, batch: date,
                          batches: int = RECENT_BATCHES) -> set[str]:  # fmt: skip
    """Titles used in the previous `batches` batches of a project (for the exclusion rule)."""
    lo = batch - timedelta(days=batches)
    return {str(q.params.get("title")) for q in questions
            if q.domain == DOMAIN and q.params.get("project") == project
            and lo <= q.batch_date < batch}  # fmt: skip
