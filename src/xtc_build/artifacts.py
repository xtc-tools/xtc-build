"""Declarative C build artifacts."""

from __future__ import annotations

import shlex
from collections.abc import Sequence
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING

from .command import Command

if TYPE_CHECKING:
    from .context import BuildContext

Pathish = str | PathLike[str]
Arguments = str | Sequence[str]


def normalize_arguments(value: Arguments) -> tuple[str, ...]:
    return tuple(shlex.split(value) if isinstance(value, str) else value)


def _validate_name(name: str) -> None:
    path = Path(name)
    if not name or path.is_absolute() or ".." in path.parts or name in {".", ".."}:
        raise ValueError(f"invalid artifact name: {name!r}")


@dataclass(frozen=True)
class ExternalLibrary:
    """An already-built library represented by its linker arguments."""

    name: str
    link_flags: Arguments = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("an external library needs a name")
        object.__setattr__(self, "link_flags", normalize_arguments(self.link_flags))


@dataclass(frozen=True)
class ExternalSharedLibrary:
    """A shared library file produced outside this build graph."""

    path: Pathish

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", Path(self.path))

    @property
    def name(self) -> str:
        return str(self.path)

    def output(self, context: BuildContext) -> Path:
        return Path(self.path)


@dataclass(frozen=True)
class ExternalObject:
    """An object file produced outside this build graph."""

    path: Pathish
    pic: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", Path(self.path))

    @property
    def name(self) -> str:
        return str(self.path)

    def output(self, context: BuildContext) -> Path:
        return Path(self.path)


@dataclass(frozen=True)
class Object:
    """One C translation unit compiled to an object file."""

    name: str
    source: Pathish
    inputs: Sequence[Pathish] = ()
    includes: Sequence[Pathish] = ()
    defines: Sequence[str] = ()
    compile_flags: Arguments = ()
    override_flags: bool = False
    override_defines: bool = False
    pic: bool = False

    def __post_init__(self) -> None:
        _validate_name(self.name)
        object.__setattr__(self, "source", Path(self.source))
        object.__setattr__(self, "inputs", tuple(Path(p) for p in self.inputs))
        object.__setattr__(self, "includes", tuple(Path(p) for p in self.includes))
        object.__setattr__(self, "defines", tuple(self.defines))
        object.__setattr__(
            self, "compile_flags", normalize_arguments(self.compile_flags)
        )

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
class ExternalArchive:
    """A static archive produced outside this build graph."""

    path: Pathish
    pic: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", Path(self.path))

    @property
    def name(self) -> str:
        return str(self.path)

    def output(self, context: BuildContext) -> Path:
        return Path(self.path)


@dataclass(frozen=True)
class Archive:
    """A static archive composed of object files."""

    name: str
    objects: Sequence[Object | ExternalObject]
    archive_flags: Arguments = ()

    def __post_init__(self) -> None:
        _validate_name(self.name)
        object.__setattr__(self, "objects", tuple(self.objects))
        object.__setattr__(
            self, "archive_flags", normalize_arguments(self.archive_flags)
        )

    def dependencies(self) -> tuple[Artifact, ...]:
        return tuple(obj for obj in self.objects if isinstance(obj, Object))

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
    objects: Sequence[Object | ExternalObject] = ()
    archives: Sequence[Archive | ExternalArchive] = ()
    libraries: Sequence[ExternalLibrary | ExternalSharedLibrary | SharedLibrary] = ()
    link_flags: Arguments = ()
    override_flags: bool = False
    require_pic: bool = True

    def __post_init__(self) -> None:
        _validate_name(self.name)
        object.__setattr__(self, "objects", tuple(self.objects))
        object.__setattr__(self, "archives", tuple(self.archives))
        object.__setattr__(self, "libraries", tuple(self.libraries))
        object.__setattr__(self, "link_flags", normalize_arguments(self.link_flags))
        if self.require_pic:
            pic_inputs: list[Object | ExternalObject | ExternalArchive] = list(
                self.objects
            )
            for archive in self.archives:
                if isinstance(archive, Archive):
                    pic_inputs.extend(archive.objects)
                else:
                    pic_inputs.append(archive)
            non_pic = [item.name for item in pic_inputs if not item.pic]
            if non_pic:
                names = ", ".join(non_pic)
                raise ValueError(
                    f"shared library {self.name!r} requires PIC objects: {names}"
                )

    def dependencies(self) -> tuple[Artifact, ...]:
        built_objects = tuple(obj for obj in self.objects if isinstance(obj, Object))
        built_archives = tuple(
            archive for archive in self.archives if isinstance(archive, Archive)
        )
        built_libraries = tuple(
            dependency
            for dependency in self.libraries
            if isinstance(dependency, SharedLibrary)
        )
        return (*built_objects, *built_archives, *built_libraries)

    def output(self, context: BuildContext) -> Path:
        return context.toolchain.shared_library_output(self, context)

    def command(self, context: BuildContext) -> Command:
        return context.toolchain.shared_library_command(self, context)

    def build(self, context: BuildContext) -> Path:
        context.build(self)
        return self.output(context)


Artifact = Object | Archive | SharedLibrary
