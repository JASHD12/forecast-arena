# 03 - Question design beyond electricity, and the baselines

How the other three domains (weather, Wikipedia attention, exchange rates) turn public data
into yes/no questions that can be resolved without judgement, and what the two baselines
(`base_rate`, `persistence`) are. Everything here follows the same rules as the power
questions in explainer 02: the rule is fixed in advance, written into the question text,
resolved from an official source, and skipped when it would be uninformative.
Code: `src/arena/domains/` (`base.py`, `weather.py`, `attention.py`, `markets.py`),
`src/arena/forecasters/baselines.py`, `src/arena/sources/` (DWD via Bright Sky, Wikimedia, ECB).

## How it works

1. **One batch, four domains.** The morning (or, since T160, the evening before) job asks every
   enabled domain for its questions for target day D = B+1. A domain that cannot build a
   question (stale data, too few days in the window, degenerate rate) logs a skip and
   publishes nothing for that template; the others carry on. A full batch is about 33
   questions: 6 power, 15 weather, 8 attention, 4 markets. On Sundays there are no markets
   questions because the ECB publishes no fixing.
2. **Weather** (`weather.py`). Questions about tomorrow at four DWD stations: the daily
   maximum above a threshold, rain, frost day (minimum below 0.0 °C), a gust threshold, and
   "city A warmer / wetter than city B". Thresholds come from a trailing window of the
   station's own observations (14 days for the maximum, 90 for rain). Resolution uses DWD
   observations only, never forecasts; a day with more than 2 missing hourly values is void.
   The MOSMIX forecast is stored with its fetch time and is part of the context the LLMs see.
3. **Attention** (`attention.py`). "Will this Wikipedia article get at least K views on D?"
   Candidates are articles ranked 5-200 on the latest published top list, minus non-articles,
   person articles (Wikidata P31 = Q5; a failed lookup also excludes), blocklisted titles and
   anything used in the last three batches. A seeded sample picks 2 articles from ranks 5-50
   and 2 from ranks 51-200 per language (de, en). K is the article's views on the reference day
   times the median three-day growth ratio of the top-200 articles over the previous 90 days.
4. **Markets** (`markets.py`). The control domain: ECB reference rates EUR/USD and EUR/JPY.
   `absmove_gt`: will the absolute log return from today's fixing to the next one exceed the
   median of the last 60 absolute returns? Both fixings are published after the 09:30 UTC lock,
   so nothing about the answer can be known. This domain is a deliberate "nothing to learn"
   test: a forecaster that claims skill here should be treated with suspicion.
5. **Degeneracy rule** (`is_degenerate`). A template is skipped when its trailing YES
   frequency is outside [0.10, 0.90]. With no history the template is kept.
6. **Template versions.** A question published the evening before is `template_version` 2, one
   published on the batch morning is 1. The text and the lock are identical, but the
   threshold is computed from slightly older data, so it counts as a new version (SPEC 2.9).
   Old records are never edited.
7. **`base_rate`.** The Laplace-smoothed YES frequency, (yes + 1) / (n + 2), over the latest 90
   resolved instances of the same template and entity; 0.5 when there are fewer than 10.
8. **`persistence`.** The same smoothing, but conditioned on yesterday's outcome over the
   latest 180 instances: P(YES | yesterday was YES/NO). It falls back to the base rate when
   yesterday is unknown or fewer than 10 such transitions exist, and says so in its metadata.

## Why it was built this way

- **Rules over discretion.** Every threshold is a formula on past public data, so nobody can
  pick a threshold after seeing a forecast, and anyone can re-resolve a question by hand.
- **Mixed domains on purpose.** Power has a strong classical model; weather and Wikipedia are
  noisier; markets should be unforecastable. Together they show *when* a model helps, not
  just whether it does, which is the research question.
- **Two baselines, always shown** (integrity rule I7). A model that cannot beat the base rate
  has no skill; one that cannot beat persistence has found nothing beyond "same as last time".
- **Conservative exclusions.** Person articles are excluded for privacy (S12), and values from
  a substitute station count as missing instead of silently filling a gap.

## What was rejected

- Forecast-based weather resolution (MOSMIX is an input, never the truth).
- Questions on named people, or on any article chosen by hand.
- A direction question for exchange rates: the template exists but is answered with 0.5,
  because a direction model would only be added after a backtest showed skill.
- Picking thresholds to make the base rate exactly 50%: the rule is fixed, the resulting rate
  is whatever the data give, and degenerate templates are skipped instead.

## Honest limits

- **A new template has no history.** `base_rate` then answers 0.5 or a thin estimate, and it can
  score worse than a constant 0.5 (above 0.25 Brier) for a while. The live rehearsal shows
  this; Methods explains it.
- **Questions on one day are correlated** (one warm front moves most weather questions), so
  intervals resample whole days.
- **Wikipedia attention depends on events** the system cannot see; K is a growth-ratio rule,
  not a model of news.
- **Source rate limits** (Open-Meteo, GDELT, Wikimedia) are why the weather domain uses Bright
  Sky and why some data fetches are recorded as skips instead of retried forever.

## Ten interview questions

1. **Why these four domains?**
   Each is public, official, resolvable by a rule and updated daily. They differ in how much a
   model can know: power (strong calendar and lag signal), weather (persistence plus season),
   attention (events), markets (almost nothing). That contrast is the point.
2. **How do you resolve "Wikipedia views" without trusting a news site?**
   From the Wikimedia per-article pageviews API, with the URL and the values stored as evidence
   in the resolution record. A deleted or moved article becomes a void after a grace period.
3. **Why exclude person articles?**
   Privacy and ethics: questions about individuals' attention can be sensitive. The rule checks
   Wikidata `instance of human`; if the lookup fails, the article is excluded rather than kept.
4. **Why is the markets domain a "control"?**
   ECB fixings are close to a random walk. A forecaster that beats the base rate there with an
   interval excluding zero would be surprising and would deserve a check for leakage first.
5. **What does the base rate do with only a few instances?**
   Below 10 resolved instances it answers 0.5 and records `fewer_than_10`; above, it uses the
   Laplace-smoothed frequency of the latest 90.
6. **Why can the base rate score above 0.25?**
   A constant 0.5 always scores 0.25. The base rate is an estimate from past instances of the
   same template, so on a new or shifting template it can be confidently wrong. It is a fair
   baseline, not a floor; Methods says so.
7. **What is `persistence` for?**
   It is the simplest "use yesterday" model. In the electricity backtest the ML model is
   compared with it as well as with the base rate, because day-to-day persistence is the
   strongest simple signal for prices.
8. **Why version the template when it is published in the evening?**
   The data window ends a day earlier, so the threshold can differ. Changing meaning without
   changing the version would make old and new records look comparable when they are not.
9. **What happens when a source is down?**
   The domain logs a skip for that template and the job continues; the health check reports
   fresh sources and an incident opens if a domain is missing. Nothing is invented.
10. **What would you add next?**
    More weather stations and a second market (for example a power-price question for another
    bidding zone), each as a new template version so the current record stays valid; and a
    measured check of whether Wikipedia growth ratios carry any signal beyond the base rate.
