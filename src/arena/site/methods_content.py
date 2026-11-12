"""Principles (SPEC 2), where each is enforced in code, and the known limitations.

Shared by the Methods page and checked against docs/METHODS.md by a test.
"""

from __future__ import annotations

PRINCIPLES: tuple[tuple[str, str, str, str], ...] = (
    (
        "2.1",
        "Forecast before truth",
        "Every question locks at 09:30 UTC on its batch day; forecasts are written and "
        "committed before it. A late run writes nothing; nothing is backdated.",
        "ops/jobs.py (lock re-checked before every append), models.py (created_at <= lock), "
        "ledger/verify.py and ledger/gitcheck.py (created_at < lock, commit times)",
    ),
    (
        "2.2",
        "Append-only public ledger",
        "Questions, forecasts, resolutions and run records are appended to files on the "
        "public ledger branch and sealed with a SHA-256 hash chain. Nothing is edited.",
        "ledger/store.py (atomic appends, earlier bytes never change, sealed files immutable), "
        "ledger/seal.py, ledger/gitsync.py (never force-push)",
    ),
    (
        "2.3",
        "No leakage",
        "Forecasters only see data available at forecast time, through one as-of gateway with "
        "conservative availability rules; models train only on data available then.",
        "domains/base.py (AsOfStore), sources/*.py (availability rules), "
        "forecasters/replay.py, backtest/harness.py, agent/tools.py (news ends at the forecast "
        "time)",
    ),
    (
        "2.4",
        "Honest scoring",
        "Proper scoring rules, the base rate on every board, intervals everywhere, live and "
        "backtest kept apart, voids counted and shown.",
        "scoring/core.py, scoring/stats.py, scoring/boards.py, scoring/findings.py, "
        "backtest/harness.py (backtest records cannot enter the ledger)",
    ),
    (
        "2.5",
        "Idempotent, restartable jobs",
        "Any job can be re-run for any date; the second run changes nothing.",
        "ops/jobs.py (existing ids skipped, seals written once), tests/e2e (schedule run twice)",
    ),
    (
        "2.6",
        "Boring infrastructure",
        "GitHub Actions, GitHub Pages and files on a branch; no servers to keep alive.",
        ".github/workflows/, site/build.py (static pages, no JavaScript)",
    ),
    (
        "2.7",
        "Hard budget caps on LLM usage",
        "Daily request and token caps and a per-call output cap, counted across all runs of a "
        "UTC day from the provider's own usage figures.",
        "llm/budget.py (checked before every call), forecasters/llm.py and agent/forecaster.py "
        "(budget_exhausted skips)",
    ),
    (
        "2.8",
        "Not advice, no personal data",
        "Research-only disclaimer on every page; person articles are excluded from the "
        "attention domain; the human panel is pseudonymous.",
        "site/templates/base.html, domains/attention.py (Wikidata check, fails closed), "
        "forecasters/panel.py",
    ),
    (
        "2.9",
        "Pre-registered official start",
        "The official record starts the day after the first run of 5 consecutive clean days; "
        "the date is written once and never changed; headline scores use only official days.",
        "scoring/boards.py and site/build.py (headline = official record only); the clean-day "
        "streak and the one-time write are task T035 (waits for the live pipeline)",
    ),
)

LIMITATIONS: tuple[str, ...] = (
    "Git commit times are evidence, not cryptographic proof, and the hash chain is not "
    "externally anchored; see the ledger section of docs/METHODS.md.",
    "Model artefacts under models/ are protected by their recorded SHA-256 and the branch "
    "history, not by day seals.",
    "Replayed history for the baselines resolves past questions against values as stored "
    "today; a later source revision is reflected in the replayed outcome.",
    "Power: the conservative availability rule (prices known from 14:00 Berlin on D-1) is "
    "an assumption checked against one observation, not a published guarantee.",
    "Weather: the daily maximum is the highest hourly reading, not DWD's 10-minute extreme; "
    "the ml forecaster is a fixed rule until 60 days of forecast snapshots exist.",
    "Attention: K uses top-list ratios with an upper bound for articles that drop out of "
    "the list, which slightly overestimates the typical ratio; per-article base rates are "
    "uninformative (always 0.5).",
    "Markets: persistence equals the base rate because the previous fixing is published "
    "after the lock.",
    "LLM forecasts are not reproducible bit-for-bit: providers may change models behind an "
    "id, and the current Anthropic models do not accept a temperature setting.",
    "The agent's news search depends on GDELT, which throttles shared IP addresses; a "
    "failed search is shown to the agent as an error, never replaced.",
    "Backtests use the same code as production but not the same information: historical "
    "forecasts (weather, power fundamentals) are not available, so they are not used.",
    "With few official days, intervals are wide; most comparisons will be 'too early to "
    "tell' for weeks.",
)
