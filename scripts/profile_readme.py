"""Generate the GitHub profile README draft that presents Forecast Arena (T326).

    python scripts/profile_readme.py          # writes docs/profile/PROFILE_README.md
    python scripts/profile_readme.py --check  # fails if the file is stale

The profile page is the README of the owner's separate repository `JASHD12/JASHD12`, which this
repository's automation never writes to (CLAUDE.md). The owner pastes this file there. Every
figure comes from the same generators as the main README (I5); contact lines appear only when the
owner supplied them in `site_content/recruiter_facts.json` (H16), and no personal fact is invented.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import readme_sections as rs  # noqa: E402

from arena.site.recruiters import PROOFS, load_facts  # noqa: E402

SITE = "https://jashd12.github.io/forecast-arena/"
OUT = ROOT / "docs" / "profile" / "PROFILE_README.md"


def render() -> str:
    """The profile README text."""
    facts = load_facts(ROOT / "site_content")
    contact = []
    if facts.get("cv_url"):
        contact.append(f"[CV (PDF)]({facts['cv_url']})")
    if facts.get("linkedin"):
        contact.append(f"[LinkedIn]({facts['linkedin']})")
    if facts.get("email"):
        contact.append(f"[Email]({facts['email']})")
    cv_file = ROOT / "site_content" / "profile_cv.md"
    cv = cv_file.read_text(encoding="utf-8").strip() if cv_file.is_file() else ""
    cv_top, _, cv_more = cv.partition("<!-- featured-project -->")
    skills = " · ".join(skill for skill, _, _, _ in PROOFS)
    lines = [
        "# Jashdeep Singh",
        "",
        "**Werkstudent AI / Machine Learning / Data Science (Germany)**, also open to "
        "full-time applied ML engineering roles.",
        "",
    ]
    if contact:
        lines += [" · ".join(contact), ""]
    if cv_top.strip():  # the owner's own CV text, copied verbatim; never written by the agent (I5)
        lines += [cv_top.strip(), ""]
    lines += [
        "## Featured project: Forecast Arena",
        "",
        "A live, public benchmark: simple baselines, a classical ML model, and LLM forecasters "
        "publish probabilities for about 30 yes/no questions a day (electricity, weather, "
        "Wikipedia attention, exchange rates, crypto thresholds) **before the answer exists**, "
        "into an append-only, hash-chained ledger. The research question: when does an LLM "
        'agent beat a classical model, and when does it not? An honest "it does not" is a '
        "valid result.",
        "",
        f"**[Live site]({SITE})** · **[Ask the Arena]({SITE}ask.html)** (free chat over the "
        f"published record) · **[For recruiters]({SITE}recruiters.html)** · "
        f"**[forecast-audit]({SITE}audit.html)** (offline decision-audit tool and worked case) "
        "· [Source](https://github.com/JASHD12/forecast-arena)",
        "",
        rs.headline(),
        "",
        "### What it shows",
        "",
        rs.highlights(),
        "",
        "### Skills with the code behind them",
        "",
        skills,
        "",
        "## How it was built",
        "",
        "Specified and directed by me; implemented with AI coding agents; every figure on the "
        "site is generated from the public record by code. Research project, not advice of "
        "any kind.",
        "",
    ]
    if cv_more.strip():
        lines += [cv_more.strip(), ""]
    return "\n".join(lines)


def main() -> int:
    """Write the file, or with --check compare it."""
    text = render()
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print("profile README is stale: run python scripts/profile_readme.py")
            return 1
        print("profile README up to date")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
