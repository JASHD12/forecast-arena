# Jashdeep Singh

**Werkstudent AI / Machine Learning / Data Science (Germany)**, also open to full-time applied ML engineering roles.

M.Sc. Data Science student with three years of software engineering experience. I use Python to compare forecasts and text classifiers on fixed test sets and document how to repeat the experiments.

📍 Gießen, Germany · open to relocating anywhere in Germany

## Education

**Master of Science (M.Sc.) in Data Science**, Philipps-Universität Marburg · Oct 2026 – present (expected graduation Oct 2028)
Current coursework in forecasting and computer vision.

**Bachelor of Engineering (B.E.) in Computer Engineering**, Thapar Institute of Engineering & Technology, India · Jul 2019 – Jun 2023 · CGPA 8.16/10

## Work experience

**Software Engineer, Paytm Money** · India · Jan 2025 – Sep 2026
- Built Java/Spring Boot services for 100K+ monthly portfolio syncs and 50K+ monthly sell and switch orders. Added retry handling to prevent duplicate orders.
- Built Kafka ingestion and validation across 5M accounts. Investigated production issues with AWS logs and metrics.

**Software Engineer 1, MAQ Software** · India · Nov 2023 – Nov 2024
- Developed a Python/FastAPI service for a LangChain document assistant and evaluated its answers against the passages it retrieved.
- Automated SQL Server-to-Power BI reporting with Azure and Databricks, saving about 15 hours per week.

**Software Developer (Full-time), Advantage Club** · India · Jul 2023 – Sep 2023
- Built React survey forms for a planned 1M+ user rollout and improved performance on lower-end devices.

**Software Development Intern, Advantage Club** · India · Jan 2023 – Jun 2023
- Integrated an HR dashboard with third-party systems and cut award email processing time by 60%.

## Featured project: Forecast Arena

A live, public benchmark: simple baselines, a classical ML model, and LLM forecasters publish probabilities for about 30 yes/no questions a day (electricity, weather, Wikipedia attention, exchange rates, crypto thresholds) **before the answer exists**, into an append-only, hash-chained ledger. The research question: when does an LLM agent beat a classical model, and when does it not? An honest "it does not" is a valid result.

