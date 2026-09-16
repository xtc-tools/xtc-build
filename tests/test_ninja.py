from __future__ import annotations

import os
import subprocess
import sys
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


class CommandMetadataToolchain(GnuToolchain):
    def object_command(self, obj: Object, context: BuildContext) -> Command:
        command = super().object_command(obj, context)
        return replace(
            command,
            cwd=Path("working $directory"),
            env={"BUILD_MODE": "debug $build"},
        )


def test_ninja_contains_rules_depfiles_dependencies_and_quoted_commands(
    tmp_path: Path,
) -> None:
    context = BuildContext(
        tmp_path / "build",
        toolchain=CommandMetadataToolchain(),
    )
    source = tmp_path / "source file.c"
    header = tmp_path / "header file.h"
    obj = Object("example", source, inputs=[header], pic=True)
    external_object = ExternalObject(tmp_path / "external.o", pic=True)
    archive = Archive("core", objects=[obj, external_object])
    external_archive = ExternalArchive(tmp_path / "external.a", pic=True)
    external_shared = ExternalSharedLibrary(tmp_path / "external.so")
    library = SharedLibrary(
        "example",
        archives=[archive, external_archive],
        libraries=[external_shared],
    )

    ninja_file = context.write_ninja(tmp_path / "build.ninja", targets=[library])

    text = ninja_file.read_text(encoding="utf-8")
    assert "rule xtc_compile" in text
    assert "rule xtc_command" in text
    assert "deps = gcc" in text
    assert "depfile = $depfile" in text
    assert str(obj.depfile(context)) in text
    assert str(source).replace(" ", "$ ") in text
    assert str(header).replace(" ", "$ ") in text
    assert str(external_object.path) in text
    assert str(external_archive.path) in text
    assert str(external_shared.path) in text
    assert "working $$directory" in text
    assert "debug $$build" in text
    assert "build example: phony" in text
    assert "default example" in text


def test_ninja_rejects_duplicate_target_aliases(tmp_path: Path) -> None:
    context = BuildContext(tmp_path / "build")
    archive = Archive("duplicate", objects=[])
    shared = SharedLibrary("duplicate")

    with pytest.raises(ValueError, match="distinct names"):
        context.write_ninja(tmp_path / "build.ninja", targets=[archive, shared])


def test_ninja_file_is_not_rewritten_when_unchanged(tmp_path: Path) -> None:
    context = BuildContext(tmp_path / "build")
    obj = Object("example", tmp_path / "example.c")
    path = context.write_ninja(tmp_path / "build.ninja", targets=[obj])
    first_stat = path.stat()

    context.write_ninja(path, targets=[obj])

    second_stat = path.stat()
    assert second_stat.st_mtime_ns == first_stat.st_mtime_ns
    assert second_stat.st_ino == first_stat.st_ino

    changed = Object("changed", tmp_path / "changed.c")
    context.write_ninja(path, targets=[changed])
    assert "build changed: phony" in path.read_text(encoding="utf-8")


def _loaded_value(library: Path) -> int:
    program = (
        "import ctypes; "
        f"library = ctypes.CDLL({str(library)!r}); "
        "library.header_value.restype = ctypes.c_int; "
        "print(library.header_value())"
    )
    output = subprocess.check_output([sys.executable, "-c", program], text=True)
    return int(output)


def test_ninja_uses_compiler_depfiles_for_discovered_headers(tmp_path: Path) -> None:
    header = tmp_path / "value.h"
    source = tmp_path / "value.c"
    header.write_text("#define VALUE 1\n", encoding="utf-8")
    source.write_text(
        '#include "value.h"\nint header_value(void) { return VALUE; }\n',
        encoding="utf-8",
    )
    context = BuildContext(tmp_path / "build")
    obj = Object("value", source, includes=[tmp_path], pic=True)
    library = SharedLibrary("value", objects=[obj])
    ninja_file = context.write_ninja(tmp_path / "build.ninja", targets=[library])

    subprocess.run(["ninja", "-f", str(ninja_file)], check=True, cwd=tmp_path)
    assert _loaded_value(library.output(context)) == 1

    object_time = obj.output(context).stat().st_mtime_ns
    header.write_text("#define VALUE 2\n", encoding="utf-8")
    newer_time = object_time + 1_000_000_000
    os.utime(header, ns=(newer_time, newer_time))
    subprocess.run(["ninja", "-f", str(ninja_file)], check=True, cwd=tmp_path)

    assert obj.output(context).stat().st_mtime_ns > object_time
    assert _loaded_value(library.output(context)) == 2
