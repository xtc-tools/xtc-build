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
