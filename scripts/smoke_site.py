"""Smoke test of the published site (T182): `python scripts/smoke_site.py URL`.

Checks over plain HTTP, with no browser and no third-party requests:
- the key pages and data files answer 200 and look like Forecast Arena pages;
- every stylesheet, script and image a page references from its own origin answers 200;
- the footer's build time is recent (default: at most 26 hours old), so a stale deploy
  shows up even when every page loads;
- the security headers or meta the site relies on are present (CSP meta tag).

Used after every Pages deploy in the workflows (the agent sandbox cannot reach
github.io, so this runs where it can). Retries for up to two minutes because a fresh deploy
needs a moment to propagate. Exit code 1 and a list of problems on failure.
"""

from __future__ import annotations

import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta

PAGES = (
    "index.html",
    "leaderboard.html",
    "questions/index.html",
    "play.html",
    "recruiters.html",
    "backtests.html",
    "status.html",
    "methods.html",
)
FILES = ("data/game.json", "api/v1/leaderboard.json", "static/app.js", "static/style.css")
BUILT = re.compile(r"Built (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) UTC")
ASSET = re.compile(r'(?:href|src)="([^"#:?]+\.(?:css|js|png|svg|ico|xml))"')
USER_AGENT = "ForecastArena-smoke/1 (+https://github.com/JASHD12/forecast-arena)"


def fetch(url: str, timeout: float = 20.0) -> tuple[int, str]:
    """(status, body) of a GET; HTTP errors return their status instead of raising."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""


def check(base: str, now: datetime, max_age: timedelta = timedelta(hours=26)) -> list[str]:
    """Every problem found on the site at `base` (empty list = pass)."""
    base = base.rstrip("/") + "/"
    problems: list[str] = []
    assets: set[str] = set()
    built: datetime | None = None
    for page in PAGES:
        status, body = fetch(base + page)
        if status != 200:
            problems.append(f"{page}: HTTP {status}")
            continue
        if "Forecast Arena" not in body:
            problems.append(f"{page}: does not look like a Forecast Arena page")
        if "Content-Security-Policy" not in body:
            problems.append(f"{page}: no Content-Security-Policy meta tag")
        assets.update(urllib.parse.urljoin(base + page, a) for a in ASSET.findall(body))
        m = BUILT.search(body)
        if m and built is None:
            built = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
    for f in FILES:
        status, _ = fetch(base + f)
        if status != 200:
            problems.append(f"{f}: HTTP {status}")
    for url in sorted(a for a in assets if a.startswith(base)):
        status, _ = fetch(url)
        if status != 200:
            problems.append(f"asset {url[len(base) :]}: HTTP {status}")
    if built is None:
        problems.append("no build time found in the page footer")
    elif now - built > max_age:
        problems.append(f"site built {built:%Y-%m-%d %H:%M} UTC, older than {max_age}")
    return problems


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    wait = 120.0 if "--no-retry" not in argv else 0.0
    deadline = time.monotonic() + wait
    while True:
        problems = check(args[0], datetime.now(UTC))
        if not problems or time.monotonic() >= deadline:
            break
        time.sleep(15)
    for p in problems:
        print(f"smoke-site: {p}")
    if not problems:
        print(f"smoke-site: ok ({args[0]})")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
