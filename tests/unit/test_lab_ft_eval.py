"""T246: the fine-tune evaluation pairs arms on identical items only."""

from arena.lab import ft_eval as fe
from arena.lab.ft_parity import compare


def _data(n_days: int = 12):
    rows, a, b, m = {}, {}, {}, {}
    for d in range(n_days):
        for k in range(3):
            i = f"q{d}-{k}"
            y = (d + k) % 2
            rows[i] = {
                "split": "test_oct",
                "batch_date": f"2026-10-{d + 1:02d}",
                "base_rate": 0.5,
                "outcome": y,
            }
            a[i] = {
                "p": 0.8 if y else 0.2,
                "margin": 0.0,
                "outcome": y,
                "split": "test_oct",
                "variant": "good",
            }
            b[i] = {"p": 0.5, "margin": 0.0, "outcome": y, "split": "test_oct", "variant": "flat"}
            m[i] = 0.6 if y else 0.4
    return rows, {"good": a, "flat": b}, m


def test_metrics_and_paired_intervals() -> None:
    rows, scores, ml = _data()
    metrics, paired = fe.evaluate(
        scores, rows, ml, [("good", "flat"), ("good", "ml"), ("ml", "base_rate")]
    )
    assert metrics["good / test_oct"]["brier"] < metrics["flat / test_oct"]["brier"]
    assert metrics["flat / test_oct"]["brier"] == 0.25 == metrics["base_rate / test_oct"]["brier"]
    d = next(p for p in paired if (p["a"], p["b"], p["split"]) == ("good", "flat", "test_oct"))
    assert d["diff"] < 0 and d["hi"] < 0 and d["n"] == 36 and d["days"] == 12


def test_a_pair_needs_items_covered_by_both_arms() -> None:
    rows, scores, ml = _data()
    few = {k: v for k, v in list(ml.items())[:5]}
    _, paired = fe.evaluate(scores, rows, few, [("good", "ml")])
    assert paired == []  # only five common items: not reported


def test_missing_test_nov_split_is_simply_absent() -> None:
    rows, scores, _ = _data()
    metrics, _ = fe.evaluate(scores, rows, None, [])
    assert not any("test_nov" in k for k in metrics) and "good / test_all" in metrics


def test_parity_compare_reports_margin_and_brier_loss() -> None:
    colab = {
        "a": {"margin": 1.0, "outcome": 1},
        "b": {"margin": -1.0, "outcome": 0},
        "c": {"margin": 0.5, "outcome": 1},
    }
    res = compare({"a": 1.1, "b": -0.9, "c": 0.4}, colab, (2.0, 0.0))
    assert res["n"] == 3 and abs(res["margin_mean_abs_diff"] - 0.1) < 1e-9
    assert abs(res["brier_loss"]) < 0.01
