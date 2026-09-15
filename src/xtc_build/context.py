"""Build configuration and entry points."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .artifacts import Arguments, Artifact, normalize_arguments
from .graph import BuildGraph
from .toolchains import GnuToolchain


@dataclass
class BuildContext:
    """Platform policy and output location for declarative artifacts.

    A context is intentionally lighter than a project: artifacts can be reused
    with multiple contexts and no global target registry is required.
    """

    build_dir: Path | str = Path("build")
    toolchain: GnuToolchain = field(default_factory=GnuToolchain)
    compile_flags: Arguments = ()
    link_flags: Arguments = ()
    defines: Sequence[str] = ()

    def __post_init__(self) -> None:
        self.build_dir = Path(self.build_dir)
        self.compile_flags = normalize_arguments(self.compile_flags)
        self.link_flags = normalize_arguments(self.link_flags)
        self.defines = tuple(self.defines)

    def graph(self, *targets: Artifact) -> BuildGraph:
        if not targets:
            raise ValueError("at least one build target is required")
        return BuildGraph.from_targets(tuple(targets), self)

    def build(self, *targets: Artifact) -> tuple[Artifact, ...]:
        """Immediately build targets and return artifacts that were rebuilt."""

        from .executor import execute

        return execute(self.graph(*targets))

    def write_makefile(
        self,
        path: str | Path,
        *,
        targets: Iterable[Artifact],
    ) -> Path:
        from .makefile import write

        selected = tuple(targets)
        return write(self.graph(*selected), path)
