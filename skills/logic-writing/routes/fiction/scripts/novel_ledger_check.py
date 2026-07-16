#!/usr/bin/env python3
"""Validate StorylineDesign long-form novel ledgers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import storyline_route_check


LEVELS = {"none", "chapter", "volume", "book", "series"}
PASS_STATUSES = {"pass", "passed"}
BLOCKING_STATUSES = {"blocked", "gap", "stale", "unsupported", "human_review", "human-review"}
UNRESOLVED_PROMISE_STATUSES = {
    "open",
    "setup",
    "escalated",
    "payoff_planned",
    "partial",
    "blocked",
    "stale",
    "unsupported",
    "volume_deferred",
    "book_deferred",
}
SERIES_ALLOWED_FOR_BOOK = {"series_deferred", "human_review", "human-review"}
PLACEHOLDERS = {"", "tbd", "todo", "n/a", "na", "none", "unknown", "placeholder", "fix later", "..."}


class Reporter:
    def __init__(self) -> None:
        self.issues: list[dict[str, str]] = []

    def issue(self, severity: str, code: str, path: str, message: str) -> None:
        self.issues.append({"severity": severity, "code": code, "path": path, "message": message})

    def error(self, code: str, path: str, message: str) -> None:
        self.issue("error", code, path, message)

    def warning(self, code: str, path: str, message: str) -> None:
        self.issue("warning", code, path, message)

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue["severity"] == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue["severity"] == "warning")


def text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().lower().split())


def is_blank(value: Any) -> bool:
    return text(value) in PLACEHOLDERS


def is_pass(status: Any) -> bool:
    return isinstance(status, str) and status in PASS_STATUSES


def type_name(expected: type | tuple[type, ...]) -> str:
    if isinstance(expected, tuple):
        return " or ".join(item.__name__ for item in expected)
    return expected.__name__


def check_fields(obj: Any, fields: dict[str, type | tuple[type, ...]], path: str, reporter: Reporter) -> bool:
    if not isinstance(obj, dict):
        reporter.error("invalid_type", path, f"Expected object, got {type(obj).__name__}.")
        return False
    ok = True
    for field, expected in fields.items():
        field_path = f"{path}.{field}" if path else field
        if field not in obj:
            reporter.error("missing_required_field", field_path, "Required field is missing.")
            ok = False
            continue
        if not isinstance(obj[field], expected):
            reporter.error("invalid_type", field_path, f"Expected {type_name(expected)}, got {type(obj[field]).__name__}.")
            ok = False
            continue
        if expected is str and is_blank(obj[field]):
            reporter.error("empty_required_field", field_path, "Required field is empty or placeholder text.")
            ok = False
    return ok


def rows(value: Any, path: str, reporter: Reporter) -> list[tuple[str, dict[str, Any]]]:
    if not isinstance(value, list):
        reporter.error("invalid_type", path, "Expected list.")
        return []
    output: list[tuple[str, dict[str, Any]]] = []
    for index, item in enumerate(value):
        item_path = f"{path}[{index}]"
        if isinstance(item, dict):
            output.append((item_path, item))
        else:
            reporter.error("invalid_row_type", item_path, "Expected object row.")
    return output


def check_nonempty_list(obj: dict[str, Any], field: str, path: str, reporter: Reporter) -> None:
    value = obj.get(field)
    field_path = f"{path}.{field}" if path else field
    if not isinstance(value, list):
        reporter.error("invalid_type", field_path, "Expected list.")
    elif not value:
        reporter.error("empty_required_list", field_path, "Required list is empty.")


def check_unique_ids(named_rows: list[tuple[str, dict[str, Any]]], reporter: Reporter) -> None:
    seen: dict[str, str] = {}
    for path, row in named_rows:
        row_id = row.get("id")
        if not isinstance(row_id, str) or is_blank(row_id):
            continue
        if row_id in seen:
            reporter.error("duplicate_id", f"{path}.id", f"Id {row_id!r} duplicates {seen[row_id]}.")
        seen[row_id] = path


def validate_target(ledger: dict[str, Any], reporter: Reporter) -> tuple[str, dict[str, Any] | None]:
    target = ledger.get("target_artifact")
    fields = {
        "artifact_type": str,
        "closure_level": str,
        "reader_visibility": str,
        "claim_boundary": str,
        "prose_allowed": bool,
    }
    if not check_fields(target, fields, "target_artifact", reporter):
        return "none", None
    if not isinstance(target.get("prose_phase"), str) or not target["prose_phase"]:
        reporter.error("missing_required_field", "target_artifact.prose_phase", "Current prose phase is required.")
        return str(target.get("closure_level", "none")), None
    try:
        route_decision = storyline_route_check.compile_route_decision(target)
    except storyline_route_check.RouteBlocked as exc:
        reporter.error(exc.code, f"target_artifact.{exc.field}" if exc.field else "target_artifact", exc.message)
        route_decision = None
    if route_decision is not None and route_decision.get("route_id") != "route:longform":
        reporter.error("invalid_artifact_type", "target_artifact.artifact_type", "Novel ledger target must compile to the canonical longform route.")
    closure_level = target["closure_level"]
    if closure_level not in LEVELS:
        reporter.error("invalid_closure_level", "target_artifact.closure_level", f"{closure_level!r} is not one of {sorted(LEVELS)}.")
    if route_decision is not None and route_decision.get("closure_level") != closure_level:
        reporter.error("route_closure_level_mismatch", "target_artifact.closure_level", "Declared closure level does not match the canonical route decision.")
    return closure_level, route_decision


def validate_hierarchy(ledger: dict[str, Any], reporter: Reporter) -> dict[str, set[str]]:
    hierarchy = ledger.get("hierarchy")
    if not isinstance(hierarchy, dict):
        reporter.error("invalid_type", "hierarchy", "Hierarchy must be an object.")
        return {"books": set(), "volumes": set(), "chapters": set(), "scenes": set()}
    collections = {"books": set(), "volumes": set(), "chapters": set(), "scenes": set()}
    row_fields = {
        "id": str,
        "kind": str,
        "title": str,
        "parent_id": str,
        "order": (int, float),
        "status": str,
        "summary": str,
        "entry_state": str,
        "exit_state": str,
        "depends_on": list,
        "evidence_refs": list,
    }
    all_rows: list[tuple[str, dict[str, Any]]] = []
    for key in collections:
        collection_rows = rows(hierarchy.get(key), f"hierarchy.{key}", reporter)
        if key in {"books", "chapters"} and not collection_rows:
            reporter.error("missing_required_rows", f"hierarchy.{key}", f"At least one {key[:-1]} row is required.")
        for path, row in collection_rows:
            check_fields(row, row_fields, path, reporter)
            expected_kind = key[:-1]
            if row.get("kind") != expected_kind:
                reporter.error("invalid_kind", f"{path}.kind", f"Expected kind {expected_kind!r}.")
            if isinstance(row.get("status"), str) and row["status"] in BLOCKING_STATUSES:
                reporter.error("blocking_hierarchy_status", f"{path}.status", "Blocking hierarchy status prevents long-form closure.")
            if isinstance(row.get("id"), str):
                collections[key].add(row["id"])
            all_rows.append((path, row))
    check_unique_ids(all_rows, reporter)
    return collections


def validate_story_units(ledger: dict[str, Any], reporter: Reporter) -> None:
    unit_fields = {
        "id": str,
        "kind": str,
        "parent_id": str,
        "importance": str,
        "status": str,
        "contribution": str,
        "downstream_use": list,
        "terminal_treatment": str,
        "repair_action": str,
        "evidence_refs": list,
    }
    unit_rows = rows(ledger.get("story_units"), "story_units", reporter)
    if not unit_rows:
        reporter.error("missing_story_units", "story_units", "Long-form ledgers require story_units contribution rows.")
    check_unique_ids(unit_rows, reporter)
    for path, row in unit_rows:
        check_fields(row, unit_fields, path, reporter)
        if row.get("status") in {"orphan", "duplicate", "weak", "unsupported", "stale", "blocked", "human_review", "human-review"}:
            reporter.error("blocking_story_unit", f"{path}.status", "Story unit requires repair before aggregate closure.")
        if row.get("status") == "pass":
            check_nonempty_list(row, "downstream_use", path, reporter)


def validate_arcs_threads(ledger: dict[str, Any], reporter: Reporter) -> None:
    arc_fields = {"id": str, "arc_type": str, "owner": str, "scope": str, "start_state": str, "turning_points": list, "end_state": str, "linked_chapters": list, "status": str}
    thread_fields = {"id": str, "thread_type": str, "introduced_by": str, "active_in": list, "resolved_by": list, "deferred_to": str, "importance": str, "status": str}
    for path, row in rows(ledger.get("arcs"), "arcs", reporter):
        check_fields(row, arc_fields, path, reporter)
        check_nonempty_list(row, "turning_points", path, reporter)
        check_nonempty_list(row, "linked_chapters", path, reporter)
        if row.get("status") in BLOCKING_STATUSES:
            reporter.error("blocking_arc_status", f"{path}.status", "Arc has a blocking status.")
    for path, row in rows(ledger.get("threads"), "threads", reporter):
        check_fields(row, thread_fields, path, reporter)
        check_nonempty_list(row, "active_in", path, reporter)
        if row.get("importance") in {"key", "major"} and row.get("status") in {"open", "blocked", "unsupported", "stale"}:
            reporter.error("unresolved_thread", f"{path}.status", "Key or major thread is unresolved.")


def validate_promises(ledger: dict[str, Any], closure_level: str, reporter: Reporter) -> None:
    promise_fields = {
        "id": str,
        "importance": str,
        "promise_type": str,
        "introduced_by": list,
        "expected_payoff": (str, dict),
        "status": str,
        "payoff_rows": list,
        "deferral_level": str,
        "claim_boundary": str,
        "evidence_refs": list,
    }
    promise_rows = rows(ledger.get("promises"), "promises", reporter)
    if not promise_rows:
        reporter.error("missing_promises", "promises", "Long-form ledgers require promise rows.")
    for path, row in promise_rows:
        check_fields(row, promise_fields, path, reporter)
        importance = row.get("importance")
        status = row.get("status")
        if importance in {"key", "major"}:
            if closure_level in {"book", "series"} and status in UNRESOLVED_PROMISE_STATUSES:
                reporter.error("unresolved_key_or_major_promise", f"{path}.status", "Key or major promise is unresolved for book/series closure.")
            if status in SERIES_ALLOWED_FOR_BOOK:
                if row.get("deferral_level") != "series" or is_blank(row.get("claim_boundary")):
                    reporter.error("missing_series_deferral_boundary", f"{path}.deferral_level", "Series deferral requires deferral_level='series' and claim_boundary.")
            elif status in {"paid", "inverted", "abandoned_with_reason"}:
                check_nonempty_list(row, "evidence_refs", path, reporter)
            elif status not in {"paid", "inverted", "abandoned_with_reason", "deferred", "series_deferred", "human_review", "human-review"}:
                reporter.error("blocking_promise_status", f"{path}.status", f"Status {status!r} cannot close a key or major promise.")


def validate_continuity(ledger: dict[str, Any], reporter: Reporter) -> None:
    fields = {"id": str, "continuity_type": str, "fact": str, "scope": str, "first_seen": str, "last_checked": str, "affected_units": list, "status": str, "repair_action": str, "evidence_refs": list}
    continuity_rows = rows(ledger.get("continuity"), "continuity", reporter)
    if not continuity_rows:
        reporter.error("missing_continuity", "continuity", "Long-form ledgers require continuity rows.")
    for path, row in continuity_rows:
        check_fields(row, fields, path, reporter)
        check_nonempty_list(row, "affected_units", path, reporter)
        if row.get("status") in {"blocked", "stale", "unsupported", "drift", "human_review", "human-review"}:
            reporter.error("blocking_continuity_status", f"{path}.status", "Continuity row blocks long-form closure.")


def validate_draft_validation_closure(ledger: dict[str, Any], reporter: Reporter) -> None:
    draft_fields = {"chapters_planned": list, "chapters_drafted": list, "chapters_reverse_outlined": list, "current_revision_round": (int, str), "prose_claim_boundary": str, "latest_draft_refs": list, "stale_after": list}
    check_fields(ledger.get("draft_state"), draft_fields, "draft_state", reporter)

    validation_rows = rows(ledger.get("validation"), "validation", reporter)
    if not validation_rows:
        reporter.error("missing_validation", "validation", "Long-form ledgers require validation rows.")
    for path, row in validation_rows:
        check_fields(row, {"id": str, "check_name": str, "surface": str, "checked_ids": list, "status": str, "evidence_ref": str, "rerun_required_when": list}, path, reporter)
        if row.get("status") not in PASS_STATUSES:
            reporter.error("validation_not_passed", f"{path}.status", "Validation rows must pass for the positive ledger fixture.")

    closure_fields = {"closure_level": str, "decision": str, "claim_boundary": str, "blocking_rows": list, "deferred_rows": list, "stale_rows": list, "latest_validation_refs": list, "prose_allowed": bool}
    if check_fields(ledger.get("closure"), closure_fields, "closure", reporter):
        closure = ledger["closure"]
        if closure.get("decision") not in {"pass", "passed", "partial", "blocked", "human_review", "human-review"}:
            reporter.error("invalid_closure_decision", "closure.decision", "Unexpected closure decision.")
        if closure.get("decision") in {"pass", "passed"}:
            for field in ("blocking_rows", "stale_rows"):
                if closure.get(field):
                    reporter.error("closure_has_blocking_rows", f"closure.{field}", "Passing closure cannot include blocking or stale rows.")


def validate_ledger(payload: Any, source_path: str) -> dict[str, Any]:
    reporter = Reporter()
    ledger = payload.get("novel_ledger") if isinstance(payload, dict) and isinstance(payload.get("novel_ledger"), dict) else payload
    if not isinstance(ledger, dict):
        reporter.error("invalid_root_type", "$", "Novel ledger root must be an object.")
        return build_report(source_path, reporter, 0, 0)

    root_fields = {
        "schema_version": str,
        "project_id": str,
        "model_revision": str,
        "target_artifact": dict,
        "longform_scope": dict,
        "hierarchy": dict,
        "story_units": list,
        "arcs": list,
        "threads": list,
        "promises": list,
        "continuity": list,
        "chapter_interfaces": list,
        "draft_state": dict,
        "validation": list,
        "closure": dict,
    }
    check_fields(ledger, root_fields, "", reporter)
    if ledger.get("schema_version") != "storyline-design.novel_ledger.v2":
        reporter.error("invalid_schema_version", "schema_version", "Expected storyline-design.novel_ledger.v2.")

    closure_level, route_decision = validate_target(ledger, reporter)
    scope_fields = {"series_id": str, "book_id": str, "volume_ids": list, "chapter_ids": list, "length_scope": str, "genre_promise": str, "pov_policy": str, "continuity_policy": str, "deferred_scope": list}
    check_fields(ledger.get("longform_scope"), scope_fields, "longform_scope", reporter)
    hierarchy_ids = validate_hierarchy(ledger, reporter)
    validate_story_units(ledger, reporter)
    validate_arcs_threads(ledger, reporter)
    validate_promises(ledger, closure_level, reporter)
    validate_continuity(ledger, reporter)
    validate_draft_validation_closure(ledger, reporter)
    report = build_report(source_path, reporter, len(hierarchy_ids["chapters"]), len(ledger.get("promises", [])) if isinstance(ledger.get("promises"), list) else 0)
    report["project_id"] = ledger.get("project_id", "")
    report["model_revision"] = ledger.get("model_revision", "")
    report["route_decision"] = route_decision
    return report


def build_report(source_path: str, reporter: Reporter, chapter_count: int, promise_count: int) -> dict[str, Any]:
    return {
        "schema_version": "storyline-design.novel_ledger_check.report.v1",
        "source_path": source_path,
        "passed": reporter.error_count == 0,
        "summary": {
            "error_count": reporter.error_count,
            "warning_count": reporter.warning_count,
            "issue_count": len(reporter.issues),
            "chapter_count": chapter_count,
            "promise_count": promise_count,
        },
        "issues": reporter.issues,
    }


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def error_report(source_path: str, code: str, message: str) -> dict[str, Any]:
    reporter = Reporter()
    reporter.error(code, source_path, message)
    return build_report(source_path, reporter, 0, 0)


def print_text_report(report: dict[str, Any]) -> None:
    print(f"Novel ledger check: {'passed' if report['passed'] else 'failed'}")
    print(f"Source: {report['source_path']}")
    for issue in report["issues"]:
        print(f"- [{issue['severity']}] {issue['code']} at {issue['path']}: {issue['message']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a StorylineDesign long-form novel ledger.")
    parser.add_argument("input")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    path = Path(args.input)
    try:
        payload = load_json(path)
    except OSError as exc:
        report = error_report(str(path), "read_error", str(exc))
    except json.JSONDecodeError as exc:
        report = error_report(str(path), "json_decode_error", f"{exc.msg} at line {exc.lineno}, column {exc.colno}")
    else:
        report = validate_ledger(payload, str(path))
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_text_report(report)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
