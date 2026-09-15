from __future__ import annotations

import ctypes
import subprocess
import sys
from pathlib import Path
from typing import Literal

import pytest

from xtc_build import (
    Archive,
    BuildContext,
    ExternalArchive,
    ExternalLibrary,
    ExternalObject,
    ExternalSharedLibrary,
    Object,
    SharedLibrary,
)

Backend = Literal["immediate", "makefile"]


def _write_source(path: Path, source: str) -> Path:
    path.write_text(source, encoding="utf-8")
    return path


def _create_external_inputs(
    tmp_path: Path, context: BuildContext
) -> tuple[ExternalObject, ExternalArchive, ExternalSharedLibrary]:
    external_object_source = _write_source(
        tmp_path / "external-object.c",
        "int external_object_value(void) { return 2; }\n",
    )
    external_object_path = tmp_path / "external-object.o"
    subprocess.run(
        [
            "cc",
            "-fPIC",
            "-c",
            str(external_object_source),
            "-o",
            str(external_object_path),
        ],
        check=True,
    )

    external_archive_source = _write_source(
        tmp_path / "external-archive.c",
        "int external_archive_value(void) { return 8; }\n",
    )
    external_archive_object = tmp_path / "external-archive.o"
    external_archive_path = tmp_path / "libexternal-archive.a"
    subprocess.run(
        [
            "cc",
            "-fPIC",
            "-c",
            str(external_archive_source),
            "-o",
            str(external_archive_object),
        ],
        check=True,
    )
    subprocess.run(
        ["ar", "rcs", str(external_archive_path), str(external_archive_object)],
        check=True,
    )

    external_shared_source = _write_source(
        tmp_path / "external-shared.c",
        "int external_shared_value(void) { return 32; }\n",
    )
    suffix = context.toolchain.shared_library_suffix
    external_shared_path = tmp_path / f"libexternal-shared{suffix}"
    if sys.platform == "darwin":
        shared_options = [
            "-dynamiclib",
            "-Wl,-install_name,@rpath/" + external_shared_path.name,
        ]
    else:
        shared_options = ["-shared", "-Wl,-soname," + external_shared_path.name]
    subprocess.run(
        [
            "cc",
            "-fPIC",
            *shared_options,
            str(external_shared_source),
            "-o",
            str(external_shared_path),
        ],
        check=True,
    )

    return (
        ExternalObject(external_object_path, pic=True),
        ExternalArchive(external_archive_path, pic=True),
        ExternalSharedLibrary(external_shared_path),
    )


def _declare_complete_library(tmp_path: Path) -> tuple[BuildContext, SharedLibrary]:
    context = BuildContext(tmp_path / "build")
    external_object, external_archive, external_shared = _create_external_inputs(
        tmp_path, context
    )

    direct_source = _write_source(
        tmp_path / "direct.c",
        "int direct_value(void) { return 1; }\n",
    )
    archive_source = _write_source(
        tmp_path / "archive.c",
        "int archive_value(void) { return 4; }\n",
    )
    shared_source = _write_source(
        tmp_path / "shared.c",
        "int shared_value(void) { return 16; }\n",
    )
    api_source = _write_source(
        tmp_path / "api.c",
        "#include <math.h>\n"
        "int direct_value(void);\n"
        "int external_object_value(void);\n"
        "int archive_value(void);\n"
        "int external_archive_value(void);\n"
        "int shared_value(void);\n"
        "int external_shared_value(void);\n"
        "double xtc_build_input = 4096.0;\n"
        "int combined_value(void) {\n"
        "  return direct_value() + external_object_value() + archive_value()\n"
        "    + external_archive_value() + shared_value()\n"
        "    + external_shared_value() + (int)sqrt(xtc_build_input);\n"
        "}\n",
    )

    direct_object = Object("direct", direct_source, pic=True)
    archive_object = Object("archive", archive_source, pic=True)
    built_archive = Archive("built", objects=[archive_object])
    shared_object = Object("shared", shared_source, pic=True)
    built_shared = SharedLibrary("built-dependency", objects=[shared_object])
    api_object = Object("api", api_source, pic=True)
    system_math = ExternalLibrary("math", link_flags=["-lm"])
    library = SharedLibrary(
        "complete",
        objects=[api_object, direct_object, external_object],
        archives=[built_archive, external_archive],
        libraries=[built_shared, external_shared, system_math],
    )
    return context, library


@pytest.mark.parametrize("backend", ["immediate", "makefile"])
def test_complete_shared_library_build_and_load(
    tmp_path: Path, backend: Backend
) -> None:
    context, library = _declare_complete_library(tmp_path)

    if backend == "immediate":
        library.build(context)
    else:
        makefile = context.write_makefile(tmp_path / "Makefile", targets=[library])
        subprocess.run(["make", "-f", str(makefile)], check=True, cwd=tmp_path)

    loaded = ctypes.CDLL(str(library.output(context)))
    loaded.combined_value.restype = ctypes.c_int
    assert loaded.combined_value() == 127
