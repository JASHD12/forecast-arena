"""A table of contents for the long reference pages (no JavaScript needed).

Post-processes a rendered page: finds its `<h2>` headings after the page head, gives each a
unique id (an existing id is kept), and inserts an "On this page" list after the head.
Pages with fewer than `MIN_SECTIONS` headings are left alone."""

from __future__ import annotations

import re
from html import escape

MIN_SECTIONS = 4
_H2 = re.compile(r"<h2(?P<attrs>(?:\s[^>]*)?)>(?P<inner>.*?)</h2>", re.S)
_ID = re.compile(r'\sid="([^"]+)"')
_TAG = re.compile(r"<[^>]+>")
#: Long reference pages whose sections fold on phones (script-driven; open without it).
FOLD_PAGES = ("methods.html", "backtests.html", "experiments.html", "stack.html")
#: Pages that get a table of contents (the long ones).
TOC_PAGES = (
    "methods.html",
    "backtests.html",
    "experiments.html",
    "stack.html",
    "status.html",
    "data.html",
    "findings.html",
    "guide.html",
    "about.html",
    "evals.html",
    "llm.html",
)


def _slug(text: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "section"
    slug, n = base, 2
    while slug in taken:
        slug, n = f"{base}-{n}", n + 1
    taken.add(slug)
    return slug


def add_toc(html: str) -> str:
    """Return `html` with ids on its h2 headings and a contents list after the page head."""
    end_head, close = html.find("</header>", html.find('<header class="page-head">')), "</header>"
    if end_head < 0 or '<header class="page-head">' not in html:
        start = html.find('<section class="hero')  # pages with a hero instead of a page head
        end_head, close = (html.find("</section>", start), "</section>") if start >= 0 else (-1, "")
    if end_head < 0:
        return html
    head, body = html[: end_head + len(close)], html[end_head + len(close) :]
    taken = set(_ID.findall(html))
    items: list[tuple[str, str]] = []

    def repl(m: re.Match[str]) -> str:
        attrs, inner = m.group("attrs"), m.group("inner")
        label = " ".join(_TAG.sub("", inner).split())
        if not label:
            return m.group(0)
        found = _ID.search(attrs)
        if found:
            slug = found.group(1)
        else:
            slug = _slug(label, taken)
            attrs = f'{attrs} id="{slug}"'
        items.append((slug, label))
        return f"<h2{attrs}>{inner}</h2>"

    new_body = _H2.sub(repl, body)
    if len(items) < MIN_SECTIONS:
        return html
    links = "".join(f'<li><a href="#{escape(s)}">{escape(t)}</a></li>' for s, t in items)
    toc = (
        f'\n<nav class="toc" aria-label="On this page"><details open><summary>On this page '
        f"({len(items)} sections)</summary><ol>{links}</ol></details></nav>\n"
    )
    return head + toc + new_body


def mark_fold(html: str) -> str:
    """Flag `<main>` so the phone script folds its sections (without it everything stays open)."""
    return html.replace('<main id="main">', '<main id="main" data-fold>', 1)
