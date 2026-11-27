"""Record raw GDELT DOC 2.0 timeline responses as test fixtures (T371).

    python scripts/record_gdelt_fixture.py OUT_DIR [--start 20261101000000] [--end 20261110000000]

Saves, for one coin query and both modes (``TimelineTone``, ``TimelineVolRaw``), the unmodified
response body plus ``provenance.json`` (URL, UTC time, status, SHA-256). It parses nothing, so
the parser written afterwards is checked against a real response. Waits 6 seconds between calls
(GDELT asks for one request every 5 seconds, SOURCES.md). Needs the network; never part of
``make check``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

BASE = "https://api.gdeltproject.org/api/v2/doc/doc"
USER_AGENT = "forecast-arena-research/0.1 (github.com/JASHD12/forecast-arena)"


def main() -> None:
    """Fetch and save the two responses."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--query", default="bitcoin sourcelang:english")
    ap.add_argument("--start", default="20261101000000")
    ap.add_argument("--end", default="20261110000000")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    provenance = []
    for i, mode in enumerate(("TimelineTone", "TimelineVolRaw")):
        if i:
            time.sleep(6)
        q = urllib.parse.urlencode(
            {
                "query": args.query,
                "mode": mode,
                "format": "json",
                "startdatetime": args.start,
                "enddatetime": args.end,
            }
        )
        url = f"{BASE}?{q}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read()
            status = resp.status
        (args.out_dir / f"{mode.lower()}.json").write_bytes(body)
        provenance.append(
            {
                "mode": mode,
                "url": url,
                "status": status,
                "fetched_at": datetime.now(UTC).isoformat(),
                "sha256": hashlib.sha256(body).hexdigest(),
            }
        )
    (args.out_dir / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", "utf-8")
    print(f"saved {len(provenance)} responses to {args.out_dir}")


if __name__ == "__main__":
    main()
