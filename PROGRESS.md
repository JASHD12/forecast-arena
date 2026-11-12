# PROGRESS.md - state between sessions

The agent keeps this file current. Newest information first. Keep it under 120 lines;
move older "Done log" lines to `docs/progress-archive.md`.

## Now

- Phase: 1 - Ledger done; Phase 2 next (T002 CI is still open from Phase 0)
- Rehearsal start date: (not yet live)
- Official record start date: (not yet set, see SPEC 2.9)
- Live site URL: (not yet deployed)

## In progress

(nothing)

## Open risks and surprises

- Session 1 ran in a cloud sandbox with no PyPI and no GitHub access. Consequences:
  - `requirements-lock.txt` pins the versions that were preinstalled there (see DECISIONS).
    First local session: run `make setup`; if it fails on a pin, regenerate the lock with uv.
  - T002 (CI) not started: action versions could not be looked up. Do it first locally,
    once the repo is on GitHub and `gh auth status` works.
  - `origin` is https://github.com/JASHD12/forecast-arena.git but nothing is pushed yet:
    the session's git proxy refused (repo not in the session's authorized set).
  - SMARD, Wikimedia and ECB were unreachable from that sandbox (egress allowlist), so
    T021/T040/T042/T044 need a session whose network allows those hosts.
- `make setup-offline` exists for environments without network (reuses system packages).

## Done log

- 2026-11-12 T056 (work done, blocked on H10): weekly job + weekly.yml; live dry run: power candidate Brier 0.1418 on 168 questions, would promote
- 2026-11-12 T083 (work done, blocked on H10): Dockerfile + CI build/run job; install+check verified on Python 3.12 (no Docker daemon here)
- 2026-11-12 T103: 90-second demo script (docs/DEMO.md)
- 2026-11-12 T100: README; verified make setup && make check on a fresh clone with a new venv
- 2026-11-12 T102: METHODS.md and Methods page: every SPEC 2 principle with code locations, limitations list
- 2026-11-12 T101: `arena report cv` from the ledger only; refuses wins while too early or unsupported
- 2026-11-12 T091: panel CSV intake (pseudonyms, late/duplicate/bad-token rules, median of >=3), PANEL_SETUP.md
- 2026-11-12 T075: explainer 06 scoring and statistics (10 interview Q&A)
- 2026-11-12 T074 (work done, blocked on H10): axe-core lint 0 serious locally, focusable scroll regions, landmarks, CI job written
- 2026-11-12 T073: Findings page: H1-H4 statements from official scores (supported only if interval excludes 0) + owner block
- 2026-11-12 T072: site v2 (leaderboards, SVG calibration, question archive and pages, changelog), phone-checked
- 2026-11-12 T071: leaderboards (common set, all questions, per domain), too-early label, supported-only wording
- 2026-11-12 T070: calibration bins (sparse merged), ECE, Murphy decomposition, day-block bootstrap, paired diffs
- 2026-11-12 T054: markets EWMA-t model; 2-year backtest: no supported gain over base_rate (H3-consistent); direction 0.5
- 2026-11-12 T052: weather model stage 1: transparent MOSMIX rules (weather-rules-r1) until 60 days of snapshots
- 2026-11-12 T067: agent forecaster (bounded tool loop, injection test, traces to agent_traces/), in e2e
- 2026-11-12 T055: model registry on the ledger (xz artefacts, hashes, promotions), model_missing skips
- 2026-11-12 T066: agent tools (series, base rate, ml, GDELT news as-of, Wikipedia), 4-call/90 s limits, traces
- 2026-11-12 T051: power ml model; 1-year backtest Brier 0.193 vs base_rate 0.247, persistence 0.221 (intervals exclude 0); model card
- 2026-11-12 T063: llm_plain and llm_context, seeded stratified daily sample, e2e with FakeLLM
- 2026-11-12 T062: versioned prompt files, strict parser, one repair retry, parse_failure skips
- 2026-11-12 T061: budget guard: daily caps across manifests, budget_exhausted skips
- 2026-11-12 T060: LLM client protocol, FakeLLM, Anthropic (SDK) and OpenAI-compatible adapters, mocked tests
- 2026-11-12 T050: walk-forward backtest harness, labelled store outside the ledger, refusal test
- 2026-11-12 T045: markets questions (absmove_gt, up), publication-day rules, resolver; all 4 domains dry-run live (26 q)
- 2026-11-12 T044: ECB reference-rate client, TARGET calendar verified against 8 years of data, smoke
- 2026-11-12 T043: attention selection (persons, blocklist, namespaces, recent), K rule, resolver, recorded goldens
- 2026-11-12 T042: Wikimedia top/per-article client, title encoding, Wikidata person check (fail closed), smoke
- 2026-11-12 T041: weather templates, resolver (void on >2 missing hours), MOSMIX as-of snapshot, goldens
- 2026-11-12 T040: weather via Bright Sky (DWD obs + MOSMIX), 4 stations, fixtures, smoke
- 2026-11-12 T029: static site v1 (Home, Methods, Status, About), disclaimer/attribution on every page, light/dark, link check
- 2026-11-12 T028: scoring v1 (clip, Brier, log, skill vs base_rate, counts), property tests, `arena score show`
- 2026-11-12 T027: daily morning/resolve jobs (lock enforced, idempotent, error skips, revisions), replay history, 5-day e2e
- 2026-11-12 T025: power resolver (grace void, ties, 23/25h days, revision detection)
- 2026-11-12 T024: six power templates; golden tests (ordinary, 23h, 25h, Christmas) on real SMARD fixtures
- 2026-11-12 T023: power history/as-of store; live backfill 424 chunks, 2964 complete days, 0 gaps
- 2026-11-12 T021: SMARD client (index, weekly chunks, nulls, Berlin days, cache), fixtures, smoke
- 2026-11-12 T026: base_rate and persistence baselines, LedgerHistory/StaticHistory
- 2026-11-12 T022: domain contract, as-of gateway, degeneracy rule, registry, toy domain
- 2026-11-12 T020: stdlib HTTP client (retries, backoff, User-Agent, snapshots)
- 2026-11-12 T002 (part): ci.yml written with verified action versions; tick after first green run
- 2026-11-12 T015: arena CLI with all groups; ledger verify / seal-batch / seal-days
- 2026-11-12 T013: verify --git checks batch commits landed before lock; limits in METHODS
- 2026-11-12 T014: run manifests on success and failure
- 2026-11-12 T012: ledger git sync (orphan create, clone, rebase-retry push, never force)
- 2026-11-12 T011: batch/day seals, hash chain, verify with tamper tests
- 2026-11-12 T010: append-only ledger storage, atomic writes, duplicate refusal
- 2026-11-12 T005: docs scaffolding
- 2026-11-12 T004: pydantic schemas, canonical JSON, exported JSON Schemas
- 2026-11-12 T003: settings and clock
- 2026-11-12 T001: skeleton, Makefile, pinned deps

## Session summaries

- 2026-11-12 (cloud sandbox, no network to PyPI/GitHub): built Phase 0 except T002 and all
  of Phase 1. `make check` green: 57 unit tests + e2e placeholder. Next: T002 locally,
  then T020/T022 (offline) and T021 (needs live SMARD docs).
