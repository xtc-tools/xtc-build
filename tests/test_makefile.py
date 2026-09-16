from dataclasses import replace
from pathlib import Path

import pytest

from xtc_build import (
    Archive,
    BuildContext,
    Command,
    ExternalArchive,
    ExternalObject,
    ExternalSharedLibrary,
    GnuToolchain,
    Object,
    SharedLibrary,
)
from xtc_build.command import (
    make_argv_fragment,
    make_command_fragment,
    make_recipe,
    posix_shell_fragment,
)


def test_make_argv_fragment_quotes_shell_arguments_and_make_variables() -> None:
    assert make_argv_fragment(["rm", "-f", "build/$output file"]) == (
        "rm -f 'build/$$output file'"
    )


class CommandMetadataToolchain(GnuToolchain):
    def object_command(self, obj: Object, context: BuildContext) -> Command:
        command = super().object_command(obj, context)
        return replace(
            command,
            cwd=Path("working $directory"),
            env={"BUILD_MODE": "debug $build"},
        )


def test_makefile_renders_command_environment_and_working_directory(
    tmp_path: Path,
) -> None:
    context = BuildContext(
        tmp_path / "build",
        toolchain=CommandMetadataToolchain(),
    )
    obj = Object("example", "example.c")

    makefile = context.write_makefile(tmp_path / "build.mk", targets=[obj])

    text = makefile.read_text(encoding="utf-8")
    command = context.graph(obj).command(obj)
    recipe = make_recipe(command)
    assert "\n" not in recipe
    assert " && " in recipe
    assert posix_shell_fragment(command) == (
        "cd 'working $directory' && env 'BUILD_MODE=debug $build' "
        + " ".join(command.argv)
    )
    assert recipe in text
    assert make_command_fragment(command) in recipe
    assert "working $$directory" in text
    assert "debug $$build" in text


def test_makefile_rejects_duplicate_target_aliases(tmp_path: Path) -> None:
    context = BuildContext(tmp_path / "build")
    archive = Archive("duplicate", objects=[])
    shared = SharedLibrary("duplicate")

    with pytest.raises(ValueError, match="distinct names"):
        context.write_makefile(tmp_path / "build.mk", targets=[archive, shared])


def test_makefile_tracks_external_inputs_without_generating_rules(
    tmp_path: Path,
) -> None:
    context = BuildContext(tmp_path / "build")
    object_path = tmp_path / "prebuilt.o"
    archive_path = tmp_path / "prebuilt.a"
    shared_path = tmp_path / "prebuilt.so"
    archive = Archive("object-input", objects=[ExternalObject(object_path)])
    shared = SharedLibrary(
        "archive-input",
        archives=[ExternalArchive(archive_path, pic=True)],
        libraries=[ExternalSharedLibrary(shared_path)],
    )

    makefile = context.write_makefile(
        tmp_path / "build.mk",
        targets=[archive, shared],
    )

    text = makefile.read_text(encoding="utf-8")
    assert str(object_path) in text
    assert str(archive_path) in text
    assert str(shared_path) in text
    assert f"\n{object_path}:" not in text
    assert f"\n{archive_path}:" not in text
    assert f"\n{shared_path}:" not in text


def test_makefile_without_objects_has_no_depfile_include(tmp_path: Path) -> None:
    context = BuildContext(tmp_path / "build")
    shared = SharedLibrary("empty")

    makefile = context.write_makefile(tmp_path / "build.mk", targets=[shared])

    assert "-include" not in makefile.read_text(encoding="utf-8")
