#!/usr/bin/env python3
"""Run the forecast audit: python3 examples/forecast-audit/report.py --help

A thin wrapper so the tool works from any directory (also one with spaces in its path) with the
standard library only; the calculation lives in forecast_audit.py next to this file.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from forecast_audit import main

if __name__ == "__main__":
    sys.exit(main())
