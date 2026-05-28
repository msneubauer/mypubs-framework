.PHONY: all fetch normalize pdf clean validate

PYTHON ?= python3

all: fetch normalize pdf

fetch:
	$(PYTHON) scripts/fetch_inspire.py --config config.json

normalize:
	$(PYTHON) scripts/normalize_bib.py --config config.json

pdf:
	$(PYTHON) scripts/build.py --config config.json

validate:
	$(PYTHON) scripts/normalize_bib.py --config config.json --validate-only

clean:
	rm -rf build/*
