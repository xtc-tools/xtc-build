import shutil

import pytest


@pytest.fixture(scope="session", autouse=True)
def require_build_tools() -> None:
    missing = [
        tool for tool in ("cc", "ar", "make", "ninja") if shutil.which(tool) is None
    ]
    if missing:
        pytest.fail(f"required build tools not found: {', '.join(missing)}")
