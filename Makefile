# Forecast Arena - developer entry points. See README.md.
VENV ?= .venv
PY ?= $(if $(wildcard $(VENV)/bin/python),$(VENV)/bin/python,python3)
RUFF ?= $(shell $(PY) -m ruff --version >/dev/null 2>&1 && echo '$(PY) -m ruff' || echo ruff)
export PYTHONPATH := src

.PHONY: setup setup-offline lint test e2e check status smoke-sources schemas

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
	$(RUFF) check src tests scripts
	$(RUFF) format --check src tests scripts

test:
	$(PY) -m pytest tests/unit

e2e:
	$(PY) -m pytest tests/e2e

check: lint test e2e

status:
	$(PY) scripts/status.py

schemas:  ## Re-export JSON Schemas after changing arena.models
	$(PY) -m arena.models

smoke-sources:  ## Live source checks (network). Not part of `make check`.
	@echo "No live sources implemented yet (Phase 2)."
