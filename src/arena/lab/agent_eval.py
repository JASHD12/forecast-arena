# ruff: noqa: E501
"""Lab results for the skills and committee evaluations (T355, T365), built from one eval file.

`arena eval run` already computes Brier, log score, cost and paired day-block intervals per pair. This
module only reshapes that file into a `LabResult` (so the Lab page, the cards and the budget check see
it) and applies the pre-registered decision rules (`lab/prereg/agent-skills.md`,
`lab/prereg/agent-committee.md`) to the numbers. Nothing is typed by hand (I5).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arena.lab.results import LabResult


@dataclass(frozen=True)
class Experiment:
    """One pre-registered comparison: `new` against `ref`, on the same items."""

    key: str
    title: str
    why: str
    prereg: str
    arms: tuple[str, ...]
    new: str
    ref: str
    cost_ratio_max: float
    rule_names: tuple[str, str]
    note: str
    own_arms: tuple[str, ...] = ()  # arms whose cost this result carries (none counted twice)
    extra_notes: bool = False  # first-try validity, repairs and skills loaded (the r2/r3 results)


EXPERIMENTS = {
    "agent-skills": Experiment(
        "agent-skills",
        "Forecasting skills for the tool-using agent",
        "Progressive disclosure of short, reviewed skill notes is how Anthropic and others "
        "package domain know-how for agents without growing every prompt; the question is "
        "whether it helps a forecaster. (anthropic-skills)",
        "lab/prereg/agent-skills.md",
        ("agent", "agent_quant", "agent_skills"),
        "agent_skills",
        "agent_quant",
        1.3,
        ("H-S1", "H-S2"),
        "agent_skills is agent_quant plus load_skill; agent is the live prompt with replay tools.",
        ("agent", "agent_quant", "agent_skills"),
    ),
    "agent-committee": Experiment(
        "agent-committee",
        "A committee of specialist agents over A2A against one agent with skills",
        "Multi-agent systems and the A2A protocol are how companies split a job between "
        "specialised agents; the question is whether the split beats one agent with the same "
        "tools. (a2a-protocol)",
        "lab/prereg/agent-committee.md",
        ("agent_skills", "agent_committee"),
        "agent_committee",
        "agent_skills",
        2.5,
        ("H-C1", "H-C2"),
        "The replay has no news backend and no retriever: the news scout answered 'no evidence "
        "available' and the historian gave the base rate only, so this tests a reduced committee.",
        ("agent_committee",),  # the agent_skills arm is counted in the agent-skills result
    ),
    "agent-committee-r2": Experiment(
        "agent-committee-r2",
        "The committee, version r2 (output budget and reply parsing fixed), against one agent with skills",
        "Multi-agent systems and the A2A protocol are how companies split a job between "
        "specialised agents; this is the same question as the first run after fixing the defect "
        "it exposed. (a2a-protocol)",
        "lab/prereg/agent-committee-r2.md",
        ("agent_skills", "agent_committee"),
        "agent_committee",
        "agent_skills",
        2.5,
        ("H-C1", "H-C2"),
        "r2 changes only the output budget and the parsing of the scout's and skeptic's replies "
        "(pre-registered before the run). The agent_skills arm is the one of run 45883972017, "
        "reused on the same golden file. The replay has no news backend and no retriever, so this "
        "still tests a reduced committee.",
        ("agent_committee",),
    ),
    "agent-quant-r2": Experiment(
        "agent-quant-r2",
        "agent_quant r2: a better reference estimate and a prompt that may move away from it",
        "Giving an LLM agent a numeric tool and a statistical reference is how companies make "
        "tool-using forecasters less hedgy; the question is whether the r2 estimate and prompt "
        "fix what r1 got wrong. (anthropic-tool-use)",
        "lab/prereg/agent-quant-r2.md",
        ("agent", "agent_quant"),
        "agent_quant",
        "agent",
        1.75,
        ("H-Q6", "H-Q7"),
        "agent_quant r2 uses the persistence estimate (`quant-r2`) and prompt `agent_system_v6`; "
        "agent is the live prompt with replay tools. The replayed ml probabilities were not "
        "passed to the arms (the workflow passes them only when agent_analyst is in the run; "
        "the agent never called get_ml_forecast in 588 stored traces).",
        ("agent", "agent_quant"),
        True,
    ),
    "agent-skills-r2": Experiment(
        "agent-skills-r2",
        "agent_skills r2: topic-only skills index and skill text matching the new estimate",
        "Progressive disclosure of short, reviewed skill notes is how Anthropic and others "
        "package domain know-how for agents without growing every prompt; this is the "
        "re-test after the cost and anchoring defects of the first version. (anthropic-skills)",
        "lab/prereg/agent-skills-r2.md",
        ("agent_quant", "agent_skills"),
        "agent_skills",
        "agent_quant",
        1.3,
        ("H-S1'", "H-S2'"),
        "agent_skills r2 is agent_quant r2 plus load_skill with a topic-only index (prompt "
        "`agent_system_v7`, skills revision 2). The replayed ml probabilities were not passed "
        "to the arms (see the agent_quant r2 result).",
        ("agent_skills",),  # agent and agent_quant are counted in the agent-quant-r2 result
        True,
    ),
    "agent-committee-r3": Experiment(
        "agent-committee-r3",
        "agent_committee r3: working repairs, topic guidance for the chair, a skeptic that sees the data",
        "Multi-agent systems and the A2A protocol are how companies split a job between "
        "specialised agents; this is the re-test after the defects found in r2. (a2a-protocol)",
        "lab/prereg/agent-committee-r3.md",
        ("agent_skills", "agent_committee"),
        "agent_committee",
        "agent_skills",
        2.5,
        ("H-C1''", "H-C2''"),
        "r3 carries the failed reply in the chair's repair, cites members in key_factors, gives "
        "the chair the topic skill text and the skeptic the stored data. The replay still has no "
        "news backend and no retriever (a reduced committee), and the replayed ml probabilities "
        "were not passed to the arms.",
        ("agent_committee",),
        True,
    ),
}


def merge_reference(res: dict[str, Any], ref: dict[str, Any], arm: str) -> dict[str, Any]:
    """`res` plus the arm `arm` taken from another run on the same golden file (nothing is re-run).

    The files must name the same golden file hash; the pairs of `res` with that arm are recomputed from
    the rows with the harness's own function, so they are on identical questions.
    """
    if res["golden_sha256"] != ref["golden_sha256"]:
        raise ValueError("the reference run used another golden file")
    if arm not in ref["metrics"] or arm in res["metrics"]:
        raise ValueError(f"arm {arm} must be in the reference run and not in this run")
    from arena.evals.run import paired

    out = dict(res)
    out["metrics"] = {**res["metrics"], arm: ref["metrics"][arm]}
    out["versions"] = {**res["versions"], arm: ref["versions"][arm]}
    out["rows"] = [*res["rows"], *[r for r in ref["rows"] if r["variant"] == arm]]
    out["reference_run"] = {"arm": arm, "run_id": ref["run_id"]}
    out["paired"] = paired(out["rows"], [*res["metrics"], arm])
    return out


def _per_question_cost(m: dict[str, Any]) -> float | None:
    cost, n = m.get("cost_usd"), m.get("n")
    return None if cost is None or not n else float(cost) / int(n)


def _r(x: float | None) -> float | None:
    return None if x is None else round(float(x), 4)


def _same_items(
    res: dict[str, Any], new: str, ref: str
) -> dict[str, float | int | str | None] | None:
    """Brier of `ref` on the questions `new` answered, when `new` answered fewer than `ref` (from the rows)."""
    got = {
        r["question_id"]
        for r in res.get("rows", [])
        if r["variant"] == new and r["probability"] is not None
    }
    mine = [
        r
        for r in res.get("rows", [])
        if r["variant"] == ref and r["probability"] is not None and r["question_id"] in got
    ]
    if not got or len(got) == res["metrics"][ref]["answered"] or not mine:
        return None
    b = sum((r["probability"] - r["outcome"]) ** 2 for r in mine) / len(mine)
    return {"n": len(mine), "brier": round(b, 4)}


def _pair(res: dict[str, Any], new: str, ref: str) -> dict[str, Any] | None:
    """Brier(new) - Brier(ref) with its interval, whichever way the harness stored the pair."""
    for p in res.get("paired", []):
        if (p["a"], p["b"]) == (new, ref):
            return {k: p[k] for k in ("diff", "lo", "hi", "n", "days")}
        if (p["a"], p["b"]) == (ref, new):
            return {
                "diff": -p["diff"],
                "lo": -p["hi"],
                "hi": -p["lo"],
                "n": p["n"],
                "days": p["days"],
            }
    return None


def _skills_loaded_notes(res: dict[str, Any], arms: tuple[str, ...]) -> list[str]:
    """H-S3: how often each skill was loaded, from the rows that carry `skills_loaded` (T400)."""
    out: list[str] = []
    for arm in arms:
        rows = [r for r in res.get("rows", []) if r["variant"] == arm and "skills_loaded" in r]
        if not rows:
            continue
        counts: dict[str, int] = {}
        for r in rows:
            for name in dict.fromkeys(r["skills_loaded"]):
                counts[name] = counts.get(name, 0) + 1
        loaded = ", ".join(f"{n} {c}/{len(rows)}" for n, c in sorted(counts.items())) or "none"
        out.append(f"{arm} skills loaded (questions that loaded each skill): {loaded}.")
    return out


def build(res: dict[str, Any], experiment: str, *, run_id: str | None = None) -> LabResult:
    """The `LabResult` of one experiment from an eval run file that contains its arms."""
    e = EXPERIMENTS[experiment]
    missing = [a for a in e.arms if a not in res["metrics"]]
    if missing:
        raise ValueError(f"the eval run has no arm {', '.join(missing)}")
    metrics: dict[str, dict[str, float | int | str | None]] = {}
    for arm in e.arms:
        m = res["metrics"][arm]
        c = _per_question_cost(m)
        metrics[f"{arm} / eval"] = {
            "n": m["answered"],
            "asked": m["n"],
            "brier": _r(m["brier"]),
            "log_score": _r(m["log_score"]),
            "ece": _r(m.get("ece")),
            "cost_usd_per_1k": None if c is None else round(1000 * c, 4),
            **(
                {"cost_usd_per_1k_answered": round(1000 * m["cost_usd_per_answered"], 4)}
                if m.get("cost_usd_per_answered") is not None
                else {}
            ),
        }
    topics = sorted({tp for a in e.arms for tp in res["metrics"][a].get("by_topic", {})})
    if len(topics) > 1:  # per-topic reporting, only when the run has more than one topic (T382)
        for arm in e.arms:
            for tp in topics:
                bt = res["metrics"][arm].get("by_topic", {}).get(tp)
                if bt:
                    metrics[f"{arm} / {tp}"] = {
                        "n": bt["answered"],
                        "asked": bt["n"],
                        "brier": _r(bt["brier"]),
                    }
        first = res["metrics"][e.arms[0]].get("by_topic", {})
        for tp in topics:
            if first.get(tp):
                metrics[f"base_rate / {tp}"] = {
                    "n": first[tp]["answered"],
                    "brier": _r(first[tp]["base_rate_brier_same_items"]),
                }
    newm = res["metrics"][e.new]
    metrics["base_rate / eval"] = {
        "n": newm["answered"],
        "brier": _r(newm["base_rate_brier_same_items"]),  # on the items the new arm answered
    }
    same = _same_items(res, e.new, e.ref)
    if same is not None:
        metrics[f"{e.ref} / same items as {e.new}"] = same
    pair = _pair(res, e.new, e.ref)
    paired = [] if pair is None else [{"a": e.new, "b": e.ref, "split": "eval", **pair}]
    for p in res.get("paired_by_topic", []):  # per-topic intervals (T382)
        if {p["a"], p["b"]} == {e.new, e.ref}:
            same_way = (p["a"], p["b"]) == (e.new, e.ref)
            paired.append(
                {
                    "a": e.new,
                    "b": e.ref,
                    "split": p["topic"],
                    "diff": p["diff"] if same_way else -p["diff"],
                    "lo": p["lo"] if same_way else -p["hi"],
                    "hi": p["hi"] if same_way else -p["lo"],
                    "n": p["n"],
                    "days": p["days"],
                }
            )
    cost = round(sum(res["metrics"][a].get("cost_usd") or 0.0 for a in e.own_arms), 6)
    notes = [
        *(
            [
                f"The {res['reference_run']['arm']} arm is reused from run {res['reference_run']['run_id']} (same golden file)."
            ]
            if "reference_run" in res
            else []
        ),
        f"Run {run_id or res['run_id']} of llm-eval.yml on {res['golden']} ({res['n_items']} questions), "
        "replay with the tools a replay can honour; labelled evaluation, never the live record.",
        e.note,
        "Skips per arm: "
        + "; ".join(f"{a} {res['metrics'][a]['skips'] or 'none'}" for a in e.arms)
        + ". Versions: "
        + "; ".join(f"{a} `{res['versions'][a]}`" for a in e.arms)
        + ".",
        *[
            f"{a} answered {res['metrics'][a]['answered']} of {res['metrics'][a]['n']} questions; its cost per "
            f"answered question is {res['metrics'][a]['cost_usd'] / res['metrics'][a]['answered'] * 1000:.2f} US$ per 1,000."
            for a in e.arms
            if res["metrics"][a]["answered"] < res["metrics"][a]["n"]
        ],
        *[
            f"{a}: {100 * res['metrics'][a]['json_valid_first_try']:.1f}% of answers were valid JSON "
            f"on the first try, repair rate {100 * res['metrics'][a]['repair_rate']:.1f}%."
            for a in e.arms
            if e.extra_notes and res["metrics"][a].get("json_valid_first_try") is not None
        ],
        *(_skills_loaded_notes(res, e.arms) if e.extra_notes else []),
        "Cost is the run's recorded tokens at the list price of the model, per arm; this result carries "
        f"the cost of {', '.join(e.own_arms)}.",
        "Brier of the arms that answered fewer questions is on their answered items only; paired "
        "differences use the questions both arms answered (the pair's n).",
    ]
    return LabResult(
        experiment=experiment,
        title=e.title,
        created_at=res["created_at"],
        why=e.why,
        prereg_sha256=hashlib.sha256(Path(e.prereg).read_bytes()).hexdigest(),
        dataset_sha256={"eval": res["golden_sha256"]},
        artefacts={"eval_run": run_id or res["run_id"]},
        metrics=metrics,
        paired=paired,
        cost_usd=cost,
        notes=notes,
        limits=[
            "Electricity only (the one topic a replay can reproduce), 90 questions from 15 days; "
            "the six questions of a day are correlated, so the intervals are day-block intervals.",
            "One run, one sample of the model's answers; a repeat could differ.",
            "Weather, Wikipedia, currencies and crypto are judged only on live days.",
        ],
    )


def verdicts(r: LabResult) -> list[dict[str, Any]]:
    """The pre-registered rules applied to the stored numbers: name, passed (or None), sentence."""
    e = EXPERIMENTS[r.experiment]
    new, ref = r.metrics[f"{e.new} / eval"], r.metrics[f"{e.ref} / eval"]
    out: list[dict[str, Any]] = []
    if r.experiment in ("agent-committee-r2", "agent-committee-r3"):  # H-C5: answered share
        asked, got = int(str(new.get("asked") or new["n"])), int(str(new["n"]))
        out.append(
            {
                "rule": "H-C5''" if r.experiment == "agent-committee-r3" else "H-C5",
                "passed": got >= 0.9 * asked,
                "text": f"the committee answered {got} of {asked} questions; the rule needs at least 90%.",
            }
        )
    p = r.paired[0] if r.paired else None
    if p is None:
        out.append(
            {"rule": e.rule_names[0], "passed": None, "text": "no paired interval (too few items)"}
        )
    else:
        ok = bool(p["hi"] < 0)
        out.append(
            {
                "rule": e.rule_names[0],
                "passed": ok,
                "text": f"Brier difference {p['diff']:+.4f} (95% day-block interval {p['lo']:+.4f} to {p['hi']:+.4f}); "
                f"the rule needs the whole interval below zero.",
            }
        )
    cn, cr = new.get("cost_usd_per_1k"), ref.get("cost_usd_per_1k")
    if cn is None or not cr:
        out.append({"rule": e.rule_names[1], "passed": None, "text": "cost not available"})
    else:
        ratio = float(cn) / float(cr)
        out.append(
            {
                "rule": e.rule_names[1],
                "passed": ratio <= e.cost_ratio_max,
                "text": f"cost per question {ratio:.2f} times the reference; the limit is {e.cost_ratio_max:g}.",
            }
        )
    return out


def decision_sentence(r: LabResult) -> str:
    """One generated sentence: what the pre-registered rule says to do (no figures)."""
    v = verdicts(r)
    if all(x["passed"] for x in v):
        return "Both pre-registered conditions hold; the next step is a dry run in an unsealed window, nothing is live yet."
    if any(x["passed"] is None for x in v):
        return "The pre-registered rule cannot be applied to this run; nothing changes."
    return "The pre-registered rule is not met, so the forecaster stays off and the result is published as it is."
