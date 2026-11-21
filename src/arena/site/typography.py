"""Small typographic post-processing of built pages: dates never break at their hyphens."""

from __future__ import annotations

import re

_TAG = re.compile(r"(<[^>]*>)")
_DATE = re.compile(r"(?<![\w\"'=/#.\-])(\d{4}-\d{2}-\d{2})(?![\w\-])")
_SKIP_OPEN = ("<script", "<style", "<pre", "<textarea")
_SKIP_CLOSE = ("</script", "</style", "</pre", "</textarea")


def nowrap_dates(html: str) -> str:
    """Wrap ISO dates in the page body in `<span class="nw">` (text only, never attributes)."""
    start, end = html.find("<main"), html.find("</main>")
    if start < 0 or end < start:
        return html
    out: list[str] = []
    skipping = False
    for part in _TAG.split(html[start:end]):
        if part.startswith("<"):
            low = part.lower()
            if low.startswith(_SKIP_OPEN):
                skipping = True
            elif low.startswith(_SKIP_CLOSE):
                skipping = False
            out.append(part)
        else:
            out.append(part if skipping else _DATE.sub(r'<span class="nw">\1</span>', part))
    return html[:start] + "".join(out) + html[end:]
