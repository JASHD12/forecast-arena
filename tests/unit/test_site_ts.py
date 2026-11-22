"""T296: the site script is compiled from TypeScript; the committed output is marked as such."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_the_static_app_is_generated_from_typescript_sources() -> None:
    ts = (ROOT / "site_ts" / "app.ts").read_text(encoding="utf-8")
    js = (ROOT / "src/arena/site/static/app.js").read_text(encoding="utf-8")
    assert "TypeScript since T296" in ts and "TypeScript since T296" in js
    assert js.startswith('"use strict";') and "interface " not in js  # types are gone
    assert "make site-ts" in js
    cfg = (ROOT / "tools/site-ts/tsconfig.json").read_text(encoding="utf-8")
    assert '"strict": true' in cfg and '"noUnusedLocals": true' in cfg


def test_the_typescript_has_no_any_and_no_ignore_comments() -> None:
    ts = (ROOT / "site_ts" / "app.ts").read_text(encoding="utf-8")
    assert ": any" not in ts and "as any" not in ts and "@ts-ignore" not in ts
