.DEFAULT_GOAL := help

.PHONY: help check check-format check-lint check-type check-pytest

help:
	@printf '%s\n' \
	  'help          Show this help message (default)' \
	  'check         Run all checks' \
	  'check-format  Check source formatting with Ruff' \
	  'check-lint    Check source linting with Ruff' \
	  'check-type    Check static types with Pyright' \
	  'check-pytest  Run the test suite with pytest'

check: check-format check-lint check-type check-pytest

check-format:
	ruff format --check

check-lint:
	ruff check

check-type:
	pyright

check-pytest:
	python3 -m pytest
