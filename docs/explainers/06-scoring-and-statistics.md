# 06 - Scoring and statistics

How Forecast Arena turns probabilities and outcomes into scores, leaderboards and
statements about the hypotheses, and why it is built this way.
Code: `src/arena/scoring/` (`core.py`, `stats.py`, `boards.py`, `findings.py`).

## How it works

1. **What gets scored.** Every forecast with a resolution and no void (a `source_revised`
   void keeps the first resolution in the scores). Scores are recomputed from the ledger on
   every site build and never stored in the ledger: the ledger holds facts, scores are a
   function of facts.
2. **Clipping.** Probabilities are clipped to [0.01, 0.99] before scoring; the raw value
   stays in the ledger. Without clipping one confident miss would give an infinite log
   score and dominate everything.
3. **Brier score** = mean of (p - y)^2, where y is 1 for YES and 0 for NO. 0 is perfect,
   0.25 is what a constant 0.5 earns, lower is better. **Log score** = mean of -ln(p) for
   YES and -ln(1 - p) for NO; it punishes confident mistakes much harder.
4. **Skill against the base rate.** Brier skill = 1 - Brier(forecaster) / Brier(base_rate),
   on the questions both answered. Positive means better than the base rate.
5. **Calibration.** Forecasts are put into 10 equal-width bins; bins with fewer than 10
   forecasts are merged into a neighbour. For each bin, the mean forecast is plotted
   against the observed YES rate (reliability diagram). The **expected calibration error**
   is the share-weighted average gap between the two.
6. **Murphy decomposition.** Brier = reliability - resolution + uncertainty. Reliability
   is how far forecasts are from observed frequencies (lower is better); resolution is
   how much the forecasts separate days that turn out differently (higher is better);
   uncertainty is ō(1 - ō), a property of the questions, not the forecaster. The identity
   is exact when forecasts are constant within bins, which the tests check.
7. **Uncertainty.** Questions asked on the same day share weather, news and market moods,
   so they are not independent. The intervals therefore resample **days**, not questions:
   a day-block bootstrap with 2,000 replicates and a fixed seed gives a 95% percentile
   interval for each score and for the **paired difference** between two forecasters on
   the same questions.
8. **Leaderboards.** The headline is the **common set**: only questions answered by every
   active member of the comparison group (base_rate, ml, llm_plain, llm_context, agent),
   so the LLMs' daily sample is compared like for like. A second board covers **all
   questions** for the forecasters that answer everything. Both exist overall and per
   domain, and headline boards use only the official record.
9. **Wording rules.** Below 30 official days or 300 resolved common-set forecasts every
   board says "too early to tell". A difference is called supported only when its
   interval excludes zero. The Findings page applies the same rule to H1-H4 and never uses
   causal language.

## Why it was built this way

- **Proper scoring rules.** Brier and log score are *proper*: a forecaster minimises its
  expected score by reporting its true belief, so nobody can game them by shading
  probabilities. Accuracy (right/wrong at 0.5) is not proper and throws away information.
- **Two scores, not one.** Brier is bounded and easy to explain; the log score is
  sensitive to overconfidence. Showing both makes it harder for one property to hide.
- **Baseline always present.** A Brier of 0.20 means nothing on its own; 0.20 against a
  base rate of 0.25 on the same questions does. That is why skill is computed on the
  questions both answered, and why base_rate is on every board.
- **Days, not questions, in the bootstrap.** Resampling questions would treat 25 correlated
  questions from one day as 25 independent pieces of evidence and make intervals far too
  narrow. Day blocks are the honest unit.
- **Paired differences.** Two forecasters' scores are correlated through the questions;
  the interval of their *difference* on the same questions is much tighter and more
  meaningful than comparing two separate intervals.

## What was rejected

- **Accuracy or AUC as headline metrics**: not proper, or ignores calibration.
- **Question-level bootstrap or a t-test**: assumes independence that does not exist.
- **Significance stars / p-values**: the project reports intervals and a single, simple
  rule (interval excludes zero) instead of a hierarchy of significance levels.
- **Storing scores in the ledger**: scores would then need correcting whenever a rule or a
  resolution changes; computing them from facts keeps the ledger append-only and simple.
- **A strict common set over all five group members from day one**: before `ml` and the
  LLM forecasters are live it would be empty; the board instead uses the active members
  and lists them (docs/project/DECISIONS.md).

## Ten questions you will be asked

1. **Why the Brier score?** It is a proper scoring rule, bounded between 0 and 1, and has a
   clean decomposition into calibration and resolution. A forecaster cannot improve its
   expected Brier by reporting anything other than what it believes.
2. **What does a Brier of 0.25 mean?** It is what a constant 0.5 forecast scores whatever
   happens. A forecaster above 0.25 is worse than saying "I don't know" every time.
3. **Why clip to [0.01, 0.99]?** So that one wrong 0% or 100% forecast does not produce an
   infinite log score. It is a published policy applied to everyone; raw values are kept,
   so anyone can rescore without clipping.
4. **Why resample days?** Questions from the same day are correlated (a windy day moves
   several power questions at once). Resampling days keeps that structure; resampling
   questions would produce overconfident intervals.
5. **When do you say one forecaster beats another?** Only when the 95% interval of the
   paired Brier difference on the same questions excludes zero, and only after 30 official
   days and 300 common-set forecasts. Otherwise the site says "too early to tell" or "no
   supported difference".
6. **Isn't 95% with many comparisons a multiple-testing problem?** Yes. The project
   compares several forecasters in several domains, so a few intervals will exclude zero
   by chance. The mitigations are pre-registered hypotheses (H1-H4), a fixed rule, and
   showing every comparison rather than picking favourites. A formal correction is a
   reasonable improvement.
7. **What is the common set and why is it the headline?** The LLM forecasters only answer a
   daily sample of questions to stay within budget. Comparing them with forecasters that
   answer everything would mix different questions; the common set compares everyone on
   exactly the same questions.
8. **How do you know a forecaster is calibrated?** The reliability diagram and expected
   calibration error: when it says 30%, about 30% of those questions should resolve YES.
   Sparse bins are merged so single points do not mislead.
9. **What does the Murphy decomposition add?** It separates being honest about uncertainty
   (reliability) from being informative (resolution). A base-rate forecaster can be
   perfectly calibrated and still have zero resolution; the decomposition shows that.
10. **What can the scores not tell you?** They say how well each forecaster did on these
    questions in this period. They do not explain why, do not guarantee future
    performance, and with few official days the intervals are wide. That is why the site
    avoids causal language and keeps the "too early to tell" label until the thresholds
    are met.
