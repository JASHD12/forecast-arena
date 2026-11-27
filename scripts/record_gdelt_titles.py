"""Record one raw GDELT DOC 2.0 article-list response as a test fixture (T375).

    python scripts/record_gdelt_titles.py OUT_DIR [--query "bitcoin sourcelang:english"]

Saves the unmodified body of ``mode=artlist&format=json`` for one day with 20 records, plus
``provenance.json`` (URL, UTC time, status, SHA-256). It parses nothing, so the parser written
afterwards is checked against a real response. GDELT's article list has titles, outlets, URLs
and times only (no article text, S7). Retries on 429 with growing pauses. Standard library only,
runs on Python 3.9. Network only; never part of ``make check``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UTC_TZ = timezone.utc  # noqa: UP017 (not datetime.UTC: that needs Python 3.11, macOS ships 3.9)
BASE = "https://api.gdeltproject.org/api/v2/doc/doc"
USER_AGENT = "forecast-arena-research/0.1 (github.com/JASHD12/forecast-arena)"


def main() -> None:
    """Fetch and save the response."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--query", default="bitcoin sourcelang:english")
    ap.add_argument("--start", default="20261120000000")
    ap.add_argument("--end", default="20261120235959")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    q = urllib.parse.urlencode(
        {
            "query": args.query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": "20",
            "sort": "datedesc",
            "startdatetime": args.start,
            "enddatetime": args.end,
        }
    )
    url = f"{BASE}?{q}"
    status, body = 0, b""
    for attempt in range(6):
        if attempt:
            time.sleep(30 * attempt)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                status, body = resp.status, resp.read()
            break
        except urllib.error.HTTPError as exc:
            status = exc.code
            print(f"HTTP {status}, attempt {attempt + 1} of 6", flush=True)
        except OSError as exc:
            print(f"{exc!r}, attempt {attempt + 1} of 6", flush=True)
    if status != 200:
        raise SystemExit(f"no good response (last status {status})")
    (args.out_dir / "artlist.json").write_bytes(body)
    prov = {
        "mode": "artlist",
        "url": url,
        "status": status,
        "fetched_at": datetime.now(UTC_TZ).isoformat(),
        "sha256": hashlib.sha256(body).hexdigest(),
    }
    (args.out_dir / "provenance.json").write_text(json.dumps([prov], indent=2) + "\n", "utf-8")
    print(f"saved {len(body)} bytes to {args.out_dir}")


if __name__ == "__main__":
    main()
