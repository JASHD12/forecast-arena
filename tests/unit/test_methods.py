from datetime import UTC, datetime
from pathlib import Path

from arena.clock import FixedClock
from arena.ledger import Ledger
from arena.site.build import build_site
from arena.site.methods_content import LIMITATIONS, PRINCIPLES

ROOT = Path(__file__).parents[2]
SPEC = (ROOT / "docs" / "SPEC.md").read_text()


def test_every_principle_of_spec_section_2_is_explained_with_code_locations(tmp_path) -> None:
    spec_ids = {
        line.split("**")[1].split(" ")[0] for line in SPEC.splitlines() if line.startswith("- **2.")
    }
    assert {p[0] for p in PRINCIPLES} == spec_ids
    methods = (ROOT / "docs" / "METHODS.md").read_text()
    site = build_site(
        Ledger(tmp_path / "l"),
        tmp_path / "site",
        FixedClock(datetime(2026, 11, 13, tzinfo=UTC)),
        tmp_path / "none",
    )
    page = (site.out_dir / "methods.html").read_text()
    for key, name, _rule, code in PRINCIPLES:
        assert f"| {key} {name} |" in methods and code in methods
        assert name in page and key in page
        for path in [c.strip().split(" ")[0] for c in code.split(",")]:
            if path.endswith(".py") and "/" in path and "*" not in path:
                assert (ROOT / "src" / "arena" / path).exists(), path
    for lim in LIMITATIONS:
        assert lim in methods
