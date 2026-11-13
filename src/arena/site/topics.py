"""Topic pages (T133): one page per domain with its source and terms, the kinds of
questions in plain words, the per-topic boards and race, and the latest questions.

Source terms are only what `docs/SOURCES.md` records as verified; where a licence was not
verified, the page names the source without claiming one.
"""

from __future__ import annotations

from typing import Any

from arena.scoring.core import Record
from arena.site.titles import plain_title
from arena.sources.brightsky import ATTRIBUTION as WX_ATTRIBUTION
from arena.sources.brightsky import LICENCE as WX_LICENCE
from arena.sources.coingecko import ATTRIBUTION as CG_ATTRIBUTION
from arena.sources.ecb import ATTRIBUTION as ECB_ATTRIBUTION
from arena.sources.smard import ATTRIBUTION as SMARD_ATTRIBUTION
from arena.sources.smard import LICENCE as SMARD_LICENCE
from arena.sources.wikimedia import ATTRIBUTION as WIKI_ATTRIBUTION

#: domain -> (what it is about, source, terms as verified, source home page)
TOPIC_INFO: dict[str, tuple[str, str, str, str]] = {
    "power": ("Day-ahead wholesale electricity prices for Germany/Luxembourg: the hourly "
              "auction result for tomorrow, published by the federal network agency.",
              SMARD_ATTRIBUTION, f"{SMARD_LICENCE}; daily statistics computed by this project",
              "https://www.smard.de"),
    "weather": ("Observed temperature, rain and wind at official German weather stations, "
                "compared with thresholds and with each other.", WX_ATTRIBUTION,
                f"{WX_LICENCE}; daily values computed by this project", "https://brightsky.dev"),
    "attention": ("How many people read a Wikipedia article on a given day; articles about "
                  "people are excluded.", WIKI_ATTRIBUTION,
                  "licence of the pageview statistics not verified; the source is named",
                  "https://wikimedia.org/api/rest_v1/"),
    "markets": ("Euro foreign exchange reference rates and how much they move from one "
                "fixing to the next.", ECB_ATTRIBUTION,
                "free use with the ECB cited as source; returns computed by this project",
                "https://www.ecb.europa.eu"),
    "crypto": ("Daily cryptocurrency prices at 00:00 UTC.", CG_ATTRIBUTION,
               "CoinGecko API terms, attribution required", "https://www.coingecko.com"),
}  # fmt: skip
RECENT = 12


def topic(domain: str, rec: Record) -> dict[str, Any]:
    """Question types (one example each), counts and the latest questions of a domain."""
    qs = sorted((q for q in rec.questions.values() if q.domain == domain),
                key=lambda q: (q.batch_date, q.question_id), reverse=True)  # fmt: skip
    kinds: dict[str, dict[str, Any]] = {}
    for q in qs:
        k = kinds.setdefault(q.template, {"template": q.template, "n": 0, "example": q})
        k["n"] += 1
    about, source, terms, url = TOPIC_INFO.get(domain, ("", "", "", ""))
    return {
        "domain": domain,
        "about": about,
        "source": source,
        "terms": terms,
        "url": url,
        "n_questions": len(qs),
        "n_resolved": sum(1 for q in qs if q.question_id in rec.resolutions),
        "kinds": [
            {**k, "title": plain_title(k["example"]), "rule": k["example"].resolution_rule}
            for k in sorted(kinds.values(), key=lambda k: k["template"])
        ],
        "recent": qs[:RECENT],
    }
