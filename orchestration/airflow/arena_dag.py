"""Forecast Arena's daily jobs as Airflow DAGs (T153, Airflow 3).

Production scheduling is GitHub Actions (free, no server). These DAGs mirror the same
CLI commands and schedule so the pipeline could move to Airflow unchanged; they are
validated in CI by parsing them with Airflow's DagBag, and are not deployed anywhere.

Mapping (UTC):
- arena_evening   18:00 daily: publish tomorrow's questions -> verify -> site -> health (T160).
- arena_morning   05:30 daily: morning job -> verify -> site -> health -> official start.
                  The 09:30 lock is enforced inside `arena daily morning` (a late run
                  writes nothing), and the DAG run times out at the lock as a second guard.
- arena_resolve   03:30, 12:30, 16:30, 20:30: resolve -> verify -> site -> health.
- arena_weekly    Sunday 02:00: weekly retraining -> health -> official start.
All four share one pool slot ("arena_ledger") so only one job writes the ledger at a time,
like the shared concurrency group in GitHub Actions.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

ARENA = "{{ var.value.get('arena_bin', '.venv/bin/arena') }}"
POOL = "arena_ledger"
DEFAULTS = {"retries": 1, "retry_delay": timedelta(minutes=10), "pool": POOL}
START = datetime(2026, 11, 13, tzinfo=UTC)


def _task(dag: DAG, task_id: str, cmd: str) -> BashOperator:
    return BashOperator(task_id=task_id, bash_command=f"{ARENA} {cmd}", dag=dag)


with DAG(
    "arena_evening",
    schedule="0 18 * * *",
    start_date=START,
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULTS,
    tags=["forecast-arena"],
    doc_md="Publish tomorrow's questions tonight; the forecasts follow in the morning.",
) as evening:
    e_run = _task(evening, "evening", "daily evening --push")
    e_verify = _task(evening, "verify", "ledger verify --git")
    e_site = _task(evening, "build_site", "site build --out site")
    e_health = _task(evening, "health_check", "health check --job evening --record")
    e_run >> e_verify >> e_site >> e_health

with DAG(
    "arena_morning",
    schedule="30 5 * * *",
    start_date=START,
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(hours=4),  # 05:30 + 4 h = the 09:30 UTC lock
    default_args=DEFAULTS,
    tags=["forecast-arena"],
    doc_md="Create questions, collect forecasts and seal the batch before the 09:30 lock.",
) as morning:
    m_run = _task(morning, "morning", "daily morning --push")
    m_verify = _task(morning, "verify", "ledger verify --git")
    m_site = _task(morning, "build_site", "site build --out site")
    m_health = _task(morning, "health_check", "health check --job morning --record")
    m_official = _task(morning, "official_start", "official update --push")
    m_run >> m_verify >> m_site >> m_health >> m_official

with DAG(
    "arena_resolve",
    schedule="30 3,12,16,20 * * *",
    start_date=START,
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULTS,
    tags=["forecast-arena"],
    doc_md="Record answers from the official sources, score, seal finished days.",
) as resolve:
    r_run = _task(resolve, "resolve", "daily resolve --push")
    r_verify = _task(resolve, "verify", "ledger verify --git")
    r_site = _task(resolve, "build_site", "site build --out site")
    r_health = _task(resolve, "health_check", "health check --job resolve --record")
    r_official = _task(resolve, "official_start", "official update --push")
    r_run >> r_verify >> r_site >> r_health >> r_official

with DAG(
    "arena_weekly",
    schedule="0 2 * * 0",
    start_date=START,
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULTS,
    tags=["forecast-arena"],
    doc_md="Retrain the models, promote only by the written rule, publish reports.",
) as weekly:
    w_run = _task(weekly, "weekly", "weekly run --push")
    w_health = _task(weekly, "health_check", "health check --job weekly --record")
    w_official = _task(weekly, "official_start", "official update --push")
    w_run >> w_health >> w_official
