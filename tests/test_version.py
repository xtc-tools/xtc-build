from importlib.metadata import PackageNotFoundError

import pytest

import xtc_build._version as version_module


def test_version_comes_from_installed_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    def installed_version(_name: str) -> str:
        return "1.2.3"

    monkeypatch.setattr(version_module, "version", installed_version)

    assert version_module.resolve_version() == "1.2.3"


def test_version_falls_back_outside_an_install(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing_version(_name: str) -> str:
        raise PackageNotFoundError

    monkeypatch.setattr(version_module, "version", missing_version)

    assert version_module.resolve_version() == "0.0.0"
