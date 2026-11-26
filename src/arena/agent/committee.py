# ruff: noqa: E501
"""`agent_committee` (T363): a chair that forecasts with four specialist agents it calls over A2A.

Experimental, off by default, a new forecaster id (integrity rule I8: no existing forecaster or version
changes). Fixed flow per question, pre-registered in `lab/prereg/agent-committee.md`:

    chair -> quant-analyst, historian, news-scout (parallel A2A tasks)
          -> chair draft -> skeptic (A2A task) -> chair final

The members are separate A2A agents (cards, task lifecycle, JSON-RPC) reached through the in-process
transport (`arena.a2a.transport`), so no socket is opened in the morning job. The chair itself is the A2A
client and calls the model twice; the members that use a model (`news-scout`, `skeptic`) call it once.
All model calls go through the shared guarded client (daily cap), and every tool result a member reads
passes the harness guards. Quorum (I6): the committee answers only if the chair's calls succeed, the
skeptic succeeded and at least two of the three research members completed; otherwise it records a skip
with the reason and the failed members, never a filler number.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from arena import a2a
from arena.a2a.cards import AgentSpec
from arena.a2a.client import CallResult
from arena.a2a.transport import InProcessHub, run_sync
from arena.agent import skills
from arena.agent.committee_members import (
    HISTORIAN,
    QUANT_MEMBER,
    RESEARCH_MEMBERS,
    REVISIONS,
    SCOUT,
    SKEPTIC,
    Members,
    member_specs,
)
from arena.agent.forecaster import AgentForecaster
from arena.agent.hybrid import GUARD_VERSION, _guard
from arena.agent.tools import ToolBox
from arena.forecasters.llm import render_context
from arena.llm import prompts
from arena.llm.budget import BudgetExhausted
from arena.llm.client import LLMClient, LLMError, Usage, UserText
from arena.llm.parse import Answer, ParseError, parse_answer
from arena.models import Forecast, Question, Skip

COMMITTEE_REVISION = "committee-r2"
MEMBER_TIMEOUT = 90.0
COMMITTEE_TIMEOUT = 300.0
MIN_RESEARCH_MEMBERS = 2


class AgentCommittee(AgentForecaster):
    """`agent_committee`; see the module docstring."""

    forecaster_id = "agent_committee"
    prompt_files = (
        "committee_chair",
        "committee_brief",
        "committee_final",
        "committee_scout",
        "committee_skeptic",
        "repair",
    )
    prompt_versions = {"repair": "v2"}  # noqa: RUF012 - read-only class default

    def __init__(self, client: LLMClient | None, **kw: Any) -> None:
        kw.setdefault("prompt_version", "v1")
        super().__init__(client, guard=_guard, **kw)
        self.members = Members(client, toolbox=self._member_toolbox)

    # -- identity -------------------------------------------------------------------------------
    def version(self) -> str:
        """Model, prompt fingerprint, every member revision, protocol and SDK versions, guards."""
        model = self.client.model if self.client is not None else "none"
        fp = prompts.fingerprint_map({n: self._pv(n) for n in self.prompt_files})
        rag = f"|rag-{self.retriever.embedder.name}" if self.retriever is not None else ""
        members = ",".join(REVISIONS[m] for m in (QUANT_MEMBER, HISTORIAN, SCOUT, SKEPTIC))
        return (
            f"{model}|prompt-{fp}|{COMMITTEE_REVISION}|members-{members}{rag}"
            f"|a2a-{a2a.PROTOCOL_VERSION}|sdk-{a2a.sdk_version()}|{GUARD_VERSION}"
            f"|skills-{skills.fingerprint()}|out-{self.max_output_tokens}"
        )

    def _member_version_suffix(self) -> str:
        return f"|{COMMITTEE_REVISION}|sdk-{a2a.sdk_version()}"

    def agent_specs(self) -> dict[str, AgentSpec]:
        """The four served members' specs (cards)."""
        return member_specs(self._member_version_suffix())

    # -- tools for members ---------------------------------------------------------------------
    def _peer_probabilities(
        self, q: Question, ctx: dict[str, Any], asof: datetime
    ) -> dict[str, dict[str, float]]:
        return {}  # members get the base rate in the payload; the committee never sees `ml`

    def _member_toolbox(
        self, q: Question, ctx: dict[str, Any], asof: datetime, extra: dict[str, Any]
    ) -> ToolBox:
        return self._toolbox(q, ctx, asof, **extra)

    def _base_rate(self, q: Question, ctx: dict[str, Any], asof: datetime) -> dict[str, float]:
        out: dict[str, float] = {}
        for fid, f in self.peers.items():
            try:
                r = f.forecast(q, ctx, asof)
            except Exception:  # a failing peer only means the historian has no base rate
                continue
            if isinstance(r, Forecast):
                out[fid] = r.probability
        return out

    # -- the forecast ---------------------------------------------------------------------------
    def forecast(self, q: Question, ctx: dict[str, Any], asof: datetime) -> Forecast | Skip:
        """See `Forecaster.forecast`."""
        if self.client is None:
            return self._skip(q, "model_missing", "no LLM configured", asof)
        if self.sample is not None and q.question_id not in self.sample:
            return self._skip(q, "not_sampled", "not in today's LLM sample", asof)
        run = _Run()
        try:
            answer = run_sync(
                asyncio.wait_for(self._deliberate(q, ctx, asof, run), timeout=COMMITTEE_TIMEOUT)
            )
        except BudgetExhausted as exc:
            return self._finish_skip(q, run, "budget_exhausted", str(exc), asof)
        except _Quorum as exc:
            return self._finish_skip(q, run, exc.reason, exc.detail, asof)
        except LLMError as exc:
            return self._finish_skip(q, run, "error", f"{type(exc).__name__}: {exc}", asof)
        except ParseError as exc:
            return self._finish_skip(
                q, run, "parse_failure", f"two unparseable answers: {exc}", asof
            )
        except TimeoutError:
            return self._finish_skip(
                q, run, "error", f"committee timeout after {COMMITTEE_TIMEOUT:.0f}s", asof
            )
        self._trace_run(q, run, "forecast")
        assert self.client is not None
        return Forecast(
            forecast_id=f"{q.question_id}::{self.forecaster_id}",
            question_id=q.question_id,
            forecaster_id=self.forecaster_id,
            forecaster_version=self.version(),
            probability=answer.probability,
            created_at=asof,
            rationale=answer.rationale,
            meta={
                "model": self.client.model,
                "provider": self.client.provider,
                "prompt_version": self.prompt_version,
                "sampling": self.client.sampling(),
                "key_factors": list(answer.key_factors),
                "usage": run.usage.as_dict(),
                "committee": run.summary(),
            },
        )

    async def _deliberate(
        self, q: Question, ctx: dict[str, Any], asof: datetime, run: _Run
    ) -> Answer:
        peers = self._base_rate(q, ctx, asof)
        payload: dict[str, Any] = {
            "question": q.model_dump(mode="json"),
            "asof": asof.isoformat(),
            "context": ctx,
            "peers": peers,
        }
        specs = self.agent_specs()
        handlers = self.members.handlers()
        agents = {name: (specs[name], handlers[name]) for name in specs}
        async with InProcessHub(
            agents, server_timeout=MEMBER_TIMEOUT, client_timeout=MEMBER_TIMEOUT + 10
        ) as hub:
            results = await asyncio.gather(*(hub.client(n).ask(payload) for n in RESEARCH_MEMBERS))
            run.calls.update(zip(RESEARCH_MEMBERS, results, strict=True))
            reports = {n: r.data for n, r in run.calls.items() if r.ok and r.data is not None}
            for r in run.calls.values():
                run.add_member_usage(r)
            failed = [n for n in RESEARCH_MEMBERS if n not in reports]
            self._raise_if_budget(run)
            if len(reports) < MIN_RESEARCH_MEMBERS:
                raise _Quorum("error", f"quorum not met: {', '.join(failed)} failed")
            brief = self._fill("committee_brief", q, ctx, asof, reports=_dump(reports))
            draft = await self._chair(q, brief, run, "draft")
            run.draft = draft.probability
            skeptic_in = {
                "question": payload["question"],
                "draft": {"probability": draft.probability, "rationale": draft.rationale},
                "reports": reports,
            }
            crit = await hub.client(SKEPTIC).ask(skeptic_in)
            run.calls[SKEPTIC] = crit
            run.add_member_usage(crit)
            self._raise_if_budget(run)
            if not crit.ok or crit.data is None:
                raise _Quorum("error", f"skeptic failed: {crit.error}")
            run.critique = {k: crit.data.get(k) for k in ("severity", "direction")}
            final_in = self._fill(
                "committee_final",
                q,
                ctx,
                asof,
                reports=_dump(reports),
                draft=json.dumps(
                    {
                        "probability": draft.probability,
                        "rationale": draft.rationale,
                        "key_factors": list(draft.key_factors),
                    },
                    ensure_ascii=False,
                ),
                critique=_dump({k: crit.data.get(k) for k in ("severity", "issues", "direction")}),
            )
            return await self._chair(q, final_in, run, "final")

    def _fill(
        self, name: str, q: Question, ctx: dict[str, Any], asof: datetime, **blocks: str
    ) -> str:
        text = (
            prompts.load(name, self._pv(name))
            .replace("{today}", asof.date().isoformat())
            .replace("{lock_time}", q.lock_time.strftime("%Y-%m-%d %H:%M UTC"))
            .replace("{asof}", asof.strftime("%Y-%m-%d %H:%M UTC"))
            .replace("{question_id}", q.question_id)
            .replace("{question}", q.text)
            .replace("{rule}", q.resolution_rule)
            .replace("{context}", render_context(ctx))
        )
        for key, value in blocks.items():
            text = text.replace("{" + key + "}", value)
        return text

    async def _chair(self, q: Question, user: str, run: _Run, step: str) -> Answer:
        """One chair call with one repair attempt; usage goes into the run."""
        assert self.client is not None
        system = prompts.load("committee_chair", self._pv("committee_chair"))
        resp = await asyncio.to_thread(
            self.client.complete, system, [UserText(user)], max_tokens=self.max_output_tokens
        )
        run.usage = run.usage + resp.usage
        try:
            return parse_answer(resp.text)
        except ParseError as first:
            repair = prompts.load("repair", self._pv("repair")).replace("{error}", str(first))
            resp = await asyncio.to_thread(
                self.client.complete,
                system,
                [UserText(user), UserText(repair)],
                max_tokens=self.max_output_tokens,
            )
            run.usage = run.usage + resp.usage
            run.repairs.append(step)
            return parse_answer(resp.text)

    @staticmethod
    def _raise_if_budget(run: _Run) -> None:
        for r in run.calls.values():
            if r.error and "BudgetExhausted" in r.error:
                raise BudgetExhausted(r.error)

    # -- traces ---------------------------------------------------------------------------------
    def _finish_skip(
        self, q: Question, run: _Run, reason: str, detail: str, asof: datetime
    ) -> Skip:
        failed = [n for n, r in run.calls.items() if not r.ok]
        suffix = f" [failed members: {', '.join(failed)}]" if failed else ""
        self._trace_run(q, run, reason)
        return self._skip(q, reason, detail + suffix, asof)

    def _trace_run(self, q: Question, run: _Run, outcome: str) -> None:
        self.traces[q.question_id] = {
            "question_id": q.question_id,
            "outcome": outcome,
            "a2a_calls": [r.trace() for r in run.calls.values()],
            "committee": run.summary(),
            "usage": run.usage.as_dict(),
        }


