"""Prepare and validate the representative reader judgment under one owner."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from prepare_reader_quality_receipt import prepare


def check(root: Path, runtime_root: Path | None = None) -> dict:
    root = root.resolve()
    runtime = (
        runtime_root.resolve()
        if runtime_root is not None
        else root / "run-artifacts" / "reader-judgment-owner"
    )
    receipt_root = runtime / "receipts"
    request_path = runtime / "reader-quality-judgment.json"
    result_path = runtime / "reader-quality-judgment-result.json"

    preparation = prepare(root, receipt_root, request_path)
    skill_scripts = root / "skills" / "logic-writing" / "scripts"
    if str(skill_scripts) not in sys.path:
        sys.path.insert(0, str(skill_scripts))

    from _common import load_json
    from validate_judgment_receipt import build_judgment_receipt

    judgment = build_judgment_receipt(
        load_json(request_path), receipt_root=receipt_root
    )
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(judgment, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    passed = (
        preparation.get("status") == "passed"
        and judgment.get("status") == "current_pass"
    )
    return {
        "check": "reader-judgment-owner",
        "status": "passed" if passed else "failed",
        "preparation_status": preparation.get("status"),
        "judgment_status": judgment.get("status"),
        "artifact": preparation.get("artifact"),
        "runtime_outputs": [request_path.name, result_path.name],
        "claim_boundary": (
            "This owner generates current deterministic prerequisites and validates "
            "the existing qualitative assessment against the representative actual "
            "artifact in one frozen execution. It does not generalize that judgment "
            "to other artifacts."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = check(args.root, args.runtime_root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        report = {
            "check": "reader-judgment-owner",
            "status": "failed",
            "error": str(exc),
            "claim_boundary": (
                "No reader-judgment pass is claimed when preparation or validation "
                "cannot complete under the same execution owner."
            ),
        }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"reader judgment owner: {report['status']}")
    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
