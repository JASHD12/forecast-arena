"""Prompt formatting and token ids for the YES/NO answer (no torch needed)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from arena.lab.dataset import Row

YES, NO = "YES", "NO"


class Tokenizer(Protocol):
    """The slice of the Hugging Face tokenizer interface that the lab uses."""

    pad_token_id: int | None

    def apply_chat_template(self, messages: list[dict[str, str]], **kw: Any) -> str:
        """Render a chat to text."""

    def encode(self, text: str, **kw: Any) -> list[int]:
        """Text to token ids."""


@dataclass(frozen=True)
class Encoded:
    """One tokenized row."""

    id: str
    ids: list[int]
    label: float  # 1 = YES; a teacher probability when distilling (soft label)


def prompt_text(tokenizer: Tokenizer, system: str, user: str) -> str:
    """The chat text up to the start of the assistant answer (the live prompt, unchanged)."""
    return tokenizer.apply_chat_template(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        tokenize=False,
        add_generation_prompt=True,
    )


def answer_token_ids(tokenizer: Tokenizer) -> tuple[int, int]:
    """Token ids of `YES` and `NO`; both must be a single, different token."""
    yes = tokenizer.encode(YES, add_special_tokens=False)
    no = tokenizer.encode(NO, add_special_tokens=False)
    if len(yes) != 1 or len(no) != 1 or yes == no:
        raise ValueError(f"YES/NO must be one distinct token each, got {yes} and {no}")
    return yes[0], no[0]


def encode_rows(
    tokenizer: Tokenizer, rows: Sequence[Row], max_len: int
) -> tuple[list[Encoded], int]:
    """Tokenize rows; rows longer than `max_len` are dropped (never cut) and counted."""
    out: list[Encoded] = []
    dropped = 0
    for r in rows:
        ids = tokenizer.encode(prompt_text(tokenizer, r.system, r.user), add_special_tokens=False)
        if len(ids) > max_len:
            dropped += 1
            continue
        out.append(Encoded(r.id, ids, r.outcome))
    return out, dropped
