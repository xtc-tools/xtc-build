"""Immediate build graph executor."""

from __future__ import annotations

import os
import subprocess

from .artifacts import Artifact
from .command import Command, command_state_path, serialize_command
from .graph import BuildGraph


def _is_stale(command: Command, dependency_rebuilt: bool) -> bool:
    if dependency_rebuilt:
        return True
    if any(not output.exists() for output in command.outputs):
        return True

    state_path = command_state_path(command)
    try:
        recorded = state_path.read_text(encoding="utf-8")
    except OSError:
        return True
    if recorded != serialize_command(command):
        return True

    missing = [path for path in command.inputs if not path.exists()]
    if missing:
        raise FileNotFoundError(f"build input does not exist: {missing[0]}")

    oldest_output = min(path.stat().st_mtime_ns for path in command.outputs)
    return any(path.stat().st_mtime_ns > oldest_output for path in command.inputs)


def execute(graph: BuildGraph) -> tuple[Artifact, ...]:
    """Build stale graph nodes and return the nodes that were rebuilt."""

    rebuilt: set[Artifact] = set()
    ordered_rebuilt: list[Artifact] = []
    for node in graph.topological_order():
        command = graph.command(node)
        dependency_rebuilt = any(dep in rebuilt for dep in node.dependencies())
        if not _is_stale(command, dependency_rebuilt):
            continue

        for input_path in command.inputs:
            if not input_path.exists():
                raise FileNotFoundError(f"build input does not exist: {input_path}")
        for output in command.outputs:
            output.parent.mkdir(parents=True, exist_ok=True)
        if command.remove_outputs_first:
            for output in command.outputs:
                output.unlink(missing_ok=True)

        environment = os.environ.copy()
        environment.update(command.env)
        subprocess.run(
            command.argv,
            cwd=command.cwd,
            env=environment,
            check=True,
        )
        missing_outputs = [output for output in command.outputs if not output.exists()]
        if missing_outputs:
            raise RuntimeError(
                f"command did not create expected output: {missing_outputs[0]}"
            )
        state_path = command_state_path(command)
        state_path.write_text(serialize_command(command), encoding="utf-8")
        rebuilt.add(node)
        ordered_rebuilt.append(node)

    return tuple(ordered_rebuilt)
