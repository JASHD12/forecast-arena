"""Fine-tuning of a small open LLM on forecasting questions (T244, experiment `qlora-forecast`).

The target is one token: the model reads the exact live prompt and its next-token logits for
`YES` and `NO` give P(YES). Training is a binary cross-entropy on the logit difference, which is
supervised fine-tuning of that single answer token; scoring is the same softmax, followed by a
Platt map fitted on the validation split.
"""
