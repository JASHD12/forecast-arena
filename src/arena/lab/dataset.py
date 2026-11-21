"""Leak-free supervised data for the fine-tuning experiments (T241, SPEC 17 rule L3).

Rows are rebuilt by replaying the production domain code for past batch days: the
question, the as-of context the live forecasters would have seen at 05:30 UTC, and the
outcome. The input text is the exact live prompt (`LLMContext.user_prompt` and the
`system` prompt), so a model trained here sees what `llm_context` sees.

Splits are by batch day and never overlap: train < validation < test. Test sets are
frozen files whose hashes are committed before any training run.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from arena.domains.base import Domain
from arena.evals.golden import GoldenItem, build
from arena.forecasters.llm import LLMContext
from arena.llm import prompts

#: Inclusive batch-day windows (rule L3). Qwen2.5's training data ends in 2024, before every window.
SPLITS: dict[str, tuple[date, date]] = {
    "train": (date(2018, 12, 1), date(2026, 6, 30)),
    "val": (date(2026, 7, 1), date(2026, 9, 30)),
    "test_oct": (date(2026, 10, 1), date(2026, 10, 31)),
    "test_nov": (date(2026, 11, 1), date(2026, 11, 15)),
}


@dataclass(frozen=True)
class Row:
    """One supervised example: the live prompt and the outcome."""

    id: str
    domain: str
    template: str
    batch_date: str
    asof: str
    split: str
    system: str
    user: str
    outcome: int
    base_rate: float | None

    def as_json(self) -> str:
        """Canonical one-line JSON."""
        return json.dumps(self.__dict__, sort_keys=True, ensure_ascii=False)


def check_windows(splits: Mapping[str, tuple[date, date]] = SPLITS) -> None:
    """Raise if windows are inverted, overlap, or are not ordered train < val < test."""
    order = ["train", "val", "test_oct", "test_nov"]
    prev_end: date | None = None
    for name in order:
        first, last = splits[name]
        if first > last:
            raise ValueError(f"split {name}: first is after last")
        if prev_end is not None and first <= prev_end:
            raise ValueError(f"split {name} starts on or before the previous split ends")
        prev_end = last


def to_row(item: GoldenItem, split: str) -> Row:
    """The supervised row of one replayed question, with the exact live prompt."""
    q = item.question
    forecaster = LLMContext(None)
    return Row(
        id=q.question_id,
        domain=q.domain,
        template=q.template,
        batch_date=q.batch_date.isoformat(),
        asof=item.asof.isoformat(),
        split=split,
        system=prompts.load("system", forecaster.prompt_version),
        user=forecaster.user_prompt(q, item.context, item.asof),
        outcome=item.outcome,
        base_rate=item.base_rate,
    )


def build_split(
    domain: Domain, split: str, splits: Mapping[str, tuple[date, date]] = SPLITS
) -> list[Row]:
    """All rows of one split for `domain`, sorted by (batch_date, id)."""
    first, last = splits[split]
    resolve_at = datetime.combine(last + timedelta(days=3), datetime.min.time(), tzinfo=UTC)
    rows = [to_row(it, split) for it in build(domain, first, last, resolve_at)]
    return sorted(rows, key=lambda r: (r.batch_date, r.id))


def subsample(rows: Sequence[Row], max_rows: int, seed: int = 0) -> list[Row]:
    """A seeded, template-proportional subsample (stable under re-runs; sorted like the input)."""
    if max_rows >= len(rows):
        return list(rows)
    by_template: dict[str, list[Row]] = defaultdict(list)
    for r in rows:
        by_template[r.template].append(r)
    keep: set[str] = set()
    templates = sorted(by_template)
    quota = {t: max(1, round(max_rows * len(by_template[t]) / len(rows))) for t in templates}
    for t in templates:
        ranked = sorted(
            by_template[t], key=lambda r: hashlib.sha256(f"{seed}:{r.id}".encode()).hexdigest()
        )
        keep.update(r.id for r in ranked[: quota[t]])
    return [r for r in rows if r.id in keep]


def write_split(rows: Sequence[Row], path: Path) -> str:
    """Write JSON Lines atomically; returns the SHA-256 of the file."""
    body = ("\n".join(r.as_json() for r in rows) + "\n").encode() if rows else b""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    # a `.gz` file is deterministic (no timestamp); the hash is always over the plain bytes
    tmp.write_bytes(gzip.compress(body, 9, mtime=0) if path.suffix == ".gz" else body)
    tmp.replace(path)
    return hashlib.sha256(body).hexdigest()


def read_split(path: Path) -> list[Row]:
    """Read a split file back."""
    raw = path.read_bytes()
    text = (gzip.decompress(raw) if path.suffix == ".gz" else raw).decode("utf-8")
    return [Row(**json.loads(line)) for line in text.splitlines() if line]


def plain_sha256(path: Path) -> str:
    """SHA-256 of the plain (decompressed) bytes of a split file."""
    raw = path.read_bytes()
    return hashlib.sha256(gzip.decompress(raw) if path.suffix == ".gz" else raw).hexdigest()


def summary(rows: Sequence[Row]) -> dict[str, Any]:
    """Counts for the data card: rows, YES rate, per template, first and last day."""
    if not rows:
        return {"rows": 0}
    templates: dict[str, int] = defaultdict(int)
    for r in rows:
        templates[r.template] += 1
    days = sorted({r.batch_date for r in rows})
    return {
        "rows": len(rows),
        "yes_rate": round(sum(r.outcome for r in rows) / len(rows), 4),
        "templates": dict(sorted(templates.items())),
        "first_day": days[0],
        "last_day": days[-1],
        "days": len(days),
        "chars_user_p50": sorted(len(r.user) for r in rows)[len(rows) // 2],
    }


def assert_no_overlap(split_rows: Mapping[str, Sequence[Row]]) -> None:
    """Raise if one batch day appears in two splits."""
    seen: dict[str, str] = {}
    for name, rows in split_rows.items():
        for r in rows:
            other = seen.setdefault(r.batch_date, name)
            if other != name:
                raise ValueError(f"batch day {r.batch_date} is in both {other} and {name}")


def data_card(manifest: Mapping[str, Any]) -> str:
    """The data card (markdown) generated from the manifest; every figure is copied from it."""
    lines = [
        "# Data card: forecast SFT rows (power)",
        "",
        "**EVALUATION / EXPERIMENT DATA, not the live record.** Rebuilt by replaying the",
        "production question, context and resolution code for past batch days (SPEC 17,",
        "rule L3). Prompts are the exact live `llm_context` prompts.",
        "",
        "| Split | Window | Rows | YES rate | Days | SHA-256 |",
        "|---|---|---|---|---|---|",
    ]
    for name, s in manifest["splits"].items():
        w = s["window"]
        lines.append(
            f"| {name} | {w[0]} to {w[1]} | {s['rows']} | {s.get('yes_rate', '-')} "
            f"| {s.get('days', 0)} | `{s['sha256'][:16]}...` |"
        )
    lines += [
        "",
        "Leakage argument: windows are ordered train < validation < test and never share a",
        "batch day (checked in code); every context was built by the as-of store as it would",
        "have been at 05:30 UTC of the batch day; the base model (Qwen2.5) has a training",
        "cutoff in 2024, before every window. The training split is a seeded,",
        f"template-proportional subsample (seed {manifest['seed']}).",
        "",
        "Limits: power only (attention contexts need live per-article API calls, weather has",
        "no forecast history); the replay resolves against current SMARD values, so later",
        "data revisions can show in outcomes; one German market.",
        "",
    ]
    return "\n".join(lines)
