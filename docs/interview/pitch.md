# The 2-minute pitch

## English

> Forecast Arena is a public benchmark I built to answer one question honestly: **when
> does an LLM agent beat a classical model at forecasting, and when does it not?**
>
> Every day it turns live public data, starting with German day-ahead electricity
> prices, into yes/no questions about the next day, like "will the average price be
> above X euros?". Several forecasters answer each question with a probability *before*
> the answer exists: simple baselines, a gradient-boosted model, Claude with and without
> data, a tool-using agent, a LangGraph agent and a small open-weights model running on
> the CI machine. Everything goes into an append-only, hash-chained ledger on a git
> branch, so anyone can check that no forecast was written after the question locked.
> When the official data arrives, every forecast is scored with proper scoring rules and
> a static website shows the track record with confidence intervals.
>
> The engineering is the interesting part: integrity rules enforced in code (forecast
> before lock, an as-of data gateway so no model sees the future, no silent defaults
> when a model fails), hard cost caps on the LLMs, champion/challenger retraining,
> evaluation and tracing for the LLM calls, and it all runs on GitHub Actions and Pages
> at almost no cost.
>
> The honest result so far: in a one-year backtest the classical model clearly beats the
> base rate on electricity, and the live comparison with the LLMs is still "too early to
> tell". I designed the site to say exactly that rather than overclaim.

Follow-up hooks to offer: the backtest numbers (see `numbers.md`), the JSON-truncation bug
the eval harness caught, why the ledger is append-only, how the as-of gateway prevents
leakage.

## Deutsch

> Forecast Arena ist ein öffentlicher Benchmark, den ich gebaut habe, um eine Frage
> ehrlich zu beantworten: **Wann schlägt ein KI-Agent mit Sprachmodell ein klassisches
> Modell beim Prognostizieren, und wann nicht?**
>
> Jeden Tag entstehen aus öffentlichen Daten, zunächst den deutschen
> Day-Ahead-Strompreisen, Ja/Nein-Fragen über den nächsten Tag, zum Beispiel: „Liegt der
> Durchschnittspreis über X Euro?“ Mehrere Prognosemodelle geben ihre Wahrscheinlichkeit
> ab, *bevor* die Antwort feststeht: einfache Baselines, ein Gradient-Boosting-Modell,
> Claude mit und ohne Daten, ein Agent mit Werkzeugen, ein LangGraph-Agent und ein
> kleines Open-Weights-Modell auf dem CI-Rechner. Alles landet in einem nur erweiterbaren,
> per Hash verketteten Protokoll auf einem Git-Branch; jeder kann prüfen, dass keine
> Prognose nach dem Fragenschluss geschrieben wurde. Sobald die offiziellen Daten da sind,
> wird jede Prognose mit strikt richtigen Bewertungsregeln bewertet, und eine statische
> Website zeigt die Ergebnisse mit Konfidenzintervallen.
>
> Technisch spannend sind die Integritätsregeln im Code (Prognose vor dem Lock, ein
> As-of-Datenzugang gegen Datenlecks, keine stillen Ersatzwerte bei Fehlern), feste
> Kostengrenzen für die Sprachmodelle, Champion/Challenger-Training, Evaluation und
> Tracing der LLM-Aufrufe – und alles läuft fast kostenlos auf GitHub Actions und Pages.
>
> Ehrliches Zwischenergebnis: Im einjährigen Backtest schlägt das klassische Modell die
> Basisrate beim Strom deutlich; der Live-Vergleich mit den Sprachmodellen ist noch „zu
> früh für eine Aussage“, und genau das zeigt die Website auch.
