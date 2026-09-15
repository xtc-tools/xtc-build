# Contributor guidance

## Repository layout

- Python package sources live in `src/xtc_build/`.
- Tests live in `tests/`.
- Public API objects are re-exported from `src/xtc_build/__init__.py`.
- Keep build artifacts and virtual environments out of the repository.

## Development

The project supports Python 3.10 and newer.

```sh
uv sync
source .venv/bin/activate
make check
```

The `dev` dependency group is installed by default. Keep `uv.lock` synchronized
with `pyproject.toml`; `uv run make check` can be used without activating the
virtual environment.

Run `make check` before submitting changes. Individual checks are available as
`make check-lock`, `make check-format`, `make check-lint`, `make check-type`,
`make check-pytest`, and `make check-pytest-coverage`. Use `ruff format` to
apply formatting.
Coverage checks require 100% line and branch coverage and generate terminal and
HTML reports.

The test suite requires `gcc`, `ar`, and GNU Make. Missing build tools are test
errors rather than skips.

## Design constraints

- Keep artifact declarations immutable and free of execution side effects.
- Keep toolchain-specific command construction separate from graph traversal.
- Represent commands as argument vectors; immediate execution must not use
  `shell=True`.
- Immediate execution and Makefile generation must consume the same graph and
  commands.
- Dependencies between generated artifacts must remain explicit.
- Avoid introducing a mandatory project/global target registry. Configuration
  belongs in `BuildContext`; optional grouping can be layered on top.
- Add tests for graph behavior and both execution backends when extending the
  artifact model.
