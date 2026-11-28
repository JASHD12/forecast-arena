"""Forecasting skills for `agent_skills` (T351): short procedural notes loaded on demand.

Progressive disclosure, the same pattern as Anthropic's Agent Skills but implemented here so it
runs under the project's own budget guard, `FakeLLM` tests and as-of rules: the prompt carries a
one-line index (`index_text`), and the model may load the full text of a skill with the
`load_skill` tool (`ToolBox`, at most two loads per question).

Each skill is a folder `<name>/SKILL.md` with a small front matter:

    ---
    name: electricity-day-ahead
    description: one line shown in the index
    topics: power
    revision: 1
    ---

The files are trusted operator text shipped with the code (reviewed in the repository). Every
number in them comes from `scripts/skill_tables.py` between `<!-- generated:NAME -->` markers and
uses data that ends on 2026-10-31 (integrity rule I8: no skill is written because of how a live
question resolved). A fingerprint of all skill files is part of the `agent_skills` version.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

CUTOFF = "2026-10-31"
MAX_WORDS = 900
_FRONT = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.S)


@dataclass(frozen=True)
class Skill:
    """One skill: front matter fields and the body shown to the model."""

    name: str
    description: str
    topics: tuple[str, ...]
    revision: int
    body: str


def _parse(raw: str, folder: str) -> Skill:
    m = _FRONT.match(raw)
    if m is None:
        raise ValueError(f"skill {folder!r}: missing front matter")
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    for key in ("name", "description", "topics", "revision"):
        if not meta.get(key):
            raise ValueError(f"skill {folder!r}: front matter lacks {key!r}")
    if meta["name"] != folder:
        raise ValueError(f"skill folder {folder!r} and name {meta['name']!r} differ")
    topics = tuple(t.strip() for t in meta["topics"].split(",") if t.strip())
    return Skill(
        meta["name"], meta["description"], topics, int(meta["revision"]), m.group(2).strip()
    )


@lru_cache(maxsize=1)
def _all() -> dict[str, Skill]:
    root = resources.files("arena.agent.skills")
    out: dict[str, Skill] = {}
    for entry in sorted(root.iterdir(), key=lambda e: e.name):
        if not entry.is_dir():
            continue
        f = entry.joinpath("SKILL.md")
        if f.is_file():
            out[entry.name] = _parse(f.read_text(encoding="utf-8"), entry.name)
    return out


def names() -> list[str]:
    """Skill names, sorted."""
    return sorted(_all())


def get(name: str) -> Skill:
    """The skill called `name`; `KeyError` (with the valid names) if there is none."""
    try:
        return _all()[name]
    except KeyError:
        raise KeyError(f"unknown skill {name!r}; available: {', '.join(names())}") from None


def load(name: str) -> str:
    """The text of a skill as shown to the model."""
    s = get(name)
    return f"# Skill: {s.name} (revision {s.revision})\n\n{s.body}"


def index_text(domain: str | None = None) -> str:
    """One line per skill for the system prompt: name, what it is for, topics.

    With a `domain` (the question's topic) only the skills for that topic and the general ones
    (topics `all`) are listed, which keeps the prompt that is re-sent on every call short (r2);
    `load` still accepts any skill name.
    """
    return "\n".join(
        f"- {s.name}: {s.description} (topics: {', '.join(s.topics)})"
        for s in _all().values()
        if domain is None or "all" in s.topics or domain in s.topics
    )


def fingerprint() -> str:
    """First 8 hex digits of the sha256 over every skill file (name and bytes, sorted)."""
    h = hashlib.sha256()
    root = resources.files("arena.agent.skills")
    for name in names():
        h.update(name.encode() + b"\n" + root.joinpath(name, "SKILL.md").read_bytes())
    return h.hexdigest()[:8]
