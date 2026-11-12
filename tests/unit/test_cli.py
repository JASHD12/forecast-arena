from pathlib import Path

from click.testing import CliRunner
from factories import B, forecast, question

from arena.cli import main
from arena.ledger import Ledger, layout

GROUPS = ["questions", "forecast", "resolve", "score", "site", "ledger", "daily", "report"]


def run(*args: str):
    return CliRunner().invoke(main, list(args), catch_exceptions=False)


def test_help_lists_all_groups() -> None:
    res = run("--help")
    assert res.exit_code == 0
    for g in GROUPS:
        assert g in res.output
    for opt in ("--date", "--dry-run", "--ledger-dir"):
        assert opt in res.output


def test_seal_list_and_verify(tmp_path: Path) -> None:
    led = Ledger(tmp_path)
    q = question("A", B)
    led.append(layout.questions_path(B), [q])
    led.append(layout.forecasts_path(B), [forecast(q)])
    common = ["--ledger-dir", str(tmp_path), "--date", B.isoformat()]
    assert run(*common, "--dry-run", "ledger", "seal-batch").exit_code == 0
    assert not led.exists(layout.batch_seal_path(B))
    assert run(*common, "ledger", "seal-batch").exit_code == 0
    assert led.exists(layout.batch_seal_path(B))
    listed = run(*common, "questions", "list")
    assert q.question_id in listed.output
    ok = run(*common, "ledger", "verify")
    assert ok.exit_code == 0 and "PASS" in ok.output
    led.abspath(layout.forecasts_path(B)).write_text("")
    bad = run(*common, "ledger", "verify")
    assert bad.exit_code == 1 and "FAIL" in bad.output


def test_cv_report_on_an_empty_ledger() -> None:
    res = CliRunner().invoke(main, ["--ledger-dir", "/nonexistent-ledger", "report", "cv"])
    assert res.exit_code == 0 and "too early to tell" in res.output
