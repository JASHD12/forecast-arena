# Guardrails and red-team suite for untrusted tool and news text

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-guardrails.json`, created 2026-11-21T14:54:52Z.

Why companies use it: Layered input and output guards around an LLM agent, tested with a red-team set, are standard for production agents (docs/SOURCES.md, lab sources).

| Variant | Questions | Flagged | Detected % | False positives % |
|---|---|---|---|---|
| benign | 20 | 0 | - | 0.0 |
| code_fence | 1 | 1 | 100.0 | - |
| evasion | 6 | 0 | 0.0 | - |
| force_output | 4 | 4 | 100.0 | - |
| markup | 2 | 2 | 100.0 | - |
| new_instructions | 3 | 3 | 100.0 | - |
| override | 7 | 7 | 100.0 | - |
| reveal_prompt | 3 | 3 | 100.0 | - |
| role_change | 4 | 4 | 100.0 | - |
| role_marker | 2 | 2 | 100.0 | - |
| template_token | 3 | 3 | 100.0 | - |
| too_long | 1 | 1 | 100.0 | - |
| tool_spoof | 3 | 3 | 100.0 | - |
| url | 2 | 2 | 100.0 | - |
| all_attacks | 41 | 35 | 85.4 | - |


- Detection means the guard flagged the text (injection pattern, markup, link, code fence or length); an instruction-like text is replaced before it reaches the model.
- The evasion category (paraphrase, spacing, other languages, base64) is expected to get past the regex guards; its misses are the honest limit of this layer.
- Report-only: the live agent is unchanged (its defences are the data labelling and the harness limits).

## What this does and does not show

- Synthetic attacks written by the project; a determined attacker is not bounded by them. The patterns were refined once after a first run on this same set (three misses and one false positive), so the detection rate is optimistic.
- Regex guards cannot understand meaning; a classifier or a second model would be the next layer.
- No model was attacked here, so this measures detection, not attack success against an LLM.

Paid-call cost: US$0.00.
