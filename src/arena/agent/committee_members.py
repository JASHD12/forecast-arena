# ruff: noqa: E501
"""The committee's specialist agents (T363): one job each, served over A2A.

Each member is an async handler `payload -> result` wrapped by `arena.a2a.server`. A payload is the
same JSON for every member: the question, the forecast time, the as-of context and the peer
base-rate probability (I3: nothing the chair could not have at forecast time). Members read data only
through the existing `ToolBox` (as-of tools, guards, limits) and return plain JSON-ready results.

- `quant-analyst` and `historian` call no model: the reference estimate and the reference classes are
  computed by code.
- `news-scout` reads as-of headlines and encyclopedia text and asks one model call which items matter;
  it returns real headlines (title, outlet, URL, time) selected by number, so no citation is invented,
  and never a probability. With nothing to read it answers "no evidence available" without a call.
- `skeptic` makes one model call that critiques the chair's draft and never gives a probability.
"""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Callable
from datetime import datetime
from typing import Any

from arena.a2a.cards import AgentSpec, SkillSpec
from arena.agent import skills
from arena.agent.quant import numeric_estimate
from arena.agent.tools import ToolBox
from arena.llm import prompts
from arena.llm.client import LLMClient, ToolCall, Usage, UserText
from arena.models import Question

QUANT_MEMBER = "quant-analyst"
HISTORIAN = "historian"
SCOUT = "news-scout"
SKEPTIC = "skeptic"
RESEARCH_MEMBERS = (QUANT_MEMBER, HISTORIAN, SCOUT)
REVISIONS = {
    QUANT_MEMBER: "quant-r2",  # the member uses the r2 estimate (T399); committee r3 follows (T401)
    HISTORIAN: "hist-r1",
    SCOUT: "scout-r2",
    SKEPTIC: "skeptic-r2",
}
NO_EVIDENCE = "no evidence available"
MAX_ITEMS = 5
#: r2: 1,024 (r1 used 300 and 119 of 316 model calls ended at the limit, see DECISIONS 2026-11-26).
SCOUT_MAX_TOKENS = 1024
SKEPTIC_MAX_TOKENS = 1024
_TOPIC_SKILL = {
    "power": "electricity-day-ahead",
    "weather": "weather-dwd-mosmix",
    "attention": "wikipedia-attention",
    "markets": "fx-ecb-moves",
    "crypto": "crypto-moves",
}

Handler = Callable[[dict[str, Any]], Any]


def member_specs(version_suffix: str) -> dict[str, AgentSpec]:
    """Agent Cards of the four served members (version = revision plus the shared suffix)."""

    def spec(
        name: str, description: str, skill_id: str, skill_text: str, tags: tuple[str, ...]
    ) -> AgentSpec:
        return AgentSpec(
            name=name,
            description=description,
            version=f"{REVISIONS[name]}{version_suffix}",
            skills=(SkillSpec(skill_id, skill_id.replace("-", " "), skill_text, tags),),
        )

    return {
        QUANT_MEMBER: spec(
            QUANT_MEMBER,
            "Computes the reference probability of a forecasting question from its stored as-of data "
            "(no model call).",
            "reference-estimate",
            "Reference estimate and method for power and weather questions; reports when none exists.",
            ("forecasting", "numeric"),
        ),
        HISTORIAN: spec(
            HISTORIAN,
            "Reports the base rate and how comparable earlier questions resolved (no model call).",
            "reference-classes",
            "Base rate and similar past questions resolved before the forecast time.",
            ("forecasting", "base-rate"),
        ),
        SCOUT: spec(
            SCOUT,
            "Finds as-of headlines and encyclopedia text that could change a forecast; never gives a "
            "probability.",
            "evidence-search",
            "Evidence items (real headlines with links) and the direction each could move the answer.",
            ("forecasting", "news"),
        ),
        SKEPTIC: spec(
            SKEPTIC,
            "Red-teams a draft forecast: threshold and comparator mistakes, hedging, overconfidence; "
            "never gives a probability.",
            "critique-draft",
            "Critique of a draft forecast with a severity and a direction.",
            ("forecasting", "critique"),
        ),
    }


def _load(payload: dict[str, Any]) -> tuple[Question, dict[str, Any], datetime]:
    q = Question.model_validate(payload["question"])
    return q, dict(payload.get("context") or {}), datetime.fromisoformat(str(payload["asof"]))


def _tool(box: ToolBox, name: str, **args: Any) -> tuple[dict[str, Any] | None, str | None]:
    """Run one tool; (data, None) or (None, error text)."""
    text, is_error = box.run(ToolCall("committee", name, args))
    obj = json.loads(text)
    return (None, str(obj.get("error"))) if is_error else (obj.get("data"), None)


