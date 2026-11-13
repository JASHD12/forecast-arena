"""The Airflow DAGs (T153) mirror the GitHub Actions jobs: same commands, same times.
(The DagBag parse itself runs in the CI `airflow` job, in Airflow's own environment.)"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DAG = (ROOT / "orchestration" / "airflow" / "arena_dag.py").read_text()


def test_every_dag_command_is_run_by_the_matching_workflow() -> None:
    blocks = re.split(r'with DAG\(\n\s+"arena_', DAG)[1:]
    assert len(blocks) == 3
    for block in blocks:
        job = block.split('"', 1)[0]
        wf = (ROOT / ".github" / "workflows" / f"{job}.yml").read_text()
        for cmd in re.findall(r'_task\(\w+, "\w+", "([^"]+)"\)', block):
            base = cmd.replace(" --record", "")
            assert base.split(" --")[0] in wf, (job, cmd)


def test_schedules_match_the_workflows() -> None:
    for job, cron in (("morning", "30 5 * * *"), ("resolve", "30 3,12,16,20 * * *"),
                      ("weekly", "0 2 * * 0")):  # fmt: skip
        assert f'"arena_{job}",\n    schedule="{cron}"' in DAG
    resolve = (ROOT / ".github" / "workflows" / "resolve.yml").read_text()
    assert all(f'"30 {h} * * *"' in resolve for h in (3, 12, 16, 20))
