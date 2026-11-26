---
name: forecasting-core
description: how to turn a reference estimate and evidence into one calibrated probability, and a checklist before answering
topics: all
revision: 1
---

You are scored with the Brier score: the squared miss of your probability. A confident correct answer earns the most, a confident wrong answer costs the most, and saying 0.5 or staying near the base rate earns a middling score every time. Calibration and sharpness are both rewarded.

## From estimate to answer

1. Start from a number you can defend: the `estimate_probability` result, or the `get_ml_forecast` result if you were told to use it, or your own calculation with `calculate_probability` (centre, spread, threshold).
2. Ask what the estimate cannot see: news, an event, a holiday, an outage, a data quirk. If you find nothing, keep the estimate. Do not move toward 0.5 "to be safe": that is a bet that the estimate is wrong, and it has to be paid for with evidence.
3. If you do move, move by an amount the evidence justifies and say which evidence. A small, concrete reason justifies a small move. Only a strong, specific reason justifies a large one.
4. Use the base rate and similar past questions as a sanity check and a fallback when no numeric estimate exists, not as the anchor when one does.
5. Keep probabilities away from the extremes unless the outcome is nearly certain: a single surprise at 0.99 costs far more than the points you gain at 0.95.

## Read the question exactly

- The comparator matters: strictly greater, at least, or less than. A tie goes with the rule text.
- Units and time zones: German electricity days are Europe/Berlin days, weather days are the station's calendar day, Wikipedia days are UTC.
- The threshold is part of the question. A value exactly at the threshold is close to a coin flip unless the spread is small.

## Before you answer

- Is your number consistent with the estimate you computed, and can you name the reason if it is not?
- Did you check the direction of the comparison (above or below)?
- Is the rationale at most 80 words and does it name the evidence that moved you?
