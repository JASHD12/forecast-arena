"""Model registry on the ledger (T055): versioned artefacts, metadata, promotions.

Layout (never overwritten; `Ledger.write_raw` refuses existing paths):

    models/<domain>/<version>/model.joblib.xz   the fitted model (xz-compressed joblib)
    models/<domain>/<version>/metadata.json     version, training cut-off, sizes, hashes
    models/<domain>/<version>/model_card.md     optional model card
    models/<domain>/promotions/<UTC timestamp>-<version>.json   one file per promotion

The current model of a domain is the one named by the latest promotion file. Artefacts
are stored only for promoted models, to keep the ledger branch small (SPEC 15).
"""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import joblib

from arena.ledger import Ledger
from arena.ledger.manifest import code_sha, package_versions

ARTEFACT = "model.joblib.xz"


class RegistryError(Exception):
    """The registry is inconsistent (e.g. a hash mismatch)."""


@dataclass(frozen=True)
class ModelInfo:
    """Metadata of a stored model."""

    domain: str
    version: str
    sha256: str
    meta: dict[str, Any]


def _dir(domain: str, version: str) -> str:
    return f"models/{domain}/{version}"


def save_model(
    ledger: Ledger,
    domain: str,
    model: Any,
    *,
    created_at: datetime,
    meta: dict[str, Any] | None = None,
    card: str | None = None,
) -> ModelInfo:
    """Store a model artefact with metadata (refuses to overwrite a version)."""
    version = str(model.version)
    buf = io.BytesIO()
    joblib.dump(model, buf, compress=("xz", 9))
    blob = buf.getvalue()
    sha = hashlib.sha256(blob).hexdigest()
    info = {
        "domain": domain,
        "version": version,
        "artefact_sha256": sha,
        "artefact_bytes": len(blob),
        "created_at": created_at.isoformat(),
        "code_sha": code_sha(),
        "package_versions": package_versions(),
        **(meta or {}),
    }
    d = _dir(domain, version)
    ledger.write_raw(f"{d}/{ARTEFACT}", blob)
    ledger.write_raw(
        f"{d}/metadata.json",
        (json.dumps(info, sort_keys=True, indent=1, default=str) + "\n").encode(),
    )
    if card:
        ledger.write_raw(f"{d}/model_card.md", card.encode())
    return ModelInfo(domain, version, sha, info)


def promote(ledger: Ledger, domain: str, version: str, *, at: datetime, reason: str) -> str:
    """Record that `version` is now the current model of `domain`."""
    if not ledger.exists(f"{_dir(domain, version)}/metadata.json"):
        raise RegistryError(f"cannot promote unknown model {domain}/{version}")
    rel = f"models/{domain}/promotions/{at.strftime('%Y%m%dT%H%M%SZ')}-{version}.json"
    body = {"domain": domain, "version": version, "promoted_at": at.isoformat(), "reason": reason}
    ledger.write_raw(rel, (json.dumps(body, sort_keys=True) + "\n").encode())
    return rel


def versions(ledger: Ledger, domain: str) -> list[str]:
    """Stored versions of a domain's model."""
    out = set()
    for rel in ledger.list_files(f"models/{domain}"):
        parts = rel.split("/")
        if len(parts) == 4 and parts[3] == "metadata.json":
            out.add(parts[2])
    return sorted(out)


def current_version(ledger: Ledger, domain: str) -> str | None:
    """The version named by the latest promotion, or None."""
    files = sorted(ledger.list_files(f"models/{domain}/promotions"))
    if not files:
        return None
    return str(json.loads(ledger.read_bytes(files[-1]))["version"])


def load(ledger: Ledger, domain: str, version: str) -> Any:
    """Load a stored model, checking its hash against the metadata."""
    d = _dir(domain, version)
    if not ledger.exists(f"{d}/{ARTEFACT}"):
        raise RegistryError(f"no artefact for {domain}/{version}")
    blob = ledger.read_bytes(f"{d}/{ARTEFACT}")
    meta = json.loads(ledger.read_bytes(f"{d}/metadata.json"))
    if hashlib.sha256(blob).hexdigest() != meta["artefact_sha256"]:
        raise RegistryError(f"artefact hash mismatch for {domain}/{version}")
    return joblib.load(io.BytesIO(blob))


def load_current(ledger: Ledger, domains: list[str]) -> dict[str, Any]:
    """Current model per domain; domains without a promoted model are left out (the `ml`
    forecaster then records `model_missing` skips for them)."""
    out = {}
    for d in domains:
        v = current_version(ledger, d)
        if v is not None:
            out[d] = load(ledger, d, v)
    return out
