"""Portable one-owner wrapper for each read-only SkillGuard authority check."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Iterator

from _release_common import emit, run


CHECKS = ("compile", "runtime", "contract", "depth", "static", "project")
PROJECT_ID = "LogicWriting"


def _commands(repository: Path, target: Path, scripts: Path) -> dict[str, list[str]]:
    cli = scripts / "skillguard.py"
    compiler = scripts / "skillguard_compile.py"
    return {
        "compile": [sys.executable, str(compiler), str(target), "--repository-root", str(repository), "--check"],
        "runtime": [sys.executable, str(cli), "check-runtime-authority", "--target", str(target), "--target-root", str(repository), "--require-authority", "current", "--output", "-"],
        "contract": [sys.executable, str(cli), "check-contract", "--target", str(target), "--repository-root", str(repository), "--output", "-"],
        "depth": [sys.executable, str(cli), "check-depth", "--target", str(target), "--target-root", str(repository), "--output", "-"],
        "static": [sys.executable, str(cli), "check-skill", "--target", str(target), "--repository-root", str(repository), "--output", "-"],
        "project": [sys.executable, str(cli), "maintainer-audit", "--root", str(repository)],
    }


@contextmanager
def _execution_projection(
    repository: Path,
    target: Path,
    check_id: str,
) -> Iterator[tuple[Path, Path, str]]:
    if check_id != "project":
        yield repository, target, "repository-root"
        return

    manifest_path = repository / ".skillguard" / "author-project.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        yield repository, target, "repository-root"
        return
    project_id = str(manifest.get("project_id", ""))
    if project_id != PROJECT_ID:
        yield repository, target, "repository-root"
        return
    if repository.name == project_id:
        yield repository, target, "repository-root"
        return

    target_relative = target.relative_to(repository)
    projection_paths = (
        Path("AGENTS.md"),
        Path(".skillguard/author-project.json"),
        target_relative / "SKILL.md",
        target_relative / ".skillguard/contract-source.json",
        target_relative / ".skillguard/compiled-contract.json",
        target_relative / ".skillguard/check-manifest.json",
    )
    with tempfile.TemporaryDirectory(prefix="logic-writing-project-audit-") as temp:
        projected_repository = Path(temp) / project_id
        for relative in projection_paths:
            source = repository / relative
            if not source.is_file():
                continue
            destination = projected_repository / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        yield (
            projected_repository,
            projected_repository / target_relative,
            "stable-project-id",
        )


def check(repository: Path, target: Path, codex_home: Path, check_id: str) -> dict:
    repository = repository.resolve()
    target = target.resolve()
    scripts = codex_home.resolve() / "skills" / "skillguard" / "scripts"
    findings: list[str] = []
    execution_projection = "not-run"
    provider_result = {
        "returncode": None,
        "status": "not_run",
        "decision": "not_run",
        "findings": [],
    }
    if check_id not in CHECKS:
        findings.append("unsupported_skillguard_check")
    elif not (scripts / "skillguard.py").is_file() or not (scripts / "skillguard_compile.py").is_file():
        findings.append("skillguard_runtime_missing")
    elif not target.is_relative_to(repository):
        findings.append("target_outside_repository")
    else:
        with _execution_projection(repository, target, check_id) as (
            execution_repository,
            execution_target,
            execution_projection,
        ):
            completed = run(
                _commands(execution_repository, execution_target, scripts)[check_id],
                cwd=execution_repository,
                timeout=900,
            )
        if completed.returncode != 0:
            findings.append(f"skillguard_{check_id}_failed")
        decision = "pass" if completed.returncode == 0 else "block"
        provider_result["returncode"] = completed.returncode
        try:
            parsed = json.loads(completed.stdout)
            decision = str(parsed.get("decision", parsed.get("status", decision)))
            provider_result.update(
                {
                    "status": str(parsed.get("status", "unknown")),
                    "decision": decision,
                    "findings": [
                        str(item) for item in parsed.get("findings", [])
                    ],
                }
            )
            if decision not in {"pass", "passed", "current", "current_pass"}:
                findings.append(f"skillguard_{check_id}_nonpassing_decision")
        except json.JSONDecodeError:
            provider_result.update(
                {
                    "status": "invalid_output",
                    "decision": decision,
                }
            )
            if check_id != "compile" and completed.returncode == 0:
                findings.append(f"skillguard_{check_id}_non_json_output")
    return {
        "check": f"skillguard-{check_id}",
        "status": "passed" if not findings else "failed",
        "decision": "pass" if not findings else "block",
        "findings": sorted(set(findings)),
        "execution_projection": execution_projection,
        "provider_result": provider_result,
        "claim_boundary": "This wrapper executes exactly one named read-only SkillGuard owner check. It does not combine checks or claim target work was performed.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")),
    )
    parser.add_argument("--check", required=True, choices=CHECKS)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    return emit(
        check(args.repository_root, args.target, args.codex_home, args.check),
        as_json=args.json,
    )


if __name__ == "__main__":
    raise SystemExit(main())
