"""Structured build commands."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


def _empty_environment() -> dict[str, str]:
    return {}


@dataclass(frozen=True)
class Command:
    """A command and the files it consumes and produces.

    ``argv`` is intentionally represented as an argument vector rather than a
    shell command. Executors can therefore run it without a shell, while text
    backends such as Make can quote it for their target environment.
    """

    argv: tuple[str, ...]
    inputs: tuple[Path, ...]
    outputs: tuple[Path, ...]
    cwd: Path | None = None
    env: Mapping[str, str] = field(default_factory=_empty_environment)
    remove_outputs_first: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "argv", tuple(str(arg) for arg in self.argv))
        object.__setattr__(self, "inputs", tuple(Path(path) for path in self.inputs))
        object.__setattr__(self, "outputs", tuple(Path(path) for path in self.outputs))
        object.__setattr__(self, "env", dict(self.env))
