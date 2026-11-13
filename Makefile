# Forecast Arena - developer entry points. See README.md.
VENV ?= .venv
PY ?= $(if $(wildcard $(VENV)/bin/python),$(VENV)/bin/python,python3)
RUFF ?= $(shell $(PY) -m ruff --version >/dev/null 2>&1 && echo '$(PY) -m ruff' || echo ruff)
export PYTHONPATH := src
# One OpenMP thread: deterministic model fits and no oversubscription in parallel jobs.
export OMP_NUM_THREADS ?= 1

.PHONY: setup setup-offline lint test e2e check status smoke-sources schemas site-e2e a11y notebook

setup:  ## Create .venv and install pinned dependencies
	@if uv --version >/dev/null 2>&1; then \
		uv venv $(VENV) && uv pip install --python $(VENV)/bin/python -r requirements-lock.txt && \
		uv pip install --python $(VENV)/bin/python --no-deps -e . ; \
	else \
		python3 -m venv $(VENV) && $(VENV)/bin/pip install -r requirements-lock.txt && \
		$(VENV)/bin/pip install --no-deps -e . ; \
	fi

setup-offline:  ## Like setup, but reuse already-installed system packages (no network)
	python3 -m venv --system-site-packages $(VENV)
	$(VENV)/bin/pip install --no-deps --no-build-isolation --no-index -e .

lint:
	$(RUFF) check src tests scripts apps
	$(RUFF) format --check src tests scripts apps
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

site-e2e:  ## Build the site from the offline e2e run into _site_e2e/ (link-checked)
	$(PY) scripts/build_e2e_site.py _site_e2e
	$(PY) -m arena.site.linkcheck _site_e2e

a11y: site-e2e  ## axe-core accessibility lint (needs Node and tools/a11y dependencies)
	NODE_PATH=tools/a11y/node_modules node tools/a11y/check.js _site_e2e
	NODE_PATH=tools/a11y/node_modules node tools/a11y/play.js _site_e2e

notebook: site-e2e  ## Execute notebooks/explore.ipynb on the e2e Parquet export (needs requirements-nb.txt)
	$(PY) scripts/run_notebook.py notebooks/explore.ipynb _site_e2e/data
