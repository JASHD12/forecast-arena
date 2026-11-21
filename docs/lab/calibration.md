# Calibration methods compared: identity, Platt, isotonic, beta

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-calibration.json`, created 2026-11-21T14:56:09Z.

Why companies use it: Probabilistic forecasts are only useful if they are calibrated; production teams monitor and re-calibrate them (docs/SOURCES.md, lab sources).

| Variant | Questions | Brier | ECE |
|---|---|---|---|
| identity | 1470 | 0.1935 | 0.0699 |
| platt | 1470 | 0.1921 | 0.0546 |
| isotonic | 1470 | 0.193 | 0.0562 |
| beta | 1470 | 0.1922 | 0.0545 |

- platt minus identity: Brier difference -0.0015, 95% interval [-0.0034, +0.0005] over 1470 questions (interval includes zero).
- isotonic minus identity: Brier difference -0.0006, 95% interval [-0.0035, +0.0025] over 1470 questions (interval includes zero).
- beta minus identity: Brier difference -0.0013, 95% interval [-0.0032, +0.0007] over 1470 questions (interval includes zero).

- The `ml` backtest probabilities of run power-2025-11-01-2026-10-31-20261113T0954, re-calibrated day by day on earlier days only (batch days 2026-03-01 to 2026-10-31, 120 warm-up days, weekly refit).
- Identity is the power champion as it is (it is already Platt-calibrated inside its own training).

## What this does and does not show

- A backtest, not live: one market, one year, six strongly correlated questions a day.
- Re-calibrating already calibrated probabilities can only add noise unless the model drifted; no live change follows from this study (rule I8).

Paid-call cost: US$0.00.
