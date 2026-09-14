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
