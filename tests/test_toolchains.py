from pathlib import Path

import pytest

import xtc_build.toolchains as toolchains
from xtc_build import (
    Archive,
    BuildContext,
    ExternalSharedLibrary,
    GnuToolchain,
    Object,
    SharedLibrary,
)


def test_default_toolchain_uses_system_c_tools(tmp_path: Path) -> None:
    context = BuildContext(tmp_path)
    obj = Object("member", "member.c")
    archive = Archive("example", objects=[obj])

    assert obj.command(context).argv[0] == "cc"
    assert archive.command(context).argv[0] == "ar"


def test_context_defaults_and_artifact_overrides(tmp_path: Path) -> None:
    context = BuildContext(
        tmp_path,
        compile_flags='-O2 "-DDEFAULT FLAG"',
        link_flags="-Wl,--default-link",
        defines=["CONTEXT=1"],
    )
    obj = Object(
        "member",
        "member.c",
        defines=["OBJECT=2"],
        compile_flags="-Wall",
        pic=True,
    )
    object_argv = obj.command(context).argv
    assert object_argv.index("-O2") < object_argv.index("-Wall")
    assert object_argv.index("-DCONTEXT=1") < object_argv.index("-DOBJECT=2")
    assert "-DDEFAULT FLAG" in object_argv

    overriding = Object(
        "overriding",
        "overriding.c",
        defines=["OBJECT=2"],
        compile_flags="-Wall",
        override_flags=True,
        override_defines=True,
    )
    overriding_argv = overriding.command(context).argv
    assert "-O2" not in overriding_argv
    assert "-DCONTEXT=1" not in overriding_argv
    assert "-Wall" in overriding_argv
    assert "-DOBJECT=2" in overriding_argv

    library = SharedLibrary("example", objects=[obj], link_flags="-Wl,--artifact-link")
    library_argv = library.command(context).argv
    assert library_argv.index("-Wl,--default-link") < library_argv.index(
        "-Wl,--artifact-link"
    )

    overriding_library = SharedLibrary(
        "overriding",
        objects=[obj],
        link_flags="-Wl,--artifact-link",
        override_flags=True,
    )
    overriding_library_argv = overriding_library.command(context).argv
    assert "-Wl,--default-link" not in overriding_library_argv
    assert "-Wl,--artifact-link" in overriding_library_argv


def test_linux_shared_library_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(toolchains.sys, "platform", "linux")
    context = BuildContext(tmp_path, GnuToolchain())
    obj = Object("member", "member.c", pic=True)
    external_dir = tmp_path / "external"
    first = ExternalSharedLibrary(external_dir / "libfirst.so")
    second = ExternalSharedLibrary(external_dir / "libsecond.so")
    library = SharedLibrary("example", objects=[obj], libraries=[first, second])

    assert library.output(context).name == "libexample.so"
    command = library.command(context)
    assert "-shared" in command.argv
    assert command.argv.count(f"-Wl,-rpath,{external_dir.resolve()}") == 1


def test_darwin_shared_library_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(toolchains.sys, "platform", "darwin")
    context = BuildContext(tmp_path, GnuToolchain())
    obj = Object("member", "member.c", pic=True)
    external = ExternalSharedLibrary(tmp_path / "libexternal.dylib")
    library = SharedLibrary("example", objects=[obj], libraries=[external])

    assert library.output(context).name == "libexample.dylib"
    command = library.command(context)
    assert "-dynamiclib" in command.argv
    assert f"-Wl,-rpath,{tmp_path.resolve()}" in command.argv


def test_windows_outputs_and_pic_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(toolchains.sys, "platform", "win32")
    context = BuildContext(tmp_path, GnuToolchain())
    obj = Object("member", "member.c", pic=True)
    external = ExternalSharedLibrary(tmp_path / "external.dll")
    library = SharedLibrary("example", objects=[obj], libraries=[external])

    assert library.output(context).name == "example.dll"
    assert "-fPIC" not in obj.command(context).argv
    assert not any(
        arg.startswith("-Wl,-rpath,") for arg in library.command(context).argv
    )
