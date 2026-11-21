"""The pinned artefact of a fine-tuned live forecaster (T271, SPEC 17 rule L4).

`lab/artefacts/llm_local_ft.json` is committed only after the owner has uploaded the files of a
Colab run (HUMAN_TODO H26, H28) and the evaluation has been shown (H32). Until then
`load_artefact` returns None and the forecaster records `model_missing` skips with that reason.
A download whose SHA-256 differs from the pin is refused (an `error`, never a fallback).
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "lab" / "artefacts" / "llm_local_ft.json"
CHUNK = 1 << 20


@dataclass(frozen=True)
class FtArtefact:
    """What is needed to run, version and audit the fine-tuned model."""

    name: str  # e.g. "qwen2.5-1.5b-qlora-r1"
    url: str  # GitHub release asset of the GGUF file
    sha256: str  # of the GGUF file
    filename: str
    platt: tuple[float, float]  # (a, b) fitted on the validation split only
    yes_id: int
    no_id: int
    base_model: str
    base_revision: str
    adapter_sha256: str
    run_id: str  # the Colab run (its run_summary.json hash is in the release)
    prereg_sha256: str

    def version(self, prompt_tag: str) -> str:
        """The forecaster version: changes with the artefact, calibration and prompt (SPEC 8.5)."""
        a, b = self.platt
        return f"{self.name}|gguf-{self.sha256[:8]}|platt-{a:.4f}-{b:.4f}|{prompt_tag}"


def load_artefact(path: Path = DEFAULT_PATH) -> FtArtefact | None:
    """The committed pin, or None if the model has not been published yet."""
    if not path.is_file():
        return None
    d = json.loads(path.read_text(encoding="utf-8"))
    d["platt"] = (float(d["platt"][0]), float(d["platt"][1]))
    return FtArtefact(**d)


def sha256_file(path: Path) -> str:
    """SHA-256 of a file, read in chunks."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def fetch(art: FtArtefact, cache_dir: Path, user_agent: str = "forecast-arena") -> Path:
    """The GGUF file in `cache_dir`, downloaded once and verified against the pin."""
    dest = cache_dir / art.filename
    if dest.is_file() and sha256_file(dest) == art.sha256:
        return dest
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(art.url, headers={"User-Agent": user_agent})
    h = hashlib.sha256()
    with urllib.request.urlopen(req, timeout=120) as r, tmp.open("wb") as out:
        while chunk := r.read(CHUNK):
            h.update(chunk)
            out.write(chunk)
    if h.hexdigest() != art.sha256:
        tmp.unlink(missing_ok=True)
        raise ValueError(f"downloaded file has SHA-256 {h.hexdigest()}, pinned {art.sha256}")
    tmp.replace(dest)
    return dest
