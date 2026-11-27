"""Record raw GDELT DOC 2.0 daily tone and volume history for the five coins (T371).

    python scripts/record_gdelt_history.py OUT_DIR [--start 2025-11-01] [--end 2026-11-10]

For each coin query of lab/prereg/sentiment.md and each mode (TimelineTone, TimelineVolRaw)
the range is fetched in 90-day chunks and every response body is saved unmodified, with a
``manifest.json`` (URL, status, bytes, SHA-256, UTC time). A 429 or a network error is retried
after a pause; a chunk that still fails is recorded as failed, never filled. One request every
6 seconds (GDELT asks for one every 5). Network only; never part of ``make check``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

UTC_TZ = timezone.utc  # noqa: UP017 (not datetime.UTC: that needs Python 3.11, macOS ships 3.9)
BASE = "https://api.gdeltproject.org/api/v2/doc/doc"
USER_AGENT = "forecast-arena-research/0.1 (github.com/JASHD12/forecast-arena)"
QUERIES = {
    "bitcoin": "bitcoin sourcelang:english",
    "ethereum": "ethereum sourcelang:english",
    "solana": "solana crypto sourcelang:english",
    "ripple": "(xrp OR ripple) crypto sourcelang:english",
    "binancecoin": '("binance coin" OR bnb) sourcelang:english',
}
MODES = ("TimelineTone", "TimelineVolRaw")
CHUNK_DAYS = 90
PAUSE = 6.0
RETRIES = 5
MAX_FAILED_IN_A_ROW = 3


def fetch(url: str) -> tuple[int, bytes]:
    """GET with retries on 429 and network errors; returns (status, body) of the last try."""
    status, body = 0, b""
    for attempt in range(RETRIES):
        if attempt:
            time.sleep(30 * attempt)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=90) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            status, body = exc.code, exc.read() or b""
            if exc.code != 429 and exc.code < 500:
                return status, body
        except (OSError, TimeoutError):
            status, body = 0, b""
    return status, body


def chunks(start: date, end: date) -> list[tuple[date, date]]:
    """Consecutive [start, end] ranges of at most CHUNK_DAYS days covering start..end."""
    out = []
    d = start
    while d <= end:
        e = min(end, d + timedelta(days=CHUNK_DAYS - 1))
        out.append((d, e))
        d = e + timedelta(days=1)
    return out


def main() -> None:
    """Fetch every coin, mode and chunk; write files and the manifest."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--start", default="2025-11-01")
    ap.add_argument("--end", default="2026-11-10")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    first = True
    streak = 0
    for coin, query in QUERIES.items():
        for mode in MODES:
            for a, b in chunks(date.fromisoformat(args.start), date.fromisoformat(args.end)):
                if not first:
                    time.sleep(PAUSE)
                first = False
                q = urllib.parse.urlencode(
                    {
                        "query": query,
                        "mode": mode,
                        "format": "json",
                        "startdatetime": a.strftime("%Y%m%d") + "000000",
                        "enddatetime": b.strftime("%Y%m%d") + "235959",
                    }
                )
                url = f"{BASE}?{q}"
                status, body = fetch(url)
                name = f"{coin}_{mode.lower()}_{a:%Y%m%d}_{b:%Y%m%d}.json"
                if status == 200:
                    (args.out_dir / name).write_bytes(body)
                manifest.append(
                    {
                        "coin": coin,
                        "mode": mode,
                        "start": a.isoformat(),
                        "end": b.isoformat(),
                        "file": name if status == 200 else None,
                        "status": status,
                        "bytes": len(body),
                        "sha256": hashlib.sha256(body).hexdigest(),
                        "url": url,
                        "fetched_at": datetime.now(UTC_TZ).isoformat(),
                    }
                )
                print(f"{status} {len(body):>8} {name}", flush=True)
                streak = 0 if status == 200 else streak + 1
                if streak >= MAX_FAILED_IN_A_ROW:
                    print("stopping: GDELT keeps refusing", flush=True)
                    break
            if streak >= MAX_FAILED_IN_A_ROW:
                break
        if streak >= MAX_FAILED_IN_A_ROW:
            break
    (args.out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", "utf-8")
    failed = sum(1 for m in manifest if m["status"] != 200)
    print(f"{len(manifest) - failed} of {len(manifest)} chunks saved, {failed} failed")


if __name__ == "__main__":
    main()
