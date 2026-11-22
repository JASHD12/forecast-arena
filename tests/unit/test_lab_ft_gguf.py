"""T246b: sharded GGUF scoring and calibration on validation margins only."""

import pytest

from arena.lab import ft_gguf as fg


def test_shards_partition_the_items_without_overlap() -> None:
    items = list(range(10))
    parts = [fg.shard(items, i, 4) for i in range(4)]
    assert sorted(x for p in parts for x in p) == items
    assert [len(p) for p in parts] == [3, 3, 2, 2]
    with pytest.raises(ValueError):
        fg.shard(items, 4, 4)


def test_merge_refuses_an_item_scored_twice() -> None:
    assert fg.merge([{"a": 1.0}, {"b": 2.0}]) == {"a": 1.0, "b": 2.0}
    with pytest.raises(ValueError, match="twice"):
        fg.merge([{"a": 1.0}, {"a": 2.0}])


def _rows():
    rows = {}
    for split, n in (("val", 60), ("test_oct", 20), ("test_nov", 10)):
        for k in range(n):
            rows[f"{split}-{k}"] = {"split": split, "outcome": k % 2}
    return rows


def test_calibration_uses_validation_margins_only_and_reports_all_splits() -> None:
    rows = _rows()
    # margins carry the outcome in val, and are pure noise (zero) in the test splits
    margins = {
        i: (1.0 if r["outcome"] else -1.0) if r["split"] == "val" else 0.0 for i, r in rows.items()
    }
    res = fg.calibrate(margins, rows, (0.1, 0.0))
    a, _ = res["platt_new"]
    assert a > 1.0  # the fit is driven by the validation margins
    assert set(res["splits"]) == {"val", "test_oct", "test_nov"}
    assert res["splits"]["val"]["brier_new_platt"] < res["splits"]["val"]["brier_old_platt"]
    # test margins do not influence the map: changing them leaves the map unchanged
    margins2 = {**margins, **{i: 5.0 for i, r in rows.items() if r["split"] != "val"}}
    assert fg.calibrate(margins2, rows, (0.1, 0.0))["platt_new"] == res["platt_new"]


def test_calibration_requires_a_margin_for_every_row() -> None:
    rows = _rows()
    with pytest.raises(ValueError, match="no margin"):
        fg.calibrate({"val-0": 0.0}, rows, (0.1, 0.0))


def test_scoring_modules_import_without_pytorch() -> None:
    """The lab-eval shard jobs install no PyTorch: they must reach the scorer without it."""
    import subprocess
    import sys

    code = (
        "import sys; sys.modules['torch'] = None\n"
        "from arena.lab import ft_gguf, dataset, artefacts, ft_runtime\n"
        "assert ft_gguf.shard(list(range(5)), 1, 2) == [1, 3]\n"
        "from arena.cli import lab_cmds\n"
        "assert len(lab_cmds._ft_rows()) == 828\n"
    )
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr[-500:]
