"""Small declarative C build graphs for Python."""

from importlib.metadata import PackageNotFoundError, version

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

try:
    __version__ = version("xtc-build")
except PackageNotFoundError:
    # The package may be imported directly from a source checkout.
    __version__ = "0.0.0"
