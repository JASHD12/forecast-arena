# Forecast Arena - developer entry points. See README.md.
VENV ?= .venv
PY ?= $(if $(wildcard $(VENV)/bin/python),$(VENV)/bin/python,python3)
RUFF ?= $(shell $(PY) -m ruff --version >/dev/null 2>&1 && echo '$(PY) -m ruff' || echo ruff)
export PYTHONPATH := src
# One OpenMP thread: deterministic model fits and no oversubscription in parallel jobs.
export OMP_NUM_THREADS ?= 1

.PHONY: setup setup-offline lint test e2e check status smoke-sources smoke-site smoke-observability site-ts schemas site-e2e a11y notebook dbt

setup:  ## Create .venv and install pinned dependencies
	@if uv --version >/dev/null 2>&1; then \
		uv venv $(VENV) && uv pip install --python $(VENV)/bin/python -r requirements/lock.txt && \
		uv pip install --python $(VENV)/bin/python --no-deps -e . ; \
	else \
		python3 -m venv $(VENV) && $(VENV)/bin/pip install -r requirements/lock.txt && \
		$(VENV)/bin/pip install --no-deps -e . ; \
	fi

setup-offline:  ## Like setup, but reuse already-installed system packages (no network)
	python3 -m venv --system-site-packages $(VENV)
	$(VENV)/bin/pip install --no-deps --no-build-isolation --no-index -e .

lint:
	$(RUFF) check src tests scripts apps orchestration examples
	$(RUFF) format --check src tests scripts apps orchestration examples
	$(PY) -m mypy src/arena

PYTEST_ARGS ?=

test:
	$(PY) -m pytest tests/unit $(PYTEST_ARGS)

e2e:
	$(PY) -m pytest tests/e2e

check: lint test e2e

status:
	$(PY) scripts/status.py

schemas:  ## Re-export JSON Schemas after changing arena.models
	$(PY) -m arena.models

smoke-sources:  ## Live source checks (network). Not part of `make check`.
	$(PY) -m arena.sources.smoke

smoke-site:  ## Smoke-test the published site over HTTP (T182; override with SITE_URL=...)
	$(PY) scripts/smoke_site.py $(or $(SITE_URL),https://jashd12.github.io/forecast-arena/)

site-e2e:  ## Build the site from the offline e2e run into _site_e2e/ (link-checked)
	$(PY) scripts/build_e2e_site.py _site_e2e
	$(PY) -m arena.site.linkcheck _site_e2e

a11y: site-e2e  ## axe-core accessibility lint (needs Node and tools/a11y dependencies)
	NODE_PATH=tools/a11y/node_modules node tools/a11y/check.js _site_e2e
	NODE_PATH=tools/a11y/node_modules node tools/a11y/layout.js _site_e2e
	NODE_PATH=tools/a11y/node_modules node tools/a11y/play.js _site_e2e

notebook: site-e2e  ## Execute notebooks/explore.ipynb on the e2e Parquet export (needs requirements/nb.txt)
	$(PY) scripts/run_notebook.py notebooks/explore.ipynb _site_e2e/data

dbt: site-e2e  ## dbt build over the e2e export (dbt in its own venv: .venv-dbt, requirements/dbt.txt)
	test -x .venv-dbt/bin/dbt || (python3 -m venv .venv-dbt && .venv-dbt/bin/pip install -r requirements/dbt.txt)
	cd analytics/dbt && DBT_SEND_ANONYMOUS_USAGE_STATS=false ARENA_DATA_DIR=$(CURDIR)/_site_e2e/data ../../.venv-dbt/bin/dbt build --profiles-dir .

site-ts:  ## T296: compile site_ts/*.ts (tsc --strict) to src/arena/site/static/app.js (needs `npm ci --prefix tools/site-ts`)
	cd tools/site-ts && npx tsc -p tsconfig.json

smoke-observability: ## T295: needs Docker; Prometheus scrapes the API, Jaeger receives OTLP traces (the CI job `observability` runs the same script)
	scripts/smoke_observability.sh

.PHONY: forecast-audit-demo forecast-audit-test
forecast-audit-demo:  ## T321: the four-case example and the German electricity case (offline, standard library only)
	python3 -I examples/forecast-audit/report.py --cases examples/forecast-audit/cases.csv --predictions examples/forecast-audit/predictions.csv --candidate demo --baseline reference --false-alert-cost 1 --miss-cost 4 --on-missing no-alert --out build/forecast-audit-four-cases
	python3 -I examples/forecast-audit/report.py --cases examples/forecast-audit/german-electricity/cases.csv --predictions examples/forecast-audit/german-electricity/predictions.csv --candidate fine_tuned_gguf --baseline base_rate --timing-label replayed --false-alert-cost 1 --miss-cost 4 --out build/forecast-audit-electricity

forecast-audit-test:  ## T323: only the forecast-audit tests (offline)
	$(PY) -m pytest tests/unit/test_forecast_audit.py tests/unit/test_forecast_audit_electricity.py -q
