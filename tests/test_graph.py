from pathlib import Path

import pytest

from xtc_build import Archive, BuildContext, ExternalLibrary, Object, SharedLibrary


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
