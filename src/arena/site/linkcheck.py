"""Internal link check for the built site: every relative href/src must resolve to a file."""

from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for k, v in attrs:
            if k in ("href", "src") and v:
                self.links.append(v)
            if k == "id" and v:
                self.ids.add(v)


def check_site(root: Path) -> list[str]:
    """Return a list of broken internal links (empty when everything resolves)."""
    errors: list[str] = []
    pages = sorted(root.rglob("*.html"))
    parsed: dict[Path, _Links] = {}
    for page in pages:
        p = _Links()
        p.feed(page.read_text(encoding="utf-8"))
        parsed[page.resolve()] = p
    for page in pages:
        for link in parsed[page.resolve()].links:
            parts = urlsplit(link)
            if parts.scheme or parts.netloc or link.startswith("mailto:"):
                continue
            target = page if not parts.path else (page.parent / unquote(parts.path)).resolve()
            if parts.path and not target.is_file():
                errors.append(f"{page.relative_to(root)}: broken link {link}")
                continue
            if parts.fragment and target.suffix == ".html":
                ids = parsed.get(target.resolve())
                if ids is not None and parts.fragment not in ids.ids:
                    errors.append(f"{page.relative_to(root)}: missing anchor {link}")
    if not pages:
        errors.append("no pages found")
    return errors


def main(argv: list[str] | None = None) -> int:
    """CLI: `python -m arena.site.linkcheck site/`."""
    args = argv if argv is not None else sys.argv[1:]
    root = Path(args[0] if args else "site")
    errors = check_site(root)
    for e in errors:
        print(e)
    print(f"link check: {'FAIL' if errors else 'PASS'} ({len(list(root.rglob('*.html')))} pages)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
