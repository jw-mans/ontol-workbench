from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from uml_dsl.graphviz_render import DEFAULT_DOT_PATH


GRAPHVIZ_BIN = Path(DEFAULT_DOT_PATH).parent


def pytest_configure() -> None:
    if GRAPHVIZ_BIN.exists() and not shutil.which("dot"):
        os.environ["PATH"] = str(GRAPHVIZ_BIN) + os.pathsep + os.environ.get("PATH", "")


def has_dot() -> bool:
    return bool(shutil.which("dot") or Path(DEFAULT_DOT_PATH).exists())


@pytest.fixture
def require_dot() -> None:
    if not has_dot():
        pytest.skip("Graphviz dot is required for SVG rendering tests")
