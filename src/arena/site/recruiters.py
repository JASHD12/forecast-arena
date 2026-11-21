"""The 'For recruiters' page (T140): what a working-student posting asks for, mapped to
the page that shows it and the code that does it.

Every entry names files that exist in the repository and that CI runs (a test checks
both), so nothing is listed that the project does not really use (integrity rule I5).
Numbers are not typed here: the page shows live counts from the ledger and links to the
generated backtest and evaluation pages.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

#: (skill, what it does in this project, site page or "", repository paths)
PROOFS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "Python, typing, testing",
        "Typed package, mypy, hundreds of unit tests, property-based tests, offline end-to-end "
        "run on every push",
        "status.html",
        ("src/arena", "tests", "Makefile"),
    ),
    (
        "SQL, DuckDB, Parquet, Polars",
        "Open data as Parquet; analytics SQL with DuckDB, shown with its queries; the "
        "analysis notebook cross-checks DuckDB against Polars on the same files",
        "data.html",
        ("src/arena/analytics/sql.py", "notebooks/explore.ipynb"),
    ),
    (
        "dbt",
        "Staging and mart models with tests (unique, not null, accepted values, foreign "
        "keys), built in CI",
        "data.html",
        ("analytics/dbt",),
    ),
    (
        "scikit-learn, calibration",
        "Gradient-boosted quantile regression turned into calibrated probabilities",
        "backtests.html",
        ("src/arena/forecasters/ml_power.py",),
    ),
    (
        "LightGBM, Optuna, SHAP",
        "Challenger tuned with time-ordered cross-validation; SHAP explanations",
        "experiments.html",
        ("src/arena/forecasters/ml_power_lgbm.py", "src/arena/ops/explain.py"),
    ),
    (
        "PyTorch",
        "Quantile neural network trained with pinball loss; measured against the champion",
        "backtests.html",
        ("src/arena/forecasters/ml_power_torch.py",),
    ),
    (
        "Time-series models",
        "ETS, SARIMAX (statsmodels) and a pretrained Chronos-Bolt model as benchmarks",
        "backtests.html",
        ("src/arena/forecasters/ts_bench.py",),
    ),
    (
        "MLOps: MLflow, Evidently, champion/challenger",
        "Weekly retraining with a written promotion rule, run tracking and drift reports",
        "experiments.html",
        ("src/arena/ops/weekly.py", "src/arena/ops/drift.py"),
    ),
    (
        "Statistics",
        "Proper scoring rules, day-block bootstrap, Diebold-Mariano test, power analysis, "
        "conformal prediction",
        "findings.html",
        ("src/arena/scoring", "src/arena/ops/explain.py"),
    ),
    (
        "LLM APIs, prompts, structured output",
        "Versioned prompts, strict JSON answers with one repair, hard daily cost caps",
        "llm.html",
        ("src/arena/forecasters/llm.py", "src/arena/llm"),
    ),
    (
        "Agents and tool use",
        "Tool-calling agent with call and time limits and prompt-injection-safe tool output",
        "questions/index.html",
        ("src/arena/agent/forecaster.py", "src/arena/agent/tools.py"),
    ),
    (
        "RAG, embeddings",
        "Local ONNX embeddings, similarity search over past questions with a no-leakage rule",
        "",
        ("src/arena/agent/retrieval.py",),
    ),
    (
        "LangGraph",
        "The agent as a state machine (plan, retrieve, tools, critique) behind the same caps",
        "",
        ("src/arena/agent/graph.py",),
    ),
    (
        "Open-weight models (llama.cpp)",
        "A 1.5B model on the CI runner's CPU, same contract as the API model, no API cost",
        "",
        ("src/arena/llm/local.py",),
    ),
    (
        "LLM evals, tracing, OpenTelemetry",
        "Frozen golden set, prompt A/B, JSON validity and cost; one span per model call, "
        "exported as OTLP/JSON with the OpenTelemetry GenAI attribute names",
        "llm.html",
        ("src/arena/evals", "src/arena/llm/tracing.py", "src/arena/llm/otlp.py"),
    ),
    (
        "MCP",
        "Read-only MCP server so AI assistants can query the benchmark",
        "",
        ("src/arena/mcp_server.py",),
    ),
    (
        "REST and JSON APIs",
        "FastAPI service and a static JSON API with schemas generated from pydantic models",
        "api.html",
        ("src/arena/api/app.py", "src/arena/site/api.py"),
    ),
    (
        "Docker, Kubernetes, Airflow",
        "Image built and API smoke-tested in CI; manifests applied to a kind cluster; DAGs "
        "parsed by Airflow (validated in CI, not hosted)",
        "",
        ("Dockerfile", "deploy/k8s", "orchestration/airflow"),
    ),
    (
        "CI/CD on GitHub Actions",
        "Scheduled jobs, promotion to a stable branch after green CI, incident issues",
        "status.html",
        (".github/workflows",),
    ),
    (
        "Data integrity",
        "Append-only ledger with a daily hash chain; anyone can verify it",
        "guide.html#verify",
        ("src/arena/ledger",),
    ),
    (
        "Dashboards and frontend",
        "Streamlit dashboard; static site with an accessible game, checked in Chromium",
        "play.html",
        ("apps/dashboard", "src/arena/site", "tools/a11y"),
    ),
)


#: Three reading paths for the three role families (P2). Each entry: (role, why, links) with
#: links as (label, site page or repository path, is_repo_path). A test checks every one
#: resolves; a repository path must exist and be run by CI.
ROLE_PATHS: tuple[tuple[str, str, tuple[tuple[str, str, bool], ...]], ...] = (
    (
        "AI engineering",
        "LLM and agent forecasters with budgets, tracing and an eval that caught a real bug.",
        (
            ("The eval that caught a bug", "evals.html", False),
            ("How the LLM calls are traced", "llm.html", False),
            ("The agent loop (code)", "src/arena/agent/forecaster.py", True),
            ("Experiments lab: fine-tuning, retrieval, guardrails", "lab.html", False),
        ),
    ),
    (
        "ML and MLOps",
        "Weekly retraining, promotion by rule, hashed model artifacts, CI-gated releases.",
        (
            ("Champion and challenger timeline", "experiments.html", False),
            ("Model registry (code)", "src/arena/forecasters/registry.py", True),
            ("Pipeline status", "status.html", False),
            ("Calibration study (code)", "src/arena/lab/calibration_study.py", True),
        ),
    ),
    (
        "Data science",
        "Proper scores, day-block intervals and honest comparison against a base rate.",
        (
            ("A year of backtests", "backtests.html", False),
            ("Live leaderboard", "leaderboard.html", False),
            ("The SQL behind the numbers", "data.html", False),
            ("Retrieval and grounding experiments", "lab.html", False),
        ),
    ),
)

FACT_KEYS = ("city", "availability", "languages", "linkedin", "cv_url", "email")
_DRAFT = "[FILL IN"


def load_facts(content_dir: Path | None) -> dict[str, str]:
    """The owner's optional facts from `recruiter_facts.json` (owner item H16).

    Missing file, missing keys, empty values, draft markers and unsafe link schemes are
    all dropped, so nothing unconfirmed is ever shown (I5). Links must be https, mailto
    for `email`."""
    if content_dir is None:
        return {}
    path = content_dir / "recruiter_facts.json"
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[str, str] = {}
    for key in FACT_KEYS:
        val = raw.get(key) if isinstance(raw, dict) else None
        if not isinstance(val, str) or not val.strip() or _DRAFT in val:
            continue
        val = val.strip()
        if key in ("linkedin", "cv_url") and not val.startswith("https://"):
            continue
        if key == "email" and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", val):
            continue
        out[key] = val
    return out


def hero_result(backtest: dict[str, Any] | None) -> dict[str, str] | None:
    """The one result line of the first screen, copied from the backtest card (I5).

    Needs `ml` and `persistence` rows; returns None otherwise so the page shows no number
    rather than a guessed one."""
    if not backtest:
        return None
    vals = {fid: v for fid, v, _ in backtest["rows"]}
    vp = backtest.get("vs_persistence")
    if "ml" not in vals or "persistence" not in vals or not vp:
        return None
    return {
        "ml": vals["ml"],
        "persistence": vals["persistence"],
        "days": str(backtest["days"]),
        "diff": vp["diff"],
        "interval": vp["interval"],
        "supported": "yes" if vp["supported"] else "no",
    }
