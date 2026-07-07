from __future__ import annotations

import json
import os
import subprocess
import sys


def test_cli_noninteractive_smoke_outputs_ast_json(repo_root) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")

    completed = subprocess.run(
        [sys.executable, "main.py", "text.txt", "--format", "txt"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["format"] == "txt"
    assert payload["root_entity"] == "page"
    assert payload["root"]["entity"] == "document"
