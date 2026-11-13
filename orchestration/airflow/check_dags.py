"""Parse the DAGs with Airflow's DagBag and check their shape (T153; run in CI):
`python orchestration/airflow/check_dags.py`."""

import sys
from pathlib import Path

from airflow.models.dagbag import DagBag

HERE = Path(__file__).resolve().parent
EXPECTED = {
    "arena_evening": (["evening", "verify", "build_site", "health_check"], "0 18 * * *"),
    "arena_morning": (
        ["morning", "verify", "build_site", "health_check", "official_start"],
        "30 5 * * *",
    ),
    "arena_resolve": (
        ["resolve", "verify", "build_site", "health_check", "official_start"],
        "30 3,12,16,20 * * *",
    ),
    "arena_weekly": (["weekly", "health_check", "official_start"], "0 2 * * 0"),
}


def main() -> int:
    bag = DagBag(dag_folder=str(HERE))
    if bag.import_errors:
        print("import errors:", bag.import_errors)
        return 1
    ok = True
    for dag_id, (order, schedule) in EXPECTED.items():
        dag = bag.dags.get(dag_id)
        if dag is None:
            print(f"missing DAG {dag_id}")
            ok = False
            continue
        ids = [t.task_id for t in dag.topological_sort()]
        sched = str(dag.schedule)
        pools = {t.pool for t in dag.tasks}
        print(f"{dag_id}: {' -> '.join(ids)} | {sched} | pool {sorted(pools)}")
        if ids != order or sched != schedule or pools != {"arena_ledger"}:
            print(f"  unexpected shape for {dag_id}")
            ok = False
    print("DAG check:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
