"""The Airflow DAGs (T153) mirror the GitHub Actions jobs: same commands, same times.
(The DagBag parse itself runs in the CI `airflow` job, in Airflow's own environment.)"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DAG = (ROOT / "orchestration" / "airflow" / "arena_dag.py").read_text()


def test_every_dag_command_is_run_by_the_matching_workflow() -> None:
    blocks = re.split(r'with DAG\(\n\s+"arena_', DAG)[1:]
    assert len(blocks) == 4
    for block in blocks:
        job = block.split('"', 1)[0]
        wf = (ROOT / ".github" / "workflows" / f"{job}.yml").read_text()
        for cmd in re.findall(r'_task\(\w+, "\w+", "([^"]+)"\)', block):
            base = cmd.replace(" --record", "")
            assert base.split(" --")[0] in wf, (job, cmd)


def test_schedules_match_the_intended_times() -> None:
    """The DAGs keep the intended times (Airflow starts on time). GitHub starts scheduled
    runs late, so the workflows run more often behind a gate (T180) instead."""
    for job, cron in (("evening", "0 18 * * *"), ("morning", "30 5 * * *"),
                      ("resolve", "30 3,12,16,20 * * *"), ("weekly", "0 2 * * 0")):  # fmt: skip
        assert f'"arena_{job}",\n    schedule="{cron}"' in DAG
    wf = ROOT / ".github" / "workflows"
    assert '"15 0-8 * * *"' in (wf / "morning.yml").read_text()  # covers 05:30 and earlier
    assert '"0 16-23 * * *"' in (wf / "evening.yml").read_text()  # covers 18:00
    assert '"30 */3 * * *"' in (wf / "resolve.yml").read_text()  # includes 03:30 ... 21:30
    for job in ("morning", "evening", "players"):
        assert f"arena schedule due --job {job} --sync" in (wf / f"{job}.yml").read_text()
