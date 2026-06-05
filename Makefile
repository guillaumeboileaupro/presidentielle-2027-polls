PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,$(shell command -v python3.10 2>/dev/null || command -v python3 2>/dev/null || command -v python))
PACKAGE = presidentielle2027

.PHONY: install init-db ingest normalize dashboard test lint format notebook notebook-kernel wiki-datasets

install:
	$(PYTHON) -m pip install -e ".[dev]"

init-db:
	$(PYTHON) -m $(PACKAGE).cli init-db

ingest:
	$(PYTHON) -m $(PACKAGE).cli ingest-wikipedia

normalize:
	$(PYTHON) -m $(PACKAGE).cli normalize

dashboard:
	$(PYTHON) -m $(PACKAGE).cli run-dashboard

wiki-datasets:
	$(PYTHON) make_wiki_datasets.py

notebook-kernel:
	$(PYTHON) -m $(PACKAGE).cli install-notebook-kernel

notebook:
	$(PYTHON) -m jupyter lab notebooks

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check src tests

format:
	$(PYTHON) -m ruff format src tests
