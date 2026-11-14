"""Static site content: navigation, attributions, library list, information sets (T187).

Split out of `site/build.py`; nothing here reads the ledger.
"""

from __future__ import annotations

from arena.agent.tools import GDELT_ATTRIBUTION
from arena.sources.brightsky import ATTRIBUTION as WX_ATTRIBUTION
from arena.sources.brightsky import LICENCE as WX_LICENCE
from arena.sources.ecb import ATTRIBUTION as ECB_ATTRIBUTION
from arena.sources.smard import ATTRIBUTION as SMARD_ATTRIBUTION
from arena.sources.smard import LICENCE as SMARD_LICENCE
from arena.sources.wikimedia import ATTRIBUTION as WIKI_ATTRIBUTION

#: T185: the primary links a first-time visitor needs; everything else is under "More".
NAV: tuple[tuple[str, str], ...] = (
    ("index.html", "Home"),
    ("questions/index.html", "Questions"),
    ("leaderboard.html", "Leaderboard"),
    ("play.html", "Play"),
    ("guide.html", "How it works"),
    ("stack.html", "Tech stack"),
    ("recruiters.html", "For recruiters"),
)


NAV_MORE: tuple[tuple[str, str], ...] = (
    ("findings.html", "Findings"),
    ("calibration.html", "Calibration"),
    ("backtests.html", "Backtests"),
    ("experiments.html", "Experiments"),
    ("evals.html", "LLM evals"),
    ("llm.html", "LLM observability"),
    ("data.html", "Open data and SQL"),
    ("api.html", "JSON API"),
    ("methods.html", "Methods"),
    ("status.html", "Status"),
    ("about.html", "About"),
)


#: CC BY 4.0 asks to indicate changes: daily statistics, thresholds and returns are
#: computed by this project from the published values.
ATTRIBUTIONS = (
    f"electricity prices: {SMARD_ATTRIBUTION} ({SMARD_LICENCE}; daily statistics computed "
    "by this project)",
    f"weather: {WX_ATTRIBUTION} ({WX_LICENCE}; daily values computed by this project)",
    f"attention: {WIKI_ATTRIBUTION}",
    f"exchange rates: {ECB_ATTRIBUTION}",
    f"news headlines for the agent: {GDELT_ATTRIBUTION}",
)


FEED_BATCHES = 7


#: Marker of an unfinished owner-written draft (docs/legal/*.md); such files stay unpublished.
PLACEHOLDER = "[FILL IN"


SKIP_HELP = {
    "not_sampled": "the AI forecasters answer a fixed daily sample per topic, to cap cost",
    "budget_exhausted": "the daily AI token or request cap was reached",
    "parse_failure": "the AI answer did not match the required JSON format, even after a repair",
    "model_missing": "no AI model or key configured",
    "error": "the forecaster raised an error (for example missing input data)",
}


#: Libraries shown on the tech-stack page, with the version installed where the site is
#: built (read at build time, never typed in by hand).
STACK_LIBRARIES = (
    ("scikit-learn", "gradient-boosted quantile regression and classification, calibration"),
    ("numpy", "numerics"),
    ("scipy", "Student-t distributions for volatility models"),
    ("anthropic", "official Claude SDK for the LLM and agent forecasters"),
    ("pydantic", "typed, validated ledger records and settings"),
    ("jinja2", "static site generation"),
    ("click", "command-line interface for every job"),
    ("joblib", "model artefacts in the registry"),
    ("lightgbm", "challenger gradient-boosting models (quantile regression, classification)"),
    ("optuna", "hyperparameter search for the LightGBM challenger (time-series folds)"),
    ("shap", "SHAP explanations of LightGBM models"),
    ("statsmodels", "ETS and SARIMAX benchmarks in the power backtest"),
    ("llama-cpp-python", "runs the open-weights model of llm_local on the CPU (morning job)"),
    ("dbt-duckdb", "dbt models and tests (staging, marts) over the open data, built in CI"),
    ("fastapi", "the read-only REST API (`arena api`), served from the Docker image in CI"),
    ("uvicorn", "the ASGI server that runs the REST API"),
    ("streamlit", "the interactive dashboard (apps/dashboard), smoke-tested with AppTest in CI"),
    ("nbclient", "executes the analysis notebook (pandas, DuckDB, Polars on the open data) in CI"),
    (
        "polars",
        "the notebook's second engine: the Brier table from the Parquet files, checked"
        " against DuckDB",
    ),
    ("mcp", "official MCP SDK: the read-only `arena mcp` server over the ledger"),
    ("langgraph", "the agent_graph forecaster's state machine (plan, retrieve, tools, critique)"),
    ("fastembed", "local ONNX text embeddings for the agent's similar-questions tool (RAG)"),
    ("chronos-forecasting", "Chronos-Bolt tiny (pretrained time-series model), backtest only"),
    ("mlflow-skinny", "experiment tracking of the weekly retraining (SQLite backend)"),
    ("evidently", "data-drift reports on model inputs"),
)


INFORMATION_SETS = (
    ("base_rate", "Trailing outcomes of the same template and entity", "all questions"),
    ("persistence", "Yesterday's outcome of the same template and entity", "all questions"),
    ("ml", "The full as-of context", "all questions (planned)"),
    (
        "llm_plain",
        "Question text, resolution rule, current date; no data, no tools",
        "daily sample (planned)",
    ),
    (
        "llm_context",
        "The above plus a compact rendering of the as-of context",
        "daily sample (planned)",
    ),
    ("agent", "As llm_context, plus read-only tools", "daily sample (planned)"),
    (
        "llm_local",
        "As llm_context, answered by an open model (Qwen2.5-1.5B) on the runner's CPU",
        "daily sample (planned)",
    ),
    (
        "agent_graph",
        "As agent, run as a LangGraph graph: plan, retrieved evidence, tools, self-check",
        "1 question per topic per day (planned)",
    ),
)


AI_FORECASTERS = frozenset({"llm_plain", "llm_context", "agent", "agent_graph", "llm_local"})


TEMPLATE_VERSION_NOTES = {
    1: "published on the morning of the batch day",
    2: "published the evening before the batch day (T160); same text and lock",
}
