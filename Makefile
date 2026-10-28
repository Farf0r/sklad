ifeq ($(OS),Windows_NT)
    PYTHON ?= python
    VENV_PY = ".venv/Scripts/python.exe"
else
    PYTHON ?= python3
    VENV_PY = .venv/bin/python
endif

.PHONY: setup run migrate test quality format verify createadmin

setup:
	$(PYTHON) -m venv .venv
	$(VENV_PY) -m pip install --upgrade pip
	$(VENV_PY) -m pip install -r requirements-dev.txt

run:
	$(VENV_PY) -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

migrate:
	$(VENV_PY) -m app.cli migrate

test:
	$(VENV_PY) -m pytest

quality:
	$(VENV_PY) -m ruff check .
	$(VENV_PY) -m ruff format --check .

format:
	$(VENV_PY) -m ruff format .
	$(VENV_PY) -m ruff check --fix .

verify: quality test

createadmin:
	$(VENV_PY) -m app.cli create-user --username admin --role admin
