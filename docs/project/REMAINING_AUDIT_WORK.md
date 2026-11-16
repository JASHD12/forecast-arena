# Remaining audit implementation work

Starting point: main 9d82bf2, after merged PR #3 (T194). This branch starts the remaining
work; the initial commit contains planning documents only. It does not implement the
unchecked tasks below. The detailed dated audit is in AUDIT_IMPLEMENTATION_PLAN_2026_11_16.md.
Its historical observations must be refreshed before using them as current state.

## Already merged in PR #3

- Initial finite observation/record/JSON boundaries and parsed SQL statement validation.
- Initial participation counts and additive API fields; question ML method/provenance
  panels and LangGraph sample links.
- Per-domain live versions, forecast-domain profile labels, promotion display correction.
- Initial recruiter hero/mobile wrapping, CLI migration guidance and content corrections.

These are initial changes, not blanket completion of every acceptance criterion in R01–R17.

## Remaining implementation checklist

- [ ] R01/R02: finish cross-source numeric-boundary coverage and REST/MCP mutation regressions.
- [ ] R03: complete shared participant states across home/topics/calibration/profiles;
      distinguish pending, disabled, legacy missing and errors; separately scoped paired diagnostics.
- [ ] R04: record optional numerical prediction diagnostics prospectively before lock;
      preserve probabilities and historical bytes; test missing diagnostics and family-specific methods.
- [ ] R05/R06: complete model inventory and legacy/failed-promotion display regressions.
- [ ] R07: reconcile incidents with final setup/application/deploy/smoke outcomes and qualified recovery.
- [ ] R08: triage advisories, update compatible pins and audit actual isolated environments.
- [ ] R09: prepare scheduler/dispatch/deadline package; external setup remains owner-controlled.
- [ ] R10/R11: complete command documentation, canonical schedules and dated live acceptance updates.
- [ ] R12/R13: complete recruiter/home/README/DE evidence hierarchy and responsive,
      keyboard, no-JS, accessibility and print verification.
- [ ] R14: prepare GitHub metadata/social assets; repository/profile settings require owner action.
- [ ] R15: pin comparable evaluation artifacts and share proof definitions across generated content.
- [ ] R16: add frozen grounding/probability-summary consistency evaluation and explicit limitations.
- [ ] R17: label diagnostic training overlap; add genuinely held-out diagnostics where justified.
- [ ] Integration: targeted regressions, full offline checks, minimal-runtime model loading,
      README/schema/link consistency, exact-SHA CI and deployment smoke evidence.
- [ ] Natural live acceptance: verify due resolutions and score/export agreement, later batches
      and qualifying champion replacement; do not trigger paid runs merely for presentation.
- [ ] Owner gates: approved candidate facts/contributions/contact, German proofreading,
      external scheduler, GitHub presentation settings and real-reader comprehension test.

## Boundaries

Do not backfill forecasts/skips, rewrite sealed records, weaken checks or modify registered
comparison groups to improve appearance. Do not invent candidate biography or human feedback.
Use fixtures and fake providers locally. Keep the PR draft until the scoped implementation
and validation are complete; split independent changes into smaller PRs if necessary.
