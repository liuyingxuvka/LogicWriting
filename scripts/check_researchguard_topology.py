#!/usr/bin/env python3
"""Reject retired ResearchGuard consumer routes and alternate execution paths."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


RETIRED_SKILL_IDS = (
    "logicguard-source-library",
    "logicguard-structured-artifact",
    "logicguard-model-deepening",
    "logicguard-artifact-synthesis",
    "logicguard-project-library-viewer",
    "traceguard-library",
)
TEXT_SUFFIXES = {".py", ".md", ".json", ".yaml", ".yml", ".toml"}
SKIP_PARTS = {
    ".git",
    "__pycache__",
    "archive",
    ".pytest_cache",
    "compiled-contract.json",
    "check-manifest.json",
}
GOVERNED_ROOTS = ("skills/logic-writing", "tests", "scripts", ".flowguard")
OLD_EXECUTION_PATTERNS = (
    re.compile(r"\bpython\s+-m\s+(?:logicguard|sourceguard|traceguard)\b", re.IGNORECASE),
    re.compile(r"^\s*(?:from|import)\s+(?:logicguard|sourceguard|traceguard)\b", re.MULTILINE),
    re.compile(
        r"""importlib\.import_module\(\s*["'](?:logicguard|sourceguard|traceguard)["']\s*\)"""
    ),
)
BARE_RECEIPT_ROUTE = re.compile(
    r"""["'](?:route_id|native_route_id)["']\s*:\s*["'](?:logicguard|sourceguard|traceguard)["']"""
)
REQUIRED_BINDINGS = {
    "logicguard": ("logic", "primary:researchguard:logic"),
    "sourceguard": ("source", "primary:researchguard:source"),
    "traceguard": ("trace", "primary:researchguard:trace"),
}


def _governed_files(root: Path):
    for relative in GOVERNED_ROOTS:
        target = root / relative
        if not target.exists():
            continue
        for path in target.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            relative_path = path.relative_to(root)
            if relative_path.as_posix() == "scripts/check_researchguard_topology.py":
                continue
            if any(part in SKIP_PARTS for part in relative_path.parts):
                continue
            yield relative_path, path


def check(root: Path) -> dict[str, object]:
    findings: list[dict[str, object]] = []
    for relative, path in _governed_files(root):
        text = path.read_text(encoding="utf-8")
        for skill_id in RETIRED_SKILL_IDS:
            if skill_id in text:
                findings.append(
                    {
                        "code": "retired_skill_id",
                        "path": relative.as_posix(),
                        "value": skill_id,
                    }
                )
        for pattern in OLD_EXECUTION_PATTERNS:
            if match := pattern.search(text):
                findings.append(
                    {
                        "code": "alternate_member_execution_path",
                        "path": relative.as_posix(),
                        "value": match.group(0),
                    }
                )
        if match := BARE_RECEIPT_ROUTE.search(text):
            findings.append(
                {
                    "code": "bare_member_receipt_route",
                    "path": relative.as_posix(),
                    "value": match.group(0),
                }
            )

    provider_path = root / "skills/logic-writing/scripts/provider_preflight.py"
    provider_text = provider_path.read_text(encoding="utf-8")
    for member_id, (command, primary_path) in REQUIRED_BINDINGS.items():
        for token in (f'"{member_id}"', f'"member_command": "{command}"', primary_path):
            if token not in provider_text:
                findings.append(
                    {
                        "code": "required_member_binding_missing",
                        "path": provider_path.relative_to(root).as_posix(),
                        "value": token,
                    }
                )

    status = "pass" if not findings else "fail"
    return {
        "schema_version": "logic-writing.researchguard-topology-check.v1",
        "status": status,
        "ok": not findings,
        "findings": findings,
        "governed_roots": list(GOVERNED_ROOTS),
        "member_bindings": {
            member_id: {
                "console": "researchguard",
                "member_command": command,
                "primary_path_id": primary_path,
            }
            for member_id, (command, primary_path) in REQUIRED_BINDINGS.items()
        },
        "claim_boundary": (
            "This static check proves current Logic Writing consumer surfaces "
            "declare one ResearchGuard console topology. It does not prove the "
            "console is installed or that native member work ran."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = check(Path(args.root).resolve())
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"status={report['status']} findings={len(report['findings'])}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
