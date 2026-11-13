# CV bullets and LinkedIn text

Pick three or four bullets for a CV. Before using any live figure, refresh
[numbers.md](numbers.md) with `--ledger` and copy it from the "Live record" block; until
the official record has run long enough, quote only backtests and say so.

## CV bullets (English)

- Built **Forecast Arena**, a public forecasting benchmark comparing baselines, a
  gradient-boosted model and LLM agents (Claude, LangGraph, a local open-weights model) on
  daily questions from live public data; forecasts are locked in an append-only,
  hash-chained ledger before the answer exists. *(Python, GitHub Actions, GitHub Pages)*
- Designed leakage-free ML with an as-of data gateway and walk-forward backtests; the
  quantile-regression model reached a Brier score of 0.1930 against 0.2466 for the base
  rate over a one-year electricity backtest (paired interval [-0.0655, -0.0414]).
  *(scikit-learn, LightGBM, Optuna, PyTorch, statsmodels)*
- Ran a champion/challenger process with time-ordered cross-validation: an Optuna-tuned
  LightGBM challenger improved Brier by 0.0045 (interval [-0.0069, -0.0021]); a PyTorch
  network and three time-series benchmarks did not beat the champion, and were reported
  as such. *(MLflow, SHAP, Evidently)*
- Built LLM evaluation and tracing: a frozen golden set, prompt A/B, JSON validity and cost
  metrics; it caught an output-cap truncation and lifted first-try valid JSON from 17% to
  100%. *(Anthropic API, structured output, tool use, RAG with local embeddings)*
- Engineered for unattended operation: idempotent scheduled jobs, CI-gated promotion,
  health checks with automatic incident issues, hard LLM cost caps, Docker and Kubernetes
  (kind) checks, dbt models and tests, and Airflow DAGs validated in CI.
  *(FastAPI, DuckDB, Parquet, dbt, Docker, Kubernetes, Airflow)*

## CV bullets (Deutsch)

- Entwicklung von **Forecast Arena**, einem öffentlichen Prognose-Benchmark, der
  Baselines, ein Gradient-Boosting-Modell und LLM-Agenten (Claude, LangGraph, ein lokales
  Open-Weights-Modell) auf täglichen Fragen aus öffentlichen Live-Daten vergleicht; jede
  Prognose wird vor der Auflösung in ein nur erweiterbares, per Hash verkettetes Protokoll
  geschrieben.
- Datenleckfreies ML mit As-of-Datenzugang und Walk-forward-Backtests: Brier-Score 0.1930
  gegenüber 0.2466 für die Basisrate im einjährigen Strompreis-Backtest.
- LLM-Evaluation und Tracing (Golden Set, Prompt-A/B, JSON-Validität, Kosten); dadurch
  einen Abschneidefehler gefunden und die gültigen JSON-Antworten im ersten Versuch von 17%
  auf 100% gesteigert.
- Betrieb ohne Aufsicht: idempotente Jobs, CI-gesteuerte Freigabe, Health-Checks mit
  automatischen Incident-Issues, harte Kostengrenzen, Docker-, Kubernetes-, dbt- und
  Airflow-Prüfungen in der CI.

## LinkedIn project text

> **Forecast Arena: can an LLM agent beat a classical model at forecasting?**
>
> A public benchmark I run on GitHub Actions and Pages. Every day it asks yes/no
> questions about tomorrow from live public data (German electricity prices first).
> Baselines, a gradient-boosted model, Claude with and without tools, a LangGraph agent
> and a small local open-weights model each publish a probability before the answer
> exists, into an append-only, hash-chained public ledger. When the data arrives, every
> forecast is scored with proper scoring rules and confidence intervals.
>
> So far: in a one-year backtest the classical model clearly beats the base rate on
> electricity; the live comparison with the LLMs is still "too early to tell", and the
> site says exactly that. Built with an AI coding agent under my direction; every number
> on the site is computed from the ledger by code. Research project, not advice.
