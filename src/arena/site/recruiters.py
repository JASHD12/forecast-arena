"""The 'For recruiters' page (T140): what a working-student posting asks for, mapped to
the page that shows it and the code that does it.

Every entry names files that exist in the repository and that CI runs (a test checks
both), so nothing is listed that the project does not really use (integrity rule I5).
Numbers are not typed here: the page shows live counts from the ledger and links to the
generated backtest and evaluation pages.
"""

from __future__ import annotations

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
        "SQL, DuckDB, Parquet",
        "Open data as Parquet; analytics SQL with DuckDB, shown with its queries",
        "data.html",
        ("src/arena/analytics/sql.py",),
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
        "LLM evals and tracing",
        "Frozen golden set, prompt A/B, JSON validity and cost; one span per model call",
        "evals.html",
        ("src/arena/evals", "src/arena/llm/tracing.py"),
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
