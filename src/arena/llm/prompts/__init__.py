"""Versioned prompt files (SPEC 9.2). Changing any file requires a new version."""

from __future__ import annotations

import hashlib
from importlib import resources

PROMPT_VERSION = "v1"


def load(name: str, version: str = PROMPT_VERSION) -> str:
    """The text of `<name>_<version>.md`."""
    return (
        resources.files("arena.llm.prompts")
        .joinpath(f"{name}_{version}.md")
        .read_text(encoding="utf-8")
    )


def fingerprint(names: tuple[str, ...], version: str = PROMPT_VERSION) -> str:
    """Short hash of the named prompt files of a version (part of forecaster versions)."""
    h = hashlib.sha256()
    for name in sorted(names):
        h.update(name.encode() + b"\n" + load(name, version).encode())
    return h.hexdigest()[:12]
