"""Small standard-library helpers shared by release validation entrypoints."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


RELEASE_CONTRACT_RELATIVE = Path("openspec/verification-contract.yaml")


def run(command: list[str], *, cwd: Path, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    resolved = list(command)
    executable = shutil.which(resolved[0])
    if executable is None and os.name == "nt":
        executable = shutil.which(resolved[0] + ".cmd") or shutil.which(resolved[0] + ".exe")
    if executable is not None:
        resolved[0] = executable
    return subprocess.run(
        resolved,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def git_lines(root: Path, *args: str) -> list[str]:
    completed = run(["git", *args], cwd=root)
    if completed.returncode != 0:
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def emit(report: dict[str, Any], *, as_json: bool) -> int:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"{report.get('check', 'check')}: {report.get('status', 'unknown')}")
        for item in report.get("findings", []):
            print(f"- {item}")
    return 0 if report.get("status") == "passed" else 1
