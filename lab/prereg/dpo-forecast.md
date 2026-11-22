# Pre-registration: DPO preference tuning of a small open model on forecasting questions

Experiment id: `dpo-forecast`. Registered 2026-11-22, before any training run (SPEC 17, rule L2). Notebook:
`notebooks/lab/dpo_qwen_forecast.ipynb`; code: `src/arena/lab/finetune/train.py` (`dpo_loss`), `run.py` (`Spec.dpo_beta`).

## Question

QLoRA (run `lab-qlora-r1`) trained Qwen2.5-1.5B-Instruct with a cross-entropy loss on the YES/NO margin and ended worse than the
plain base rate. Does preference tuning (Direct Preference Optimisation) with the same data, model, adapter and budget change that?

## Method

Same data as the QLoRA experiment (the four committed, hashed splits of `lab/data/forecast-sft/`, 2,000 training rows, windows and
hashes in `lab/prereg/qlora-forecast.md`). For a one-token answer the log-probability difference between YES and NO is the logit
margin, so the DPO objective is `-log sigmoid(beta * s * (m - m_ref))` with `s = +1` when the outcome is YES and `-1` otherwise, and
`m_ref` the margin of the untuned model (the frozen reference). `beta = 0.1`, learning rate 2e-4, 1 epoch, 4-bit NF4 base, LoRA
r = 16, alpha = 32, dropout 0.05, all projections, seed 0 (the QLoRA settings). The Platt map is fitted on the validation split only.
The GGUF export is the checked export of the notebook.

## Hypotheses (written before the run)

- **H-DPO1**: DPO does not beat the plain base rate on the combined test sets (the expectation is the same negative result as QLoRA:
  the outcomes are close to coin flips given the prompt, and the preference signal is the outcome).
- **H-DPO2**: DPO and QLoRA differ by less than 0.01 Brier on the combined test sets (a paired day-block interval that includes zero).
- **H-DPO3**: the 4-bit GGUF export loses less than 0.005 Brier against the Colab scores of the same adapter (the QLoRA export
  missed this on a 31-row subset; it is re-checked on the full test sets by the calibration workflow).

## Decision rule and reporting

Whatever the numbers, they are published with their paired intervals against the base rate, the `ml` champion and the QLoRA model on
identical items (`arena lab ft-eval`). A result changes nothing live (I8); a new live model would need the owner's decision and a new
version string. Negative results are results.
