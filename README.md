# mypubs framework

This is a cleaner, repeatable replacement for the old `run.sh` workflow.

The pipeline is:

1. Fetch INSPIRE records into `data/raw/` as JSON.
2. Normalize records into stable BibTeX.
3. Split entries into journal, conference-proceedings, and preprint files.
4. Build `build/mypubs.pdf` with sections for Journal Articles, Conference Proceedings, and Pre-prints.

## Quick test with bundled BibTeX

The `output/` directory is seeded with your current cleaned files, so you can test the LaTeX build immediately:

```sh
make pdf
```

The PDF will be written to:

```text
build/mypubs.pdf
```

## Full refresh from INSPIRE

```sh
make fetch
make normalize
make pdf
```

or:

```sh
make all
```

The default configuration lives in `config.json`.

## Important files

- `scripts/fetch_inspire.py`: downloads INSPIRE JSON into `data/raw/`.
- `scripts/normalize_bib.py`: converts cached JSON or existing BibTeX into cleaned/split BibTeX.
- `scripts/build.py`: runs the LaTeX/Biber build in `build/`.
- `tex/mypubs.tex`: PDF document with a separate preprints section.
- `tex/arcpubs.cls`: lightly updated bibliography class.
- `output/pubs_journal.bib`: journal articles and other non-proceeding published entries.
- `output/pubs_proceedings.bib`: conference proceedings.
- `output/pubs_preprints.bib`: arXiv-only preprints.

## Preprint rule

An entry is treated as a preprint when it has an arXiv eprint but no journal field. Once INSPIRE reports journal metadata for an arXiv entry, it is classified into `pubs_journal.bib` instead of `pubs_preprints.bib`. Preprint entries receive:

```bibtex
keywords = {preprint},
note = "{arXiv:... [...]}"
```

This makes the TeX filtering explicit and avoids relying on `.bst` or `.bbx` style-specific treatment of `eprint`.
