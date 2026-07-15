"""Portable one-owner wrapper for each read-only SkillGuard authority check."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from _release_common import emit, run


CHECKS = ("compile", "runtime", "contract", "depth", "static", "project")


def _commands(repository: Path, target: Path, scripts: Path) -> dict[str, list[str]]:
    cli = scripts / "skillguard.py"
    compiler = scripts / "skillguard_compile.py"
    return {
        "compile": [sys.executable, str(compiler), str(target), "--repository-root", str(repository), "--check"],
        "runtime": [sys.executable, str(cli), "check-runtime-authority", "--target", str(target), "--target-root", str(repository), "--require-authority", "current", "--output", "-"],
        "contract": [sys.executable, str(cli), "check-contract", "--target", str(target), "--target-root", str(repository), "--output", "-"],
        "depth": [sys.executable, str(cli), "check-depth", "--target", str(target), "--target-root", str(repository), "--output", "-"],
        "static": [sys.executable, str(cli), "check-skill", "--target", str(target), "--output", "-"],
        "project": [sys.executable, str(cli), "project-audit", "--root", str(repository)],
    }


def check(repository: Path, target: Path, codex_home: Path, check_id: str) -> dict:
    repository = repository.resolve()
    target = target.resolve()
    scripts = codex_home.resolve() / "skills" / "skillguard" / "scripts"
    findings: list[str] = []
    if check_id not in CHECKS:
        findings.append("unsupported_skillguard_check")
    elif not (scripts / "skillguard.py").is_file() or not (scripts / "skillguard_compile.py").is_file():
        findings.append("skillguard_runtime_missing")
    elif not target.is_relative_to(repository):
        findings.append("target_outside_repository")
    else:
        completed = run(_commands(repository, target, scripts)[check_id], cwd=repository, timeout=900)
        if completed.returncode != 0:
            findings.append(f"skillguard_{check_id}_failed")
        decision = "pass" if completed.returncode == 0 else "block"
        try:
            parsed = json.loads(completed.stdout)
            decision = str(parsed.get("decision", parsed.get("status", decision)))
            if decision not in {"pass", "passed", "current", "current_pass"}:
                findings.append(f"skillguard_{check_id}_nonpassing_decision")
        except json.JSONDecodeError:
            if check_id != "compile" and completed.returncode == 0:
                findings.append(f"skillguard_{check_id}_non_json_output")
    return {
        "check": f"skillguard-{check_id}",
        "status": "passed" if not findings else "failed",
        "decision": "pass" if not findings else "block",
        "findings": sorted(set(findings)),
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
