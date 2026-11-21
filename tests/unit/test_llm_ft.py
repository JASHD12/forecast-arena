"""T271: the fine-tuned live forecaster (fake scorer), its pin, download and wiring."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from factories import question

from arena.forecasters.llm import LLMContext
from arena.forecasters.llm_ft import LLMLocalFT
from arena.lab import artefacts as art
from arena.lab import ft_runtime as rt
from arena.llm import prompts
from arena.llm.client import LLMError
from arena.models import Forecast, Skip

ASOF = datetime(2026, 11, 22, 7, 0, tzinfo=UTC)


def _pin(sha: str = "ab" * 32, url: str = "file:///x", filename: str = "m.gguf") -> art.FtArtefact:
    return art.FtArtefact(
        name="qwen2.5-1.5b-qlora-r1", url=url, sha256=sha, filename=filename, platt=(0.8, -0.1),
        yes_id=14004, no_id=8996, base_model="Qwen/Qwen2.5-1.5B-Instruct", base_revision="989aa79",
        adapter_sha256="cd" * 32, run_id="colab-1", prereg_sha256="ef" * 32,
    )  # fmt: skip


class FakeScorer:
    model = "qwen2.5-1.5b-qlora-r1"

    def __init__(self, margin: float | Exception = 1.2) -> None:
        self.value, self.calls = margin, []

    def margin(self, system: str, user: str) -> float:
        self.calls.append((system, user))
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


def test_chatml_matches_the_qwen_chat_template_text() -> None:
    text = rt.chatml("SYS text", "USER text\nline2")
    assert text == (
        "<|im_start|>system\nSYS text<|im_end|>\n<|im_start|>user\nUSER text\nline2<|im_end|>\n"
        "<|im_start|>assistant\n"
    )


def test_calibration_is_clipped_and_matches_the_training_code() -> None:
    assert rt.calibrated(0.0, (1.0, 0.0)) == pytest.approx(0.5)
    assert rt.calibrated(50, (1.0, 0.0)) == 0.99 and rt.calibrated(-50, (1.0, 0.0)) == 0.01
    torch = pytest.importorskip("torch")  # noqa: F841
    from arena.lab.finetune import train as tr

    for m in (-3.0, -0.5, 0.0, 2.2):
        assert rt.calibrated(m, (0.7, 0.2)) == pytest.approx(tr.apply_platt(m, 0.7, 0.2))


def test_forecast_uses_the_llm_context_prompt_and_the_platt_map() -> None:
    scorer = FakeScorer(1.2)
    f = LLMLocalFT(scorer, _pin())
    out = f.forecast(question(), {"x": 1}, ASOF)
    assert isinstance(out, Forecast) and out.forecaster_id == "llm_local_ft"
    assert out.probability == pytest.approx(rt.calibrated(1.2, (0.8, -0.1)))
    system, user = scorer.calls[0]
    assert system == prompts.load("system", f.prompt_version)
    assert user == LLMContext(None).user_prompt(question(), {"x": 1}, ASOF)
    assert out.meta["margin"] == 1.2 and out.meta["experimental"] is True
    assert out.meta["artefact_sha256"] == "ab" * 32
    assert out.rationale is None
    assert (
        "gguf-abababab" in out.forecaster_version
        and "platt-0.8000--0.1000" in out.forecaster_version
    )


def test_the_version_changes_with_the_artefact_and_the_calibration() -> None:
    a = LLMLocalFT(FakeScorer(), _pin()).version()
    assert a != LLMLocalFT(FakeScorer(), _pin(sha="12" * 32)).version()
    other = _pin()
    other = art.FtArtefact(**{**other.__dict__, "platt": (0.9, 0.0)})
    assert a != LLMLocalFT(FakeScorer(), other).version()
    assert LLMLocalFT(None, None).version().startswith("none|prompt-")


def test_skips_carry_their_reason_and_never_a_number() -> None:
    q = question()
    out = LLMLocalFT(None, None).forecast(q, {}, ASOF)
    assert isinstance(out, Skip) and out.reason_code == "model_missing"
    assert "not published" in out.detail
    err = LLMLocalFT(FakeScorer(LLMError("run time budget used up")), _pin()).forecast(q, {}, ASOF)
    assert isinstance(err, Skip) and err.reason_code == "error" and "budget" in err.detail
    f = LLMLocalFT(FakeScorer(), _pin())
    f.sample = set()  # nothing sampled today
    ns = f.forecast(q, {}, ASOF)
    assert isinstance(ns, Skip) and ns.reason_code == "not_sampled"


def test_pin_file_round_trip_and_missing_pin(tmp_path) -> None:
    assert art.load_artefact(tmp_path / "none.json") is None
    d = {**_pin().__dict__, "platt": [0.8, -0.1]}
    p = tmp_path / "pin.json"
    p.write_text(json.dumps(d))
    assert art.load_artefact(p) == _pin()


def test_fetch_verifies_the_hash_and_reuses_a_good_cache(tmp_path) -> None:
    src = tmp_path / "src.bin"
    src.write_bytes(b"gguf-bytes" * 1000)
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    good = _pin(sha=sha, url=src.as_uri())
    got = art.fetch(good, tmp_path / "cache")
    assert got.read_bytes() == src.read_bytes()
    src.unlink()  # a valid cached file needs no second download
    assert art.fetch(good, tmp_path / "cache") == got
    bad = _pin(sha="00" * 32, url=got.as_uri(), filename="other.gguf")
    with pytest.raises(ValueError, match="pinned"):
        art.fetch(bad, tmp_path / "cache")
    assert not (tmp_path / "cache" / "other.gguf").exists()
    assert not list((tmp_path / "cache").glob("*.part"))


def test_the_committed_pin_is_either_absent_or_complete() -> None:
    p = Path(__file__).resolve().parents[2] / "lab" / "artefacts" / "llm_local_ft.json"
    if p.is_file():
        pin = art.load_artefact(p)
        assert (
            pin is not None and len(pin.sha256) == 64 and pin.url.startswith("https://github.com/")
        )


def test_wiring_registers_the_forecaster_only_when_switched_on(tmp_path, monkeypatch) -> None:
    from factories import B

    from arena.config import Settings
    from arena.ledger import Ledger
    from arena.ops.wiring import build_forecasters

    monkeypatch.setattr(art, "DEFAULT_PATH", tmp_path / "no-pin.json")
    monkeypatch.setattr(art, "load_artefact", lambda path=tmp_path / "no-pin.json": None)
    off, _ = build_forecasters(Ledger(tmp_path), [], Settings.from_env({}), B, dry_run=True)
    assert "llm_local_ft" not in [f.forecaster_id for f in off]
    on, _ = build_forecasters(
        Ledger(tmp_path), [], Settings.from_env({"ARENA_LLM_LOCAL_FT": "1"}), B, dry_run=True
    )
    (ft,) = [f for f in on if f.forecaster_id == "llm_local_ft"]
    out = ft.forecast(question(), {}, ASOF)
    assert isinstance(out, Skip) and out.reason_code == "model_missing"
    ids = [f.forecaster_id for f in on]
    assert ids.index("llm_local_ft") > ids.index("agent")
