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


def fingerprint(version: str = PROMPT_VERSION) -> str:
    """Short hash of every prompt file of a version (recorded in forecast meta)."""
    h = hashlib.sha256()
    for f in sorted(resources.files("arena.llm.prompts").iterdir(), key=lambda p: p.name):
        if f.name.endswith(f"_{version}.md"):
            h.update(f.name.encode() + b"\n" + f.read_bytes())
    return h.hexdigest()[:12]
