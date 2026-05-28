#!/usr/bin/env python3
"""Build the publication-list PDF in an isolated build directory."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def run(cmd: list[str], cwd: Path) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd), check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    args = parser.parse_args()

    root = Path.cwd()
    cfg = load_config(root / args.config)
    build_dir = root / cfg["build_dir"]
    output_dir = root / cfg["output_dir"]
    tex_dir = root / "tex"
    build_dir.mkdir(parents=True, exist_ok=True)

    for filename in ("mypubs.tex", "arcpubs.cls"):
        shutil.copy2(tex_dir / filename, build_dir / filename)
    for filename in (cfg["journal_bib"], cfg["proceedings_bib"], cfg["preprints_bib"]):
        shutil.copy2(output_dir / filename, build_dir / filename)

    if shutil.which("latexmk"):
        run(["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", "mypubs.tex"], build_dir)
    else:
        run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "mypubs.tex"], build_dir)
        run(["biber", "mypubs"], build_dir)
        run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "mypubs.tex"], build_dir)
        run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "mypubs.tex"], build_dir)

    print(f"PDF: {build_dir / 'mypubs.pdf'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
