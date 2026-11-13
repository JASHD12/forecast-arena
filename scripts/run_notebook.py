"""Execute a notebook headlessly (T138): `python scripts/run_notebook.py NOTEBOOK DATA_DIR`.

Fails with a non-zero exit code if any cell raises. Outputs are not written back, so the
committed notebook stays free of fixture results."""

import os
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient


def main() -> int:
    nb_path, data_dir = Path(sys.argv[1]), Path(sys.argv[2])
    os.environ["ARENA_DATA_DIR"] = str(data_dir.resolve())
    nb = nbformat.read(nb_path, as_version=4)
    NotebookClient(
        nb,
        timeout=300,
        kernel_name="python3",
        resources={"metadata": {"path": str(nb_path.parent)}},
    ).execute()
    last = [c for c in nb.cells if c.cell_type == "code"][-1]
    for out in last.get("outputs", []):
        if out.get("output_type") == "stream":
            print(out.get("text", "").strip())
    print(f"notebook ran: {nb_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
