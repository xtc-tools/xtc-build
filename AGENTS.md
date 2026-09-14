# Contributor guidance

## Repository layout

- Python package sources live in `src/xtc_build/`.
- Tests live in `tests/`.
- Public API objects are re-exported from `src/xtc_build/__init__.py`.
- Keep build artifacts and virtual environments out of the repository.

## Development

The project supports Python 3.10 and newer.

```sh
python -m pip install -e '.[dev]'
make check
```

Run `make check` before submitting changes. Individual checks are available as
`make check-format`, `make check-lint`, `make check-type`, and
`make check-pytest`. Use `ruff format` to apply formatting and `make coverage`
to generate terminal and HTML coverage reports.

Some integration tests require `gcc`, `ar`, and GNU Make; they skip when those
tools are unavailable.

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
