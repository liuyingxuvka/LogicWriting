"""Compare the target-owned consumer projection with the active skill."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from _release_common import canonical_hash, emit


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
        from skillguard_v2.consumer_distribution import (  # type: ignore[import-not-found]
            audit_consumer_distribution,
            consumer_distribution_plan,
        )
        from skillguard_v2.contract_compiler import (  # type: ignore[import-not-found]
            canonical_hash as skillguard_canonical_hash,
        )

        contract_path = source / ".skillguard" / "compiled-contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        plan = consumer_distribution_plan(source, contract)
        if plan.get("status") != "passed":
            findings.extend(
                f"{row.get('code', 'consumer_projection_blocked')}:{row.get('path', '')}"
                for row in plan.get("findings", [])
                if isinstance(row, dict)
            )
        paths = tuple(str(row["path"]) for row in plan.get("files", []))
        active = home / "skills" / "logic-writing"
        audit = audit_consumer_distribution(active)
        if audit.get("status") != "passed":
            findings.extend(
                f"{row.get('code', 'consumer_audit_blocked')}:{row.get('path', '')}"
                for row in audit.get("findings", [])
                if isinstance(row, dict)
            )
        source_projection = {
            "projection_id": "projection:consumer-distribution",
            "release_id": str(plan.get("release_id", "")),
            "member_paths_hash": skillguard_canonical_hash(
                sorted([*paths, "consumer-release.json"])
            ),
        }
        active_projection = {
            "projection_id": "projection:consumer-distribution",
            "release_id": str(audit.get("release_id", "")),
            "member_paths_hash": skillguard_canonical_hash(
                sorted(
                    [
                        *[
                            str(row.get("path", ""))
                            for row in audit.get("manifest", {}).get("files", [])
                            if isinstance(row, dict)
                        ],
                        "consumer-release.json",
                    ]
                )
            ),
        }
        if source_projection["release_id"] != active_projection["release_id"]:
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
        "claim_boundary": "This author-side check compares the target-owned consumer manifest and files with the current source projection and committed local activation receipt; the installed consumer itself requires no SkillGuard state.",
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
