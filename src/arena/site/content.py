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
    ("lab.html", "Experiments lab"),
    ("llm-engineering.html", "LLM engineering"),
    ("ask.html", "Ask the Arena"),
    ("audit.html", "Forecast audit"),
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
    "model_missing": "no model or required configuration available",
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
    ("ml", "The full as-of context", "all questions"),
    (
        "llm_plain",
        "Question text, resolution rule, current date; no data, no tools (retired 2026-11-27: "
        "no new forecasts, earlier ones stay)",
        "daily sample",
    ),
    (
        "llm_context",
        "The above plus a compact rendering of the as-of context",
        "daily sample",
    ),
    ("agent", "As llm_context, plus read-only tools", "daily sample"),
    (
        "llm_local",
        "As llm_context, answered by an open model (Qwen2.5-1.5B) on the runner's CPU",
        "daily sample",
    ),
    (
        "agent_graph",
        "As agent, run as a LangGraph graph: plan, retrieved evidence, tools, self-check",
        "1 question per topic per day",
    ),
    (
        "llm_local_ft",
        "As llm_context, answered by Qwen2.5-1.5B fine-tuned with QLoRA (experimental)",
        "daily sample",
    ),
    (
        "llm_router",
        "The forecasts of ml, llm_local_ft and llm_context for one question (experimental)",
        "daily sample",
    ),
    (
        "agent_hybrid",
        "As agent, with hybrid retrieval of past questions and guarded tool text (experimental)",
        "daily sample",
    ),
    (
        "agent_quant",
        "As agent, plus a reference estimate computed from the stored data and a probability "
        "calculator (experimental)",
        "daily sample",
    ),
    (
        "agent_analyst",
        "As agent, told to start from the ml forecast and change it only for evidence the model "
        "cannot see (experimental)",
        "daily sample",
    ),
    (
        "agent_skills",
        "As agent_quant, plus the load_skill tool: short topic notes written by the project team, "
        "loaded on demand (experimental)",
        "daily sample",
    ),
    (
        "agent_graph_skills",
        "As agent_graph (the LangGraph agent), plus the reference estimate, the probability "
        "calculator and the load_skill tool (experimental)",
        "daily sample",
    ),
    (
        "agent_hybrid_skills",
        "As agent_hybrid (hybrid retrieval and guarded tool text), plus the reference estimate, "
        "the probability calculator and the load_skill tool (experimental)",
        "daily sample",
    ),
    (
        "agent_committee",
        "A committee: a chair that calls four specialist agents over the A2A protocol (a reference "
        "estimate, the base rate and similar past questions, as-of headlines, and a skeptic that "
        "critiques the draft); it sees only the stored data, the base rate and tool results "
        "published before the forecast time, never the ML forecast (experimental)",
        "daily sample",
    ),
    (
        "llm_context_cal",
        "The raw answer of llm_context for the same question, passed through one fixed logit map "
        "fitted on lab training answers (power questions only; other topics pass through "
        "unchanged); no tokens, no other data (experimental)",
        "the daily sample of llm_context",
    ),
    (
        "sentiment",
        "The ml probability of the same crypto question and the news tone and article count of "
        "the days before it (GDELT, aggregate numbers only, each day counted 12 hours after it "
        "ended); backtest only so far, not running live (experimental)",
        "crypto questions",
    ),
    (
        "bandit_hedge",
        "The other forecasters' forecasts of the same question, blended with weights learned "
        "online from resolved questions (Hedge; experimental)",
        "every question with two or more forecasts",
    ),
)


AI_FORECASTERS = frozenset(
    {
        "llm_plain",
        "llm_context",
        "agent",
        "agent_graph",
        "llm_local",
        "llm_local_ft",
        "llm_router",
        "agent_hybrid",
        "agent_quant",
        "agent_analyst",
        "agent_skills",
        "agent_graph_skills",
        "agent_hybrid_skills",
        "agent_committee",
        "llm_context_cal",
    }
)
#: Forecasters that no longer write new forecasts (their history stays visible).
RETIRED_FORECASTERS = frozenset({"llm_plain"})  # retired 2026-11-27 (owner decision)
#: Experimental forecasters (SPEC 17): named "(experimental)", outside the common-set board.
EXPERIMENTAL_FORECASTERS = frozenset(
    {
        "llm_local_ft",
        "llm_router",
        "agent_hybrid",
        "agent_quant",
        "agent_analyst",
        "agent_skills",
        "agent_graph_skills",
        "agent_hybrid_skills",
        "agent_committee",
        "llm_context_cal",
        "sentiment",
        "bandit_hedge",
    }
)


TEMPLATE_VERSION_NOTES = {
    1: "published on the morning of the batch day",
    2: "published the evening before the batch day (T160); same text and lock",
}
