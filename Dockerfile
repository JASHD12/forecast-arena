# Reproducibility image (SPEC 12): installs the pinned dependencies and runs the offline
# end-to-end test. No network access is needed at run time; nothing is pushed anywhere.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    OMP_NUM_THREADS=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends make git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements/lock.txt requirements/api.txt ./requirements/
COPY pyproject.toml README.md LICENSE Makefile ./
COPY src ./src
COPY tests ./tests
COPY scripts ./scripts
RUN python -m venv .venv \
    && .venv/bin/pip install -r requirements/lock.txt \
    && .venv/bin/pip install -r requirements/api.txt \
    && .venv/bin/pip install --no-deps -e .

EXPOSE 8000
# Default: the offline end-to-end test. The API (T150) is started by compose.yaml or by
# overriding the command: generate the offline ledger, then serve it read-only.
CMD ["make", "e2e"]
