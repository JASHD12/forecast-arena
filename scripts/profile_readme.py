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

from arena.site.recruiters import load_facts  # noqa: E402

SITE = "https://jashd12.github.io/forecast-arena/"
OUT = ROOT / "docs" / "profile" / "PROFILE_README.md"


RAW = "https://raw.githubusercontent.com/JASHD12/forecast-arena/main/"
REPO = "https://github.com/JASHD12/forecast-arena"
BADGES = (
    ("Python", "3776AB"),
    ("Azure", "0078D4"),
    ("GitHub_Actions", "2088FF"),
    ("PyTorch", "EE4C2C"),
    ("LangChain", "1C3C3C"),
)
# The three highlight bullets shown on the profile, picked by their opening words (the text and
# every figure in them come from readme_sections.highlights(), never typed here: I5).
HIGHLIGHT_KEYS = ("A classical model", "Forecasts locked")


def cv_sections(text: str) -> dict[str, str]:
    """Split the owner's CV text by its `## ` headings; the lead text is under the key ''."""
    out: dict[str, list[str]] = {"": []}
    key = ""
    for line in text.splitlines():
        if line.startswith("## "):
            key = line[3:].strip()
            out[key] = []
        else:
            out[key].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def _pick(section_prefix: str, secs: dict[str, str]) -> str:
    return next((v for k, v in secs.items() if k.startswith(section_prefix)), "")


def _highlights() -> str:
    bullets = [b for b in rs.highlights().splitlines() if b.startswith("- ")]
    chosen = [b for key in HIGHLIGHT_KEYS for b in bullets if b[2:].lstrip("*").startswith(key)]
    return "\n".join(chosen)


def _headline() -> str:
    """The generated result paragraph without its long caveat, then the live-record verdict."""
    first, _, live = rs.headline().partition("\n\n")
    verdict = live[live.index("Whether") :]
    return first.split(" Caveat:")[0] + "\n\n**Live record:** " + verdict


def _skill_table(skills: str) -> str:
    rows = ["| Area | Tools |", "|---|---|"]
    for line in skills.splitlines():
        if line.startswith("- **") and ":**" in line:
            area, _, tools = line[4:].partition(":**")
            rows.append(f"| {area} | {tools.strip()} |")
    return "\n".join(rows)


def render() -> str:
    """The profile README text: short, open to all roles, every figure generated."""
    facts = load_facts(ROOT / "site_content")
    contact = []
    if facts.get("email"):
        contact.append(f"[{facts['email']}](mailto:{facts['email']})")
    if facts.get("cv_url"):
        contact.append(f"[CV (PDF)]({facts['cv_url']})")
    if facts.get("linkedin"):
        contact.append(f"[LinkedIn]({facts['linkedin']})")
    cv_file = ROOT / "site_content" / "profile_cv.md"
    secs = cv_sections(cv_file.read_text(encoding="utf-8")) if cv_file.is_file() else {"": ""}
    lead, _, place = secs[""].partition("\n\n")
    if place.strip():
        contact.append(place.strip().removeprefix("\U0001f4cd").strip())
    badges = " ".join(
        f"![{n.replace('_', ' ')}](https://img.shields.io/badge/-{n}-{c}?logo={n.lower()}"
        f"&logoColor=white)"
        for n, c in BADGES
    )
    exp = _pick("Work experience", secs)
    exp_lines = [ln for ln in exp.splitlines() if ln.startswith("**")]
    lines = [
        "# Jashdeep Singh",
        "",
        "**Software engineer and M.Sc. Data Science student (Marburg, expected 2028)**, open to "
        "Werkstudent and full-time roles in AI/ML, data science, data engineering and "
        "software engineering in Germany.",
        "",
        (
            " · ".join(
                f"\U0001f4cd {c}" if c == contact[-1] and place.strip() else c for c in contact
            )
        ),
        "",
        badges,
        "",
        lead.strip(),
        "",
        "## What I work on",
        "",
        "- **Forecasting and ML evaluation:** Forecast Arena, below.",
        "- **Data platforms and backend:** Kafka ingestion, Azure Databricks reporting, "
        "Java/Spring Boot APIs (see Experience).",
        "- **LLM apps and evaluation:** a LangChain document assistant, and a measured QLoRA "
        "fine-tuning study inside Forecast Arena.",
        "",
        "## Featured projects",
        "",
        f"### [Forecast Arena]({REPO})",
        "",
        "A live, public benchmark: simple baselines, a classical ML model and LLM forecasters "
        "publish probabilities for yes/no questions about tomorrow (German day-ahead "
        "electricity, weather, Wikipedia attention, exchange rates, crypto) **before the answer "
        "exists**, into an append-only, hash-chained ledger. When does an LLM agent beat a "
        'classical model, and when does it not? An honest "it does not" is a valid result.',
        "",
        f"**[Live site]({SITE})** · **[For recruiters]({SITE}recruiters.html)** · "
        f"**[Ask the Arena]({SITE}ask.html)** · [Source]({REPO})",
        "",
        f"[![Standings]({RAW}docs/img/standings.svg)]({SITE})",
        "",
        _headline(),
        "",
        _highlights(),
        "",
    ]
    dp = _pick("Another project", secs)
    if dp:
        title = next(k for k in secs if k.startswith("Another project"))
        lines += [f"### {title.removeprefix('Another project: ')}", "", dp, ""]
    lines += [
        "## Experience",
        "",
        "\n".join(f"- {ln}" for ln in exp_lines),
        "",
        "<details><summary>What I did in each role</summary>",
        "",
        exp,
        "",
        "</details>",
        "",
        "## Skills",
        "",
        _skill_table(_pick("Technical skills", secs)),
        "",
        "## Education, achievements, languages",
        "",
        _pick("Education", secs),
        "",
        _pick("Achievements", secs),
        "",
        "**Languages:** " + _pick("Languages", secs),
        "",
        "## How it was built",
        "",
        "Specified and directed by me; implemented with AI coding agents; every figure on the "
        "site is generated from the public record by code. Research project, not advice of "
        "any kind.",
        "",
    ]
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
