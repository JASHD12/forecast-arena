import os
from pathlib import Path

import pytest
from factories import B, forecast, question, resolution, skip

from arena.ledger import Ledger, LedgerError, layout


@pytest.fixture
def led(tmp_path: Path) -> Ledger:
    return Ledger(tmp_path)


def test_append_never_changes_earlier_bytes(led: Ledger) -> None:
    qp = layout.questions_path(B)
    led.append(qp, [question("A")])
    first = led.read_bytes(qp)
    led.append(qp, [question("B"), question("C")])
    second = led.read_bytes(qp)
    assert second.startswith(first) and len(second) > len(first)
    assert [q.entity for q in led.read(qp)] == ["A", "B", "C"]


def test_mixed_kinds_per_family(led: Ledger) -> None:
    q = question()
    led.append(layout.forecasts_path(B), [forecast(q), skip(q)])
    led.append(layout.resolutions_path(B), [resolution(q)])
    with pytest.raises(LedgerError, match="accepts only"):
        led.append(layout.questions_path(B), [forecast(q, "ml")])


def test_duplicates_refused_within_and_across_files(led: Ledger) -> None:
    q = question()
    led.append(layout.questions_path(B), [q])
    with pytest.raises(LedgerError, match="duplicate"):
        led.append(layout.questions_path(B), [q])
    with pytest.raises(LedgerError, match="duplicate"):
        led.append("questions/2026/11/13.jsonl", [q])
    with pytest.raises(LedgerError, match="duplicate"):
        led.append(layout.forecasts_path(B), [forecast(q), skip(q, "base_rate")])
    assert led.read(layout.forecasts_path(B)) == []


def test_crash_before_rename_leaves_no_partial_file(
    led: Ledger, monkeypatch: pytest.MonkeyPatch
) -> None:
    qp = layout.questions_path(B)
    led.append(qp, [question("A")])
    before = led.read_bytes(qp)

    def boom(*_a, **_k):
        raise OSError("simulated crash")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        led.append(qp, [question("B")])
    monkeypatch.undo()
    assert led.read_bytes(qp) == before
    assert led.list_files() == [qp], "no temp file may be left behind"


def test_corrupt_or_non_canonical_lines_rejected_on_read(led: Ledger) -> None:
    qp = layout.questions_path(B)
    led.append(qp, [question("A")])
    path = led.abspath(qp)
    path.write_text(path.read_text().replace('{"base', '{ "base'))
    with pytest.raises(LedgerError, match="canonical"):
        led.read(qp)
    path.write_text("not json\n")
    with pytest.raises(LedgerError, match="invalid record"):
        led.read(qp)


def test_write_json_never_overwrites(led: Ledger) -> None:
    q = question()
    led.write_json("meta/x.json", q)
    with pytest.raises(LedgerError, match="already exists"):
        led.write_json("meta/x.json", q)


def test_paths_cannot_escape_root(led: Ledger) -> None:
    for bad in ("../x.jsonl", "/etc/passwd", ""):
        with pytest.raises(LedgerError):
            led.abspath(bad)
    with pytest.raises(LedgerError, match="not a record file"):
        led.append("notes.txt", [question()])
