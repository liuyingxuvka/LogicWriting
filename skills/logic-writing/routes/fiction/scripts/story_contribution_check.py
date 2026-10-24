#!/usr/bin/env python3
"""Validate Longform Mode story-unit contribution rows."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from fiction_plan import project_surface

from typing import Any

import storyline_route_check


BLOCKING_STATUSES = {"orphan", "duplicate", "weak", "unsupported", "stale", "blocked", "human_review", "human-review"}
PASS_STATUSES = {"pass", "passed"}
TERMINAL_TREATMENTS = {"keep", "revise", "cut", "merge", "defer", "scoped_out", "human_review", "human-review"}
PLACEHOLDERS = {"", "tbd", "todo", "n/a", "na", "none", "unknown", "placeholder", "fix later", "adds flavor", "continues story", "..."}


class Reporter:
    def __init__(self) -> None:
        self.issues: list[dict[str, str]] = []

    def error(self, code: str, path: str, message: str) -> None:
        self.issues.append({"severity": "error", "code": code, "path": path, "message": message})

    def warning(self, code: str, path: str, message: str) -> None:
        self.issues.append({"severity": "warning", "code": code, "path": path, "message": message})

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue["severity"] == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue["severity"] == "warning")


def normalize(value: Any) -> str:
    return " ".join(value.strip().lower().split()) if isinstance(value, str) else ""


def is_blank(value: Any) -> bool:
    return normalize(value) in PLACEHOLDERS


def extract_units(payload: Any, reporter: Reporter) -> tuple[list[tuple[str, dict[str, Any]]], str]:
    if isinstance(payload, dict) and isinstance(payload.get("story_units"), list):
        source = payload["story_units"]
        path = "story_units"
    elif isinstance(payload, dict) and isinstance(payload.get("novel_ledger"), dict) and isinstance(payload["novel_ledger"].get("story_units"), list):
        source = payload["novel_ledger"]["story_units"]
        path = "novel_ledger.story_units"
    elif isinstance(payload, list):
        source = payload
        path = "story_units"
    else:
        reporter.error("missing_story_units", "$", "Expected story_units list, novel_ledger.story_units list, or a list of units.")
        return [], ""
    rows: list[tuple[str, dict[str, Any]]] = []
    for index, item in enumerate(source):
        item_path = f"{path}[{index}]"
        if isinstance(item, dict):
            rows.append((item_path, item))
        else:
            reporter.error("invalid_row_type", item_path, "Story unit must be an object.")
    return rows, path


def check_unit(path: str, unit: dict[str, Any], reporter: Reporter) -> None:
    fields = {"id": str, "kind": str, "parent_id": str, "importance": str, "contribution": str,
              "downstream_use": list, "terminal_treatment": str, "repair_action": str, "evidence_refs": list}
    for field, expected in fields.items():
        if not isinstance(unit.get(field), expected):
            reporter.error("missing_required_field", f"{path}.{field}", "Required plan/domain field is missing.")
    if is_blank(unit.get("contribution")):
        reporter.error("missing_parent_contribution", path, "The current plan has no concrete contribution.")
    treatment = unit.get("terminal_treatment")
    if treatment not in TERMINAL_TREATMENTS:
        reporter.error("invalid_terminal_treatment", path, "Unknown domain treatment.")
    if not unit.get("downstream_use") and not unit.get("plan_terminal") and treatment not in {"cut", "scoped_out"}:
        reporter.error("missing_downstream_use", path, "A nonterminal unit needs a planned downstream consumer.")


def validate(payload: Any, source_path: str) -> dict[str, Any]:
    reporter = Reporter()
    payload, plan_context = project_surface(payload, source_path, "novel_ledger", reporter)
    route_decision: dict[str, Any] | None = None
    target = payload.get("target_artifact") if isinstance(payload, dict) else None
    if target is None and isinstance(payload, dict) and isinstance(payload.get("novel_ledger"), dict):
        target = payload["novel_ledger"].get("target_artifact")
    try:
        route_decision = storyline_route_check.compile_route_decision(target)
    except storyline_route_check.RouteBlocked as exc:
        reporter.error("route_blocked", "target_artifact", str(exc))
    if route_decision is not None and route_decision.get("route_id") != "route:longform":
        reporter.error("route_mismatch", "target_artifact.artifact_type", "Story-contribution rows require the canonical Longform route.")
    unit_rows, collection_path = extract_units(payload, reporter)
    seen: dict[str, str] = {}
    for path, unit in unit_rows:
        unit_id = unit.get("id")
        if isinstance(unit_id, str) and unit_id in seen:
            reporter.error("duplicate_unit_id", f"{path}.id", f"Unit id {unit_id!r} duplicates {seen[unit_id]}.")
        elif isinstance(unit_id, str):
            seen[unit_id] = path
        check_unit(path, unit, reporter)
    if not unit_rows:
        reporter.error("missing_story_units", collection_path or "$", "No story contribution rows were found.")
    return {
        "schema_version": "storyline-design.story_contribution_check.report.v1",
        "source_path": source_path,
        "collection_path": collection_path,
        "route_decision": route_decision,
        "passed": reporter.error_count == 0,
        "summary": {"error_count": reporter.error_count, "warning_count": reporter.warning_count, "issue_count": len(reporter.issues), "unit_count": len(unit_rows)},
        "issues": reporter.issues,
    }


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate long-form story contribution rows.")
    parser.add_argument("input")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = validate(load_json(Path(args.input)), args.input)
    except OSError as exc:
        report = validate({}, args.input)
        report["issues"].append({"severity": "error", "code": "read_error", "path": args.input, "message": str(exc)})
        report["passed"] = False
        report["summary"]["error_count"] += 1
    except json.JSONDecodeError as exc:
        report = validate({}, args.input)
        report["issues"].append({"severity": "error", "code": "json_decode_error", "path": args.input, "message": f"{exc.msg} at line {exc.lineno}, column {exc.colno}"})
        report["passed"] = False
        report["summary"]["error_count"] += 1
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Story contribution check: {'passed' if report['passed'] else 'failed'}")
        for issue in report["issues"]:
            print(f"- [{issue['severity']}] {issue['code']} at {issue['path']}: {issue['message']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
