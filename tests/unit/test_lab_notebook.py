"""T244: the Colab notebook is valid JSON, its code compiles, and it uses only code that exists."""

import ast
import json
from pathlib import Path

NB = Path(__file__).resolve().parents[2] / "notebooks" / "lab" / "qlora_qwen_forecast.ipynb"


def _code() -> str:
    nb = json.loads(NB.read_text())
    out = []
    for c in nb["cells"]:
        if c["cell_type"] != "code":
            continue
        # IPython magics and shell lines are not Python
        lines = [
            ln[: len(ln) - len(ln.lstrip())] + "pass" if ln.lstrip().startswith(("!", "%")) else ln
            for ln in "".join(c["source"]).splitlines()
        ]
        out.append("\n".join(lines))
    return "\n\n".join(out)


def test_notebook_is_valid_and_compiles() -> None:
    nb = json.loads(NB.read_text())
    assert nb["nbformat"] == 4 and len(nb["cells"]) >= 8
    ast.parse(_code())


def test_notebook_calls_only_existing_lab_functions() -> None:
    import importlib

    tree = ast.parse(_code())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("arena."):
            mod = importlib.import_module(node.module)
            for alias in node.names:
                if not hasattr(
                    mod, alias.name
                ):  # a submodule, as in `from arena.lab import dataset`
                    importlib.import_module(f"{node.module}.{alias.name}")


def test_notebook_pins_match_the_environment_and_run_the_preregistered_settings() -> None:
    text = NB.read_text()
    for pin in (
        "transformers==5.22.2",
        "peft==0.22.0",
        "accelerate==1.15.0",
        "bitsandbytes==0.50.2",
    ):
        assert pin in text, pin
    assert "TRAIN_ROWS = 2000" in text and "Qwen/Qwen2.5-1.5B-Instruct" in text
    assert "T4" in text
