"""`arena-oracle` (T364): the benchmark's published record as a read-only A2A agent.

The A2A counterpart of `arena mcp` (MCP is agent-to-tool, A2A is agent-to-agent). It answers four
skills over a snapshot of the ledger and writes nothing: `list_questions`, `get_question`,
`leaderboard` (all three are `arena.mcp_server.Benchmark`, so the two interfaces cannot disagree)
and `explain_method` (cited sentences from the project documents, or "Not in the documents.").
The same refusal rules as Ask the Arena (`site_ts/chat.ts`) apply: no stocks, funds, trading or
advice, no private persons or personal data; a test keeps the patterns identical to the page's.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from starlette.applications import Starlette

from arena import a2a
from arena.a2a.cards import AgentSpec, SkillSpec, build_card
from arena.a2a.server import build_app
from arena.ledger import Ledger
from arena.mcp_server import Benchmark

NAME = "arena-oracle"
REVISION = "oracle-r1"
SKILLS = ("list_questions", "get_question", "leaderboard", "explain_method")
DOMAINS = {
    "power": "power",
    "electricity": "power",
    "weather": "weather",
    "wikipedia": "attention",
    "attention": "attention",
    "markets": "markets",
    "currency": "markets",
    "exchange": "markets",
    "crypto": "crypto",
}

# Ported from `site_ts/chat.ts` (the guard of Ask the Arena); tests compare the pattern sources.
STOCK = r"\b(stocks?|shares?|share price|equity|equities|aktie[n]?|etf[s]?|nasdaq|nyse|dax|dow jones|s&p|ftse|index fund|mutual fund|hedge fund|ticker)\b"  # noqa: E501
COMPANY = r"\b(google|alphabet|apple|microsoft|amazon|tesla|nvidia|meta platforms|netflix)\b"
PRICEY = (
    r"\b(price|worth|value|stock|share|forecast|predict|rise|fall|go up|go down|double|crash)\b"
)
ADVICE = r"\b(should i (?:buy|sell|invest|trade|hold)|shall i (?:buy|sell)|buy|sell|invest|investing|investment|trade|trading|portfolio|financial advice|stock tip|worth buying|go long|go short|kaufen|verkaufen|anlegen)\b"  # noqa: E501
PERSONAL = r"\b(my (email|phone|address|password|iban|salary)|home address|social security)\b"
PERSON_NAME = r"\b[Ww]ho is [A-Z][a-z]+ [A-Z][a-z]+\b"
_RE = {
    k: re.compile(v, 0 if k == "PERSON_NAME" else re.I)
    for k, v in {
        "STOCK": STOCK,
        "COMPANY": COMPANY,
        "PRICEY": PRICEY,
        "ADVICE": ADVICE,
        "PERSONAL": PERSONAL,
        "PERSON_NAME": PERSON_NAME,
    }.items()
}
REFUSALS = {
    "finance": (
        "I cannot help with stocks, funds, trading or what to buy or sell. This is a research "
        "project, not advice of any kind, and it forecasts only the topics it publishes: "
        "electricity, weather, Wikipedia attention, exchange rates and crypto thresholds."
    ),
    "personal": (
        "I do not answer questions about private persons or personal data, and I store nothing "
        "you send."
    ),
}
_QID = re.compile(r"[a-z]+-[a-z0-9_]+-[A-Za-z0-9_.%-]+-\d{4}-\d{2}-\d{2}-v\d+")


def refusal_kind(text: str) -> str | None:
    """ "finance", "personal" or None, by the same rules as the Ask the Arena page."""
    if _RE["STOCK"].search(text) or _RE["ADVICE"].search(text):
        return "finance"
    if _RE["COMPANY"].search(text) and _RE["PRICEY"].search(text):
        return "finance"
    if _RE["PERSONAL"].search(text) or _RE["PERSON_NAME"].search(text):
        return "personal"
    return None


def oracle_spec() -> AgentSpec:
    """The Agent Card contents of `arena-oracle`."""
    tags = ("forecasting", "benchmark", "read-only")
    return AgentSpec(
        name=NAME,
        description=(
            "Read-only answers about the Forecast Arena record: published questions, the "
            "forecasts locked before the answers existed, scores, and how the methods work."
        ),
        version=f"{REVISION}|sdk-{a2a.sdk_version()}",
        skills=(
            SkillSpec(
                "list_questions",
                "List questions",
                "Newest questions with status and outcome; arguments: domain, status, limit.",
                tags,
                ("list the open weather questions",),
            ),
            SkillSpec(
                "get_question",
                "Get one question",
                "One question with its rule, every forecast (with version and time) and the "
                "resolution; argument: question_id.",
                tags,
                ("show question power-mean_gt-DE_LU-2026-11-13-v1",),
            ),
            SkillSpec(
                "leaderboard",
                "Leaderboard",
                "Brier score, log score and skill against the base rate per forecaster; "
                "argument: domain.",
                tags,
                ("who leads on electricity?",),
            ),
            SkillSpec(
                "explain_method",
                "Explain a method",
                "Cited sentences from the project documents; says so when the answer is not "
                "in them; argument: question.",
                tags,
                ("how is the Brier score computed?",),
                input_modes=("application/json", "text/plain"),
            ),
        ),
        input_modes=("application/json", "text/plain"),
    )


class Oracle:
    """The handler behind the card: a snapshot, optional documents, no write path."""

    def __init__(self, bench: Benchmark, docs: Any | None = None) -> None:
        self.bench = bench
        self.docs = docs

    @classmethod
    def from_ledger(cls, ledger: Ledger, docs_root: Path | None = None) -> Oracle:
        """Load the snapshot and, if `docs_root` holds the documents, the explanation index."""
        docs = None
        if docs_root is not None:
            from arena.lab.docs_assistant import DOC_PATHS, DocsIndex, load_chunks

            chunks = load_chunks(docs_root, [p for p in DOC_PATHS if (docs_root / p).is_file()])
            docs = DocsIndex(chunks) if chunks else None
        return cls(Benchmark(ledger), docs)

    async def handle(self, payload: dict[str, Any]) -> dict[str, Any]:
        """One request: `{"skill", "args"}` or free `{"text"}`. Refusals are answers, not errors."""
        skill = payload.get("skill")
        args = dict(payload.get("args") or {})
        text = str(payload.get("text") or "")
        probe = " ".join([text, *(str(v) for v in args.values() if isinstance(v, str))])
        if (kind := refusal_kind(probe)) is not None:
            return self._refused(kind, REFUSALS[kind])
        if skill is None:
            skill, args = self._route(text)
        if skill not in SKILLS:
            return self._refused(
                "unknown_skill", f"Unknown skill {skill!r}; skills: {', '.join(SKILLS)}."
            )
        return {
            "skill": skill,
            "refused": False,
            "result": self._run(str(skill), args),
            "notice": a2a.DISCLAIMER,
        }

    @staticmethod
    def _refused(kind: str, message: str) -> dict[str, Any]:
        return {
            "skill": None,
            "refused": True,
            "reason": kind,
            "message": message,
            "notice": a2a.DISCLAIMER,
        }

    def _route(self, text: str) -> tuple[str, dict[str, Any]]:
        t = text.lower()
        domain = next((v for k, v in DOMAINS.items() if k in t), None)
        if m := _QID.search(text):
            return "get_question", {"question_id": m.group(0)}
        if re.search(r"leaderboard|score|brier|rank|who (leads|wins)|best forecaster", t):
            return "leaderboard", {"domain": domain} if domain else {}
        if re.search(
            r"\b(list|latest|recent|open|newest)\b.*\bquestions?\b|\bquestions?\b.*\b(open|latest)\b",
            t,
        ):
            return "list_questions", {"domain": domain} if domain else {}
        return "explain_method", {"question": text}

    def _run(self, skill: str, args: dict[str, Any]) -> Any:
        b = self.bench
        if skill == "list_questions":
            status = str(args.get("status", "all"))
            domain = args.get("domain")
            limit = int(args.get("limit", 20))
            if status == "open":
                return b.list_questions(str(domain) if domain else None, "open", limit)
            if status == "resolved":
                return b.list_questions(str(domain) if domain else None, "resolved", limit)
            if status != "all":
                raise ValueError(f"status must be open, resolved or all, not {status!r}")
            return b.list_questions(str(domain) if domain else None, "all", limit)
        if skill == "get_question":
            return b.get_question(str(args["question_id"]))
        if skill == "leaderboard":
            domain = args.get("domain")
            return b.leaderboard(str(domain) if domain else None)
        return self._explain(str(args.get("question", "")))

    def _explain(self, question: str) -> dict[str, Any]:
        if self.docs is None:
            return {
                "answer": "The project documents are not available in this deployment.",
                "citations": [],
                "refused": True,
            }
        from arena.lab.docs_assistant import ask

        a = ask(self.docs, question)
        return {"answer": a.text, "citations": list(a.citations), "refused": a.refused}


def build_oracle_app(oracle: Oracle, public_url: str) -> Starlette:
    """The ASGI app of `arena-oracle`, its card announcing `public_url` (ends with `/`)."""
    return build_app(build_card(oracle_spec(), public_url), oracle.handle)