**[Live site](https://jashd12.github.io/forecast-arena/)** · **[Ask the Arena](https://jashd12.github.io/forecast-arena/ask.html)** (free chat over the published record) · **[For recruiters](https://jashd12.github.io/forecast-arena/recruiters.html)** · **[forecast-audit](https://jashd12.github.io/forecast-arena/audit.html)** (offline decision-audit tool and worked case) · [Source](https://github.com/JASHD12/forecast-arena)

**Result so far (backtest, not the live record):** over 365 days of German day-ahead electricity, the gradient-boosted model scores Brier 0.1930 against 0.2205 for "same as last time" and 0.2466 for the base rate (lower is better; always saying 50% scores 0.25). Paired difference to persistence: -0.0275 [-0.0378, -0.0162], supported. Caveat: the 2190 questions come from only 365 independent days (about 6 correlated questions per day), so intervals resample whole days.

**Live record:** the first batch was 2026-11-13; days before 2026-11-23 are rehearsal and do not count towards the headline scores, and the official record has run since 2026-11-23 (`meta/official_start.json` on the ledger branch). Whether LLM agents beat the classical model is **too early to tell**; the [Status page](https://jashd12.github.io/forecast-arena/status.html) shows the current counts.

### What it shows

- **A classical model that clearly beats the base rate** (backtest, 365 days of German electricity): Brier 0.1930 vs 0.2466, paired difference -0.0536 [-0.0655, -0.0414]. Calibrated gradient-boosted quantile regression.
- **Honest champion/challenger:** an Optuna-tuned LightGBM challenger improved Brier by -0.0045 [-0.0069, -0.0021] (supported); a PyTorch network (-0.0003 [-0.0087, +0.0081], interval includes zero), four time-series models (Chronos-2 0.2073, Chronos-Bolt 0.2142, SARIMAX 0.2279, ETS 0.2441) and a global LightGBM (+0.0149 [+0.0097, +0.0198], supported) did not beat the champion, and say so.
- **LLM engineering with evals:** a frozen golden set caught a silent output-cap truncation; first-try valid JSON went from 17% to 100%. Tool-using agent, LangGraph agent, RAG over past questions, tracing, hard daily cost caps.
- **Forecasts locked before the truth:** an append-only, hash-chained ledger on a git branch; `arena ledger verify --git` lets anyone check that no forecast was written after its question locked. Failures are recorded as skips, never filled in.
- **Runs itself:** scheduled GitHub Actions jobs, CI-gated promotion to a stable branch, health checks with incident issues, Docker, Kubernetes (kind), dbt and Airflow validated in CI. Live record: "too early to tell" until the statistics can decide.
- **Agent experiments, pre-registered, negative results published:** forecasting skills loaded on demand gave a Brier difference of -0.0090 [-0.0204, +0.0028] against the calculator-only agent on 90 questions (interval includes zero, cost just over its limit: not launched); a committee of specialist agents over the A2A protocol answered 87 of 90 questions and scored +0.0060 [-0.0036, +0.0152] against one agent with skills on the same questions (interval includes zero, no benefit shown); it stays off.
- **LLM fine-tuning, measured honestly:** a QLoRA fine-tune of Qwen2.5-1.5B on replayed questions beat its untuned self (-0.0109 [-0.0154, -0.0062]) but not the base rate (+0.0196 [+0.0069, +0.0332]) and not the ML model (+0.0714 [+0.0354, +0.1061]); pre-registered, time-split, negative result published (paired Brier differences, 46 test days). Preference tuning (DPO) also beat the untuned model (-0.0123 [-0.0168, -0.0075]) but was no different from plain fine-tuning (-0.0015 [-0.0032, +0.0005]) and still worse than the base rate (+0.0181 [+0.0054, +0.0311]). The shipped 4-bit GGUF kept almost none of that gain (Brier -0.0013 [-0.0039, +0.0015] against the untuned model, +0.0292 [+0.0160, +0.0427] against the base rate): it runs live as an experiment and the loss from quantisation is itself a finding.
- **Prompt optimisation, pre-registered:** a search over eight prompt variants for the free 1.5B model, chosen on validation data only, beat the live prompt on the frozen test sets (-0.0076 [-0.0135, -0.0017]) but stayed worse than the base rate (+0.0375 [+0.0267, +0.0488]): prompting helps a little, it does not rescue a small model here.
- **Uncertainty and serving:** conformal price bands raise 80% coverage from 71.0% to 79.4% over 7 months; LightGBM models are exported to ONNX with parity tests and served behind a REST endpoint; a cited, offline docs assistant answers 60% of a hand-written question set and refuses 83% of the out-of-scope ones.

### Skills with the code behind them

Python, typing, testing · SQL, DuckDB, Parquet, Polars · dbt · scikit-learn, calibration · LightGBM, Optuna, SHAP · PyTorch · Time-series models · MLOps: MLflow, Evidently, champion/challenger · Statistics · LLM APIs, prompts, structured output · Agents and tool use · RAG, embeddings · LangGraph · Open-weight models (llama.cpp) · LLM fine-tuning (QLoRA, PEFT, GGUF) · Hybrid retrieval and guardrails · ONNX export and serving · Vector database (Qdrant) · Cloud as code (Terraform, AWS, S3) · Observability (Prometheus, Jaeger, OpenTelemetry) · TypeScript · Retrieval-grounded chat with refusals · Decision analysis and an open-source tool · Online learning and unsupervised learning · pandas and scikit-learn Pipelines · LLM evals, tracing, OpenTelemetry · MCP · Multi-agent systems, A2A · REST and JSON APIs · Docker, Kubernetes, Airflow · CI/CD on GitHub Actions · Data integrity · Dashboards and frontend

## How it was built

Specified and directed by me; implemented with AI coding agents; every figure on the site is generated from the public record by code. Research project, not advice of any kind.

## Another project: DataPilot (text classification and retrieval, 2026)

- Compared word and character TF-IDF on 40,423 chronologically split Portuguese reviews. Checked macro-F1 on held-out reviews with previously unseen wording.
- Evaluated multilingual retrieval with lexical search, E5 embeddings and reciprocal-rank fusion.

## Technical skills

- **Programming:** Python, Java, C++, SQL
- **Machine learning:** scikit-learn, LightGBM, PyTorch, time-series backtesting, calibration
- **Language models:** QLoRA, LangChain, LangGraph, retrieval, LLM evaluation
- **Software and data:** Git, Docker, GitHub Actions, Kafka, Databricks

## Achievements

- Codeforces Specialist, global rank 433 in Round 782 (Div. 2)
- Amazon ML Summer School, selected from 30K+ applicants

## Languages

English C1 (IELTS) · German A1 (learning) · Hindi native
