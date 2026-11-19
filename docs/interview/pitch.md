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

# The 90-second walkthrough: one day in the system

Draft for you to rehearse and make your own (owner item: say it aloud twice, time it). It
follows one batch from question to score and quotes no figures; if asked for numbers, open
`numbers.md`.

## English

> Let me walk you through one day. **The evening before**, the system publishes tomorrow's
> questions from live data, for example "will tomorrow's average German day-ahead
> electricity price be above this threshold?". **In the morning**, every forecaster
> publishes a probability: two baselines, a gradient-boosted model that has been live since
> mid-November, and several Claude-based forecasters, including an agent with tools.
> Each answer is written into an append-only, hash-chained ledger on a git branch.
>
> **At 09:30 UTC the questions lock.** That is before the day-ahead auction results are
> published around 13:00 Berlin time, so nobody, including me, can know the answer. A
> data gateway only lets a model see what was public at that moment, which is how I
> prevent leakage. If a model fails, the ledger records a skip with a reason; it never
> fills in a guess.
>
> **The next day**, the official price data arrives, each question is resolved with its
> evidence, and every forecast gets a Brier score. The site shows the result against the
> base rate with day-block confidence intervals, and says "too early to tell" until the
> statistics can decide. In the backtest the classical model clearly beats the baselines;
> whether an LLM agent can beat it live is the open question, and I would rather show that
> honestly than claim it.

## Deutsch

> Ich zeige Ihnen einen Tag im System. **Am Vorabend** veröffentlicht es Fragen zum
> nächsten Tag aus Live-Daten, zum Beispiel: „Liegt der durchschnittliche deutsche
> Day-Ahead-Strompreis morgen über diesem Schwellenwert?“ **Am Morgen** gibt jedes
> Prognosemodell eine Wahrscheinlichkeit ab: zwei Baselines, ein Gradient-Boosting-Modell,
> das seit Mitte November live läuft, und mehrere Claude-basierte Modelle, darunter ein
> Agent mit Werkzeugen. Jede Antwort wird in ein nur erweiterbares, per Hash verkettetes
> Protokoll auf einem Git-Branch geschrieben.
>
> **Um 09:30 UTC werden die Fragen gesperrt.** Das ist vor der Veröffentlichung der
> Day-Ahead-Ergebnisse gegen 13 Uhr deutscher Zeit, also kann niemand die Antwort kennen,
> auch ich nicht. Ein Datenzugang zeigt jedem Modell nur, was zu diesem Zeitpunkt
> öffentlich war; so verhindere ich Datenlecks. Fällt ein Modell aus, steht im Protokoll
> ein Ausfall mit Grund, nie ein geschätzter Ersatzwert.
>
> **Am nächsten Tag** kommen die offiziellen Preisdaten, jede Frage wird mit Beleg
> aufgelöst, und jede Prognose erhält einen Brier-Score. Die Website vergleicht mit der
> Basisrate samt Konfidenzintervallen und schreibt „zu früh für eine Aussage“, solange die
> Statistik nichts hergibt. Im Backtest schlägt das klassische Modell die Baselines klar;
> ob ein LLM-Agent es live schlagen kann, ist die offene Frage, und die zeige ich lieber
> ehrlich, als sie zu behaupten.
