"""Small standard-library helpers shared by release validation entrypoints."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable


RELEASE_CONTRACT_RELATIVE = Path("openspec/verification-contract.yaml")


RUNTIME_PARTS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "evidence",
    "run-artifacts",
    "run_artifacts",
    "validation-receipts",
}


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def portable_files(root: Path, *, relative_paths: Iterable[str] | None = None) -> dict[str, str]:
    root = root.resolve()
    if relative_paths is None:
        candidates = sorted(path for path in root.rglob("*") if path.is_file())
    else:
        candidates = [root / Path(*item.replace("\\", "/").split("/")) for item in relative_paths]
    result: dict[str, str] = {}
    for path in candidates:
        relative = path.relative_to(root)
        if any(part in RUNTIME_PARTS for part in relative.parts):
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"missing_or_unsafe_file:{relative.as_posix()}")
        result[relative.as_posix()] = file_hash(path)
    return result


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
