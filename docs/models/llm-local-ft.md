# Model card: `llm_local_ft` (experimental, not live)

**What it is.** Qwen2.5-1.5B-Instruct fine-tuned with QLoRA (4-bit NF4, LoRA rank 16, all projections) on 2,000 replayed electricity
questions, merged and quantised to GGUF Q4_K_M. It answers with one forward pass: the logit difference between the tokens YES and NO is
mapped to a probability by a Platt map fitted on the validation split. No text is generated, so there are no parse failures and no rationale.

**Pinned artefact** (`lab/artefacts/llm_local_ft.json`): release `lab-qlora-r1`, GGUF SHA-256 `aecc894877d19d4bacdabe3346fc2a3c36bf4f991909c3c939b88a6843521e0f`,
adapter SHA-256 `8ae397866c7b11f5564d99ac10916438c044016e06a2ec88ad9efa9174ccfe93`, base revision `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`,
pre-registration `617830f741e9ec3e89440e33d62da8273e67a978e64d03ca8ca0330843fdf522`. The code refuses a download whose hash differs.

**Status.** Not a live forecaster: the flag `ARENA_LLM_LOCAL_FT` is off and stays off until the owner decides (HUMAN_TODO H32). Results and
limits are on the evaluation card `docs/lab/qlora-r1.md`; live numbers, if it goes live, come from the ledger, not from this card.

**Known limits.** One training run and one seed; small test sets from about 46 days of one market; the 4-bit GGUF did not meet the
pre-registered parity limit against the Colab scores on a 31-question subset; about 30 seconds per question on a 4-core CPU.
