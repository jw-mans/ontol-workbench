#!/usr/bin/env python3
"""Run the Ontol v3 test suite only."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
GRAPHVIZ_BIN = Path(r"C:\Program Files\Graphviz\bin")


def main() -> int:
    env = os.environ.copy()
    env.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")

    if GRAPHVIZ_BIN.exists():
        env["PATH"] = str(GRAPHVIZ_BIN) + os.pathsep + env.get("PATH", "")

    cmd = [sys.executable, "-m", "pytest", "tests", *sys.argv[1:]]
    return subprocess.call(cmd, cwd=ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
