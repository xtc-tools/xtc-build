from __future__ import annotations

import ctypes
import subprocess
from pathlib import Path

from xtc_build import (
    Archive,
    BuildContext,
    ExternalArchive,
    ExternalObject,
    ExternalSharedLibrary,
    Object,
    SharedLibrary,
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
    context = BuildContext(tmp_path / "build")
    return context, helper, core, library


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
    context = BuildContext(tmp_path / "build")

    graph = context.graph(dependent)
    assert base in graph.dependencies(dependent)
    assert str(base.output(context)) in graph.command(dependent).argv

    rebuilt = context.build(dependent)
    assert rebuilt[-2:] == (base, dependent)
    loaded = ctypes.CDLL(str(dependent.output(context)))
    loaded.dependent_value.restype = ctypes.c_int
    assert loaded.dependent_value() == 42


def test_external_shared_library_is_an_input_only_dependency(tmp_path: Path) -> None:
    base_source = tmp_path / "external-base.c"
    base_source.write_text(
        "int external_base(void) { return 40; }\n",
        encoding="utf-8",
    )
    context = BuildContext(tmp_path / "build")
    base_object = Object("external-base", base_source, pic=True)
    base = SharedLibrary("external-base", objects=[base_object])
    base.build(context)

    dependent_source = tmp_path / "external-dependent.c"
    dependent_source.write_text(
        "int external_base(void);\n"
        "int external_dependent(void) { return external_base() + 2; }\n",
        encoding="utf-8",
    )
    dependent_object = Object("external-dependent", dependent_source, pic=True)
    external = ExternalSharedLibrary(base.output(context))
    dependent = SharedLibrary(
        "external-dependent",
        objects=[dependent_object],
        libraries=[external],
    )

    graph = context.graph(dependent)
    assert external.name == str(base.output(context))
    assert graph.topological_order() == (dependent_object, dependent)
    assert external.output(context) in graph.command(dependent).inputs

    dependent.build(context)
    loaded = ctypes.CDLL(str(dependent.output(context)))
    loaded.external_dependent.restype = ctypes.c_int
    assert loaded.external_dependent() == 42


def test_external_objects_and_archives_are_input_only(tmp_path: Path) -> None:
    helper_source = tmp_path / "external-helper.c"
    helper_source.write_text(
        "int external_helper(void) { return 40; }\n", encoding="utf-8"
    )
    object_path = tmp_path / "external-helper.o"
    subprocess.run(
        ["cc", "-fPIC", "-c", str(helper_source), "-o", str(object_path)],
        check=True,
    )

    context = BuildContext(tmp_path / "build")
    external_object = ExternalObject(object_path, pic=True)
    archive = Archive("external", objects=[external_object])
    assert external_object.name == str(object_path)
    assert context.graph(archive).topological_order() == (archive,)
    assert object_path in graph_command_inputs(context, archive)
    archive.build(context)

    api_source = tmp_path / "external-api.c"
    api_source.write_text(
        "int external_helper(void);\n"
        "int external_answer(void) { return external_helper() + 2; }\n",
        encoding="utf-8",
    )
    api = Object("external-api", api_source, pic=True)
    external_archive = ExternalArchive(archive.output(context), pic=True)
    library = SharedLibrary(
        "external-answer",
        objects=[api],
        archives=[external_archive],
    )
    assert external_archive.name == str(archive.output(context))
    assert context.graph(library).topological_order() == (api, library)
    assert external_archive.output(context) in graph_command_inputs(context, library)

    library.build(context)
    loaded = ctypes.CDLL(str(library.output(context)))
    loaded.external_answer.restype = ctypes.c_int
    assert loaded.external_answer() == 42


def graph_command_inputs(
    context: BuildContext, target: Archive | SharedLibrary
) -> tuple[Path, ...]:
    return context.graph(target).command(target).inputs


def test_changed_command_rebuilds_an_existing_output(tmp_path: Path) -> None:
    source = tmp_path / "value.c"
    source.write_text("int value(void) { return VALUE; }\n", encoding="utf-8")
    context = BuildContext(tmp_path / "build")
    initial = Object("value", source, defines=["VALUE=1"])
    changed = Object("value", source, defines=["VALUE=2"])

    context.build(initial)
    assert context.build(changed) == (changed,)


def test_generated_makefile_builds_the_same_graph(tmp_path: Path) -> None:
    context, _, _, library = declarations(tmp_path)
    makefile = context.write_makefile(tmp_path / "build.mk", targets=[library])

    text = makefile.read_text(encoding="utf-8")
    assert "libanswer" in text
    assert "-include" in text

    subprocess.run(["make", "-f", str(makefile)], check=True, cwd=tmp_path)
    loaded = ctypes.CDLL(str(library.output(context)))
    assert loaded.answer() == 42
