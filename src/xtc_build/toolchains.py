"""Compiler and archiver command generation."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .artifacts import (
    Archive,
    ExternalLibrary,
    ExternalSharedLibrary,
    Object,
    SharedLibrary,
)
from .command import Command

if TYPE_CHECKING:
    from .context import BuildContext


@dataclass(frozen=True)
class GnuToolchain:
    """A GCC- or Clang-compatible C toolchain using system tools by default."""

    cc: str = "cc"
    ar: str = "ar"

    @property
    def object_suffix(self) -> str:
        return ".o"

    @property
    def archive_suffix(self) -> str:
        return ".a"

    @property
    def shared_library_suffix(self) -> str:
        if sys.platform == "darwin":
            return ".dylib"
        if sys.platform == "win32":
            return ".dll"
        return ".so"

    def object_output(self, obj: Object, context: BuildContext) -> Path:
        return Path(context.build_dir) / f"{obj.name}{self.object_suffix}"

    def archive_output(self, archive: Archive, context: BuildContext) -> Path:
        return Path(context.build_dir) / f"lib{archive.name}{self.archive_suffix}"

    def shared_library_output(
        self, library: SharedLibrary, context: BuildContext
    ) -> Path:
        prefix = "" if sys.platform == "win32" else "lib"
        return (
            Path(context.build_dir)
            / f"{prefix}{library.name}{self.shared_library_suffix}"
        )

    def object_command(self, obj: Object, context: BuildContext) -> Command:
        output = self.object_output(obj, context)
        argv = [self.cc]
        argv.extend(obj.compile_flags)
        if obj.pic and sys.platform != "win32":
            argv.append("-fPIC")
        argv.extend(f"-I{path}" for path in obj.includes)
        argv.extend(f"-D{definition}" for definition in obj.defines)
        argv.extend(
            [
                "-MMD",
                "-MP",
                "-MF",
                str(obj.depfile(context)),
                "-c",
                str(obj.source),
                "-o",
                str(output),
            ]
        )
        return Command(
            argv=tuple(argv),
            inputs=(Path(obj.source), *(Path(path) for path in obj.inputs)),
            outputs=(output,),
        )

    def archive_command(self, archive: Archive, context: BuildContext) -> Command:
        output = self.archive_output(archive, context)
        inputs = tuple(obj.output(context) for obj in archive.objects)
        return Command(
            argv=(
                self.ar,
                *archive.archive_flags,
                "rcs",
                str(output),
                *(str(p) for p in inputs),
            ),
            inputs=inputs,
            outputs=(output,),
            # ar replaces named members but does not remove obsolete ones when
            # an archive's declaration changes.
            remove_outputs_first=True,
        )

    def shared_library_command(
        self, library: SharedLibrary, context: BuildContext
    ) -> Command:
        output = self.shared_library_output(library, context)
        artifact_inputs = (
            *(obj.output(context) for obj in library.objects),
            *(archive.output(context) for archive in library.archives),
            *(
                dependency.output(context)
                for dependency in library.libraries
                if not isinstance(dependency, ExternalLibrary)
            ),
        )
        argv = [self.cc]
        argv.append("-dynamiclib" if sys.platform == "darwin" else "-shared")
        argv.extend(["-o", str(output)])
        argv.extend(str(obj.output(context)) for obj in library.objects)
        argv.extend(str(archive.output(context)) for archive in library.archives)
        runtime_paths: list[Path] = []
        for dependency in library.libraries:
            if isinstance(dependency, ExternalLibrary):
                argv.extend(dependency.link_flags)
            else:
                argv.append(str(dependency.output(context)))
                if (
                    isinstance(dependency, ExternalSharedLibrary)
                    and sys.platform != "win32"
                ):
                    runtime_path = dependency.output(context).resolve().parent
                    if runtime_path not in runtime_paths:
                        runtime_paths.append(runtime_path)
        argv.extend(f"-Wl,-rpath,{path}" for path in runtime_paths)
        argv.extend(library.link_flags)
        return Command(
            argv=tuple(argv),
            inputs=artifact_inputs,
            outputs=(output,),
        )
