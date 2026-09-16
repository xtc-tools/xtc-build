"""Structured build commands."""

from __future__ import annotations

import json
import shlex
from collections.abc import Mapping, Sequence
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
        if not self.argv:
            raise ValueError("a command needs at least one argument")
        if not self.outputs:
            raise ValueError("a build command needs at least one output")


def serialize_command(command: Command) -> str:
    """Serialize build-relevant command state deterministically."""

    state = {
        "command": {
            "argv": command.argv,
            "cwd": str(command.cwd) if command.cwd is not None else None,
            "env": sorted(command.env.items()),
            "inputs": [str(path) for path in command.inputs],
            "outputs": [str(path) for path in command.outputs],
            "remove_outputs_first": command.remove_outputs_first,
        },
        "schema_version": 1,
    }
    return json.dumps(state, indent=2, sort_keys=True) + "\n"


def command_state_path(command: Command) -> Path:
    """Return the sidecar path used for immediate incremental builds."""

    output = command.outputs[0]
    return output.with_name(output.name + ".xtc-build.json")


def posix_argv_fragment(argv: Sequence[str]) -> str:
    """Render an argument vector for execution by a POSIX shell."""

    return shlex.join(argv)


def posix_shell_fragment(command: Command) -> str:
    """Render a structured command for execution by a POSIX shell."""

    argv = command.argv
    if command.env:
        assignments = tuple(
            f"{key}={value}" for key, value in sorted(command.env.items())
        )
        argv = ("env", *assignments, *argv)
    invocation = posix_argv_fragment(argv)
    if command.cwd is not None:
        invocation = f"cd {shlex.quote(str(command.cwd))} && {invocation}"
    return invocation


def escape_make_recipe(fragment: str) -> str:
    """Escape a POSIX shell fragment from an additional Make expansion pass."""

    return fragment.replace("$", "$$")


def make_argv_fragment(argv: Sequence[str]) -> str:
    """Render an arbitrary argument vector for a Make recipe."""

    return escape_make_recipe(posix_argv_fragment(argv))


def make_command_fragment(command: Command) -> str:
    """Render a structured command invocation for a Make recipe."""

    return escape_make_recipe(posix_shell_fragment(command))


def posix_recipe_fragments(command: Command) -> tuple[str, ...]:
    """Render filesystem setup and invocation as POSIX shell fragments."""

    parents = tuple(dict.fromkeys(output.parent for output in command.outputs))
    fragments = [posix_argv_fragment(("mkdir", "-p", *(str(p) for p in parents)))]
    if command.remove_outputs_first:
        fragments.append(
            posix_argv_fragment(("rm", "-f", *(str(p) for p in command.outputs)))
        )
    fragments.append(posix_shell_fragment(command))
    return tuple(fragments)


def posix_recipe(command: Command) -> str:
    """Render setup and invocation as one POSIX shell command."""

    return " && ".join(posix_recipe_fragments(command))


def make_recipe(command: Command) -> str:
    """Render a complete one-line Make recipe."""

    return f"\t{escape_make_recipe(posix_recipe(command))}"
