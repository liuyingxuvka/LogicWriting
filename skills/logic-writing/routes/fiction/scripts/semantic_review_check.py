#!/usr/bin/env python3
"""Validate structured, artifact-bound Storyline Design semantic reviews."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import evidence_identity


SCHEMA_VERSION = "storyline-design.semantic_review.v1"
REQUIRED_RUBRIC_DIMENSIONS = {
    "reader_room",
    "explanation_pressure",
    "variation",
    "story_contribution",
    "voice",
    "payoff",
    "model_prose_binding",
    "resistance_friction",
    "reader_state",
    "register_ownership",
}
PASS_STATUSES = {"pass", "passed", "not_applicable_with_reason"}
BLOCKING_STATUSES = {"partial", "blocked", "human_review", "human-review", "stale", "unreviewed"}
DECISIONS = {"passed", "partial", "blocked", "human_review", "human-review"}


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


def require_string(obj: dict[str, Any], field: str, path: str, reporter: Reporter) -> None:
    if not nonempty_str(obj.get(field)):
        reporter.error("missing_required_field", f"{path}.{field}", f"{field} is required.")


def validate_evaluator(value: Any, reporter: Reporter) -> None:
    if not isinstance(value, dict):
        reporter.error("invalid_evaluator", "evaluator", "evaluator must be a structured identity object.")
        return
    for field in ("id", "kind", "identity", "method"):
        require_string(value, field, "evaluator", reporter)
    if value.get("kind") not in {"ai", "human", "hybrid"}:
        reporter.error("invalid_evaluator_kind", "evaluator.kind", "Evaluator kind must be ai, human, or hybrid.")


def validate_rubric(value: Any, decision: str, reporter: Reporter) -> None:
    if not isinstance(value, list):
        reporter.error("invalid_rubric_dimensions", "rubric_dimensions", "rubric_dimensions must be a list.")
        return
    observed: set[str] = set()
    for index, row in enumerate(value):
        path = f"rubric_dimensions[{index}]"
        if not isinstance(row, dict):
            reporter.error("invalid_rubric_row", path, "Rubric row must be an object.")
            continue
        dimension = row.get("dimension")
        require_string(row, "dimension", path, reporter)
        if isinstance(dimension, str):
            if dimension in observed:
                reporter.error("duplicate_rubric_dimension", f"{path}.dimension", f"Duplicate rubric dimension {dimension!r}.")
            observed.add(dimension)
        status = row.get("status")
        require_string(row, "status", path, reporter)
        if status not in PASS_STATUSES | BLOCKING_STATUSES:
            reporter.error("invalid_rubric_status", f"{path}.status", f"Unknown rubric status {status!r}.")
        if status == "not_applicable_with_reason" and not nonempty_str(row.get("reason")):
            reporter.error("missing_rubric_scope_reason", f"{path}.reason", "Not-applicable rubric rows require a concrete reason.")
        findings = row.get("findings")
        if not isinstance(findings, list) or not findings:
            reporter.error("missing_rubric_findings", f"{path}.findings", "Every rubric dimension needs at least one concrete finding.")
        elif not all(nonempty_str(item) for item in findings):
            reporter.error("invalid_rubric_findings", f"{path}.findings", "Rubric findings must be non-empty strings.")
        anchors = row.get("evidence_anchors")
        if not isinstance(anchors, list) or not anchors or not all(nonempty_str(item) for item in anchors):
            reporter.error("invalid_evidence_anchors", f"{path}.evidence_anchors", "Every rubric dimension needs at least one manuscript evidence anchor.")
        if not nonempty_str(row.get("reviewer_notes")):
            reporter.error("missing_reviewer_notes", f"{path}.reviewer_notes", "Every rubric dimension needs reviewer_notes.")
        if decision == "passed" and status in BLOCKING_STATUSES:
            reporter.error("passed_with_blocking_rubric", f"{path}.status", "A passed review cannot contain a blocking rubric status.")
    for missing in sorted(REQUIRED_RUBRIC_DIMENSIONS - observed):
        reporter.error("missing_rubric_dimension", "rubric_dimensions", f"Required semantic-review dimension {missing!r} is missing.")
    for extra in sorted(observed - REQUIRED_RUBRIC_DIMENSIONS):
        reporter.error("unknown_rubric_dimension", "rubric_dimensions", f"Unknown semantic-review dimension {extra!r}.")


def validate_scope_items(name: str, value: Any, decision: str, reporter: Reporter) -> None:
    if not isinstance(value, list):
        reporter.error("invalid_type", name, f"{name} must be a list.")
        return
    for index, item in enumerate(value):
        path = f"{name}[{index}]"
        if not isinstance(item, dict):
            reporter.error("invalid_scope_item", path, f"{name} rows must be objects.")
            continue
        require_string(item, "id", path, reporter)
        require_string(item, "reason", path, reporter)
        if not isinstance(item.get("blocks_closure"), bool):
            reporter.error("missing_blocking_semantics", f"{path}.blocks_closure", "Scope item must declare blocks_closure as a boolean.")
        if name == "human_review_items":
            require_string(item, "status", path, reporter)
            if item.get("status") not in {"resolved", "unresolved"}:
                reporter.error("invalid_human_review_status", f"{path}.status", "Human-review status must be resolved or unresolved.")
            if item.get("status") == "unresolved" and item.get("blocks_closure") is not True:
                reporter.error("unresolved_human_review_not_blocking", f"{path}.blocks_closure", "Unresolved human review must block closure.")
        if decision == "passed" and item.get("blocks_closure") is True:
            reporter.error("passed_with_blocking_scope", f"{path}.blocks_closure", f"Passed review cannot retain blocking {name}.")


def validate_findings(value: Any, decision: str, reporter: Reporter) -> None:
    if not isinstance(value, list) or not value:
        reporter.error("missing_review_findings", "findings", "Structured semantic review requires at least one finding.")
        return
    for index, item in enumerate(value):
        path = f"findings[{index}]"
        if not isinstance(item, dict):
            reporter.error("invalid_finding", path, "Finding must be an object.")
            continue
        for field in ("id", "dimension", "finding", "status"):
            require_string(item, field, path, reporter)
        dimension = item.get("dimension")
        if dimension not in REQUIRED_RUBRIC_DIMENSIONS:
            reporter.error("invalid_finding_dimension", f"{path}.dimension", "Finding dimension must name a required rubric dimension.")
        status = item.get("status")
        if status not in PASS_STATUSES | BLOCKING_STATUSES:
            reporter.error("invalid_finding_status", f"{path}.status", f"Unknown finding status {status!r}.")
        if decision == "passed" and status in BLOCKING_STATUSES:
            reporter.error("passed_with_blocking_finding", f"{path}.status", "Passed review cannot retain a blocking finding.")


def validate(
    payload: Any,
    source_path: str,
    repository_root: str | Path | None = None,
) -> dict[str, Any]:
    reporter = Reporter()
    review = payload if isinstance(payload, dict) else {}
    if not isinstance(payload, dict):
        reporter.error("invalid_root_type", "$", "Semantic-review root must be an object.")
    if review.get("schema_version") != SCHEMA_VERSION:
        reporter.error("invalid_schema_version", "schema_version", f"Expected {SCHEMA_VERSION}.")
    for field in ("project_id", "review_id", "model_revision", "reviewed_at", "artifact_ref", "artifact_sha256", "decision"):
        require_string(review, field, "$", reporter)
    if nonempty_str(review.get("reviewed_at")):
        try:
            reviewed_at = datetime.fromisoformat(review["reviewed_at"].replace("Z", "+00:00"))
        except ValueError:
            reporter.error("invalid_review_timestamp", "reviewed_at", "reviewed_at must be an ISO-8601 timestamp.")
        else:
            if reviewed_at.tzinfo is None:
                reporter.error("invalid_review_timestamp", "reviewed_at", "reviewed_at must include an explicit UTC offset.")
    decision = review.get("decision") if review.get("decision") in DECISIONS else ""
    if not decision:
        reporter.error("invalid_decision", "decision", f"Unknown semantic-review decision {review.get('decision')!r}.")
    validate_evaluator(review.get("evaluator"), reporter)
    reviewed_units = review.get("reviewed_units")
    if not isinstance(reviewed_units, list) or not reviewed_units or not all(nonempty_str(item) for item in reviewed_units):
        reporter.error("invalid_reviewed_units", "reviewed_units", "reviewed_units must be a non-empty list of exact unit ids.")
    elif len(set(reviewed_units)) != len(reviewed_units):
        reporter.error("duplicate_reviewed_unit", "reviewed_units", "reviewed_units must not contain duplicate ids.")
    validate_rubric(review.get("rubric_dimensions"), decision, reporter)
    validate_findings(review.get("findings"), decision, reporter)
    validate_scope_items("skipped_scope", review.get("skipped_scope"), decision, reporter)
    limitations = review.get("limitations")
    if not isinstance(limitations, list) or not all(nonempty_str(item) for item in limitations):
        reporter.error("invalid_limitations", "limitations", "limitations must be a list of non-empty strings, which may be empty.")
    validate_scope_items("human_review_items", review.get("human_review_items"), decision, reporter)

    artifact_identity: dict[str, str] | None = None
    if nonempty_str(review.get("artifact_ref")):
        try:
            artifact_identity = evidence_identity.verify_content_reference(
                review["artifact_ref"], source_path, repository_root
            )
            evidence_identity.require_matching_sha256(review.get("artifact_sha256"), artifact_identity["sha256"])
        except evidence_identity.EvidenceIdentityError as exc:
            reporter.error(exc.code, exc.path, exc.message)

    if decision == "passed" and reporter.error_count:
        reporter.error("passed_with_review_errors", "decision", "Semantic review cannot pass while contract or identity errors remain.")
    return {
        "schema_version": "storyline-design.semantic_review_check.report.v1",
        "source_path": source_path,
        "passed": reporter.error_count == 0,
        "project_id": str(review.get("project_id", "")),
        "artifact_identity": artifact_identity,
        "summary": {
            "error_count": reporter.error_count,
            "issue_count": len(reporter.issues),
            "reviewed_unit_count": len(reviewed_units) if isinstance(reviewed_units, list) else 0,
        },
        "issues": reporter.issues,
    }


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate structured artifact-bound semantic review evidence.")
    parser.add_argument("input")
    parser.add_argument("--repo-root")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        input_path = Path(args.input).expanduser()
        report = validate(load_json(input_path), str(input_path), args.repo_root)
    except OSError as exc:
        report = validate({}, args.input, args.repo_root)
        report["issues"].append({"severity": "error", "code": "read_error", "path": args.input, "message": str(exc)})
        report["passed"] = False
        report["summary"]["error_count"] += 1
    except json.JSONDecodeError as exc:
        report = validate({}, args.input, args.repo_root)
        report["issues"].append({"severity": "error", "code": "json_decode_error", "path": args.input, "message": f"{exc.msg} at line {exc.lineno}, column {exc.colno}"})
        report["passed"] = False
        report["summary"]["error_count"] += 1
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Semantic review check: {'passed' if report['passed'] else 'failed'}")
        for issue in report["issues"]:
            print(f"- [{issue['severity']}] {issue['code']} at {issue['path']}: {issue['message']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
