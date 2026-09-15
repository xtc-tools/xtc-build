.DEFAULT_GOAL := help

.PHONY: help check check-format check-lint check-type check-pytest
.PHONY: check-pytest-coverage coverage

help:
	@printf '%s\n' \
	  'help                   Show this help message (default)' \
	  'check                  Run all checks' \
	  'check-format           Check source formatting with Ruff' \
	  'check-lint             Check source linting with Ruff' \
	  'check-type             Check static types with Pyright' \
	  'check-pytest           Run the test suite with pytest' \
	  'check-pytest-coverage  Run pytest and require 100% coverage' \
	  'coverage               Alias for check-pytest-coverage'

check: check-format check-lint check-type check-pytest-coverage

check-format:
	ruff format --check

check-lint:
	ruff check

check-type:
	pyright

check-pytest:
	python3 -m pytest

check-pytest-coverage:
	python3 -m coverage erase
	python3 -m coverage run -m pytest
	python3 -m coverage html --fail-under=0
	python3 -m coverage report

coverage: check-pytest-coverage
