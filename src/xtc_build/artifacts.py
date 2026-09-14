"""Declarative C build artifacts."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING

from .command import Command

if TYPE_CHECKING:
    from .context import BuildContext

Pathish = str | PathLike[str]


def _validate_name(name: str) -> None:
    path = Path(name)
    if not name or path.is_absolute() or ".." in path.parts or name in {".", ".."}:
        raise ValueError(f"invalid artifact name: {name!r}")


@dataclass(frozen=True)
class ExternalLibrary:
    """An already-built library represented by its linker arguments."""

    name: str
    link_flags: Sequence[str] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("an external library needs a name")
        object.__setattr__(self, "link_flags", tuple(self.link_flags))


@dataclass(frozen=True)
class Object:
    """One C translation unit compiled to an object file."""

    name: str
    source: Pathish
    inputs: Sequence[Pathish] = ()
    includes: Sequence[Pathish] = ()
    defines: Sequence[str] = ()
    compile_flags: Sequence[str] = ()
    pic: bool = False

    def __post_init__(self) -> None:
        _validate_name(self.name)
        object.__setattr__(self, "source", Path(self.source))
        object.__setattr__(self, "inputs", tuple(Path(p) for p in self.inputs))
        object.__setattr__(self, "includes", tuple(Path(p) for p in self.includes))
        object.__setattr__(self, "defines", tuple(self.defines))
        object.__setattr__(self, "compile_flags", tuple(self.compile_flags))

    def dependencies(self) -> tuple[Artifact, ...]:
        return ()

    def output(self, context: BuildContext) -> Path:
        return context.toolchain.object_output(self, context)

    def depfile(self, context: BuildContext) -> Path:
        return self.output(context).with_suffix(self.output(context).suffix + ".d")

    def command(self, context: BuildContext) -> Command:
        return context.toolchain.object_command(self, context)

    def build(self, context: BuildContext) -> Path:
        context.build(self)
        return self.output(context)


@dataclass(frozen=True)
class Archive:
    """A static archive composed of object files."""

    name: str
    objects: Sequence[Object]
    archive_flags: Sequence[str] = ()

    def __post_init__(self) -> None:
        _validate_name(self.name)
        object.__setattr__(self, "objects", tuple(self.objects))
        object.__setattr__(self, "archive_flags", tuple(self.archive_flags))

    def dependencies(self) -> tuple[Artifact, ...]:
        return tuple(self.objects)

    def output(self, context: BuildContext) -> Path:
        return context.toolchain.archive_output(self, context)

    def command(self, context: BuildContext) -> Command:
        return context.toolchain.archive_command(self, context)

    def build(self, context: BuildContext) -> Path:
        context.build(self)
        return self.output(context)


@dataclass(frozen=True)
class SharedLibrary:
    """A shared library linked from objects, archives, and libraries."""

    name: str
    objects: Sequence[Object] = ()
    archives: Sequence[Archive] = ()
    libraries: Sequence[ExternalLibrary | SharedLibrary] = ()
    link_flags: Sequence[str] = ()
    require_pic: bool = True

    def __post_init__(self) -> None:
        _validate_name(self.name)
        object.__setattr__(self, "objects", tuple(self.objects))
        object.__setattr__(self, "archives", tuple(self.archives))
        object.__setattr__(self, "libraries", tuple(self.libraries))
        object.__setattr__(self, "link_flags", tuple(self.link_flags))
        if self.require_pic:
            objects = (
                *self.objects,
                *(obj for archive in self.archives for obj in archive.objects),
            )
            non_pic = [obj.name for obj in objects if not obj.pic]
            if non_pic:
                names = ", ".join(non_pic)
                raise ValueError(
                    f"shared library {self.name!r} requires PIC objects: {names}"
                )

    def dependencies(self) -> tuple[Artifact, ...]:
        built_libraries = tuple(
            dependency
            for dependency in self.libraries
            if isinstance(dependency, SharedLibrary)
        )
        return (*self.objects, *self.archives, *built_libraries)

    def output(self, context: BuildContext) -> Path:
        return context.toolchain.shared_library_output(self, context)

    def command(self, context: BuildContext) -> Command:
        return context.toolchain.shared_library_command(self, context)

    def build(self, context: BuildContext) -> Path:
        context.build(self)
        return self.output(context)


Artifact = Object | Archive | SharedLibrary
