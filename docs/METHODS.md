# METHODS.md - rules, scoring and limits

How Forecast Arena works, where each rule is enforced in code, and what it cannot claim.
The same principles and limitations appear on the site's Methods page.

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

## Principles and where they are enforced

| Principle | Rule | Enforced in (`src/arena/`) |
|---|---|---|
| 2.1 Forecast before truth | Every question locks at 09:30 UTC on its batch day; forecasts are written and committed before it. A late run writes nothing; nothing is backdated. | ops/jobs.py (lock re-checked before every append), models.py (created_at <= lock), ledger/verify.py and ledger/gitcheck.py (created_at < lock, commit times) |
| 2.2 Append-only public ledger | Questions, forecasts, resolutions and run records are appended to files on the public ledger branch and sealed with a SHA-256 hash chain. Nothing is edited. | ledger/store.py (atomic appends, earlier bytes never change, sealed files immutable), ledger/seal.py, ledger/gitsync.py (never force-push) |
| 2.3 No leakage | Forecasters only see data available at forecast time, through one as-of gateway with conservative availability rules; models train only on data available then. | domains/base.py (AsOfStore), sources/*.py (availability rules), forecasters/replay.py, backtest/harness.py, agent/tools.py (news ends at the forecast time) |
| 2.4 Honest scoring | Proper scoring rules, the base rate on every board, intervals everywhere, live and backtest kept apart, voids counted and shown. | scoring/core.py, scoring/stats.py, scoring/boards.py, scoring/findings.py, backtest/harness.py (backtest records cannot enter the ledger) |
| 2.5 Idempotent, restartable jobs | Any job can be re-run for any date; the second run changes nothing. | ops/jobs.py (existing ids skipped, seals written once), tests/e2e (schedule run twice) |
| 2.6 Boring infrastructure | GitHub Actions, GitHub Pages and files on a branch; no servers to keep alive. | .github/workflows/, site/build.py (static pages, no JavaScript) |
| 2.7 Hard budget caps on LLM usage | Daily request and token caps and a per-call output cap, counted across all runs of a UTC day from the provider's own usage figures. | llm/budget.py (checked before every call), forecasters/llm.py and agent/forecaster.py (budget_exhausted skips) |
| 2.8 Not advice, no personal data | Research-only disclaimer on every page; person articles are excluded from the attention domain; the human panel is pseudonymous. | site/templates/base.html, domains/attention.py (Wikidata check, fails closed), forecasters/panel.py |
| 2.9 Pre-registered official start | The official record starts the day after the first run of 5 consecutive clean days; the date is written once and never changed; headline scores use only official days. | scoring/boards.py and site/build.py (headline = official record only); the clean-day streak and the one-time write are task T035 (waits for the live pipeline) |

## Forecasters and what they see

| Id | Sees | Answers |
|---|---|---|
| base_rate | Trailing outcomes of the same template and entity (Laplace-smoothed, 90 instances; 0.5 below 10) | all questions |
| persistence | Yesterday's outcome of the same template and entity (180 instances; else the base rate) | all questions |
| ml | The full as-of context; one model family per domain (docs/models/) | all questions |
| llm_plain | Question text, resolution rule, current date | daily sample |
| llm_context | The above plus a compact rendering of the as-of context | daily sample |
| agent | As llm_context plus read-only tools (series, base rate, ml, news headlines before the forecast time, Wikipedia summaries), at most 4 calls and 90 s | daily sample |
| ensemble | Other forecasters' probabilities (activates after 300 resolved common-set forecasts) | where inputs exist |
| human_panel | Whatever panel members know; median of at least 3 | what they submit |

## Scoring

Brier and log scores on probabilities clipped to [0.01, 0.99], Brier skill against base_rate on shared questions, reliability diagrams, expected calibration error and the Murphy decomposition, and 95% day-block bootstrap intervals (2,000 replicates, fixed seed) for scores and paired differences. Headline boards use the common set of the official record; below 30 official days or 300 common-set forecasts every board says "too early to tell", and a difference is called supported only when its interval excludes zero. Details: `docs/explainers/06-scoring-and-statistics.md`.

## Known limitations

- Git commit times are evidence, not cryptographic proof, and the hash chain is not externally anchored; see the ledger section of docs/METHODS.md.
- Model artefacts under models/ are protected by their recorded SHA-256 and the branch history, not by day seals.
- Replayed history for the baselines resolves past questions against values as stored today; a later source revision is reflected in the replayed outcome.
- Power: the conservative availability rule (prices known from 14:00 Berlin on D-1) is an assumption checked against one observation, not a published guarantee.
- Weather: the daily maximum is the highest hourly reading, not DWD's 10-minute extreme; the ml forecaster is a fixed rule until 60 days of forecast snapshots exist.
- Attention: K uses top-list ratios with an upper bound for articles that drop out of the list, which slightly overestimates the typical ratio; per-article base rates are uninformative (always 0.5).
- Markets: persistence equals the base rate because the previous fixing is published after the lock.
- LLM forecasts are not reproducible bit-for-bit: providers may change models behind an id, and the current Anthropic models do not accept a temperature setting.
- The agent's news search depends on GDELT, which throttles shared IP addresses; a failed search is shown to the agent as an error, never replaced.
- Backtests use the same code as production but not the same information: historical forecasts (weather, power fundamentals) are not available, so they are not used.
- With few official days, intervals are wide; most comparisons will be 'too early to tell' for weeks.
