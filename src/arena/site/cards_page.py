"""The Backtests page (T135): the committed model cards (`docs/models/*.md`), rendered
under a permanent BACKTEST banner (integrity rule I4: never mixed with the live record).

The renderer is small and safe: every card is HTML-escaped first, then only headings,
pipe tables, bullet lists, **bold**, `code` and https links are turned into markup.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

from markupsafe import Markup

#: card file stem -> (title on the page, order)
CARD_ORDER = ("power", "power-lgbm", "power-mlp", "power-ts", "attention", "markets")


def _inline(s: str) -> str:
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)


def _table(lines: list[str], label: str) -> str:
    rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines]
    head, body = rows[0], rows[2:]
    num = [
        all(re.match(r"^[-+\[\]0-9., ]+$", r[i] or "x") for r in body if i < len(r))
        for i in range(len(head))
    ]

    def cls(i: int) -> str:
        return ' class="num"' if i < len(num) and num[i] else ""

    ths = "".join(f'<th scope="col"{cls(i)}>{_inline(h)}</th>' for i, h in enumerate(head))
    out = [
        f'<div class="table-scroll" tabindex="0" role="region" aria-label="{label}"><table>',
        f"<thead><tr>{ths}</tr></thead><tbody>",
    ]
    for r in body:
        tds = "".join(f"<td{cls(i)}>{_inline(c)}</td>" for i, c in enumerate(r[1:], start=1))
        out.append(f'<tr><th scope="row">{_inline(r[0])}</th>{tds}</tr>')
    out.append("</tbody></table></div>")
    return "".join(out)


def render_card(text: str, label: str) -> Markup:
    """Markdown subset of the model cards to HTML (headings shifted down one level)."""
    esc = html.escape(text, quote=False)
    blocks = [b for b in re.split(r"\n\s*\n", esc) if b.strip()]
    out = []
    for k, b in enumerate(blocks):
        lines = b.strip("\n").split("\n")
        if all(ln.lstrip().startswith("|") for ln in lines) and len(lines) >= 2:
            out.append(_table(lines, f"{label} table {k + 1}"))
        elif all(ln.startswith("- ") for ln in lines):
            out.append("<ul>" + "".join(f"<li>{_inline(ln[2:])}</li>" for ln in lines) + "</ul>")
        elif m := re.match(r"^(#{1,3})\s+(.*)$", lines[0]):
            level = min(6, max(3, len(m.group(1)) + 1))  # cards sit under an h2
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            if len(lines) > 1:
                out.append("<p>" + _inline(" ".join(lines[1:])) + "</p>")
        else:
            out.append("<p>" + _inline(" ".join(ln.strip() for ln in lines)) + "</p>")
    return Markup("\n".join(out))


def load_cards(models_dir: Path | None) -> list[dict[str, Any]]:
    """Every committed card, in a fixed order (known stems first, then the rest)."""
    if models_dir is None or not models_dir.is_dir():
        return []
    files = {p.stem: p for p in models_dir.glob("*.md")}
    order = [s for s in CARD_ORDER if s in files] + sorted(s for s in files if s not in CARD_ORDER)
    out = []
    for stem in order:
        text = files[stem].read_text(encoding="utf-8")
        first = text.splitlines()[0] if text else stem
        title = re.sub(r"^#\s*(Model card:\s*)?", "", first).replace("`", "")
        body = "\n".join(text.splitlines()[1:])
        out.append({"id": f"card-{stem}", "stem": stem, "title": title,
                    "html": render_card(body, title)})  # fmt: skip
    return out


def headline_backtest(models_dir: Path | None, stem: str = "power") -> dict[str, Any] | None:
    """The home page's BACKTEST card (T186), parsed from a committed model card.

    Returns the Brier score of each forecaster in the card's first table, the paired
    difference of `ml` against the base rate with its interval, and the period; None when
    the card is missing or does not have that shape. Values are copied, never computed
    here, so the home page and the card can never disagree (I5).
    """
    if models_dir is None or not (models_dir / f"{stem}.md").is_file():
        return None
    text = (models_dir / f"{stem}.md").read_text(encoding="utf-8")
    rows = {m.group(1): m.group(3) for m in
            re.finditer(r"^\| (\w+) \| (\d+) \| ([0-9.]+) \| \[", text, re.M)}  # fmt: skip
    diff = re.search(r"^\| ml - base_rate \| ([-+0-9.]+) \| (\[[^\]]+\]) \| (yes|no)", text, re.M)
    span = re.search(r"Batches (\S+) to (\S+) \((\d+) batch days\)", text)
    if not rows.get("ml") or not rows.get("base_rate") or diff is None or span is None:
        return None
    return {
        "rows": [(f, v, float(v)) for f, v in sorted(rows.items(), key=lambda kv: float(kv[1]))],
        "diff": diff.group(1), "interval": diff.group(2), "supported": diff.group(3) == "yes",
        "start": span.group(1), "end": span.group(2), "days": int(span.group(3)),
    }  # fmt: skip
