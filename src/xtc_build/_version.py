"""Runtime package version lookup."""

from importlib.metadata import PackageNotFoundError, version


def resolve_version() -> str:
    """Return installed package metadata or a source-checkout fallback."""

    try:
        return version("xtc-build")
    except PackageNotFoundError:
        return "0.0.0"
