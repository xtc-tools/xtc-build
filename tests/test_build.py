from __future__ import annotations

import ctypes
import shutil
import subprocess
from pathlib import Path

import pytest

from xtc_build import Archive, BuildContext, GnuToolchain, Object, SharedLibrary

HAS_TOOLCHAIN = bool(shutil.which("gcc") and shutil.which("ar"))
requires_toolchain = pytest.mark.skipif(
    not HAS_TOOLCHAIN, reason="GCC and ar are required"
)


def declarations(
    tmp_path: Path,
) -> tuple[BuildContext, Object, Archive, SharedLibrary]:
    helper_source = tmp_path / "helper.c"
    api_source = tmp_path / "api.c"
    helper_source.write_text("int helper(void) { return 40; }\n", encoding="utf-8")
    api_source.write_text(
        "int helper(void);\nint answer(void) { return helper() + 2; }\n",
        encoding="utf-8",
    )

    helper = Object("helper", helper_source, pic=True)
    api = Object("api", api_source, pic=True)
    core = Archive("core", [helper])
    library = SharedLibrary("answer", objects=[api], archives=[core])
    context = BuildContext(
        tmp_path / "build",
        toolchain=GnuToolchain(
            cc=shutil.which("gcc") or "gcc", ar=shutil.which("ar") or "ar"
        ),
    )
    return context, helper, core, library


@requires_toolchain
def test_each_artifact_can_be_built_and_shared_library_can_be_loaded(
    tmp_path: Path,
) -> None:
    context, helper, core, library = declarations(tmp_path)

    assert context.build(helper) == (helper,)
    assert helper.output(context).is_file()
    assert context.build(helper) == ()

    assert context.build(core) == (core,)
    assert core.output(context).is_file()

    rebuilt = context.build(library)
    assert rebuilt[-1] == library
    loaded = ctypes.CDLL(str(library.output(context)))
    loaded.answer.restype = ctypes.c_int
    assert loaded.answer() == 42


@requires_toolchain
def test_artifacts_build_themselves_and_return_their_outputs(tmp_path: Path) -> None:
    context, helper, core, library = declarations(tmp_path)

    assert helper.build(context) == helper.output(context)
    assert helper.output(context).is_file()

    assert core.build(context) == core.output(context)
    assert core.output(context).is_file()

    assert library.build(context) == library.output(context)
    assert library.output(context).is_file()
    loaded = ctypes.CDLL(str(library.output(context)))
    assert loaded.answer() == 42


@requires_toolchain
def test_shared_library_can_depend_on_built_shared_library(tmp_path: Path) -> None:
    base_source = tmp_path / "base.c"
    dependent_source = tmp_path / "dependent.c"
    base_source.write_text("int base_value(void) { return 40; }\n", encoding="utf-8")
    dependent_source.write_text(
        "int base_value(void);\n"
        "int dependent_value(void) { return base_value() + 2; }\n",
        encoding="utf-8",
    )
    base_object = Object("base", base_source, pic=True)
    dependent_object = Object("dependent", dependent_source, pic=True)
    base = SharedLibrary("base", objects=[base_object])
    dependent = SharedLibrary(
        "dependent",
        objects=[dependent_object],
        libraries=[base],
    )
    context = BuildContext(
        tmp_path / "build",
        toolchain=GnuToolchain(cc="gcc", ar="ar"),
    )

    graph = context.graph(dependent)
    assert base in graph.dependencies(dependent)
    assert str(base.output(context)) in graph.command(dependent).argv

    rebuilt = context.build(dependent)
    assert rebuilt[-2:] == (base, dependent)
    loaded = ctypes.CDLL(str(dependent.output(context)))
    loaded.dependent_value.restype = ctypes.c_int
    assert loaded.dependent_value() == 42


@requires_toolchain
def test_changed_command_rebuilds_an_existing_output(tmp_path: Path) -> None:
    source = tmp_path / "value.c"
    source.write_text("int value(void) { return VALUE; }\n", encoding="utf-8")
    context = BuildContext(tmp_path / "build", GnuToolchain(cc="gcc", ar="ar"))
    initial = Object("value", source, defines=["VALUE=1"])
    changed = Object("value", source, defines=["VALUE=2"])

    context.build(initial)
    assert context.build(changed) == (changed,)


@requires_toolchain
@pytest.mark.skipif(not shutil.which("make"), reason="make is required")
def test_generated_makefile_builds_the_same_graph(tmp_path: Path) -> None:
    context, _, _, library = declarations(tmp_path)
    makefile = context.write_makefile(tmp_path / "build.mk", targets=[library])

    text = makefile.read_text(encoding="utf-8")
    assert "libanswer" in text
    assert "-include" in text

    subprocess.run(["make", "-f", str(makefile)], check=True, cwd=tmp_path)
    loaded = ctypes.CDLL(str(library.output(context)))
    assert loaded.answer() == 42
