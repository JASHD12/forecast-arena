# METHODS.md - rules, scoring and limits

Completed in T102. This version covers the ledger and the forecast-before-truth evidence.

## The ledger and what it proves

Everything the system publishes is appended to JSONL files on the public `ledger` branch
(SPEC 6). Lines are canonical JSON (sorted keys, UTF-8, no spaces), validated against the
schemas in `docs/schemas/` when written and when read.

**Batch seal.** Before the 09:30 UTC lock, the morning job writes
`chain/batch/YYYY-MM-DD.json` with the SHA-256 of that batch's questions and forecasts
files and commits it in the same commit. From then on the code refuses to change those
files (`arena/ledger/store.py`), and `arena ledger verify` reports any change.

**Day seal and chain.** The first resolve run of day X+1 seals day X:

    lines        = sorted("path:sha256" for every ledger file of day X)
    chain_sha256 = sha256(prev_chain_sha256 + "\n" + "\n".join(lines) + "\n")

with 64 zeros as the first `prev_chain_sha256`. Changing, deleting, adding or reordering
anything in a sealed day changes a file hash, which breaks that day's seal and every later
link in the chain (`arena/ledger/seal.py`, `arena/ledger/verify.py`).

**`arena ledger verify`** recomputes every seal and the chain, checks that every forecast's
`created_at` is strictly before its question's `lock_time`, and with `--git` reads the
branch history and checks that every commit touching a batch's questions, forecasts or
seal was committed before that batch's lock (`arena/ledger/gitcheck.py`).

### Honest limits

- **Git timestamps are evidence, not cryptographic proof.** Whoever makes a commit chooses
  its committer date. A determined operator with write access could fabricate an early
  date on a new commit.
- **The hash chain is self-certifying, not externally anchored.** Someone who rewrote the
  branch *and* recomputed every later seal would produce a chain that verifies on its own.
- What makes a silent edit **detectable** is the combination of three things: the public
  branch history, which every existing clone keeps and which cannot be rewritten without a
  force-push that those clones would notice; the hash chain, which turns any change into a
  visible mismatch against older clones; and the GitHub Actions run logs, which are kept by
  GitHub, not by this project, and show when each scheduled job ran and what it pushed.
- The project never force-pushes the ledger (rule I2, enforced by the git helpers and by
  the agent's operating rules). A force-push would itself be the signal of tampering.
- No external timestamping service is used; adding one is a possible future improvement.
