#!/usr/bin/env python3
"""Print the state of the backlog.

Reads TASKS.md and HUMAN_TODO.md from the repository root and prints, as KEY=VALUE lines:

  DONE                 tasks ticked [x]
  OPEN                 tasks still [ ]
  READY                open tasks whose deps are done and whose human needs are ticked
  BLOCKED              tasks marked [!]
  WAITING_ON_HUMAN     open tasks held up (directly or through a dependency) by an
                       unticked HUMAN_TODO item
  OPEN_AGENT_TASKS     open tasks the agent can finish without the human and without a
                       blocked task being unblocked. When this is 0 the agent stops.
  NEXT_TASK            the first ready task in file order
  NEEDS_HUMAN          human items that open tasks are waiting for
  WAIT_EXPIRED         blocked tasks whose WAIT(until=YYYY-MM-DD) date has passed

No third-party dependencies. Exit code is always 0 unless a file is missing or malformed.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASK_RE = re.compile(r"^- \[( |x|X|!)\] (T\d{3}[a-z]?) · (.*)$")
HUMAN_RE = re.compile(r"^- \[( |x|X)\] (H\d{2}) · (.*)$")
DEPS_RE = re.compile(r"deps:\s*([^;)]*)")
NEEDS_RE = re.compile(r"needs:\s*([^;)]*)")
WAIT_RE = re.compile(r"WAIT\(until=(\d{4}-\d{2}-\d{2})\)")
ID_RE = re.compile(r"[TH]\d{2,3}[a-z]?")


@dataclass
class Task:
    id: str
    state: str  # "open", "done", "blocked"
    title: str
    deps: list[str] = field(default_factory=list)
    needs: list[str] = field(default_factory=list)
    wait_until: date | None = None


def parse_tasks(text: str) -> list[Task]:
    tasks: list[Task] = []
    for line in text.splitlines():
        m = TASK_RE.match(line)
        if not m:
            continue
        mark, tid, rest = m.groups()
        state = {" ": "open", "x": "done", "X": "done", "!": "blocked"}[mark]
        deps_m = DEPS_RE.search(rest)
        needs_m = NEEDS_RE.search(rest)
        wait_m = WAIT_RE.search(rest)
        tasks.append(
            Task(
                id=tid,
                state=state,
                title=rest.split(" (deps:")[0].strip(),
                deps=[d for d in ID_RE.findall(deps_m.group(1)) if d.startswith("T")] if deps_m else [],
                needs=[n for n in ID_RE.findall(needs_m.group(1)) if n.startswith("H")] if needs_m else [],
                wait_until=date.fromisoformat(wait_m.group(1)) if wait_m else None,
            )
        )
    return tasks


def parse_human_done(text: str) -> set[str]:
    done: set[str] = set()
    for line in text.splitlines():
        m = HUMAN_RE.match(line)
        if m and m.group(1) in ("x", "X"):
            done.add(m.group(2))
    return done


def main() -> int:
    tasks_path = ROOT / "TASKS.md"
    human_path = ROOT / "HUMAN_TODO.md"
    if not tasks_path.exists():
        print("ERROR=TASKS.md not found", file=sys.stderr)
        return 2
    tasks = parse_tasks(tasks_path.read_text(encoding="utf-8"))
    if not tasks:
        print("ERROR=no tasks parsed from TASKS.md (check the line format)", file=sys.stderr)
        return 2
    human_done = parse_human_done(human_path.read_text(encoding="utf-8")) if human_path.exists() else set()

    by_id = {t.id: t for t in tasks}
    if len(by_id) != len(tasks):
        seen: set[str] = set()
        dupes = sorted({t.id for t in tasks if t.id in seen or seen.add(t.id)})
        print(f"ERROR=duplicate task ids: {','.join(dupes)}", file=sys.stderr)
        return 2
    unknown = sorted({d for t in tasks for d in t.deps if d not in by_id})
    if unknown:
        print(f"ERROR=unknown dependency ids: {','.join(unknown)}", file=sys.stderr)
        return 2

    done = {t.id for t in tasks if t.state == "done"}

    def human_ok(t: Task) -> bool:
        return all(n in human_done for n in t.needs)

    # A task is agent-reachable if it is open, its human needs are met, and every
    # dependency is done or itself agent-reachable. Computed as a fixpoint.
    reachable: set[str] = set()
    changed = True
    while changed:
        changed = False
        for t in tasks:
            if t.id in reachable or t.state != "open" or not human_ok(t):
                continue
            if all(d in done or d in reachable for d in t.deps):
                reachable.add(t.id)
                changed = True

    # A task waits on the human if it is open and it, or something it depends on,
    # needs an unticked human item (and no blocked task is the cause).
    def waits_on_human(t: Task, seen: frozenset[str] = frozenset()) -> bool:
        if t.state != "open" or t.id in seen:
            return False
        if not human_ok(t):
            return True
        return any(
            waits_on_human(by_id[d], seen | {t.id}) for d in t.deps if d not in done
        )

    open_tasks = [t for t in tasks if t.state == "open"]
    ready = [t for t in open_tasks if human_ok(t) and all(d in done for d in t.deps)]
    blocked = [t for t in tasks if t.state == "blocked"]
    waiting = [t for t in open_tasks if waits_on_human(t)]
    needs_human = sorted({n for t in open_tasks for n in t.needs if n not in human_done})
    today = datetime.now(timezone.utc).date()
    wait_expired = [t.id for t in blocked if t.wait_until and t.wait_until <= today]

    print(f"DONE={len(done)}")
    print(f"OPEN={len(open_tasks)}")
    print(f"READY={len(ready)}")
    print(f"BLOCKED={len(blocked)}")
    print(f"WAITING_ON_HUMAN={len(waiting)}")
    print(f"OPEN_AGENT_TASKS={len(reachable)}")
    print(f"NEXT_TASK={ready[0].id + ' · ' + ready[0].title if ready else 'none'}")
    print(f"NEEDS_HUMAN={','.join(needs_human) if needs_human else 'none'}")
    print(f"WAIT_EXPIRED={','.join(wait_expired) if wait_expired else 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
