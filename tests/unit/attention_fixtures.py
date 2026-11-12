"""Replay a recorded attention run (tests/fixtures/attention/recorded.json.gz).

The recording was made from the live APIs by `record_attention()` below on 2026-11-12:
top lists are trimmed to their first 300 entries (article, views; rank = position),
Wikidata P31 answers and per-article series are stored as returned.
"""

import gzip
import json
from datetime import date
from pathlib import Path

from arena.sources.wikimedia import TopArticle

PATH = Path(__file__).parents[1] / "fixtures" / "attention" / "recorded.json.gz"
TOP_KEEP = 300


class RecordingSource:
    """Wraps a live client and remembers every answer."""

    def __init__(self, inner) -> None:
        self.inner = inner
        self.tops: dict[str, list] = {}
        self.p31: dict[str, list | None] = {}
        self.series: dict[str, dict] = {}

    def top(self, project, day):
        arts = self.inner.top(project, day)
        if arts:
            self.tops[f"{project}|{day}"] = [[a.article, a.views] for a in arts[:TOP_KEEP]]
        return arts[:TOP_KEEP] if arts else arts

    def instance_of(self, project, titles):
        res = self.inner.instance_of(project, titles)
        for t in titles:
            v = res.get(t.replace("_", " "))
            self.p31[f"{project}|{t}"] = None if v is None else sorted(v)
        return res

    def per_article(self, project, title, first, last):
        url, sha, s = self.inner.per_article(project, title, first, last)
        self.series[f"{project}|{title}|{first}|{last}"] = {
            "url": url,
            "sha": sha,
            "views": {d.isoformat(): v for d, v in s.items()},
        }
        return url, sha, s

    def dump(self, path: Path = PATH) -> None:
        data = {"tops": self.tops, "p31": self.p31, "series": self.series}
        path.write_bytes(gzip.compress(json.dumps(data, sort_keys=True).encode(), mtime=0))


class FixtureSource:
    """Serves the recording; anything not recorded is 'not published' / 'no data'."""

    def __init__(self, path: Path = PATH) -> None:
        d = json.loads(gzip.decompress(path.read_bytes()))
        self.tops, self.p31, self.series = d["tops"], d["p31"], d["series"]
        self.calls: list[str] = []

    def top(self, project, day):
        rows = self.tops.get(f"{project}|{day}")
        if rows is None:
            return None
        return [TopArticle(a, v, i + 1) for i, (a, v) in enumerate(rows)]

    def instance_of(self, project, titles):
        out = {}
        for t in titles:
            v = self.p31.get(f"{project}|{t}")
            out[t.replace("_", " ")] = None if v is None else set(v)
        return out

    def per_article(self, project, title, first, last):
        self.calls.append(f"{project}|{title}")
        rec = self.series.get(f"{project}|{title}|{first}|{last}")
        if rec is None:
            return "fixture://none", "0" * 64, {}
        return rec["url"], rec["sha"], {date.fromisoformat(k): v for k, v in rec["views"].items()}
