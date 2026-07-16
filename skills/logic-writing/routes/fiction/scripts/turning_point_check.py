#!/usr/bin/env python3
"""Deterministic StorylineDesign turning-point validator.

This checks structure fields and does not judge prose quality.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_REQUIRED_MOMENTS = [
    "setup",
    "first_plot_point",
    "reaction",
    "midpoint",
    "attack",
    "second_plot_point",
    "climax",
    "resolution",
]

EXPECTED_PART_BY_MOMENT = {
    "setup": "part_1_setup",
    "first_plot_point": "part_1_setup",
    "reaction": "part_2_reaction",
    "midpoint": "part_2_reaction",
    "attack": "part_3_attack",
    "second_plot_point": "part_3_attack",
    "climax": "part_4_resolution",
    "resolution": "part_4_resolution",
}

ALLOWED_KINDS = {"structure_unit", "turning_point", "structure_validation"}
ALLOWED_PARTS = {"part_1_setup", "part_2_reaction", "part_3_attack", "part_4_resolution"}
ALLOWED_MOMENTS = set(DEFAULT_REQUIRED_MOMENTS) | {"custom"}
ALLOWED_PRESSURE_CHANGES = {
    "introduces",
    "escalates",
    "redirects",
    "reverses",
    "concentrates",
    "releases",
    "resolves",
}
ALLOWED_STATUSES = {
    "planned",
    "pass",
    "partial",
    "blocked",
    "gap",
    "skipped",
    "stale",
    "human-review",
    "human_review",
}
ALLOWED_CLOSURE_EFFECTS = {
    "continue",
    "return_to_ledger",
    "return_to_structure",
    "return_to_scenes",
    "return_to_promises",
    "return_to_worldguard",
    "return_to_revision",
    "user_decision",
    "scoped_out",
    "blocks_full_closure_until_checked",
}
PLACEHOLDER_VALUES = {
    "tbd",
    "todo",
    "n/a",
    "na",
    "none",
    "unknown",
    "placeholder",
    "fill later",
    "fix later",
    "...",
}

REQUIRED_ROW_FIELDS = {
    "id": str,
    "kind": str,
    "part": str,
    "moment": str,
    "entry_state": str,
    "structural_event": str,
    "choice_or_reveal": str,
    "exit_state": str,
    "irreversible_change": str,
    "pressure_change": str,
    "promise_links": list,
    "status": str,
    "closure_effect": str,
}

FUNCTION_FIELDS = [
    "entry_state",
    "structural_event",
    "choice_or_reveal",
    "exit_state",
    "irreversible_change",
]

LINK_FIELDS = [
    "promise_links",
    "arc_links",
    "worldguard_claim_links",
    "source_rows",
    "stakes_links",
    "scene_links",
    "support_links",
]


class Reporter:
    def __init__(self) -> None:
        self.issues: list[dict[str, str]] = []

    def issue(self, severity: str, code: str, path: str, message: str) -> None:
        self.issues.append(
            {
                "severity": severity,
                "code": code,
                "path": path,
                "message": message,
            }
        )

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


def type_name(expected: type | tuple[type, ...]) -> str:
    if isinstance(expected, tuple):
        return " or ".join(t.__name__ for t in expected)
    return expected.__name__


def normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().lower().split())


def is_blank_or_placeholder(value: Any) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return True
    if normalized in PLACEHOLDER_VALUES:
        return True
    if normalized.startswith("todo") or normalized.startswith("tbd"):
        return True
    if normalized.startswith("[") and normalized.endswith("]"):
        return True
    return False


def has_nonempty_list(row: dict[str, Any], field: str) -> bool:
    value = row.get(field)
    return isinstance(value, list) and len(value) > 0


def parse_required_moments(value: str | None) -> list[str]:
    if not value:
        return list(DEFAULT_REQUIRED_MOMENTS)
    return [part.strip() for part in value.split(",") if part.strip()]


def extract_turning_point_rows(payload: Any, reporter: Reporter) -> tuple[list[tuple[str, dict[str, Any]]], str]:
    if isinstance(payload, list):
        return extract_rows_from_list(payload, "turning_points", reporter), "turning_points"

    if not isinstance(payload, dict):
        reporter.error("invalid_root_type", "$", "Input must be a JSON object or list.")
        return [], ""

    if isinstance(payload.get("turning_points"), list):
        return extract_rows_from_list(payload["turning_points"], "turning_points", reporter), "turning_points"

    if isinstance(payload.get("structure"), list):
        return extract_rows_from_list(payload["structure"], "structure", reporter), "structure"

    if "moment" in payload:
        return [("$", payload)], "$"

    reporter.error(
        "missing_turning_point_collection",
        "$",
        "Expected a list, a turning_points list, a structure list, or a single turning-point object.",
    )
    return [], ""


def extract_rows_from_list(items: list[Any], path: str, reporter: Reporter) -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    for index, item in enumerate(items):
        item_path = f"{path}[{index}]"
        if not isinstance(item, dict):
            reporter.error("invalid_row_type", item_path, "Turning-point row must be an object.")
            continue
        if "moment" not in item and item.get("kind") == "structure_validation":
            continue
        rows.append((item_path, item))
    return rows


def check_type(value: Any, expected: type | tuple[type, ...], path: str, reporter: Reporter) -> bool:
    if isinstance(value, expected):
        return True
    reporter.error("invalid_type", path, f"Expected {type_name(expected)}, got {type(value).__name__}.")
    return False


def check_required_fields(row: dict[str, Any], path: str, reporter: Reporter) -> None:
    for field, expected_type in REQUIRED_ROW_FIELDS.items():
        field_path = f"{path}.{field}"
        if field not in row:
            reporter.error("missing_required_field", field_path, "Required turning-point field is missing.")
            continue
        if not check_type(row[field], expected_type, field_path, reporter):
            continue
        if expected_type is str and is_blank_or_placeholder(row[field]):
            reporter.error("empty_or_placeholder_field", field_path, "Required functional field is empty or placeholder text.")


def check_enum(value: Any, allowed: set[str], path: str, reporter: Reporter) -> None:
    if isinstance(value, str) and value in allowed:
        return
    reporter.error("invalid_enum", path, f"Value {value!r} is not one of: {', '.join(sorted(allowed))}.")


def check_function_description(row: dict[str, Any], path: str, reporter: Reporter) -> None:
    for field in FUNCTION_FIELDS:
        if field in row and is_blank_or_placeholder(row[field]):
            reporter.error(
                "invalid_function_description",
                f"{path}.{field}",
                "Function description is missing, empty, or placeholder text.",
            )

    entry_state = normalize_text(row.get("entry_state"))
    exit_state = normalize_text(row.get("exit_state"))
    if entry_state and exit_state and entry_state == exit_state:
        reporter.error(
            "invalid_state_change",
            f"{path}.exit_state",
            "exit_state must differ from entry_state.",
        )

    event = normalize_text(row.get("structural_event"))
    choice = normalize_text(row.get("choice_or_reveal"))
    if event and choice and event == choice:
        reporter.warning(
            "weak_function_distinction",
            f"{path}.choice_or_reveal",
            "choice_or_reveal duplicates structural_event; confirm the row names the pressure that creates the turn.",
        )


def check_links_and_evidence(row: dict[str, Any], path: str, reporter: Reporter) -> None:
    is_scoped_out = row.get("closure_effect") == "scoped_out" or row.get("status") == "skipped"
    has_required_link = any(has_nonempty_list(row, field) for field in LINK_FIELDS)
    if not has_required_link and not is_scoped_out:
        reporter.error(
            "missing_story_function_link",
            path,
            "Turning point must link to at least one promise, arc, scene, support, stake, source, or WorldGuard claim unless scoped out.",
        )

    if row.get("status") == "pass":
        evidence_refs = row.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not evidence_refs:
            reporter.warning(
                "missing_evidence_ref",
                f"{path}.evidence_refs",
                "Pass rows should include evidence_refs for closure replay.",
            )


def validate_row(row: dict[str, Any], path: str, reporter: Reporter) -> None:
    check_required_fields(row, path, reporter)

    if "kind" in row:
        check_enum(row["kind"], ALLOWED_KINDS, f"{path}.kind", reporter)
    if "part" in row:
        check_enum(row["part"], ALLOWED_PARTS, f"{path}.part", reporter)
    if "moment" in row:
        check_enum(row["moment"], ALLOWED_MOMENTS, f"{path}.moment", reporter)
    if "pressure_change" in row:
        check_enum(row["pressure_change"], ALLOWED_PRESSURE_CHANGES, f"{path}.pressure_change", reporter)
    if "status" in row:
        check_enum(row["status"], ALLOWED_STATUSES, f"{path}.status", reporter)
    if "closure_effect" in row:
        check_enum(row["closure_effect"], ALLOWED_CLOSURE_EFFECTS, f"{path}.closure_effect", reporter)

    moment = row.get("moment")
    expected_part = EXPECTED_PART_BY_MOMENT.get(moment)
    if expected_part and row.get("part") != expected_part:
        reporter.error(
            "invalid_moment_part",
            f"{path}.part",
            f"Moment {moment!r} must be in {expected_part!r}.",
        )

    check_function_description(row, path, reporter)
    check_links_and_evidence(row, path, reporter)


def check_required_moments(
    rows: list[tuple[str, dict[str, Any]]],
    required_moments: list[str],
    reporter: Reporter,
) -> None:
    moment_paths: dict[str, list[str]] = {}
    for path, row in rows:
        moment = row.get("moment")
        if isinstance(moment, str):
            moment_paths.setdefault(moment, []).append(path)

    for moment in required_moments:
        if moment not in ALLOWED_MOMENTS:
            reporter.error("invalid_required_moment", f"required_moments.{moment}", "Required moment is not supported by the turning-point contract.")
            continue
        if moment not in moment_paths:
            reporter.error("missing_required_turning_point", f"required_moments.{moment}", "Required turning point is missing.")
            continue
        if len(moment_paths[moment]) > 1:
            reporter.error(
                "duplicate_required_turning_point",
                f"required_moments.{moment}",
                f"Required moment appears more than once at: {', '.join(moment_paths[moment])}.",
            )


def validate_turning_points(payload: Any, source_path: str, required_moments: list[str]) -> dict[str, Any]:
    reporter = Reporter()
    rows, collection_path = extract_turning_point_rows(payload, reporter)

    for path, row in rows:
        validate_row(row, path, reporter)

    check_required_moments(rows, required_moments, reporter)

    observed_moments = [
        row.get("moment")
        for _, row in rows
        if isinstance(row.get("moment"), str)
    ]
    return {
        "schema_version": "storyline-design.turning_point_check.report.v1",
        "source_path": source_path,
        "collection_path": collection_path,
        "passed": reporter.error_count == 0,
        "summary": {
            "error_count": reporter.error_count,
            "warning_count": reporter.warning_count,
            "issue_count": len(reporter.issues),
            "turning_point_count": len(rows),
        },
        "required_moments": required_moments,
        "observed_moments": observed_moments,
        "issues": reporter.issues,
    }


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def error_report(source_path: str, code: str, message: str) -> dict[str, Any]:
    return {
        "schema_version": "storyline-design.turning_point_check.report.v1",
        "source_path": source_path,
        "collection_path": "",
        "passed": False,
        "summary": {
            "error_count": 1,
            "warning_count": 0,
            "issue_count": 1,
            "turning_point_count": 0,
        },
        "required_moments": [],
        "observed_moments": [],
        "issues": [
            {
                "severity": "error",
                "code": code,
                "path": source_path,
                "message": message,
            }
        ],
    }


def print_text_report(report: dict[str, Any]) -> None:
    print(f"Turning point check: {'passed' if report['passed'] else 'failed'}")
    print(f"Source: {report['source_path']}")
    print(f"Collection: {report['collection_path']}")
    print(
        "Issues: "
        f"{report['summary']['error_count']} error(s), "
        f"{report['summary']['warning_count']} warning(s)"
    )
    for issue in report["issues"]:
        print(f"- [{issue['severity']}] {issue['code']} at {issue['path']}: {issue['message']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate StorylineDesign turning-point rows.")
    parser.add_argument("input", help="Path to a turning-point JSON file or StorylineDesign ledger JSON file.")
    parser.add_argument(
        "--required-moments",
        help="Comma-separated required moments. Defaults to the full-story turning-point set.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON report.")
    args = parser.parse_args(argv)

    path = Path(args.input)
    required_moments = parse_required_moments(args.required_moments)
    try:
        payload = load_json(path)
    except OSError as exc:
        report = error_report(str(path), "read_error", str(exc))
    except json.JSONDecodeError as exc:
        report = error_report(str(path), "json_decode_error", f"{exc.msg} at line {exc.lineno}, column {exc.colno}")
    else:
        report = validate_turning_points(payload, str(path), required_moments)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_text_report(report)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
