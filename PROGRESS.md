# PROGRESS.md - state between sessions

The agent keeps this file current. Newest information first. Keep it under 120 lines;
move older "Done log" lines to `docs/progress-archive.md`.

## Now

- Phase: 1 - Ledger done; Phase 2 next (T002 CI is still open from Phase 0)
- Rehearsal start date: (not yet live)
- Official record start date: (not yet set, see SPEC 2.9)
- Live site URL: (not yet deployed)

## In progress

(nothing yet)

## Open risks and surprises

- Session 1 ran in a cloud sandbox with no PyPI and no GitHub access. Consequences:
  - `requirements-lock.txt` pins the versions that were preinstalled there (see DECISIONS).
    First local session: run `make setup`; if it fails on a pin, regenerate the lock with uv.
  - T002 (CI) not started: action versions could not be looked up. Do it first locally,
    once the repo is on GitHub and `gh auth status` works.
  - Nothing has been pushed; there is no `origin` remote yet (H01).
- `make setup-offline` exists for environments without network (reuses system packages).

## Done log

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
