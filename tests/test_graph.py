from pathlib import Path
from typing import cast

import pytest

from xtc_build import (
    Archive,
    BuildContext,
    DependencyCycleError,
    ExternalLibrary,
    Object,
    SharedLibrary,
)
from xtc_build.artifacts import Artifact


def test_graph_is_topological_and_commands_are_inspectable(tmp_path: Path) -> None:
    ctx = BuildContext(tmp_path / "build")
    first = Object("first", "first.c", pic=True)
    second = Object("second", "second.c", pic=True)
    archive = Archive("core", [first])
    system_math = ExternalLibrary("math", ["-lm"])
    shared = SharedLibrary(
        "example",
        objects=[second],
        archives=[archive],
        libraries=[system_math],
    )

    graph = ctx.graph(shared)

    assert graph.topological_order() == (second, first, archive, shared)
    assert graph.dependencies(shared) == (second, archive)
    assert graph.command(first).argv[-4:] == (
        "-c",
        "first.c",
        "-o",
        str(tmp_path / "build" / "first.o"),
    )
    assert "-lm" in graph.command(shared).argv


def test_an_artifact_name_cannot_escape_the_build_directory() -> None:
    with pytest.raises(ValueError, match="invalid artifact name"):
        Object("../outside", "source.c")


def test_shared_library_requires_pic_objects() -> None:
    obj = Object("plain", "plain.c")

    with pytest.raises(ValueError, match="requires PIC"):
        SharedLibrary("bad", objects=[obj])


def test_artifact_validation_and_optional_pic_check() -> None:
    with pytest.raises(ValueError, match="external library needs a name"):
        ExternalLibrary("")

    obj = Object("plain", "plain.c")
    library = SharedLibrary("allowed", objects=[obj], require_pic=False)
    assert library.objects == (obj,)


def test_context_rejects_an_empty_target_list(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least one build target"):
        BuildContext(tmp_path).graph()


def test_graph_reuses_nodes_and_rejects_output_collisions(tmp_path: Path) -> None:
    context = BuildContext(tmp_path)
    obj = Object("same", "first.c")
    graph = context.graph(obj, obj)
    assert graph.topological_order() == (obj,)

    conflicting = Object("same", "second.c")
    with pytest.raises(ValueError, match="both produce"):
        context.graph(obj, conflicting)


def test_graph_detects_cycles(tmp_path: Path) -> None:
    class CyclicArtifact:
        name = "cycle"

        def dependencies(self) -> tuple[Artifact, ...]:
            return (cast(Artifact, self),)

    cyclic = cast(Artifact, CyclicArtifact())
    with pytest.raises(DependencyCycleError, match="cycle"):
        BuildContext(tmp_path).graph(cyclic)


def test_graph_rejects_queries_for_unknown_nodes(tmp_path: Path) -> None:
    context = BuildContext(tmp_path)
    member = Object("member", "member.c")
    outsider = Object("outsider", "outsider.c")
    graph = context.graph(member)

    with pytest.raises(KeyError, match="not in this graph"):
        graph.dependencies(outsider)
    with pytest.raises(KeyError, match="not in this graph"):
        graph.command(outsider)
