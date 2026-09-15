"""Small declarative C build graphs for Python."""

from ._version import resolve_version
from .artifacts import (
    Archive,
    Arguments,
    ExternalArchive,
    ExternalLibrary,
    ExternalObject,
    ExternalSharedLibrary,
    Object,
    SharedLibrary,
)
from .command import Command
from .context import BuildContext
from .graph import BuildGraph, DependencyCycleError
from .toolchains import GnuToolchain

__all__ = [
    "Archive",
    "Arguments",
    "BuildContext",
    "BuildGraph",
    "Command",
    "DependencyCycleError",
    "ExternalArchive",
    "ExternalLibrary",
    "ExternalObject",
    "ExternalSharedLibrary",
    "GnuToolchain",
    "Object",
    "SharedLibrary",
]

__version__ = resolve_version()
