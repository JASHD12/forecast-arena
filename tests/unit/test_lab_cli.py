"""The `arena lab` commands survive the split of lab_cmds.py (T383), and cards regenerate (CLI)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from arena.cli import lab, main

ROOT = Path(__file__).parents[2]
SNAP = json.loads((ROOT / "tests/fixtures/lab_commands_snapshot.json").read_text("utf-8"))


def test_the_command_set_is_unchanged_by_the_split() -> None:
    assert sorted(lab.commands) == SNAP["lab_commands"]
    groups = {k: sorted(v.commands) for k, v in lab.commands.items() if hasattr(v, "commands")}
    assert groups == SNAP["groups"]


@pytest.mark.parametrize("name", SNAP["lab_commands"])
def test_every_lab_command_answers_help(name: str) -> None:
    res = CliRunner().invoke(main, ["lab", name, "--help"])
    assert res.exit_code == 0 and "Usage" in res.output


def test_lab_card_regenerates_every_committed_card_byte_for_byte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    results = sorted((ROOT / "evals/results").glob("lab-*.json"))
    assert results
    checked = 0
    for res_path in results:
        card = json.loads(res_path.read_text("utf-8")).get("card")
        if not card or not (ROOT / card).is_file():
            continue
        work = tmp_path / res_path.stem
        (work / "docs/lab").mkdir(parents=True)
        shutil.copy(res_path, work / res_path.name)
        monkeypatch.chdir(work)
        out = CliRunner().invoke(main, ["lab", "card", res_path.name])
        assert out.exit_code == 0, out.output
        assert (work / card).read_text("utf-8") == (ROOT / card).read_text("utf-8"), card
        checked += 1
    assert checked >= 10