class _Quorum(Exception):
    """The committee cannot answer by its pre-registered rule."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


class _Run:
    """State of one question's deliberation (for the forecast meta and the trace)."""

    def __init__(self) -> None:
        self.calls: dict[str, CallResult] = {}
        self.usage = Usage()
        self.draft: float | None = None
        self.critique: dict[str, Any] = {}
        self.repairs: list[str] = []

    def add_member_usage(self, r: CallResult) -> None:
        """Add the usage a member reported in its artifact (members with a model call)."""
        if r.data and isinstance(r.data.get("usage"), Mapping):
            u = r.data["usage"]
            self.usage = self.usage + Usage(
                requests=int(u.get("requests", 0)),
                input_tokens=int(u.get("input_tokens", 0)),
                output_tokens=int(u.get("output_tokens", 0)),
                cache_read_tokens=int(u.get("cache_read_tokens", 0)),
                cache_write_tokens=int(u.get("cache_write_tokens", 0)),
            )

    def summary(self) -> dict[str, Any]:
        """Compact, JSON-ready description of who did what (no article text)."""
        members: dict[str, Any] = {}
        for name, r in self.calls.items():
            d = r.data or {}
            members[name] = {
                "state": r.state,
                "status": d.get("status"),
                "duration_ms": r.duration_ms,
                "bytes_in": r.bytes_in,
                "sources": list(d.get("sources", []))[:10],
                "guard_flags": list(d.get("guard_flags", [])),
                "error": r.error,
            }
        quant = self.calls.get(QUANT_MEMBER)
        est = ((quant.data if quant else None) or {}).get("estimate")
        return {
            "members": members,
            "estimate": est.get("probability") if isinstance(est, dict) else None,
            "draft": self.draft,
            "critique": self.critique,
            "repairs": self.repairs,
        }


def _dump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str, separators=(",", ":"))
