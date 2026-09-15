"""Small declarative C build graphs for Python."""

from ._version import resolve_version
from .artifacts import Archive, ExternalLibrary, Object, SharedLibrary
from .command import Command
from .context import BuildContext
from .graph import BuildGraph, DependencyCycleError
from .toolchains import GnuToolchain

__all__ = [
    "Archive",
    "BuildContext",
    "BuildGraph",
    "Command",
    "DependencyCycleError",
    "ExternalLibrary",
    "GnuToolchain",
    "Object",
    "SharedLibrary",
]

__version__ = resolve_version()
