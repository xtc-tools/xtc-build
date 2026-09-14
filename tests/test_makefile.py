from dataclasses import replace
from pathlib import Path

from xtc_build import BuildContext, Command, GnuToolchain, Object


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
