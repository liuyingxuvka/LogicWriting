"""Prepare current ReaderBrief and deterministic authority for a judged artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def prepare(root: Path, receipt_root: Path, output: Path) -> dict:
    root = root.resolve()
    receipt_root = receipt_root.resolve()
    output = output.resolve()
    skill_scripts = root / "skills" / "logic-writing" / "scripts"
    for path in (root, skill_scripts):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

    from audit_reader_output import build_reader_audit_receipt
    from build_reader_brief import build_reader_brief
    from tests.support import make_current_packet

    artifact = root / "tests" / "fixtures" / "forward" / "reader-ready-report.md"
    assessment_path = root / "tests" / "fixtures" / "forward" / "reader-quality-assessment.json"
    assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
    packet = make_current_packet(
        receipt_root,
        final_owner="investigation",
        packet_id="packet:logic-writing-release-reader",
    )["packet"]
    brief_result = build_reader_brief(
        packet,
        receipt_root=receipt_root,
        brief_id="brief:logic-writing-release-reader",
        question="What can the clinic records support?",
        audience="A policy reader without specialist background",
        genre="research report",
        purpose="Explain the observed result and its evidential limit clearly.",
        concepts=[
            {
                "concept_id": "concept:observation-period",
                "term": "Observation period",
                "explanation": "the period covered by the available records",
                "introduction_order": 1,
            }
        ],
    )
    brief = brief_result["reader_brief"]
    audit = build_reader_audit_receipt(
        {
            "schema_version": "1.0",
            "audit_id": "audit:logic-writing-release-reader",
            "artifact_path": str(artifact),
            "audited_text_path": None,
            "artifact_extraction_receipt_fingerprint": None,
            "reader_brief": brief,
            "reader_brief_receipt_fingerprint": brief_result[
                "derivation_receipt_fingerprint"
            ],
            "run_id": "run:reader-audit:logic-writing-release-reader",
        },
        receipt_root=receipt_root,
    )
    if audit["status"] != "current_pass":
        raise ValueError("representative_reader_artifact_failed_deterministic_audit")
    request = {
        "schema_version": "1.0",
        "judgment_id": "judgment:logic-writing-release-reader",
        "artifact_path": str(artifact),
        "reader_brief": brief,
        "reader_brief_receipt_fingerprint": brief_result[
            "derivation_receipt_fingerprint"
        ],
        "deterministic_receipt_fingerprint": audit["receipt"][
            "receipt_fingerprint"
        ],
        "judge_id": assessment["judge_id"],
        "judge_kind": assessment["judge_kind"],
        "judged_at": assessment["judged_at"],
        "rubric": assessment["rubric"],
        "observations": assessment["observations"],
        "run_id": "run:reader-judgment:logic-writing-release-reader",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(request, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "status": "passed",
        "artifact": "tests/fixtures/forward/reader-ready-report.md",
        "judgment_request": output.name,
        "deterministic_status": audit["status"],
        "claim_boundary": "Preparation creates current brief and deterministic evidence only; the separate qualitative judgment command remains the judgment owner.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--receipt-root",
        type=Path,
        default=Path("run-artifacts/reader-receipts"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("run-artifacts/reader-quality-judgment.json"),
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = prepare(args.root, args.receipt_root, args.output)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        report = {"status": "failed", "error": str(exc)}
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) if args.json else f"reader-quality preparation: {report['status']}")
    return 0 if report.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
