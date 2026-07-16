#!/usr/bin/env python3
"""Validate Longform Mode voice/style continuity contracts and reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PASS_STATUSES = {"pass", "passed"}
BLOCKING_STATUSES = {"drift", "blocked", "stale", "unsupported", "human_review", "human-review"}
CHECK_FIELDS = {"pov", "tense", "narration_distance", "diction", "rhythm", "sentence_rhythm", "dialogue", "exposition", "pacing", "cadence", "emotional_temperature", "register"}


class Reporter:
    def __init__(self) -> None:
        self.issues: list[dict[str, str]] = []

    def error(self, code: str, path: str, message: str) -> None:
        self.issues.append({"severity": "error", "code": code, "path": path, "message": message})

    @property
    def error_count(self) -> int:
        return len(self.issues)


def nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def extract(payload: Any) -> tuple[Any, list[Any]]:
    if isinstance(payload, dict) and "voice_contract" in payload:
        return payload.get("voice_contract"), payload.get("reports", payload.get("voice_style_reports", []))
    if isinstance(payload, dict) and "voice_style" in payload and isinstance(payload["voice_style"], dict):
        return payload["voice_style"].get("voice_contract"), payload["voice_style"].get("reports", [])
    return None, []


def validate_contract(contract: Any, reporter: Reporter) -> None:
    if not isinstance(contract, dict):
        reporter.error("missing_voice_contract", "voice_contract", "Voice/style contract is required.")
        return
    for field in ("id", "pov_policy", "tense_policy", "narration_distance", "diction", "sentence_rhythm", "dialogue_policy", "exposition_policy", "pacing_policy", "status"):
        if not nonempty_str(contract.get(field)):
            reporter.error("missing_required_field", f"voice_contract.{field}", "Required voice contract field is missing.")
    for field in ("allowed_variation", "blocked_variation"):
        if not isinstance(contract.get(field), list):
            reporter.error("invalid_type", f"voice_contract.{field}", "Expected list.")
    if contract.get("status") not in PASS_STATUSES:
        reporter.error("voice_contract_not_passed", "voice_contract.status", "Voice contract must pass before continuity closure.")


def validate_report(report: Any, index: int, reporter: Reporter) -> None:
    path = f"reports[{index}]"
    if not isinstance(report, dict):
        reporter.error("invalid_row_type", path, "Voice/style report must be an object.")
        return
    for field in ("id", "contract_ref", "overall_status"):
        if not nonempty_str(report.get(field)):
            reporter.error("missing_required_field", f"{path}.{field}", "Required report field is missing.")
    checks = report.get("checks")
    if not nonempty_list(checks):
        reporter.error("missing_checks", f"{path}.checks", "Voice/style report requires checks.")
    elif isinstance(checks, list):
        for check_index, check in enumerate(checks):
            check_path = f"{path}.checks[{check_index}]"
            if not isinstance(check, dict):
                reporter.error("invalid_row_type", check_path, "Check must be an object.")
                continue
            if check.get("field") not in CHECK_FIELDS:
                reporter.error("invalid_check_field", f"{check_path}.field", "Unknown voice/style check field.")
            if check.get("status") in BLOCKING_STATUSES:
                reporter.error("blocking_voice_style_check", f"{check_path}.status", "Unresolved voice/style drift blocks closure.")
            elif check.get("status") not in PASS_STATUSES and check.get("status") not in {"partial", "scoped_out"}:
                reporter.error("invalid_check_status", f"{check_path}.status", "Unknown voice/style check status.")
            if not nonempty_str(check.get("finding")):
                reporter.error("missing_finding", f"{check_path}.finding", "Check finding is required.")
    drift = report.get("drift")
    if not isinstance(drift, list):
        reporter.error("invalid_type", f"{path}.drift", "Drift must be a list.")
    elif drift:
        for drift_index, item in enumerate(drift):
            item_path = f"{path}.drift[{drift_index}]"
            if isinstance(item, dict) and item.get("classification") == "blocking_drift":
                reporter.error("blocking_voice_style_drift", item_path, "Blocking drift must be repaired or human-reviewed before closure.")
            else:
                reporter.error("unresolved_voice_style_drift", item_path, "Drift list must be empty for positive closure.")
    if not isinstance(report.get("repair_actions"), list):
        reporter.error("invalid_type", f"{path}.repair_actions", "repair_actions must be a list.")
    if report.get("overall_status") not in PASS_STATUSES:
        reporter.error("voice_style_report_not_passed", f"{path}.overall_status", "Overall voice/style status must pass.")


def validate(payload: Any, source_path: str) -> dict[str, Any]:
    reporter = Reporter()
    contract, reports = extract(payload)
    validate_contract(contract, reporter)
    if not isinstance(reports, list) or not reports:
        reporter.error("missing_voice_style_reports", "reports", "At least one voice/style report is required.")
        reports = []
    for index, report in enumerate(reports):
        validate_report(report, index, reporter)
    return {
        "schema_version": "storyline-design.voice_style_continuity_check.report.v1",
        "source_path": source_path,
        "passed": reporter.error_count == 0,
        "summary": {"error_count": reporter.error_count, "issue_count": len(reporter.issues), "report_count": len(reports)},
        "issues": reporter.issues,
    }


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate voice/style continuity evidence.")
    parser.add_argument("input")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = validate(load_json(Path(args.input)), args.input)
    except OSError as exc:
        report = validate({}, args.input)
        report["issues"].append({"severity": "error", "code": "read_error", "path": args.input, "message": str(exc)})
        report["summary"]["error_count"] += 1
        report["passed"] = False
    except json.JSONDecodeError as exc:
        report = validate({}, args.input)
        report["issues"].append({"severity": "error", "code": "json_decode_error", "path": args.input, "message": f"{exc.msg} at line {exc.lineno}, column {exc.colno}"})
        report["summary"]["error_count"] += 1
        report["passed"] = False
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Voice/style continuity check: {'passed' if report['passed'] else 'failed'}")
        for issue in report["issues"]:
            print(f"- [{issue['severity']}] {issue['code']} at {issue['path']}: {issue['message']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
