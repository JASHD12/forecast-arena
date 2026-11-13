"""Write the offline end-to-end ledger (fixture data, FakeLLM) into a folder:
`python scripts/make_e2e_ledger.py OUT_DIR`. Used to serve the API in Docker and CI
without network access. Fixture data, not the live record."""

import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / "tests" / d) for d in ("e2e", "unit")]

from test_e2e import run_schedule  # noqa: E402

if __name__ == "__main__":
    led = run_schedule(Path(sys.argv[1]))
    print(f"e2e ledger written: {len(led.list_files())} files in {sys.argv[1]}")
