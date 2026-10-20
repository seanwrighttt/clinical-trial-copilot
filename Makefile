.PHONY: setup test lint

setup:
	python -m pip install --upgrade pip
	python -m pip install -e ".[dev]"

test:
	python -m pytest

lint:
	python -m ruff check .
	python -m ruff format --check .
