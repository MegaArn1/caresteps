# CareSteps - development entry points.
#
# The whole point of this file is that a judge can go from a fresh clone to a running
# demo without reading anything else. If a target here is not obvious, it is
# documented in the README.

PY ?= python3
VENV := .venv
BIN := $(VENV)/bin
PORT ?= 8000

.PHONY: help setup seed run run-live test test-fast lint reset clean db-shell demo-check

help:
	@echo "CareSteps - available targets:"
	@echo ""
	@echo "  make setup      Create .venv and install the 5 dependencies"
	@echo "  make seed       Rebuild the database with fictional demo data"
	@echo "  make run        Serve at http://127.0.0.1:$(PORT)  (works with no model)"
	@echo "  make run-live   Serve, expecting LLM_* to be configured"
	@echo "  make test       Run the test suite"
	@echo "  make demo-check Check every demo case reproduces (the evaluation run)"
	@echo "  make reset      Delete the database"
	@echo "  make db-shell   Open sqlite3 against the database"
	@echo ""

$(BIN)/python:
	$(PY) -m venv $(VENV)
	$(BIN)/pip install --quiet --upgrade pip
	$(BIN)/pip install --quiet -r requirements.txt

setup: $(BIN)/python
	@echo "Installed. Next: make seed && make run"

seed: $(BIN)/python
	$(BIN)/python -m scripts.seed --verbose

run: $(BIN)/python
	@echo "CareSteps on http://127.0.0.1:$(PORT)  (Ctrl-C to stop)"
	@echo "No model configured is fine - the app runs in limited mode."
	$(BIN)/uvicorn app.main:app --reload --host 127.0.0.1 --port $(PORT)

run-live: $(BIN)/python
	@if [ -z "$$LLM_BASE_URL" ] || [ -z "$$LLM_MODEL" ]; then \
		echo "LLM_BASE_URL and LLM_MODEL must be set. See docs/architecture.md."; \
		exit 1; \
	fi
	$(BIN)/uvicorn app.main:app --host 127.0.0.1 --port $(PORT)

test: $(BIN)/python
	$(BIN)/python -m pytest tests/ -v

test-fast: $(BIN)/python
	$(BIN)/python -m pytest tests/ -q

demo-check: $(BIN)/python
	$(BIN)/python -m scripts.demo_check

reset:
	rm -f caresteps.db caresteps.db-wal caresteps.db-shm
	@echo "Database removed. Run 'make seed' to rebuild."

db-shell:
	sqlite3 caresteps.db

clean: reset
	rm -rf $(VENV) .pytest_cache
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned."
