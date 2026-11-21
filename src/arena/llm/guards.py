"""Input and output guards for text that reaches an LLM (T253, report-only in the lab).

Tool results and news headlines are untrusted data. The prompts already label them as data and the
harness enforces the call limits; these guards add a second, inspectable layer:

- `scan` and `sanitize` look for instruction-like text (English and German patterns), URLs, markup,
  code fences and role markers, and cap the length;
- `scrub_pii` removes e-mail addresses and phone numbers from headlines (S7);
- `check_answer` flags impossible probabilities and over-long rationales.

Regex heuristics are brittle by nature: paraphrases, spacing tricks and other languages get past
them. The red-team set in `lab/redteam/cases.json` measures exactly that, and the lab reports the
detections and the misses.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass

MAX_TEXT = 800

#: name -> pattern. Matched against NFKC-normalised, case-folded text.
INJECTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "override": re.compile(
        r"(ignore|disregard|forget|override|bypass)\W+(all\W+|any\W+|the\W+|your\W+)?"
        r"(previous|prior|above|earlier|preceding|system)\W+(instructions?|prompts?|rules?|messages?)"
    ),
    "override_de": re.compile(
        r"(ignorier\w*|vergiss|missachte)\W+(sie\W+)?(alle\W+|die\W+|deine\W+)?"
        r"(vorherigen|bisherigen|obigen|vorigen)?\W*(anweisungen|regeln|instruktionen)"
    ),
    "role_change": re.compile(
        r"(you are now|from now on you|act as|pretend (to be|you are)|new (role|persona)\b)"
    ),
    "reveal_prompt": re.compile(
        r"(reveal|print|show|repeat|output|leak)\W+(me\W+)?(your\W+|the\W+)?"
        r"(system\W+prompt|hidden\W+(prompt|instructions?)|instructions? above)"
    ),
    "force_output": re.compile(
        r"(set|make|output|answer|respond|reply|return)\W+(with\W+)?(the\W+|your\W+)?"
        r"(probability|forecast|answer)\W*(?:to|as|of|=|is|:)?\W*(0?\.\d+|\d{1,3}\s*%|yes\b|no\b|[01]\b)"
    ),
    "new_instructions": re.compile(
        r"(new instructions?\W*(follow|below|:|are|for you)|"
        r"updated instructions?\W*(follow|below|:|are)|"
        r"system (message|notice|update)|"
        r"important (notice|instruction)s? (for|to) (the )?(ai|assistant|model|forecaster))"
    ),
    "role_marker": re.compile(r"(^|\n)\s*(system|assistant|developer|user)\s*:", re.MULTILINE),
    "tool_spoof": re.compile(r"(</?(tool|function)[_ ]?(result|call|response)>|\"tool_use_id\")"),
    "template_token": re.compile(r"(<\|im_(start|end)\|>|\[/?inst\]|<<sys>>|</?s>)"),
}
URL = re.compile(r"https?://\S+|www\.\S+")
TAG = re.compile(r"<[^>]{1,200}>")
FENCE = re.compile(r"```.*?```", re.DOTALL)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
PHONE = re.compile(r"(?<!\w)(\+?\d[\d ()/.-]{7,}\d)(?!\w)")
ZERO_WIDTH = re.compile("[​‌‍⁠﻿]")


@dataclass(frozen=True)
class Sanitized:
    """Cleaned text and what was found."""

    text: str
    flags: tuple[str, ...]


def normalise(text: str) -> str:
    """NFKC, zero-width characters removed, case-folded: what the patterns are matched against."""
    return unicodedata.normalize("NFKC", ZERO_WIDTH.sub("", text)).casefold()


def scan(text: str) -> list[str]:
    """Names of the injection patterns found in `text` (empty if none)."""
    norm = normalise(text)
    return sorted(name for name, pat in INJECTION_PATTERNS.items() if pat.search(norm))


def scrub_pii(text: str) -> str:
    """Replace e-mail addresses and phone numbers."""
    return PHONE.sub("[phone]", EMAIL.sub("[email]", text))


def sanitize(text: str, max_len: int = MAX_TEXT) -> Sanitized:
    """Flag and neutralise untrusted text: code fences, markup, links, PII and a length cap."""
    flags = list(scan(text))
    out = ZERO_WIDTH.sub("", text)
    if FENCE.search(out):
        flags.append("code_fence")
        out = FENCE.sub("[code removed]", out)
    if TAG.search(out):
        flags.append("markup")
        out = TAG.sub("", out)
    if URL.search(out):
        flags.append("url")
        out = URL.sub("[link]", out)
    out = scrub_pii(out)
    if len(out) > max_len:
        flags.append("too_long")
        out = out[:max_len]
    if any(f in INJECTION_PATTERNS for f in flags):
        out = "[removed: instruction-like text]"
    return Sanitized(out.strip(), tuple(sorted(set(flags))))


def check_answer(probability: float, rationale: str | None, max_words: int = 80) -> list[str]:
    """Flags for a model answer: impossible probability or an over-long rationale."""
    flags = []
    if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
        flags.append("probability_out_of_range")
    if rationale is not None and len(rationale.split()) > max_words:
        flags.append("rationale_too_long")
    if rationale and scan(rationale):
        flags.append("rationale_contains_instruction")
    return flags
