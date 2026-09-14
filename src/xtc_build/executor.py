"""Immediate build graph executor."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

from .artifacts import Artifact
from .command import Command
from .graph import BuildGraph


def _signature(command: Command) -> str:
    value = {
        "argv": command.argv,
        "cwd": str(command.cwd) if command.cwd else None,
        "env": sorted(command.env.items()),
        "outputs": [str(path) for path in command.outputs],
        "remove_outputs_first": command.remove_outputs_first,
    }
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _signature_path(command: Command) -> Path:
    output = command.outputs[0]
    return output.with_name(output.name + ".xtc-build.json")


def _is_stale(command: Command, dependency_rebuilt: bool) -> bool:
    if dependency_rebuilt or not command.outputs:
        return True
    if any(not output.exists() for output in command.outputs):
        return True

    signature_path = _signature_path(command)
    try:
        recorded = json.loads(signature_path.read_text(encoding="utf-8"))["signature"]
    except (OSError, KeyError, json.JSONDecodeError):
        return True
    if recorded != _signature(command):
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
        signature_path = _signature_path(command)
        signature_path.write_text(
            json.dumps({"signature": _signature(command)}, indent=2) + "\n",
            encoding="utf-8",
        )
        rebuilt.add(node)
        ordered_rebuilt.append(node)

    return tuple(ordered_rebuilt)
