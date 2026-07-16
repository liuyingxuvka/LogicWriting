#!/usr/bin/env python3
"""Validate StorylineDesign model-prose binding evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import evidence_identity


SCHEMA_VERSION = "storyline-design.model_prose_binding.v1"
PASS_DECISIONS = {"pass", "passed"}
DECISIONS = PASS_DECISIONS | {"partial", "blocked", "human_review", "human-review"}
PASS_STATUSES = {"pass", "passed", "scoped_out", "not_applicable_with_reason"}
BLOCKING_STATUSES = {"blocked", "drift", "unsupported", "stale", "unbound", "duplicate", "human_review", "human-review"}
SCOPED_VARIATION_PURPOSES = {
    "escalation",
    "contrast",
    "inversion",
    "cost",
    "rhythm",
    "deliberate_rhythm",
    "changed_interpretation",
    "changed_reader_interpretation",
    "resistance",
    "payoff",
    "setup",
    "scoped",
    "not_applicable",
}
WEAK_VARIATION_PURPOSES = {"", "none", "n/a", "na", "not recorded", "unknown", "placeholder"}
PLACEHOLDERS = WEAK_VARIATION_PURPOSES | {"todo", "tbd", "...", "fix later"}


class Reporter:
    def __init__(self) -> None:
        self.issues: list[dict[str, str]] = []

    def error(self, code: str, path: str, message: str) -> None:
        self.issues.append({"severity": "error", "code": code, "path": path, "message": message})

    @property
    def error_count(self) -> int:
        return len(self.issues)


def normalize(value: Any) -> str:
    return " ".join(value.strip().lower().split()) if isinstance(value, str) else ""


def nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and normalize(value) not in PLACEHOLDERS


def nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def extract(payload: Any) -> Any:
    if isinstance(payload, dict) and isinstance(payload.get("model_prose_binding"), dict):
        return payload["model_prose_binding"]
    return payload


def check_required_str(obj: dict[str, Any], field: str, path: str, reporter: Reporter) -> None:
    if not nonempty_str(obj.get(field)):
        reporter.error("missing_required_field", f"{path}.{field}", f"{field} is required and cannot be placeholder text.")


def check_required_list(obj: dict[str, Any], field: str, path: str, reporter: Reporter) -> None:
    if not nonempty_list(obj.get(field)):
        reporter.error("missing_required_list", f"{path}.{field}", f"{field} must be a non-empty list.")


def variation_has_purpose(value: Any) -> bool:
    normalized = normalize(value)
    return normalized in SCOPED_VARIATION_PURPOSES


def row_model_key(row: dict[str, Any]) -> tuple[str, ...]:
    refs = row.get("model_refs")
    if not isinstance(refs, list):
        return ()
    return tuple(sorted(normalize(ref) for ref in refs if isinstance(ref, str) and ref.strip()))


def check_binding_row(row: Any, index: int, reporter: Reporter) -> tuple[str, ...]:
    path = f"binding_rows[{index}]"
    if not isinstance(row, dict):
        reporter.error("invalid_row_type", path, "Binding row must be an object.")
        return ()
    for field in ("id", "prose_ref", "observed_reader_delta", "resistance_or_cost", "reader_hypothesis_delta", "variation_purpose", "status"):
        check_required_str(row, field, path, reporter)
    for field in ("model_refs", "observed_state_delta", "downstream_use", "register_notes"):
        check_required_list(row, field, path, reporter)
    status = row.get("status")
    if status in BLOCKING_STATUSES:
        reporter.error("blocking_binding_row", f"{path}.status", f"Binding row status {status!r} blocks closure.")
    elif status not in PASS_STATUSES:
        reporter.error("invalid_binding_status", f"{path}.status", f"Unknown binding status {status!r}.")
    return row_model_key(row)


def check_ref_list(name: str, value: Any, reporter: Reporter, decision: str) -> None:
    path = name
    if value is None:
        return
    if not isinstance(value, list):
        reporter.error("invalid_type", path, f"{name} must be a list when present.")
        return
    if value and decision in PASS_DECISIONS:
        reporter.error("unresolved_binding_gap", path, f"{name} must be empty before a passed binding decision.")


def check_drift_findings(value: Any, reporter: Reporter, decision: str) -> None:
    if not isinstance(value, list):
        reporter.error("invalid_type", "drift_findings", "drift_findings must be a list.")
        return
    for index, item in enumerate(value):
        path = f"drift_findings[{index}]"
        if not isinstance(item, dict):
            if decision in PASS_DECISIONS:
                reporter.error("unresolved_drift_finding", path, "Passed binding cannot contain unresolved drift.")
            continue
        status = item.get("status")
        if status not in PASS_STATUSES:
            reporter.error("unresolved_drift_finding", f"{path}.status", "Drift findings must be resolved, scoped out, or not applicable before pass.")


def check_length_outliers(value: Any, reporter: Reporter, decision: str) -> None:
    if not isinstance(value, list):
        reporter.error("invalid_type", "length_outliers", "length_outliers must be a list.")
        return
    for index, item in enumerate(value):
        path = f"length_outliers[{index}]"
        if not isinstance(item, dict):
            reporter.error("invalid_row_type", path, "Length outlier row must be an object.")
            continue
        if not nonempty_str(item.get("unit_ref")):
            reporter.error("missing_required_field", f"{path}.unit_ref", "Length outlier needs a unit_ref.")
        if not nonempty_str(item.get("binding_density_review")):
            reporter.error("missing_binding_density_review", f"{path}.binding_density_review", "Length outlier needs binding-density review.")
        status = item.get("status", "pass")
        if status not in PASS_STATUSES and decision in PASS_DECISIONS:
            reporter.error("blocking_length_outlier", f"{path}.status", "Length outlier cannot block a passed decision.")


def check_duplicate_model_bindings(rows: list[Any], reporter: Reporter) -> None:
    seen: dict[tuple[str, ...], tuple[int, dict[str, Any]]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        key = row_model_key(row)
        if not key:
            continue
        previous = seen.get(key)
        if previous is None:
            seen[key] = (index, row)
            continue
        previous_index, previous_row = previous
        current_purpose = row.get("variation_purpose")
        previous_purpose = previous_row.get("variation_purpose")
        if not variation_has_purpose(current_purpose) and not variation_has_purpose(previous_purpose):
            reporter.error(
                "duplicate_binding_without_delta",
                f"binding_rows[{index}].model_refs",
                f"Rows {previous_index} and {index} bind to the same model refs without recorded changed effect.",
            )


def validate(
    payload: Any,
    source_path: str,
    repository_root: str | Path | None = None,
) -> dict[str, Any]:
    reporter = Reporter()
    binding = extract(payload)
    if not isinstance(binding, dict):
        reporter.error("invalid_root_type", "$", "Model-prose binding root must be an object.")
        binding = {}
    if binding.get("schema_version") != SCHEMA_VERSION:
        reporter.error("invalid_schema_version", "schema_version", f"Expected {SCHEMA_VERSION}.")
    for field in ("project_id", "artifact_ref", "artifact_sha256", "binding_scope", "decision"):
        check_required_str(binding, field, "$", reporter)
    artifact_identity: dict[str, str] | None = None
    if nonempty_str(binding.get("artifact_ref")):
        try:
            artifact_identity = evidence_identity.verify_content_reference(
                binding["artifact_ref"], source_path, repository_root
            )
            evidence_identity.require_matching_sha256(
                binding.get("artifact_sha256"), artifact_identity["sha256"]
            )
        except evidence_identity.EvidenceIdentityError as exc:
            reporter.error(exc.code, exc.path, exc.message)
    elif nonempty_str(binding.get("artifact_sha256")):
        try:
            evidence_identity.parse_sha256_value(binding["artifact_sha256"])
        except evidence_identity.EvidenceIdentityError as exc:
            reporter.error(exc.code, exc.path, exc.message)
    decision = binding.get("decision")
    if decision not in DECISIONS:
        reporter.error("invalid_decision", "decision", f"Unknown binding decision {decision!r}.")
        decision_text = ""
    else:
        decision_text = str(decision)

    rows = binding.get("binding_rows")
    if not isinstance(rows, list) or not rows:
        reporter.error("missing_binding_rows", "binding_rows", "At least one model-prose binding row is required.")
        rows = []
    for index, row in enumerate(rows):
        check_binding_row(row, index, reporter)
    check_duplicate_model_bindings(rows, reporter)
    check_drift_findings(binding.get("drift_findings"), reporter, decision_text)
    check_length_outliers(binding.get("length_outliers"), reporter, decision_text)
    for field in ("unbound_prose_refs", "unrealized_model_refs", "duplicate_binding_refs"):
        check_ref_list(field, binding.get(field), reporter, decision_text)
    if decision_text in PASS_DECISIONS and reporter.error_count:
        # The specific issue rows above are enough; this preserves an obvious aggregate clue.
        reporter.error("passed_with_binding_errors", "decision", "Binding decision cannot be passed while blocking binding errors exist.")
    return {
        "schema_version": "storyline-design.model_prose_binding_check.report.v1",
        "source_path": source_path,
        "passed": reporter.error_count == 0,
        "project_id": str(binding.get("project_id", "")),
        "artifact_identity": artifact_identity,
        "summary": {"error_count": reporter.error_count, "issue_count": len(reporter.issues), "binding_row_count": len(rows)},
        "issues": reporter.issues,
    }


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate model-prose binding evidence.")
    parser.add_argument("input")
    parser.add_argument("--repo-root")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = validate(load_json(Path(args.input)), args.input, args.repo_root)
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
        print(f"Model-prose binding check: {'passed' if report['passed'] else 'failed'}")
        for issue in report["issues"]:
            print(f"- [{issue['severity']}] {issue['code']} at {issue['path']}: {issue['message']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
