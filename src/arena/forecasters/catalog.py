"""The one table of forecasters (T383): ids, names, kinds, colours, information sets and flags.

Every list that used to be kept by hand in `site/titles.py`, `site/content.py`, `site/charts.py`,
`site/shaping.py` and `ops/health.py` is derived from `CATALOG` below, so adding or retiring a
forecaster is one edit here (plus the factory in `ops/wiring.py` and the CSS colour of a new slot,
which `tests/unit/test_catalog.py` checks). The table was generated from the previous lists and a
snapshot test (`tests/fixtures/forecaster_catalog_snapshot.json`) proves every derived value is
unchanged. No behaviour changes: no version string, prompt or threshold is touched (I8).

Fields: `kind` is baseline / ml / ai / combiner / human; `ai` marks forecasters shown with the AI
label; `flag` is the `Settings` attribute that switches an optional forecaster on (None: always on);
`core` forecasters must answer every morning (health check); `display` and `race` are positions in
the per-question table and the race-chart legend; `info` is (what it sees, which questions it
answers) for the Methods page.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Entry:
    """One forecaster."""

    id: str
    name: str
    kind: str
    slot: int | None = None
    ai: bool = False
    experimental: bool = False
    retired: bool = False
    flag: str | None = None
    core: bool = False
    display: int | None = None
    race: int | None = None
    info: tuple[str, str] | None = None


CATALOG: tuple[Entry, ...] = (
    Entry(
        id="base_rate",
        name="Base rate",
        kind="baseline",
        core=True,
        display=0,
        info=(
            "Trailing outcomes of the same template and entity",
            "all questions",
        ),
    ),
    Entry(
        id="persistence",
        name="Same as last time",
        kind="baseline",
        slot=5,
        core=True,
        display=1,
        info=(
            "Yesterday's outcome of the same template and entity",
            "all questions",
        ),
    ),
    Entry(
        id="ml",
        name="ML model",
        kind="ml",
        slot=1,
        core=True,
        display=2,
        info=(
            "The full as-of context",
            "all questions",
        ),
    ),
    Entry(
        id="llm_plain",
        name="AI, question only (retired)",
        kind="ai",
        slot=2,
        ai=True,
        retired=True,
        flag="llm_plain",
        display=3,
        race=0,
        info=(
            (
                "Question text, resolution rule, current date; no data, no tools (retired "
                "2026-11-27: no new forecasts, earlier ones stay)"
            ),
            "daily sample",
        ),
    ),
    Entry(
        id="llm_context",
        name="AI with data",
        kind="ai",
        slot=3,
        ai=True,
        core=True,
        display=4,
        race=1,
        info=(
            "The above plus a compact rendering of the as-of context",
            "daily sample",
        ),
    ),
    Entry(
        id="agent",
        name="AI agent with tools",
        kind="ai",
        slot=4,
        ai=True,
        core=True,
        display=6,
        race=2,
        info=(
            "As llm_context, plus read-only tools",
            "daily sample",
        ),
    ),
    Entry(
        id="llm_local",
        name="Open model (CPU)",
        kind="ai",
        slot=6,
        ai=True,
        flag="llm_local",
        display=5,
        race=4,
        info=(
            ("As llm_context, answered by an open model (Qwen2.5-1.5B) on the runner's CPU"),
            "daily sample",
        ),
    ),
    Entry(
        id="agent_graph",
        name="AI agent (LangGraph)",
        kind="ai",
        slot=8,
        ai=True,
        flag="agent_graph",
        display=7,
        race=3,
        info=(
            ("As agent, run as a LangGraph graph: plan, retrieved evidence, tools, self-check"),
            "1 question per topic per day",
        ),
    ),
    Entry(
        id="llm_local_ft",
        name="Fine-tuned open model (experimental)",
        kind="ai",
        slot=9,
        ai=True,
        experimental=True,
        flag="llm_local_ft",
        display=8,
        race=5,
        info=(
            ("As llm_context, answered by Qwen2.5-1.5B fine-tuned with QLoRA (experimental)"),
            "daily sample",
        ),
    ),
    Entry(
        id="llm_router",
        name="Cascade router (experimental)",
        kind="ai",
        slot=10,
        ai=True,
        experimental=True,
        display=9,
        race=6,
        info=(
            ("The forecasts of ml, llm_local_ft and llm_context for one question (experimental)"),
            "daily sample",
        ),
    ),
    Entry(
        id="agent_hybrid",
        name="AI agent, hybrid retrieval (experimental)",
        kind="ai",
        slot=11,
        ai=True,
        experimental=True,
        flag="agent_hybrid",
        display=10,
        race=7,
        info=(
            (
                "As agent, with hybrid retrieval of past questions and guarded tool text "
                "(experimental)"
            ),
            "daily sample",
        ),
    ),
    Entry(
        id="agent_quant",
        name="AI agent with a calculator (experimental)",
        kind="ai",
        slot=13,
        ai=True,
        experimental=True,
        flag="agent_quant",
        display=11,
        race=8,
        info=(
            (
                "As agent, plus a reference estimate computed from the stored data and a "
                "probability calculator (experimental)"
            ),
            "daily sample",
        ),
    ),
    Entry(
        id="agent_analyst",
        name="AI analyst reviewing the ML model (experimental)",
        kind="ai",
        slot=14,
        ai=True,
        experimental=True,
        flag="agent_analyst",
        display=12,
        race=9,
        info=(
            (
                "As agent, told to start from the ml forecast and change it only for evidence"
                " the model cannot see (experimental)"
            ),
            "daily sample",
        ),
    ),
    Entry(
        id="agent_skills",
        name="AI agent with skills (experimental)",
        kind="ai",
        slot=15,
        ai=True,
        experimental=True,
        flag="agent_skills",
        display=13,
        race=10,
        info=(
            (
                "As agent_quant, plus the load_skill tool: short topic notes written by the "
                "project team, loaded on demand (experimental)"
            ),
            "daily sample",
        ),
    ),
    Entry(
        id="agent_graph_skills",
        name="AI agent (LangGraph) with skills (experimental)",
        kind="ai",
        slot=16,
        ai=True,
        experimental=True,
        flag="agent_graph_skills",
        display=14,
        race=11,
        info=(
            (
                "As agent_graph (the LangGraph agent), plus the reference estimate, the "
                "probability calculator and the load_skill tool (experimental)"
            ),
            "daily sample",
        ),
    ),
    Entry(
        id="agent_hybrid_skills",
        name="AI agent, hybrid retrieval, with skills (experimental)",
        kind="ai",
        slot=17,
        ai=True,
        experimental=True,
        flag="agent_hybrid_skills",
        display=15,
        race=12,
        info=(
            (
                "As agent_hybrid (hybrid retrieval and guarded tool text), plus the reference"
                " estimate, the probability calculator and the load_skill tool (experimental)"
            ),
            "daily sample",
        ),
    ),
    Entry(
        id="agent_committee",
        name="AI committee of specialist agents (experimental)",
        kind="ai",
        slot=18,
        ai=True,
        experimental=True,
        flag="agent_committee",
        display=16,
        race=13,
        info=(
            (
                "A committee: a chair that calls four specialist agents over the A2A protocol"
                " (a reference estimate, the base rate and similar past questions, as-of "
                "headlines, and a skeptic that critiques the draft); it sees only the stored "
                "data, the base rate and tool results published before the forecast time, "
                "never the ML forecast (experimental)"
            ),
            "daily sample",
        ),
    ),
    Entry(
        id="llm_context_cal",
        name="AI with data, recalibrated (experimental)",
        kind="ai",
        slot=19,
        ai=True,
        experimental=True,
        flag="llm_context_cal",
        display=17,
        race=14,
        info=(
            (
                "The raw answer of llm_context for the same question, passed through one "
                "fixed logit map fitted on lab training answers (power questions only; other "
                "topics pass through unchanged); no tokens, no other data (experimental)"
            ),
            "the daily sample of llm_context",
        ),
    ),
    Entry(
        id="sentiment",
        name="News-tone model for crypto (experimental, backtest only)",
        kind="ml",
        slot=20,
        experimental=True,
        info=(
            (
                "The ml probability of the same crypto question and the news tone and article"
                " count of the days before it (GDELT, aggregate numbers only, each day "
                "counted 12 hours after it ended); backtest only so far, not running live "
                "(experimental)"
            ),
            "crypto questions",
        ),
    ),
    Entry(
        id="bandit_hedge",
        name="Learned blend of forecasters (experimental)",
        kind="combiner",
        slot=12,
        experimental=True,
        flag="bandit",
        display=18,
        info=(
            (
                "The other forecasters' forecasts of the same question, blended with weights "
                "learned online from resolved questions (Hedge; experimental)"
            ),
            "every question with two or more forecasts",
        ),
    ),
    Entry(
        id="ensemble",
        name="Ensemble",
        kind="combiner",
        slot=6,
    ),
    Entry(
        id="human_panel",
        name="Human panel",
        kind="human",
        slot=7,
    ),
)

BY_ID = {e.id: e for e in CATALOG}

#: Friendly names (display only).
FORECASTER_NAMES = {e.id: e.name for e in CATALOG}
#: Colour slot per forecaster (the CSS defines `--s<slot>` and `.s-<slot>`).
SERIES_SLOTS = {e.id: e.slot for e in CATALOG if e.slot is not None}
#: What each forecaster sees and which questions it answers (the Methods page).
INFORMATION_SETS = tuple((e.id, *e.info) for e in CATALOG if e.info is not None)
AI_FORECASTERS = frozenset(e.id for e in CATALOG if e.ai)
RETIRED_FORECASTERS = frozenset(e.id for e in CATALOG if e.retired)
EXPERIMENTAL_FORECASTERS = frozenset(e.id for e in CATALOG if e.experimental)
CORE_FORECASTERS = frozenset(e.id for e in CATALOG if e.core)
#: Order of the per-question table (the rest follow alphabetically).
DISPLAY_ORDER = tuple(
    e.id
    for e in sorted((e for e in CATALOG if e.display is not None), key=lambda e: e.display or 0)
)
#: The AI forecasters of the race chart and its legend, in legend order.
RACE_AI = tuple(
    e.id for e in sorted((e for e in CATALOG if e.race is not None), key=lambda e: e.race or 0)
)
#: The `Settings` attribute that switches each optional forecaster on.
FLAGS = {e.id: e.flag for e in CATALOG if e.flag is not None}


def expected_roster(settings: object) -> frozenset[str]:
    """The declared production roster: the core forecasters and every one whose flag is on."""
    return CORE_FORECASTERS | frozenset(
        fid for fid, flag in FLAGS.items() if getattr(settings, flag)
    )
