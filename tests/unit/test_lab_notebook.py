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


def test_gguf_export_cell_fails_loudly_and_checks_the_file() -> None:
    """The first Colab run reported a GGUF export that never produced a file."""
    import json
    from pathlib import Path

    nb = json.loads(
        (
            Path(__file__).resolve().parents[2] / "notebooks/lab/qlora_qwen_forecast.ipynb"
        ).read_text()
    )
    src = next(
        "".join(c["source"])
        for c in nb["cells"]
        if c["cell_type"] == "code" and "gguf = {}" in "".join(c["source"])
    )
    assert "check=True" not in src and "returncode" in src  # errors are raised by `sh`
    assert "target.exists()" in src and src.index("target.exists()") < src.index(
        'gguf["exported"] = True'
    )
    assert "hf_hub_download" in src and "-m venv /content/conv" in src
    assert "\n!" not in src  # no ignored shell lines


def test_dpo_notebook_is_valid_uses_its_own_prereg_and_the_dpo_spec() -> None:
    nb_path = NB.with_name("dpo_qwen_forecast.ipynb")
    nb = json.loads(nb_path.read_text())
    code = "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code")
    assert "lab/prereg/dpo-forecast.md" in code and "dpo_beta=BETA" in code and "BETA = 0.1" in code
    assert "qlora-forecast" not in code and "qlora_1_5b" not in code
    assert (nb_path.parents[2] / "lab/prereg/dpo-forecast.md").is_file()
    cleaned = "\n".join(
        ln[: len(ln) - len(ln.lstrip())] + "pass" if ln.lstrip().startswith(("!", "%")) else ln
        for ln in code.splitlines()
    )
    ast.parse(cleaned)
    assert "target.exists()" in code  # the loud, checked GGUF export


def test_distillation_notebook_compiles_and_uses_soft_labels_not_outcomes() -> None:
    path = NB.with_name("distill_qwen_forecast.ipynb")
    nb = json.loads(path.read_text())
    src = []
    for c in nb["cells"]:
        if c["cell_type"] == "code":
            src.append(
                "\n".join(
                    ln[: len(ln) - len(ln.lstrip())] + "pass"
                    if ln.lstrip().startswith(("!", "%"))
                    else ln
                    for ln in "".join(c["source"]).splitlines()
                )
            )
    code = "\n\n".join(src)
    ast.parse(code)
    assert "soft_labels=SOFT" in code and "dpo_beta" not in code
    assert "lab/prereg/distill.md" in code and "lab/data/distill-labels-v1.json" in code
    assert "EXPORT_GGUF = False" in code
