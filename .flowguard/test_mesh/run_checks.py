"""Review the frozen validation ownership mesh without executing its checks."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from flowguard import review_test_mesh

from model import broken_missing_target_split_plan, release_plan


EVIDENCE_PENDING_CODES = {
    "diagnostic_accounting_incomplete",
    "diagnostic_not_run_without_reason",
    "final_receipt_artifact_version_missing",
    "final_receipt_coverage_incomplete",
    "final_receipt_exit_code_missing",
    "final_receipt_result_artifact_missing",
    "final_receipt_result_fingerprint_missing",
    "final_receipt_run_id_missing",
    "final_receipt_terminal_status_missing",
    "final_receipt_verifier_version_missing",
    "release_suite_not_current",
    "required_inventory_item_owner_missing",
    "stale_test_evidence",
}


def _load_receipts(path: Path | None):
    if path is None:
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    receipts = value.get("receipts", value)
    if not isinstance(receipts, dict):
        raise ValueError("receipt input must contain an object keyed by check id")
    return receipts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipts", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    receipts = _load_receipts(args.receipts)
    current = review_test_mesh(release_plan(receipts))
    broken = review_test_mesh(broken_missing_target_split_plan())
    finding_codes = {item.code for item in current.findings}
    structure_ok = not (finding_codes - EVIDENCE_PENDING_CODES)
    expected_current = current.ok if receipts is not None else structure_ok and not current.ok
    ok = expected_current and not broken.ok
    payload = {
        "artifact_type": "logic_writing_test_mesh_review",
        "schema_version": "1.0",
        "mode": "terminal-receipts" if receipts is not None else "frozen-plan",
        "ok": ok,
        "structure_ok": structure_ok,
        "current": asdict(current),
        "known_bad_missing_target_split": asdict(broken),
        "claim_boundary": (
            "Without --receipts this proves the frozen inventory, ownership, dependency projection, "
            "and expected evidence gaps only. With current terminal receipts it gates release evidence."
        ),
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(current.format_text(max_findings=20))
        print()
        print(broken.format_text(max_findings=10))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
