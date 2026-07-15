"""Check that Logic Writing is the sole current replacement route."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from _release_common import emit


OLD_IDS = {"research-investigation-workflow", "academic-thesis-revision-workflow"}


def check(codex_home: Path, *, phase: str) -> dict:
    home = codex_home.resolve()
    findings: list[str] = []
    registry_path = home / ".skillguard" / "global-router" / "global_registry.json"
    if not registry_path.is_file():
        return {"check": "global-routing", "status": "failed", "phase": phase, "findings": ["global_registry_missing"]}
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"check": "global-routing", "status": "failed", "phase": phase, "findings": ["global_registry_invalid"]}
    items = [item for item in registry.get("items", []) if isinstance(item, dict)]
    new_items = [item for item in items if item.get("skill_id") == "logic-writing"]
    current_new = [
        item
        for item in new_items
        if item.get("status") == "current"
        and (item.get("route_entrypoint") or {}).get("authority_decision") == "current"
    ]
    if len(current_new) != 1:
        findings.append("logic_writing_current_route_count_mismatch")
    old_items = [item for item in items if item.get("skill_id") in OLD_IDS]
    if any(
        item.get("status") == "current"
        or (item.get("route_entrypoint") or {}).get("authority_decision") == "current"
        for item in old_items
    ):
        findings.append("predecessor_route_still_authoritative")
    if phase == "retired" and old_items:
        findings.append("predecessor_route_still_registered")
    for old_id in OLD_IDS:
        exists = (home / "skills" / old_id).exists()
        if phase == "retired" and exists:
            findings.append(f"predecessor_skill_still_installed:{old_id}")
    prompt_path = home / "AGENTS.md"
    prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.is_file() else ""
    if "logic-writing" not in prompt:
        findings.append("managed_global_prompt_missing_logic_writing")
    if phase == "retired" and any(old_id in prompt for old_id in OLD_IDS):
        findings.append("managed_global_prompt_contains_predecessor")
    return {
        "check": "global-routing",
        "status": "passed" if not findings else "failed",
        "phase": phase,
        "logic_writing_entries": len(new_items),
        "current_logic_writing_entries": len(current_new),
        "predecessor_entries": len(old_items),
        "findings": sorted(set(findings)),
        "claim_boundary": "This checks the current local registry, managed prompt, and predecessor authority. It does not execute a user task or prove remote repository state.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")),
    )
    parser.add_argument("--phase", choices=("cutover", "retired"), default="cutover")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    return emit(check(args.codex_home, phase=args.phase), as_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
