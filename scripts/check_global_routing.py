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
    active = home / "skills" / "logic-writing"
    manifest = active / "SKILL.md"
    text = manifest.read_text(encoding="utf-8") if manifest.is_file() else ""
    import re
    if not re.search(r"(?m)^name:\s*logic-writing\s*$", text):
        findings.append("logic_writing_entrypoint_missing_or_wrong")
    old_items = [old_id for old_id in OLD_IDS if (home / "skills" / old_id).exists()]
    if phase == "retired" and old_items:
        findings.extend(f"predecessor_skill_still_installed:{old_id}" for old_id in old_items)
    for old_id in old_items:
        if (home / "skills" / old_id / "SKILL.md").is_file():
            findings.append(f"predecessor_entrypoint_still_active:{old_id}")
    prompt_path = home / "AGENTS.md"
    prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.is_file() else ""
    if phase == "retired" and any(old_id in prompt for old_id in OLD_IDS):
        findings.append("global_prompt_contains_predecessor")
    return {
        "check": "global-routing",
        "status": "passed" if not findings else "failed",
        "phase": phase,
        "logic_writing_entries": int(manifest.is_file()),
        "current_logic_writing_entries": int(not any("entrypoint" in item for item in findings)),
        "predecessor_entries": len(old_items),
        "findings": sorted(set(findings)),
        "claim_boundary": "This checks the actual installed entrypoint, local prompt, and predecessor directories. It does not execute a user task or prove remote repository state.",
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
