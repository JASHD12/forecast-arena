# SOURCES.md - verified external facts

Every external fact the code relies on (API endpoints, parameters, publication times,
terms, licences, GitHub Action versions) is listed here with the official page it was
checked against and the date. Code must not rely on anything that is not in this table.

| Fact | Source URL | Date checked | Notes |
|---|---|---|---|
| `actions/checkout` current major is `v7` (latest v7.0.1) | https://github.com/actions/checkout (tags) | 2026-11-12 | read via `git ls-remote --tags` |
| `actions/setup-python` current major is `v7` (latest v7.1.0) | https://github.com/actions/setup-python (tags) | 2026-11-12 | same |
| `actions/configure-pages` `v6`, `actions/upload-pages-artifact` `v5`, `actions/deploy-pages` `v5` | https://github.com/actions (tags of each repo) | 2026-11-12 | for T030 |
| `astral-sh/setup-uv` latest is v10.3.3 but moving major tags stop at `v7` | https://github.com/astral-sh/setup-uv (tags) | 2026-11-12 | not used: CI installs with pip from the lock file |

## Availability rules for historical data

Conservative rules for when a value counts as "available" to a forecaster (SPEC 7.0).
Filled in per source by T023, T040, T042, T044.
