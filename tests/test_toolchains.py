from pathlib import Path

import pytest

import xtc_build.toolchains as toolchains
from xtc_build import BuildContext, GnuToolchain, Object, SharedLibrary


def test_darwin_shared_library_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(toolchains.sys, "platform", "darwin")
    context = BuildContext(tmp_path, GnuToolchain())
    obj = Object("member", "member.c", pic=True)
    library = SharedLibrary("example", objects=[obj])

    assert library.output(context).name == "libexample.dylib"
    assert "-dynamiclib" in library.command(context).argv


def test_windows_outputs_and_pic_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(toolchains.sys, "platform", "win32")
    context = BuildContext(tmp_path, GnuToolchain())
    obj = Object("member", "member.c", pic=True)
    library = SharedLibrary("example", objects=[obj])

    assert library.output(context).name == "example.dll"
    assert "-fPIC" not in obj.command(context).argv
