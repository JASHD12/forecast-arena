#!/usr/bin/env bash
# T295: Prometheus scrapes the API's /metrics and Jaeger receives OTLP traces (needs Docker and
# the API requirements installed in .venv). Used by the CI job `observability` and `make
# smoke-observability`. Images: Apache-2.0, tags checked on Docker Hub on 2026-11-22.
set -euo pipefail
PY=${PY:-.venv/bin/python}
ARENA=${ARENA:-.venv/bin/arena}
LEDGER=${LEDGER:-/tmp/observability-ledger}
cleanup() { docker rm -f arena-prom arena-jaeger > /dev/null 2>&1 || true; kill "${API_PID:-0}" 2> /dev/null || true; }
trap cleanup EXIT

$PY scripts/make_e2e_ledger.py "$LEDGER"
$ARENA --ledger-dir "$LEDGER" api --host 0.0.0.0 --port 8000 > api.log 2>&1 &
API_PID=$!
for _ in $(seq 1 60); do curl -fsS http://127.0.0.1:8000/health > /dev/null && break; sleep 2; done

echo "== Prometheus scrapes /metrics"
docker run -d --name arena-prom --network host \
  -v "$PWD/deploy/observability/prometheus.yml:/etc/prometheus/prometheus.yml:ro" \
  prom/prometheus:v3.16.0 > /dev/null
for _ in 1 2 3; do curl -fsS "http://127.0.0.1:8000/questions?limit=2" > /dev/null; done
n=0
for _ in $(seq 1 30); do
  n=$(curl -fsS 'http://127.0.0.1:9090/api/v1/query?query=arena_http_requests_total' \
    | python3 -c "import sys,json; print(len(json.load(sys.stdin)['data']['result']))" || echo 0)
  [ "$n" -ge 1 ] && break
  sleep 3
done
test "$n" -ge 1
curl -fsS 'http://127.0.0.1:9090/api/v1/query?query=arena_ledger_questions' \
  | python3 -c "import sys,json; r=json.load(sys.stdin)['data']['result']; assert r and float(r[0]['value'][1]) > 0, r"
echo "prometheus: ok"

echo "== Jaeger receives the OTLP traces"
docker run -d --name arena-jaeger --network host jaegertracing/all-in-one:1.76.0 > /dev/null
for _ in $(seq 1 40); do curl -fsS http://127.0.0.1:16686/ > /dev/null && break; sleep 2; done
$PY scripts/otlp_sample.py | curl -fsS -X POST -H 'content-type: application/json' \
  --data-binary @- http://127.0.0.1:4318/v1/traces > /dev/null
n=0
for _ in $(seq 1 20); do
  n=$(curl -fsS "http://127.0.0.1:16686/api/traces?service=forecast-arena&limit=20" \
    | python3 -c "import sys,json; print(sum(len(t['spans']) for t in json.load(sys.stdin)['data']))" || echo 0)
  [ "$n" -ge 3 ] && break
  sleep 2
done
test "$n" -ge 3
echo "jaeger: ok ($n spans)"
