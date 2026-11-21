"""T244: the fine-tuning code path runs on CPU with a tiny random Qwen2 model (no download)."""

import pytest

torch = pytest.importorskip("torch")
transformers = pytest.importorskip("transformers")

from arena.lab.dataset import Row  # noqa: E402
from arena.lab.finetune import format as fmt  # noqa: E402
from arena.lab.finetune import train as tr  # noqa: E402


class CharTokenizer:
    """Char-level stand-in: YES and NO are one token each, everything else one token per char."""

    pad_token_id = 0

    def apply_chat_template(self, messages, **kw):
        body = "\n".join(m["content"] for m in messages)
        return f"<s>{body}\n<a>" if kw.get("add_generation_prompt") else body

    def encode(self, text, **kw):
        if text == "YES":
            return [1]
        if text == "NO":
            return [2]
        return [10 + (ord(c) % 200) for c in text]


def _rows(n: int = 48) -> list[Row]:
    out = []
    for i in range(n):
        yes = i % 2 == 0
        user = ("signal AAAA " if yes else "signal BBBB ") + "x" * (i % 5)
        out.append(Row(f"q{i}", "power", "t", "2026-01-01", "2026-01-01T05:30:00+00:00", "train",
                       "system", user, int(yes), None))  # fmt: skip
    return out


def _tiny_model():
    cfg = transformers.Qwen2Config(
        vocab_size=256, hidden_size=32, intermediate_size=64, num_hidden_layers=2,
        num_attention_heads=4, num_key_value_heads=2, max_position_embeddings=256,
    )  # fmt: skip
    torch.manual_seed(0)
    return transformers.Qwen2ForCausalLM(cfg)


def test_answer_tokens_must_be_single_and_distinct() -> None:
    assert fmt.answer_token_ids(CharTokenizer()) == (1, 2)

    class Bad(CharTokenizer):
        def encode(self, text, **kw):
            return [5, 6]

    with pytest.raises(ValueError):
        fmt.answer_token_ids(Bad())


def test_long_rows_are_dropped_not_cut() -> None:
    enc, dropped = fmt.encode_rows(CharTokenizer(), _rows(10), max_len=20)
    assert dropped + len(enc) == 10 and dropped > 0
    assert all(len(e.ids) <= 20 for e in enc)
    assert fmt.encode_rows(CharTokenizer(), _rows(10), max_len=500)[1] == 0


def test_collate_left_pads_and_counts_positions_from_the_first_token() -> None:
    enc, _ = fmt.encode_rows(CharTokenizer(), _rows(4), max_len=500)
    b = tr.collate(enc, 0, torch.device("cpu"))
    assert b["input_ids"].shape == b["attention_mask"].shape == b["position_ids"].shape
    for i, e in enumerate(enc):
        n = len(e.ids)
        assert b["attention_mask"][i].sum() == n
        assert b["position_ids"][i, -n:].tolist() == list(range(n))
        assert b["input_ids"][i, -n:].tolist() == e.ids


def test_training_lowers_the_loss_and_scores_are_calibratable() -> None:
    tok = CharTokenizer()
    yes_id, no_id = fmt.answer_token_ids(tok)
    enc, _ = fmt.encode_rows(tok, _rows(48), max_len=200)
    model = _tiny_model()
    cfg = tr.TrainConfig(lr=3e-3, epochs=6, batch_size=8, grad_accum=1, log_every=1, seed=0)
    kw = {"pad_id": 0, "yes_id": yes_id, "no_id": no_id, "device": torch.device("cpu")}
    log = tr.train(model, enc, cfg, **kw)
    assert log[-1]["loss"] < 0.5 * log[0]["loss"]
    m = tr.margins(model, enc, **kw)
    assert len(m) == len(enc)
    p = [tr.sigmoid(v) for v in m]
    assert tr.brier(p, [e.label for e in enc]) < 0.2
    # order independence: scoring rows one by one gives the same margins (padding does not leak)
    solo = [tr.margins(model, [e], **kw)[0] for e in enc[:5]]
    assert solo == pytest.approx(m[:5], abs=1e-4)
    a, b = tr.fit_platt(m, [e.label for e in enc])
    assert 0.01 <= tr.apply_platt(m[0], a, b) <= 0.99


def test_training_is_deterministic() -> None:
    tok = CharTokenizer()
    yes_id, no_id = fmt.answer_token_ids(tok)
    enc, _ = fmt.encode_rows(tok, _rows(16), max_len=200)
    cfg = tr.TrainConfig(lr=1e-3, epochs=1, batch_size=4, grad_accum=2, log_every=1)
    kw = {"pad_id": 0, "yes_id": yes_id, "no_id": no_id, "device": torch.device("cpu")}
    a = tr.train(_tiny_model(), enc, cfg, **kw)
    b = tr.train(_tiny_model(), enc, cfg, **kw)
    assert [r["loss"] for r in a] == [r["loss"] for r in b]


def test_platt_needs_both_outcomes() -> None:
    with pytest.raises(ValueError):
        tr.fit_platt([0.1, 0.2], [1, 1])


def test_lora_adds_few_trainable_parameters_and_merges_without_changing_scores() -> None:
    pytest.importorskip("peft")
    from arena.lab.finetune.load import add_lora

    tok = CharTokenizer()
    yes_id, no_id = fmt.answer_token_ids(tok)
    enc, _ = fmt.encode_rows(tok, _rows(8), max_len=200)
    kw = {"pad_id": 0, "yes_id": yes_id, "no_id": no_id, "device": torch.device("cpu")}
    model = add_lora(_tiny_model(), r=4, alpha=8)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    assert 0 < trainable < 0.2 * total
    cfg = tr.TrainConfig(lr=3e-3, epochs=2, batch_size=4, grad_accum=1)
    tr.train(model, enc, cfg, **kw)
    before = tr.margins(model, enc, **kw)
    merged = model.merge_and_unload()
    after = tr.margins(merged, enc, **kw)
    assert before == pytest.approx(after, abs=1e-3)


def test_run_variant_writes_scores_log_and_adapter(tmp_path) -> None:
    pytest.importorskip("peft")
    from arena.lab.finetune.load import add_lora
    from arena.lab.finetune.run import SCORED, Spec, run_variant

    rows = {
        "train": _rows(40),
        "val": _rows(12),
        "test_oct": _rows(8),
        "test_nov": _rows(6),
    }
    cfg = tr.TrainConfig(lr=3e-3, epochs=3, batch_size=4, grad_accum=1, log_every=1)
    out = run_variant(
        Spec("tiny", "random"),
        rows,
        CharTokenizer(),
        _tiny_model,
        lambda m: add_lora(m, r=4, alpha=8),
        tmp_path,
        cfg,
        device=torch.device("cpu"),
        train_rows=24,
        max_len=200,
    )
    assert out["rows"]["train"] == 24 and out["dropped_too_long"]["val"] == 0
    assert out["train_loss_last"] < out["train_loss_first"]
    lines = (tmp_path / "scores_tiny.jsonl").read_text().splitlines()
    assert len(lines) == 2 * (12 + 8 + 6)  # base and tuned, three scored splits
    assert {__import__("json").loads(x)["split"] for x in lines} == set(SCORED)
    assert (tmp_path / "adapter_tiny").is_dir() and (tmp_path / "train_log_tiny.json").is_file()
    assert out["brier"]["tuned"]["val"] < out["brier"]["base"]["val"]
