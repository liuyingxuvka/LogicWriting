#!/usr/bin/env python3
"""Deterministic StorylineDesign ledger validator."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


TOP_LEVEL_FIELDS = {
    "schema_version": str,
    "project_id": str,
    "ledger_version": str,
    "currentness": dict,
    "target_artifact": dict,
    "premise": dict,
    "theme": dict,
    "protagonist": dict,
    "opposition": dict,
    "stakes": (dict, list),
    "structure": list,
    "scenes": list,
    "character_arcs": list,
    "promises": list,
    "worldguard_claims": list,
    "support": list,
    "validation": list,
    "closure": dict,
}

CURRENTNESS_FIELDS = {
    "created_at": str,
    "updated_at": str,
    "source_revision": str,
    "stale_after": list,
}

TARGET_FIELDS = {
    "artifact_type": str,
    "reader_visibility": str,
    "length_scope": (str, int, float),
    "claim_boundary": str,
    "prose_allowed": bool,
}

PREMISE_FIELDS = {
    "logline": str,
    "dramatic_question": str,
    "starting_state": str,
    "disruption": str,
    "success_condition": str,
    "failure_condition": str,
    "source": str,
}

THEME_FIELDS = {
    "theme_statement": str,
    "counterforce": str,
    "embodiment_rows": list,
    "subtlety_policy": str,
}

PROTAGONIST_FIELDS = {
    "name_or_role": str,
    "external_goal": str,
    "internal_need": str,
    "flaw_or_limit": str,
    "agency_rule": str,
    "arc_start": str,
    "arc_turn": str,
    "arc_end": str,
    "linked_scenes": list,
}

OPPOSITION_FIELDS = {
    "opposition_type": str,
    "pressure_method": str,
    "escalation_path": str,
    "world_constraints": (str, list, dict),
    "linked_claims": list,
}

STAKE_FIELDS = {
    "stake_id": str,
    "stake_type": str,
    "at_risk": str,
    "beneficiary_or_victim": str,
    "escalation_points": list,
    "payoff_link": str,
}

STRUCTURE_FIELDS = {
    "id": str,
    "role": str,
    "entry_state": str,
    "exit_state": str,
    "tension_movement": str,
    "child_scene_ids": list,
    "arc_links": list,
    "promise_links": list,
}

SCENE_FIELDS = {
    "id": str,
    "parent_structure_id": str,
    "scene_contract": str,
    "entry_state": str,
    "exit_state": str,
    "irreversible_change": str,
    "conflict_pressure": str,
    "character_desire": str,
    "obstacle": str,
    "turning_point": (str, dict),
    "promise_links": list,
    "worldguard_claim_links": list,
    "prose_status": str,
}

PROMISE_FIELDS = {
    "id": str,
    "promise_type": str,
    "introduced_by": list,
    "expected_payoff": (str, dict),
    "payoff_rows": list,
    "status": str,
}

WORLDGUARD_FIELDS = {
    "id": str,
    "source_row_id": str,
    "claim_type": str,
    "claim_text": str,
    "authority_scope": str,
    "worldguard_status": str,
    "worldguard_evidence_refs": list,
    "adapter_note": str,
}

SUPPORT_FIELDS = {
    "id": str,
    "support_type": str,
    "content_summary": str,
    "scope": (str, list),
    "authority": str,
    "currentness": str,
    "required_before_prose": bool,
}

VALIDATION_FIELDS = {
    "id": str,
    "check_name": str,
    "checked_rows": list,
    "status": str,
    "evidence_ref": str,
    "invalidates": list,
    "rerun_required_when": list,
}

CLOSURE_FIELDS = {
    "decision": str,
    "claim_boundary": str,
    "blocking_rows": list,
    "deferred_rows": list,
    "stale_rows": list,
    "latest_validation_refs": list,
    "prose_allowed": bool,
    "reader_native_projection_allowed": bool,
}

ENUMS = {
    "target_artifact.artifact_type": {
        "premise",
        "outline",
        "scene_card",
        "chapter_plan",
        "novel",
        "series_plan",
        "book_plan",
        "volume_plan",
        "chapter_batch",
        "chapter_draft",
        "longform_revision_plan",
        "longform_audit",
        "short_story",
        "revision_plan",
        "audit",
        "full_story",
    },
    "target_artifact.reader_visibility": {"reader_native", "planning", "audit", "mixed"},
    "theme.subtlety_policy": {"explicit", "implicit", "ambiguous", "unresolved"},
    "opposition.opposition_type": {
        "antagonist",
        "institution",
        "environment",
        "self",
        "relationship",
        "mystery",
        "norm",
    },
    "stakes.stake_type": {
        "physical",
        "emotional",
        "relational",
        "social",
        "moral",
        "resource",
        "mystery",
        "world-state",
    },
    "structure.role": {
        "opening",
        "disruption",
        "escalation",
        "midpoint",
        "reversal",
        "crisis",
        "climax",
        "resolution",
        "epilogue",
        "custom",
    },
    "structure.tension_movement": {
        "increases",
        "redirects",
        "releases",
        "complicates",
        "resolves",
    },
    "scenes.prose_status": {
        "not_started",
        "sample_only",
        "drafted",
        "revised",
        "final_candidate",
    },
    "promises.promise_type": {
        "dramatic_question",
        "mystery",
        "emotional_contract",
        "clue",
        "threat",
        "desire",
        "norm",
        "thematic_setup",
        "relationship",
        "stakes",
        "genre",
        "support",
    },
    "promises.status": {
        "open",
        "setup",
        "escalated",
        "payoff_planned",
        "paid",
        "inverted",
        "abandoned_with_reason",
        "deferred",
        "volume_deferred",
        "book_deferred",
        "series_deferred",
        "partial",
        "blocked",
        "stale",
        "unsupported",
        "human_review",
        "human-review",
        "pass",
        "reversed",
    },
    "worldguard_claims.claim_type": {
        "event",
        "agent",
        "space",
        "resource",
        "causal",
        "conflict",
        "norm",
        "timeline",
        "authority",
    },
    "worldguard_claims.authority_scope": {
        "user_canon",
        "draft_current",
        "generated_assumption",
        "external_source",
        "unknown",
        "inferred",
    },
    "worldguard_claims.worldguard_status": {
        "pass",
        "fail",
        "gap",
        "boundary_exceeded",
        "stale",
        "stale_source",
        "forbidden_use",
        "not_run",
        "human-review",
        "human_review",
        "authority_cycle",
        "missing_handoff",
    },
    "support.support_type": {
        "user_constraint",
        "premise_support",
        "source_material",
        "generated_assumption",
        "continuity_rule",
        "human_note",
    },
    "support.authority": {"user", "source", "generated", "inferred", "unknown"},
    "support.currentness": {"current", "stale", "superseded", "disputed"},
    "validation.status": {
        "pass",
        "partial",
        "blocked",
        "skipped",
        "stale",
        "downgraded",
        "human-review",
        "human_review",
    },
    "closure.decision": {"pass", "partial", "blocked", "human-review", "human_review"},
}

COMMON_ROW_STATUS = {
    "planned",
    "draft",
    "pass",
    "partial",
    "blocked",
    "gap",
    "skipped",
    "stale",
    "deferred",
    "human-review",
    "human_review",
}

ARTIFACTS_REQUIRING_SCENES = {"chapter_plan", "short_story", "full_story"}
ARTIFACTS_REQUIRING_VALIDATION = {"short_story", "full_story", "revision_plan", "audit"}


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


def is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def check_fields(
    obj: Any,
    fields: dict[str, type | tuple[type, ...]],
    path: str,
    reporter: Reporter,
) -> None:
    if not isinstance(obj, dict):
        reporter.error("invalid_type", path, f"Expected object, got {type(obj).__name__}.")
        return
    for field, expected_type in fields.items():
        field_path = f"{path}.{field}" if path else field
        if field not in obj:
            reporter.error("missing_required_field", field_path, "Required field is missing.")
            continue
        value = obj[field]
        if not isinstance(value, expected_type):
            reporter.error(
                "invalid_type",
                field_path,
                f"Expected {type_name(expected_type)}, got {type(value).__name__}.",
            )
            continue
        if isinstance(value, str) and not value:
            reporter.error("empty_required_field", field_path, "Required field is empty.")


def check_enum(
    value: Any,
    allowed: set[str],
    path: str,
    reporter: Reporter,
    code: str = "invalid_enum",
) -> None:
    if isinstance(value, str) and value in allowed:
        return
    reporter.error(code, path, f"Value {value!r} is not one of: {', '.join(sorted(allowed))}.")


def row_items(value: Any, path: str, reporter: Reporter) -> list[tuple[str, dict[str, Any]]]:
    if isinstance(value, dict):
        return [(path, value)]
    if isinstance(value, list):
        rows: list[tuple[str, dict[str, Any]]] = []
        for index, item in enumerate(value):
            item_path = f"{path}[{index}]"
            if isinstance(item, dict):
                rows.append((item_path, item))
            else:
                reporter.error("invalid_row_type", item_path, "Expected object row.")
        return rows
    reporter.error("invalid_type", path, "Expected object or list of objects.")
    return []


def check_row_status(row: dict[str, Any], path: str, reporter: Reporter) -> None:
    if "status" not in row:
        return
    status = row["status"]
    if not isinstance(status, str):
        reporter.error("invalid_type", f"{path}.status", "Status must be a string.")
    elif status not in COMMON_ROW_STATUS and status not in ENUMS["promises.status"]:
        reporter.error(
            "invalid_enum",
            f"{path}.status",
            f"Status {status!r} is not a legal ledger status.",
        )


def check_rows(
    ledger: dict[str, Any],
    key: str,
    fields: dict[str, type | tuple[type, ...]],
    reporter: Reporter,
) -> None:
    for path, row in row_items(ledger.get(key), key, reporter):
        check_fields(row, fields, path, reporter)
        check_row_status(row, path, reporter)


def check_core_design_elements(ledger: dict[str, Any], reporter: Reporter) -> None:
    target = ledger.get("target_artifact") if isinstance(ledger.get("target_artifact"), dict) else {}
    artifact_type = target.get("artifact_type")

    if not isinstance(ledger.get("premise"), dict) or not ledger["premise"]:
        reporter.error("missing_core_design_element", "premise", "Premise must be present.")
    if not isinstance(ledger.get("protagonist"), dict) or not ledger["protagonist"]:
        reporter.error("missing_core_design_element", "protagonist", "Protagonist must be present.")
    if not isinstance(ledger.get("opposition"), dict) or not ledger["opposition"]:
        reporter.error("missing_core_design_element", "opposition", "Opposition must be present.")
    if not ledger.get("stakes"):
        reporter.error("missing_core_design_element", "stakes", "At least one stakes row or stakes object is required.")
    if not ledger.get("structure"):
        reporter.error("missing_core_design_element", "structure", "At least one structure row is required.")
    if artifact_type in ARTIFACTS_REQUIRING_SCENES and not ledger.get("scenes"):
        reporter.error(
            "missing_core_design_element",
            "scenes",
            f"Artifact type {artifact_type!r} requires scene rows.",
        )
    if artifact_type in {"short_story", "full_story", "chapter_plan"} and not ledger.get("promises"):
        reporter.error(
            "missing_core_design_element",
            "promises",
            f"Artifact type {artifact_type!r} requires promise/payoff rows.",
        )
    if artifact_type in ARTIFACTS_REQUIRING_VALIDATION and not ledger.get("validation"):
        reporter.warning(
            "missing_validation_evidence",
            "validation",
            f"Artifact type {artifact_type!r} should include validation rows before closure claims.",
        )


def check_cross_links(ledger: dict[str, Any], reporter: Reporter) -> None:
    scene_ids = {row.get("id") for row in ledger.get("scenes", []) if isinstance(row, dict)}
    structure_ids = {row.get("id") for row in ledger.get("structure", []) if isinstance(row, dict)}
    promise_ids = {row.get("id") for row in ledger.get("promises", []) if isinstance(row, dict)}

    for index, scene in enumerate(ledger.get("scenes", [])):
        if not isinstance(scene, dict):
            continue
        parent_id = scene.get("parent_structure_id")
        if parent_id and structure_ids and parent_id not in structure_ids:
            reporter.error(
                "missing_link_target",
                f"scenes[{index}].parent_structure_id",
                f"Parent structure {parent_id!r} is not defined.",
            )
        for promise_link in scene.get("promise_links", []):
            promise_id = promise_link.get("promise_id") if isinstance(promise_link, dict) else promise_link
            if isinstance(promise_id, str) and promise_ids and promise_id not in promise_ids:
                reporter.warning(
                    "missing_link_target",
                    f"scenes[{index}].promise_links",
                    f"Promise link {promise_id!r} is not defined.",
                )

    for index, structure in enumerate(ledger.get("structure", [])):
        if not isinstance(structure, dict):
            continue
        for scene_id in structure.get("child_scene_ids", []):
            if isinstance(scene_id, str) and scene_ids and scene_id not in scene_ids:
                reporter.warning(
                    "missing_link_target",
                    f"structure[{index}].child_scene_ids",
                    f"Scene link {scene_id!r} is not defined.",
                )


def validate_ledger(ledger: Any, source_path: str) -> dict[str, Any]:
    reporter = Reporter()
    if not isinstance(ledger, dict):
        reporter.error("invalid_root_type", "$", "Ledger root must be a JSON object.")
        return build_report(source_path, reporter)

    check_fields(ledger, TOP_LEVEL_FIELDS, "", reporter)

    if ledger.get("schema_version") != "storyline-design.ledger.v1":
        reporter.error(
            "invalid_schema_version",
            "schema_version",
            "Expected 'storyline-design.ledger.v1'.",
        )

    check_fields(ledger.get("currentness"), CURRENTNESS_FIELDS, "currentness", reporter)
    check_fields(ledger.get("target_artifact"), TARGET_FIELDS, "target_artifact", reporter)
    check_fields(ledger.get("premise"), PREMISE_FIELDS, "premise", reporter)
    check_fields(ledger.get("theme"), THEME_FIELDS, "theme", reporter)
    check_fields(ledger.get("protagonist"), PROTAGONIST_FIELDS, "protagonist", reporter)
    check_fields(ledger.get("opposition"), OPPOSITION_FIELDS, "opposition", reporter)

    if isinstance(ledger.get("target_artifact"), dict):
        target = ledger["target_artifact"]
        if "artifact_type" in target:
            check_enum(target["artifact_type"], ENUMS["target_artifact.artifact_type"], "target_artifact.artifact_type", reporter)
        if "reader_visibility" in target:
            check_enum(
                target["reader_visibility"],
                ENUMS["target_artifact.reader_visibility"],
                "target_artifact.reader_visibility",
                reporter,
            )

    if isinstance(ledger.get("theme"), dict) and "subtlety_policy" in ledger["theme"]:
        check_enum(ledger["theme"]["subtlety_policy"], ENUMS["theme.subtlety_policy"], "theme.subtlety_policy", reporter)
    if isinstance(ledger.get("opposition"), dict) and "opposition_type" in ledger["opposition"]:
        check_enum(
            ledger["opposition"]["opposition_type"],
            ENUMS["opposition.opposition_type"],
            "opposition.opposition_type",
            reporter,
        )

    for path, row in row_items(ledger.get("stakes"), "stakes", reporter):
        check_fields(row, STAKE_FIELDS, path, reporter)
        if "stake_type" in row:
            check_enum(row["stake_type"], ENUMS["stakes.stake_type"], f"{path}.stake_type", reporter)
        check_row_status(row, path, reporter)

    check_rows(ledger, "structure", STRUCTURE_FIELDS, reporter)
    for index, row in enumerate(ledger.get("structure", [])):
        if not isinstance(row, dict):
            continue
        if "role" in row:
            check_enum(row["role"], ENUMS["structure.role"], f"structure[{index}].role", reporter)
        if "tension_movement" in row:
            check_enum(
                row["tension_movement"],
                ENUMS["structure.tension_movement"],
                f"structure[{index}].tension_movement",
                reporter,
            )

    check_rows(ledger, "scenes", SCENE_FIELDS, reporter)
    for index, row in enumerate(ledger.get("scenes", [])):
        if isinstance(row, dict) and "prose_status" in row:
            check_enum(row["prose_status"], ENUMS["scenes.prose_status"], f"scenes[{index}].prose_status", reporter)

    check_rows(ledger, "promises", PROMISE_FIELDS, reporter)
    for index, row in enumerate(ledger.get("promises", [])):
        if not isinstance(row, dict):
            continue
        if "promise_type" in row:
            check_enum(row["promise_type"], ENUMS["promises.promise_type"], f"promises[{index}].promise_type", reporter)
        if "status" in row:
            check_enum(row["status"], ENUMS["promises.status"], f"promises[{index}].status", reporter)
        if row.get("status") == "deferred" and is_blank(row.get("deferral_reason")):
            reporter.error(
                "missing_required_field",
                f"promises[{index}].deferral_reason",
                "Deferred promises require deferral_reason.",
            )
        if row.get("status") in {"volume_deferred", "book_deferred", "series_deferred"}:
            for field in ("deferral_level", "claim_boundary"):
                if is_blank(row.get(field)):
                    reporter.error(
                        "missing_required_field",
                        f"promises[{index}].{field}",
                        "Long-form deferred promises require deferral_level and claim_boundary.",
                    )

    check_rows(ledger, "worldguard_claims", WORLDGUARD_FIELDS, reporter)
    for index, row in enumerate(ledger.get("worldguard_claims", [])):
        if not isinstance(row, dict):
            continue
        for field in ("claim_type", "authority_scope", "worldguard_status"):
            if field in row:
                check_enum(row[field], ENUMS[f"worldguard_claims.{field}"], f"worldguard_claims[{index}].{field}", reporter)

    check_rows(ledger, "support", SUPPORT_FIELDS, reporter)
    for index, row in enumerate(ledger.get("support", [])):
        if not isinstance(row, dict):
            continue
        for field in ("support_type", "authority", "currentness"):
            if field in row:
                check_enum(row[field], ENUMS[f"support.{field}"], f"support[{index}].{field}", reporter)

    check_rows(ledger, "validation", VALIDATION_FIELDS, reporter)
    for index, row in enumerate(ledger.get("validation", [])):
        if isinstance(row, dict) and "status" in row:
            check_enum(row["status"], ENUMS["validation.status"], f"validation[{index}].status", reporter)

    check_fields(ledger.get("closure"), CLOSURE_FIELDS, "closure", reporter)
    if isinstance(ledger.get("closure"), dict) and "decision" in ledger["closure"]:
        check_enum(ledger["closure"]["decision"], ENUMS["closure.decision"], "closure.decision", reporter)

    check_core_design_elements(ledger, reporter)
    check_cross_links(ledger, reporter)

    return build_report(source_path, reporter)


def build_report(source_path: str, reporter: Reporter) -> dict[str, Any]:
    return {
        "schema_version": "storyline-design.story_ledger_check.report.v1",
        "source_path": source_path,
        "passed": reporter.error_count == 0,
        "summary": {
            "error_count": reporter.error_count,
            "warning_count": reporter.warning_count,
            "issue_count": len(reporter.issues),
        },
        "issues": reporter.issues,
    }


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def print_text_report(report: dict[str, Any]) -> None:
    print(f"Story ledger check: {'passed' if report['passed'] else 'failed'}")
    print(f"Source: {report['source_path']}")
    print(
        "Issues: "
        f"{report['summary']['error_count']} error(s), "
        f"{report['summary']['warning_count']} warning(s)"
    )
    for issue in report["issues"]:
        print(f"- [{issue['severity']}] {issue['code']} at {issue['path']}: {issue['message']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a StorylineDesign story ledger JSON file.")
    parser.add_argument("ledger", help="Path to a StorylineDesign ledger JSON file.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON report.")
    args = parser.parse_args(argv)

    path = Path(args.ledger)
    try:
        ledger = load_json(path)
    except OSError as exc:
        report = {
            "schema_version": "storyline-design.story_ledger_check.report.v1",
            "source_path": str(path),
            "passed": False,
            "summary": {"error_count": 1, "warning_count": 0, "issue_count": 1},
            "issues": [
                {
                    "severity": "error",
                    "code": "read_error",
                    "path": str(path),
                    "message": str(exc),
                }
            ],
        }
    except json.JSONDecodeError as exc:
        report = {
            "schema_version": "storyline-design.story_ledger_check.report.v1",
            "source_path": str(path),
            "passed": False,
            "summary": {"error_count": 1, "warning_count": 0, "issue_count": 1},
            "issues": [
                {
                    "severity": "error",
                    "code": "json_decode_error",
                    "path": str(path),
                    "message": f"{exc.msg} at line {exc.lineno}, column {exc.colno}",
                }
            ],
        }
    else:
        report = validate_ledger(ledger, str(path))

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_text_report(report)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
