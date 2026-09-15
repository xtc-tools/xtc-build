from dataclasses import replace
from pathlib import Path

import pytest

from xtc_build import (
    Archive,
    BuildContext,
    Command,
    GnuToolchain,
    Object,
    SharedLibrary,
)


class CommandMetadataToolchain(GnuToolchain):
    def object_command(self, obj: Object, context: BuildContext) -> Command:
        command = super().object_command(obj, context)
        return replace(
            command,
            cwd=Path("working directory"),
            env={"BUILD_MODE": "debug build"},
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
    assert "cd 'working directory' &&" in text
    assert "env BUILD_MODE='debug build'" in text


def test_makefile_rejects_duplicate_target_aliases(tmp_path: Path) -> None:
    context = BuildContext(tmp_path / "build")
    archive = Archive("duplicate", objects=[])
    shared = SharedLibrary("duplicate")

    with pytest.raises(ValueError, match="distinct names"):
        context.write_makefile(tmp_path / "build.mk", targets=[archive, shared])


def test_makefile_without_objects_has_no_depfile_include(tmp_path: Path) -> None:
    context = BuildContext(tmp_path / "build")
    shared = SharedLibrary("empty")

    makefile = context.write_makefile(tmp_path / "build.mk", targets=[shared])

    assert "-include" not in makefile.read_text(encoding="utf-8")
