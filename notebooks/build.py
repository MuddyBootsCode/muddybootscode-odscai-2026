#!/usr/bin/env python3
"""Build standalone notebooks from percent-cell lessons and canonical ontologies."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parent
LESSONS = {"01_river_reading.ipynb": "river_reading.py",
           "02_one_person_one_count.ipynb": "one_person_one_count.py"}


def build(source_path):
    cells = []
    mode, lines = None, []

    def append_cell():
        if mode is None:
            return
        if mode.startswith("[ontology]"):
            name = mode.split(maxsplit=1)[1]
            path = ROOT / "ontology" / name
            content = path.read_text(encoding="utf-8")
            digest = hashlib.sha256(content.encode()).hexdigest()
            source = f"*Canonical source: `notebooks/ontology/{name}`; SHA256 `{digest}`.*\n\n" + content
            kind = "markdown"
        elif mode == "[markdown]":
            source = "\n".join(line[2:] if line.startswith("# ") else line[1:] if line.startswith("#") else line
                               for line in lines).strip() + "\n"
            kind = "markdown"
        else:
            source = "\n".join(lines).strip() + "\n"
            kind = "code"
        cell = {"cell_type": kind, "id": f"cell-{len(cells):02d}", "metadata": {},
                "source": source.splitlines(keepends=True)}
        if kind == "code":
            cell.update(execution_count=None, outputs=[])
        cells.append(cell)

    for line in source_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# %%"):
            append_cell()
            mode, lines = line[4:].strip(), []
        else:
            lines.append(line)
    append_cell()
    return {"cells": cells, "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.10"},
    }, "nbformat": 4, "nbformat_minor": 5}


def same_sources(actual, expected):
    def sources(notebook):
        return [(cell["cell_type"], "".join(cell["source"])) for cell in notebook["cells"]]
    return sources(actual) == sources(expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if notebooks differ from current source/ontology")
    parser.add_argument("--execute", action="store_true", help="Execute in fresh kernels and save observed outputs")
    args = parser.parse_args()
    if args.check and args.execute:
        parser.error("Choose --check or --execute")
    for output_name, source_name in LESSONS.items():
        notebook = build(ROOT / "lessons" / source_name)
        output = ROOT / output_name
        if args.check:
            if not output.exists() or not same_sources(json.loads(output.read_text()), notebook):
                raise SystemExit(f"Out of date: {output.name}; run python notebooks/build.py --execute")
            print(f"Source and ontology match: {output.name}")
            continue
        if args.execute:
            try:
                import nbformat
                from nbclient import NotebookClient
            except ImportError as exc:
                raise SystemExit("Install notebooks/requirements.txt before using --execute") from exc
            # Disk JSON stores sources as lines; reads normalizes them to strings
            # as required by the execution API.
            notebook = nbformat.reads(json.dumps(notebook), as_version=4)
            nbformat.validate(notebook)
            # An empty working directory proves there is no repository-file dependency.
            with tempfile.TemporaryDirectory(prefix="odsc-notebook-") as temporary:
                NotebookClient(notebook, timeout=60, kernel_name="python3",
                               resources={"metadata": {"path": temporary}}, record_timing=False).execute()
            nbformat.validate(notebook)
        output.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{'Executed and saved' if args.execute else 'Built without outputs'}: {output.name}")


if __name__ == "__main__":
    main()
