"""Replay the exact SkillGuard installation projection against the active skill."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from _release_common import canonical_hash, emit, portable_files


def _skillguard_scripts(codex_home: Path) -> Path:
    scripts = codex_home / "skills" / "skillguard" / "scripts"
    if not (scripts / "skillguard_v2" / "installation.py").is_file():
        raise ValueError("skillguard_installation_runtime_missing")
    return scripts


def check(source_skill: Path, codex_home: Path) -> dict:
    source = source_skill.resolve()
    home = codex_home.resolve()
    findings: list[str] = []
    try:
        scripts = _skillguard_scripts(home)
        sys.path.insert(0, str(scripts))
        from skillguard_v2.installation import (  # type: ignore[import-not-found]
            installation_member_paths,
            installation_projection_identity,
        )

        paths = installation_member_paths(source)
        active = home / "skills" / "logic-writing"
        source_projection = installation_projection_identity(source)
        active_projection = installation_projection_identity(active)
        source_files = portable_files(source, relative_paths=paths)
        active_files = portable_files(active, relative_paths=paths)
        actual_active = portable_files(active)
        if source_files != active_files:
            findings.append("active_bytes_do_not_match_source_projection")
        if set(actual_active) != set(paths):
            findings.append("active_tree_has_missing_or_unexpected_files")
        if source_projection != active_projection:
            findings.append("active_projection_identity_mismatch")

        head_path = home / "target-install-transactions" / "logic-writing" / "HEAD.json"
        if not head_path.is_file():
            findings.append("target_install_head_missing")
            receipt_status = "missing"
        else:
            head = json.loads(head_path.read_text(encoding="utf-8"))
            transaction_id = str(head.get("transaction_id", ""))
            receipt_path = head_path.parent / "receipts" / f"{transaction_id}.json"
            if not receipt_path.is_file():
                findings.append("target_install_receipt_missing")
                receipt_status = "missing"
            else:
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                receipt_status = str(receipt.get("status", ""))
                if receipt_status != "committed":
                    findings.append("target_install_receipt_not_committed")
                if receipt.get("canonical_projection") != source_projection:
                    findings.append("receipt_canonical_projection_mismatch")
                if receipt.get("active_projection") != active_projection:
                    findings.append("receipt_active_projection_mismatch")
        projection_hash = canonical_hash(source_projection)
    except (OSError, ValueError, json.JSONDecodeError, ImportError) as exc:
        findings.append(str(exc))
        paths = ()
        projection_hash = ""
        receipt_status = "unavailable"
    return {
        "check": "installation-parity",
        "status": "passed" if not findings else "failed",
        "skill_id": "logic-writing",
        "member_count": len(paths),
        "projection_hash": projection_hash,
        "receipt_status": receipt_status,
        "findings": sorted(set(findings)),
        "claim_boundary": "This check replays exact local installation bytes and the committed target-install receipt; it does not prove specialist availability, GitHub publication, or output quality.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-skill", required=True, type=Path)
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")),
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    return emit(check(args.source_skill, args.codex_home), as_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
