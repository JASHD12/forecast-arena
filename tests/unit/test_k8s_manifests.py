"""Kubernetes manifests (T151): static checks; the live check runs on kind in CI."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def docs():
    out = {}
    for f in sorted((ROOT / "deploy" / "k8s").glob("*.yaml")):
        for d in yaml.safe_load_all(f.read_text()):
            out[(d["kind"], d["metadata"]["name"])] = d
    return out


def test_api_deployment_service_and_cronjob() -> None:
    d = docs()
    dep = d[("Deployment", "arena-api")]
    c = dep["spec"]["template"]["spec"]["containers"][0]
    assert c["image"] == "forecast-arena:ci" and c["imagePullPolicy"] == "Never"
    assert c["readinessProbe"]["httpGet"]["path"] == "/health"
    assert "api --host 0.0.0.0 --port 8000" in " ".join(c["args"])
    assert c["resources"]["limits"] and not c["securityContext"]["allowPrivilegeEscalation"]
    svc = d[("Service", "arena-api")]
    assert svc["spec"]["selector"] == dep["spec"]["selector"]["matchLabels"]
    assert svc["spec"]["ports"][0]["targetPort"] == 8000
    cron = d[("CronJob", "arena-verify")]
    assert cron["spec"]["concurrencyPolicy"] == "Forbid"
    job = cron["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]
    assert "ledger verify" in " ".join(job["args"])


def test_ci_runs_the_manifests_on_kind() -> None:
    ci = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text())
    steps = ci["jobs"]["kubernetes"]["steps"]
    assert any(s.get("uses", "").startswith("helm/kind-action@") for s in steps)
    text = " ".join(s.get("run", "") for s in steps)
    assert "kubectl apply -f deploy/k8s/" in text and "--from=cronjob/arena-verify" in text
