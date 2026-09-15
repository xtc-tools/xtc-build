from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from xtc_build import BuildContext, Command, GnuToolchain, Object


class NoOutputToolchain(GnuToolchain):
    def object_command(self, obj: Object, context: BuildContext) -> Command:
        return Command(
            argv=(sys.executable, "-c", "pass"),
            inputs=(Path(obj.source),),
            outputs=(obj.output(context),),
        )


class MetadataExecutionToolchain(GnuToolchain):
    def object_command(self, obj: Object, context: BuildContext) -> Command:
        output = obj.output(context).resolve()
        script = (
            "import os; from pathlib import Path; "
            f"Path({str(output)!r}).write_text("
            "os.environ['XTC_BUILD_TEST'] + ':' + str(Path.cwd()))"
        )
        return Command(
            argv=(sys.executable, "-c", script),
            inputs=(Path(obj.source),),
            outputs=(output,),
            cwd=Path(context.build_dir) / "working-directory",
            env={"XTC_BUILD_TEST": "environment"},
        )


def test_command_requires_an_argv_and_output() -> None:
    with pytest.raises(ValueError, match="at least one argument"):
        Command(argv=(), inputs=(), outputs=(Path("output"),))
    with pytest.raises(ValueError, match="at least one output"):
        Command(argv=("command",), inputs=(), outputs=())


def test_executor_reports_a_missing_initial_input(tmp_path: Path) -> None:
    context = BuildContext(tmp_path / "build")
    obj = Object("missing", tmp_path / "missing.c")

    with pytest.raises(FileNotFoundError, match="build input does not exist"):
        context.build(obj)


def test_executor_reports_an_input_removed_after_build(tmp_path: Path) -> None:
    source = tmp_path / "source.c"
    source.write_text("int value;\n", encoding="utf-8")
    context = BuildContext(tmp_path / "build")
    obj = Object("source", source)
    context.build(obj)
    source.unlink()

    with pytest.raises(FileNotFoundError, match="build input does not exist"):
        context.build(obj)


def test_executor_recovers_from_a_corrupt_signature(tmp_path: Path) -> None:
    source = tmp_path / "source.c"
    source.write_text("int value;\n", encoding="utf-8")
    context = BuildContext(tmp_path / "build")
    obj = Object("source", source)
    context.build(obj)
    signature = obj.output(context).with_name("source.o.xtc-build.json")
    signature.write_text("not JSON", encoding="utf-8")

    assert context.build(obj) == (obj,)


def test_executor_rebuilds_when_an_input_is_newer(tmp_path: Path) -> None:
    source = tmp_path / "source.c"
    source.write_text("int value;\n", encoding="utf-8")
    context = BuildContext(tmp_path / "build")
    obj = Object("source", source)
    context.build(obj)
    output_time = obj.output(context).stat().st_mtime_ns
    os.utime(source, ns=(output_time + 1, output_time + 1))

    assert context.build(obj) == (obj,)


def test_executor_requires_commands_to_create_their_outputs(tmp_path: Path) -> None:
    source = tmp_path / "source.c"
    source.write_text("int value;\n", encoding="utf-8")
    context = BuildContext(tmp_path / "build", NoOutputToolchain())
    obj = Object("source", source)

    with pytest.raises(RuntimeError, match="expected output"):
        context.build(obj)


def test_executor_applies_command_environment_and_cwd(tmp_path: Path) -> None:
    source = tmp_path / "source.c"
    source.write_text("unused\n", encoding="utf-8")
    context = BuildContext(tmp_path / "build", MetadataExecutionToolchain())
    working_directory = Path(context.build_dir) / "working-directory"
    working_directory.mkdir(parents=True)
    obj = Object("metadata", source)

    context.build(obj)

    assert obj.output(context).read_text(encoding="utf-8") == (
        f"environment:{working_directory.resolve()}"
    )
