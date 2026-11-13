"""`arena mcp`: the benchmark as a read-only MCP server (T125, official `mcp` SDK).

Connect an MCP host (for example Claude Desktop or Claude Code) to a local checkout of the
ledger and ask about questions, forecasts and scores. Every tool is read-only and works on
a snapshot loaded at start-up; nothing can write to the ledger.

Tools: `list_questions`, `get_question`, `leaderboard` and `run_sql` (one SELECT over the
same DuckDB tables as the site's Open data page). SQL safety: one statement only, it must
start with SELECT or WITH, results are capped at `MAX_ROWS`, and DuckDB's external access
(files, network, extensions) is switched off and locked after the tables are loaded.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from arena.analytics.sql import connect as sql_connect
from arena.ledger import Ledger
from arena.scoring.core import Record, leaderboard, load
from arena.site.titles import domain_name, forecaster_name, plain_title

MAX_ROWS = 200
_SQL_START = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
INSTRUCTIONS = (
    "Forecast Arena: daily yes/no questions about public data, forecasts by baselines, an "
    "ML model and LLMs published before the answer exists, and their scores. Read-only. "
    "Rehearsal data until the official start; a research project, not advice."
)


class SqlRefused(ValueError):
    """A query that the read-only rules do not allow."""


def check_sql(query: str) -> str:
    """The query if it is a single SELECT/WITH statement, else SqlRefused."""
    q = query.strip().rstrip(";").strip()
    if not _SQL_START.match(q):
        raise SqlRefused("only a single SELECT (or WITH ... SELECT) query is allowed")
    if ";" in q:
        raise SqlRefused("only one statement is allowed")
    return q


def _question_row(rec: Record, qid: str) -> dict[str, Any]:
    q = rec.questions[qid]
    res = rec.resolutions.get(qid)
    void = rec.voids.get(qid)
    return {
        "question_id": qid,
        "title": plain_title(q),
        "domain": q.domain,
        "batch_date": q.batch_date.isoformat(),
        "target_date": q.target_date.isoformat(),
        "lock_time": q.lock_time.isoformat(),
        "status": "void" if void else "resolved" if res else "open",
        "outcome": None if res is None else ("YES" if res.outcome else "NO"),
    }


class Benchmark:
    """The read-only queries behind the tools (plain Python, testable without MCP)."""

    def __init__(self, ledger: Ledger) -> None:
        self.rec = load(ledger)
        self.con = sql_connect(self.rec)
        self.con.execute("SET enable_external_access = false")
        self.con.execute("SET lock_configuration = true")

    def list_questions(
        self, domain: str | None = None, status: Literal["open", "resolved", "all"] = "all",
        limit: int = 50,
    ) -> list[dict[str, Any]]:  # fmt: skip
        """Newest questions first."""
        qs = sorted(self.rec.questions.values(), key=lambda q: (q.batch_date, q.question_id),
                    reverse=True)  # fmt: skip
        rows = [_question_row(self.rec, q.question_id) for q in qs
                if domain is None or q.domain == domain]  # fmt: skip
        if status != "all":
            rows = [r for r in rows if r["status"] == status]
        return rows[: max(1, min(limit, MAX_ROWS))]

    def get_question(self, question_id: str) -> dict[str, Any]:
        """One question with its rule, every forecast and skip, and the resolution."""
        if question_id not in self.rec.questions:
            raise ValueError(f"unknown question {question_id!r}")
        q = self.rec.questions[question_id]
        res = self.rec.resolutions.get(question_id)
        return {
            **_question_row(self.rec, question_id),
            "text": q.text,
            "resolution_rule": q.resolution_rule,
            "source": q.resolution_source,
            "observed_value": None if res is None else res.observed_value,
            "forecasts": [
                {
                    "forecaster": f.forecaster_id,
                    "name": forecaster_name(f.forecaster_id),
                    "probability": f.probability,
                    "version": f.forecaster_version,
                    "created_at": f.created_at.isoformat(),
                }
                for f in sorted(self.rec.forecasts, key=lambda f: f.forecaster_id)
                if f.question_id == question_id
            ],
            "skips": [
                {"forecaster": s.forecaster_id, "reason": s.reason_code}
                for s in self.rec.skips
                if s.question_id == question_id
            ],
        }

    def leaderboard(self, domain: str | None = None) -> dict[str, Any]:
        """Brier, log score and skill against base_rate on every scored question."""
        scored = [s for s in self.rec.scored if domain is None or s.domain == domain]
        rows = [{"forecaster": r.forecaster_id, "name": forecaster_name(r.forecaster_id),
                 "n": r.n, "brier": r.brier, "log_score": r.log, "skill_vs_base_rate": r.skill}
                for r in leaderboard(scored)]  # fmt: skip
        return {
            "domain": domain_name(domain) if domain else "all topics",
            "note": "All scored questions, rehearsal included; the site's headline boards "
            "use the official record only and say 'too early to tell' below 30 days.",
            "rows": rows,
        }

    def run_sql(self, query: str) -> dict[str, Any]:
        """Run one read-only query; at most MAX_ROWS rows."""
        cur = self.con.execute(check_sql(query))
        cols = [d[0] for d in cur.description or []]
        rows = cur.fetchmany(MAX_ROWS + 1)
        return {
            "columns": cols,
            "rows": [
                [v if isinstance(v, int | float | str | None) else str(v) for v in r]
                for r in rows[:MAX_ROWS]
            ],
            "truncated": len(rows) > MAX_ROWS,
        }


def build_server(ledger: Ledger) -> Any:
    """The MCP server with the four read-only tools."""
    from mcp.server import MCPServer
    from mcp.types import ToolAnnotations

    b = Benchmark(ledger)
    ro = ToolAnnotations(read_only_hint=True, open_world_hint=False)
    server = MCPServer("forecast-arena", instructions=INSTRUCTIONS)

    @server.tool(annotations=ro)
    def list_questions(
        domain: str | None = None, status: Literal["open", "resolved", "all"] = "all",
        limit: int = 50,
    ) -> list[dict[str, Any]]:  # fmt: skip
        """List questions, newest first. domain: power, weather, attention, markets."""
        return b.list_questions(domain, status, limit)

    @server.tool(annotations=ro)
    def get_question(question_id: str) -> dict[str, Any]:
        """One question: rule, every forecast with its version and time, the outcome."""
        return b.get_question(question_id)

    @server.tool(annotations=ro)
    def leaderboard(domain: str | None = None) -> dict[str, Any]:
        """Scores per forecaster (Brier, log score, skill against the base rate)."""
        return b.leaderboard(domain)

    @server.tool(annotations=ro)
    def run_sql(query: str) -> dict[str, Any]:
        """One read-only DuckDB SELECT over tables questions, forecasts, resolutions, skips."""
        return b.run_sql(query)

    return server
