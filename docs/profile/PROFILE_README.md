# Jashdeep Singh

**Software engineer and M.Sc. Data Science student (Marburg, expected 2028)**, open to Werkstudent and full-time roles in AI/ML, data science, data engineering and software engineering in Germany.

[jashdeep188@gmail.com](mailto:jashdeep188@gmail.com) · 📍 Gießen, Germany · open to relocating anywhere in Germany

![Python](https://img.shields.io/badge/-Python-3776AB?logo=python&logoColor=white) ![Azure](https://img.shields.io/badge/-Azure-0078D4?logo=azure&logoColor=white) ![GitHub Actions](https://img.shields.io/badge/-GitHub_Actions-2088FF?logo=github_actions&logoColor=white) ![PyTorch](https://img.shields.io/badge/-PyTorch-EE4C2C?logo=pytorch&logoColor=white) ![LangChain](https://img.shields.io/badge/-LangChain-1C3C3C?logo=langchain&logoColor=white)

M.Sc. Data Science student and software engineer (three years): Python, Azure, data platforms, ML and LLM evaluation. I automate reporting, build APIs and CI/CD checks, and compare forecasts and text classifiers on fixed test sets, documenting how to repeat the experiments.

## What I work on

- **Forecasting and ML evaluation:** Forecast Arena, below.
- **Data platforms and backend:** Kafka ingestion, Azure Databricks reporting, Java/Spring Boot APIs (see Experience).
- **LLM apps and evaluation:** a LangChain document assistant, and a measured QLoRA fine-tuning study inside Forecast Arena.

## Featured projects

### [Forecast Arena](https://github.com/JASHD12/forecast-arena)

A live, public benchmark: simple baselines, a classical ML model and LLM forecasters publish probabilities for yes/no questions about tomorrow (German day-ahead electricity, weather, Wikipedia attention, exchange rates, crypto) **before the answer exists**, into an append-only, hash-chained ledger. When does an LLM agent beat a classical model, and when does it not? An honest "it does not" is a valid result.

**[Live site](https://jashd12.github.io/forecast-arena/)** · **[For recruiters](https://jashd12.github.io/forecast-arena/recruiters.html)** · **[Ask the Arena](https://jashd12.github.io/forecast-arena/ask.html)** · [Source](https://github.com/JASHD12/forecast-arena)

[![Standings](https://jashd12.github.io/forecast-arena/standings.svg)](https://jashd12.github.io/forecast-arena/)

**Result so far (backtest, not the live record):** over 365 days of German day-ahead electricity, the gradient-boosted model scores Brier 0.1930 against 0.2205 for "same as last time" and 0.2466 for the base rate (lower is better; always saying 50% scores 0.25). Paired difference to persistence: -0.0275 [-0.0378, -0.0162], supported.

**Live record:** Whether LLM agents beat the classical model is **too early to tell**; the [Status page](https://jashd12.github.io/forecast-arena/status.html) shows the current counts.

- **A classical model that clearly beats the base rate** (backtest, 365 days of German electricity): Brier 0.1930 vs 0.2466, paired difference -0.0536 [-0.0655, -0.0414]. Calibrated gradient-boosted quantile regression.
- **Forecasts locked before the truth:** an append-only, hash-chained ledger on a git branch; `arena ledger verify --git` lets anyone check that no forecast was written after its question locked. Failures are recorded as skips, never filled in.

### DataPilot (text classification and retrieval, 2026)

- Compared word and character TF-IDF on 40,423 chronologically split Portuguese reviews. Checked macro-F1 on held-out reviews with previously unseen wording.
- Evaluated multilingual retrieval with lexical search, E5 embeddings and reciprocal-rank fusion.

## Experience

- **Software Engineer, Paytm Money** · India · Jan 2025 – Sep 2026
- **Software Engineer 1, MAQ Software** · India · Nov 2023 – Nov 2024
- **Software Developer (Full-time), Advantage Club** · India · Jul 2023 – Sep 2023
- **Software Development Intern, Advantage Club** · India · Jan 2023 – Jun 2023

<details><summary>What I did in each role</summary>

**Software Engineer, Paytm Money** · India · Jan 2025 – Sep 2026
- Built Kafka ingestion and validation for portfolio data across 5M accounts. Investigated production issues using AWS logs and metrics.
- Built Java and Spring Boot APIs for 100K+ monthly portfolio syncs. Worked with MySQL and Redis and contributed to microservice designs.
- Used idempotency to prevent duplicate orders on retry. The APIs handled 50K+ mutual fund sell and switch orders per month.

**Software Engineer 1, MAQ Software** · India · Nov 2023 – Nov 2024
- Automated SQL Server-to-Power BI reporting with Azure Databricks, saving about 15 hours of manual work per week.
- Built a Python and FastAPI service for a LangChain document assistant. Added automated tests and deployment checks in GitHub Actions.

**Software Developer (Full-time), Advantage Club** · India · Jul 2023 – Sep 2023
- Built React survey forms and improved responsiveness on slower devices.

**Software Development Intern, Advantage Club** · India · Jan 2023 – Jun 2023
- Integrated services into an HR dashboard and cut award email processing time by 60%.

</details>

## Skills

| Area | Tools |
|---|---|
| Languages | Python, Java, C++, SQL |
| Cloud and data | Microsoft Azure, Databricks, Kafka, Power BI, MySQL, Redis, AWS logs and metrics |
| Machine learning | scikit-learn, LightGBM, PyTorch, time-series backtesting, calibration |
| Language models | QLoRA, LangChain, LangGraph, retrieval-augmented generation, LLM evaluation, Claude and GPT |
| APIs and backend | FastAPI, REST APIs, Spring Boot, microservice designs |
| Platform and CI/CD | Git, GitHub Actions, Docker, Linux, Kubernetes manifest checks, API smoke tests |
| Learning | Windmill orchestration, infrastructure as code (IaC) |

## Education, achievements, languages

**Master of Science (M.Sc.) in Data Science**, Philipps-Universität Marburg · Oct 2026 – present (expected graduation Oct 2028)
Current coursework in forecasting and computer vision.

**Bachelor of Engineering (B.E.) in Computer Engineering**, Thapar Institute of Engineering & Technology, India · Jul 2019 – Jun 2023 · CGPA 8.16/10

- Codeforces Specialist, global rank 433 in Round 782 (Div. 2)
- Amazon ML Summer School, selected from 30K+ applicants
- CodeChef, Data Structures and Algorithms certification

**Languages:** English C1 (IELTS) · German A1 (learning) · Hindi native

## How it was built

Specified and directed by me; implemented with AI coding agents; every figure on the site is generated from the public record by code. Research project, not advice of any kind.
