"""Dependency graph construction and inspection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .artifacts import Artifact
from .command import Command

if TYPE_CHECKING:
    from .context import BuildContext


class DependencyCycleError(ValueError):
    """Raised when artifact dependencies contain a cycle."""


@dataclass(frozen=True)
class BuildGraph:
    """A validated, topologically ordered artifact graph."""

    targets: tuple[Artifact, ...]
    nodes: tuple[Artifact, ...]
    context: BuildContext

    @classmethod
    def from_targets(
        cls, targets: tuple[Artifact, ...], context: BuildContext
    ) -> BuildGraph:
        ordered: list[Artifact] = []
        visiting: set[Artifact] = set()
        visited: set[Artifact] = set()

        def visit(node: Artifact) -> None:
            if node in visiting:
                raise DependencyCycleError(f"dependency cycle at {node.name!r}")
            if node in visited:
                return
            visiting.add(node)
            for dependency in node.dependencies():
                visit(dependency)
            visiting.remove(node)
            visited.add(node)
            ordered.append(node)

        for target in targets:
            visit(target)

        outputs: dict[Path, Artifact] = {}
        for node in ordered:
            output = node.output(context)
            previous = outputs.get(output)
            if previous is not None and previous != node:
                message = (
                    f"artifacts {previous.name!r} and {node.name!r} "
                    f"both produce {output}"
                )
                raise ValueError(message)
            outputs[output] = node

        return cls(targets=targets, nodes=tuple(ordered), context=context)

    def topological_order(self) -> tuple[Artifact, ...]:
        return self.nodes

    def dependencies(self, node: Artifact) -> tuple[Artifact, ...]:
        if node not in self.nodes:
            raise KeyError(f"artifact {node.name!r} is not in this graph")
        return node.dependencies()

    def command(self, node: Artifact) -> Command:
        if node not in self.nodes:
            raise KeyError(f"artifact {node.name!r} is not in this graph")
        return node.command(self.context)