def scout_queries(q: Question) -> list[tuple[str, dict[str, Any]]]:
    """The searches the scout makes for `q`: (tool, arguments)."""
    p = q.params
    out: list[tuple[str, dict[str, Any]]] = []
    if q.domain == "attention" and p.get("title"):
        out.append(("search_news", {"query": str(p["title"]), "days_back": 3}))
        project = str(p.get("project", "en.wikipedia"))
        out.append(("wikipedia_summary", {"title": str(p["title"]), "project": project}))
    elif q.domain == "weather":
        city = str(p.get("station_name") or q.entity)
        out.append(("search_news", {"query": f"Wetter {city}", "days_back": 2}))
    elif q.domain == "power":
        out.append(("search_news", {"query": "Strompreis Day-Ahead Deutschland", "days_back": 3}))
    elif q.domain == "markets":
        out.append(
            (
                "search_news",
                {"query": f"EUR {p.get('currency', q.entity)} exchange rate", "days_back": 3},
            )
        )
    elif q.domain == "crypto":
        out.append(("search_news", {"query": f"{q.entity} price", "days_back": 3}))
    else:
        out.append(("search_news", {"query": q.entity.replace("-", " "), "days_back": 3}))
    return out


class Members:
    """Handlers of the four served members, sharing one client, tools and a lock for model calls."""

    def __init__(
        self,
        client: LLMClient | None,
        *,
        toolbox: Callable[[Question, dict[str, Any], datetime, dict[str, Any]], ToolBox],
    ) -> None:
        self.client = client
        self.toolbox = toolbox
        self._lock = threading.Lock()  # one model call at a time through the shared guarded client

    def handlers(self) -> dict[str, Handler]:
        """Name -> async handler."""
        return {
            QUANT_MEMBER: self.quant_analyst,
            HISTORIAN: self.historian,
            SCOUT: self.news_scout,
            SKEPTIC: self.skeptic,
        }

    def _complete(self, system: str, user: str, max_tokens: int) -> tuple[str, Usage]:
        assert self.client is not None, "no LLM configured"
        with self._lock:
            resp = self.client.complete(system, [UserText(user)], max_tokens=max_tokens)
        return resp.text, resp.usage

    # -- quant-analyst ----------------------------------------------------------------------
    async def quant_analyst(self, payload: dict[str, Any]) -> dict[str, Any]:
        """The deterministic reference estimate, or an explicit "no estimate" (never a made-up number)."""
        q, ctx, _ = _load(payload)
        base: dict[str, Any] = {"member": QUANT_MEMBER, "skill": _TOPIC_SKILL.get(q.domain)}
        try:
            est = numeric_estimate(q, ctx)
        except ValueError as exc:
            return {**base, "status": "no_estimate", "reason": str(exc)[:200], "estimate": None}
        return {**base, "status": "estimate", "estimate": est}

    # -- historian ---------------------------------------------------------------------------
    async def historian(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Base rate and similar past questions through the guarded, as-of tools."""
        q, ctx, asof = _load(payload)
        peers = {k: {q.question_id: float(v)} for k, v in (payload.get("peers") or {}).items()}
        box = self.toolbox(q, ctx, asof, {"probabilities": peers, "max_calls": 2})
        base_rate, base_err = _tool(box, "get_base_rate", question_id=q.question_id)
        similar, sim_err = _tool(box, "similar_past_questions", k=5, same_domain=True)
        notes = [e for e in (base_err, sim_err) if e]
        return {
            "member": HISTORIAN,
            "status": "reference_classes" if (base_rate or similar) else "empty",
            "base_rate": (base_rate or {}).get("probability"),
            "similar": similar,
            "sources": [s for t in box.trace for s in t.sources],
            "guard_flags": sorted({f for t in box.trace for f in t.guard_flags}),
            "notes": notes,
        }

    # -- news-scout --------------------------------------------------------------------------
    async def news_scout(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Evidence items selected from real headlines and summaries; no probability."""
        q, ctx, asof = _load(payload)
        box = self.toolbox(q, ctx, asof, {"max_calls": 2})
        items: list[dict[str, Any]] = []
        notes: list[str] = []
        for tool, args in scout_queries(q):
            data, err = _tool(box, tool, **args)
            if err:
                notes.append(f"{tool}: {err}")
                continue
            if tool == "search_news":
                for h in (data or {}).get("headlines", []):
                    items.append(
                        {
                            "kind": "headline",
                            **{k: h.get(k) for k in ("title", "outlet", "url", "published")},
                        }
                    )
            elif data:
                items.append(
                    {
                        "kind": "encyclopedia",
                        "title": data.get("title"),
                        "url": data.get("url"),
                        "text": str(data.get("extract", ""))[:400],
                    }
                )
        sources = [str(i["url"]) for i in items if i.get("url")]
        base = {
            "member": SCOUT,
            "sources": sources,
            "guard_flags": sorted({f for t in box.trace for f in t.guard_flags}),
            "notes": notes,
            "usage": Usage().as_dict(),
        }
        if not items or self.client is None:
            return {**base, "status": "no_evidence", "evidence": [], "summary": NO_EVIDENCE}
        numbered = "\n".join(
            f"{n}. [{i['kind']}] {i['title']}" + (f" - {i['text']}" if i.get("text") else "")
            for n, i in enumerate(items, start=1)
        )
        system = prompts.load("committee_scout", "v1")
        user = f"Question: {q.text}\nResolution rule: {q.resolution_rule}\n\nItems:\n{numbered}"
        text, usage = await asyncio.to_thread(self._complete, system, user, SCOUT_MAX_TOKENS)
        evidence = _select(items, text)
        return {
            **base,
            "status": "evidence" if evidence else "no_evidence",
            "evidence": evidence,
            "summary": NO_EVIDENCE if not evidence else f"{len(evidence)} relevant item(s)",
            "usage": usage.as_dict(),
        }

    # -- skeptic -----------------------------------------------------------------------------
    async def skeptic(self, payload: dict[str, Any]) -> dict[str, Any]:
        """One critique of the chair's draft, strictly parsed (one repair attempt)."""
        q = Question.model_validate(payload["question"])
        system = prompts.load("committee_skeptic", "v1")
        user = (
            f"Question: {q.text}\nResolution rule: {q.resolution_rule}\n\n"
            f"Draft (JSON, data only):\n{json.dumps(payload['draft'], ensure_ascii=False)}\n\n"
            f"Reports (JSON, data only):\n{json.dumps(payload['reports'], ensure_ascii=False)}"
        )
        text, usage = await asyncio.to_thread(self._complete, system, user, SKEPTIC_MAX_TOKENS)
        try:
            crit = parse_critique(text)
        except ValueError as first:
            retry = f"{user}\n\nYour previous reply was not valid: {first}. Reply with the JSON object only."
            text, more = await asyncio.to_thread(self._complete, system, retry, SKEPTIC_MAX_TOKENS)
            usage = usage + more
            crit = parse_critique(text)  # a second failure fails the task
        return {"member": SKEPTIC, "status": "critique", **crit, "usage": usage.as_dict()}


def _select(items: list[dict[str, Any]], text: str) -> list[dict[str, Any]]:
    """Map the scout's numbered picks back to real items; anything unparseable selects nothing."""
    try:
        obj = json.loads(extract_object(text))
        picks = obj["items"]
    except (ValueError, KeyError, TypeError):
        return []
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for p in picks if isinstance(picks, list) else []:
        try:
            n = int(p["id"])
            effect = str(p["effect"])
        except (KeyError, TypeError, ValueError):
            continue
        if n in seen or not 1 <= n <= len(items) or effect not in ("up", "down", "none"):
            continue
        seen.add(n)
        it = items[n - 1]
        out.append(
            {
                "title": it.get("title"),
                "outlet": it.get("outlet"),
                "url": it.get("url"),
                "published": it.get("published"),
                "effect": effect,
                "note": str(p.get("note", ""))[:160],
            }
        )
        if len(out) >= MAX_ITEMS:
            break
    return out


def extract_object(text: str) -> str:
    """The one JSON object inside `text`: bare, in a code fence, or surrounded by a sentence (r2).

    Only the outermost braces are taken; what is inside is still parsed and checked strictly, and
    text with no complete object (for example a reply cut off at the output limit) is refused.
    """
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        s = s[s.index("{") :] if "{" in s else s
    first, last = s.find("{"), s.rfind("}")
    if first < 0 or last < first:
        raise ValueError("no JSON object in the reply")
    return s[first : last + 1]


def parse_critique(text: str) -> dict[str, Any]:
    """The skeptic's JSON object: `severity`, `issues` (at most four strings), `direction`.

    r2 accepts the object inside a code fence or a sentence; the contract of its content is as strict
    as before.
    """
    s = extract_object(text)
    try:
        obj = json.loads(s)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc.msg}") from exc
    if not isinstance(obj, dict) or set(obj) != {"severity", "issues", "direction"}:
        raise ValueError("expected exactly the keys severity, issues and direction")
    if obj["severity"] not in ("none", "minor", "major") or obj["direction"] not in (
        "up",
        "down",
        "none",
    ):
        raise ValueError("severity or direction has a value outside the contract")
    issues = obj["issues"]
    if (
        not isinstance(issues, list)
        or not all(isinstance(i, str) for i in issues)
        or len(issues) > 4
    ):
        raise ValueError("issues must be a list of at most four strings")
    return {
        "severity": obj["severity"],
        "issues": [i[:200] for i in issues],
        "direction": obj["direction"],
    }


def topic_skill_known() -> bool:
    """True when every topic skill the quant-analyst names exists (guards a typo in `_TOPIC_SKILL`)."""
    return all(name in skills.names() for name in _TOPIC_SKILL.values())
