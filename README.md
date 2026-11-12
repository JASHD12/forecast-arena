# Forecast Arena

A live, public benchmark in which different kinds of forecasters (simple baselines, a
classical ML model, LLMs with and without data, an LLM agent with tools) predict
tomorrow's real-world outcomes and are scored against what actually happens.

**Research question:** when does an LLM agent beat a classical ML model at forecasting,
and when does it not?

Status: under construction (Phase 0). This is a research project, not advice of any kind.

## Quick start

```bash
make setup     # creates .venv with pinned dependencies (uses uv if present)
make check     # lint + unit tests + offline end-to-end run
make status    # what the build backlog says is next
```

## Documentation

- [Specification](docs/SPEC.md)
- [Methods](docs/METHODS.md)
- [Runbook](docs/RUNBOOK.md)
- [Verified external sources](docs/SOURCES.md)
- [Explainers](docs/explainers/README.md)
- [Design decisions](DECISIONS.md)

## Licence

Code: MIT (see `LICENSE`). Data attributions are listed on every page of the site.
