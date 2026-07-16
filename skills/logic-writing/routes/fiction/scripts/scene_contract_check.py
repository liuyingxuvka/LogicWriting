#!/usr/bin/env python3
"""Deterministic StorylineDesign scene-contract validator.

This checks scene-card structure and references. It does not judge prose style
or replace WorldGuard review of the linked world claims.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ALLOWED_PROSE_STATUSES = {
    "not_started",
    "sample_only",
    "drafted",
    "revised",
    "final_candidate",
}
ALLOWED_EVIDENCE_STATUSES = {
    "planned",
    "pass",
    "partial",
    "blocked",
    "gap",
    "skipped",
    "stale",
    "human_review",
    "human-review",
}
ALLOWED_CONTRACT_OUTCOMES = {"keep", "revise", "cut", "human_review", "human-review"}
ALLOWED_CLOSURE_EFFECTS = {
    "continue",
    "return_to_ledger",
    "return_to_structure",
    "return_to_scene",
    "return_to_scenes",
    "return_to_promises",
    "return_to_worldguard",
    "return_to_revision",
    "return_to_chapter_interface",
    "return_to_longform_ledger",
    "return_to_voice_style",
    "return_to_reverse_outline",
    "user_decision",
    "scoped_out",
}
ALLOWED_TURN_TYPES = {
    "decision",
    "reveal",
    "reversal",
    "consequence",
    "discovery",
    "commitment",
    "refusal",
    "loss",
    "custom",
}
ALLOWED_PRESSURE_CHANGES = {
    "introduces",
    "escalates",
    "redirects",
    "reverses",
    "concentrates",
    "releases",
    "resolves",
    "complicates",
}
ALLOWED_PROMISE_ROLES = {
    "setup",
    "reminder",
    "escalation",
    "payoff",
    "reversal",
    "deferral",
    "blocker",
    "serial_hook",
    "volume_setup",
    "book_setup",
    "book_payoff",
    "series_deferral",
}
PASSABLE_WORLDGUARD_STATUSES = {"pass"}
PASSABLE_WORLDGUARD_ADAPTER_STATUSES = {"pass", "skipped"}
PASSABLE_WORLDGUARD_CLOSURE_EFFECTS = {"continue", "scoped_out"}
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

REQUIRED_SCENE_FIELDS = {
    "id": str,
    "kind": str,
    "owner_stage": str,
    "parent_structure_id": str,
    "turning_point_links": list,
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
    "evidence_status": str,
    "contract_outcome": str,
    "closure_effect": str,
}

MISSION_FIELDS = ["scene_contract"]
CONFLICT_FIELDS = ["conflict_pressure", "character_desire", "obstacle"]
STATE_CHANGE_FIELDS = ["entry_state", "exit_state", "irreversible_change"]
STORY_FUNCTION_LINK_FIELDS = [
    "promise_links",
    "arc_links",
    "stakes_links",
    "support_links",
    "worldguard_claim_links",
]


class Reporter:
    def __init__(self) -> None:
        self.issues: list[dict[str, str]] = []

    def issue(
        self,
        severity: str,
        code: str,
        path: str,
        message: str,
        scene_id: Any = "",
        field: str = "",
    ) -> None:
        issue = {
            "severity": severity,
            "code": code,
            "path": path,
            "message": message,
        }
        if scene_id:
            issue["scene_id"] = str(scene_id)
        if field:
            issue["field"] = field
        self.issues.append(issue)

    def error(self, code: str, path: str, message: str, scene_id: Any = "", field: str = "") -> None:
        self.issue("error", code, path, message, scene_id, field)

    def warning(self, code: str, path: str, message: str, scene_id: Any = "", field: str = "") -> None:
        self.issue("warning", code, path, message, scene_id, field)

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


def check_type(
    value: Any,
    expected: type | tuple[type, ...],
    path: str,
    reporter: Reporter,
    scene_id: Any = "",
    field: str = "",
) -> bool:
    if isinstance(value, expected):
        return True
    reporter.error(
        "invalid_type",
        path,
        f"Expected {type_name(expected)}, got {type(value).__name__}.",
        scene_id,
        field,
    )
    return False


def check_enum(
    value: Any,
    allowed: set[str],
    path: str,
    reporter: Reporter,
    scene_id: Any = "",
    field: str = "",
) -> None:
    if isinstance(value, str) and value in allowed:
        return
    reporter.error(
        "invalid_enum",
        path,
        f"Value {value!r} is not one of: {', '.join(sorted(allowed))}.",
        scene_id,
        field,
    )


def has_nonempty_list(row: dict[str, Any], field: str) -> bool:
    value = row.get(field)
    return isinstance(value, list) and bool(value)


def path_join(path: str, field: str) -> str:
    return f"{path}.{field}" if path else field


def extract_rows_from_list(items: list[Any], path: str, reporter: Reporter) -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    for index, item in enumerate(items):
        item_path = f"{path}[{index}]"
        if isinstance(item, dict):
            rows.append((item_path, item))
        else:
            reporter.error("invalid_row_type", item_path, "Scene row must be an object.")
    return rows


def extract_scene_rows(payload: Any, reporter: Reporter) -> tuple[list[tuple[str, dict[str, Any]]], str]:
    if isinstance(payload, list):
        return extract_rows_from_list(payload, "scenes", reporter), "scenes"

    if not isinstance(payload, dict):
        reporter.error("invalid_root_type", "$", "Input must be a JSON object or list.")
        return [], ""

    for key in ("scenes", "scene_contracts"):
        if key in payload:
            value = payload[key]
            if not isinstance(value, list):
                reporter.error("invalid_type", key, f"{key} must be a list.")
                return [], key
            return extract_rows_from_list(value, key, reporter), key

    if isinstance(payload.get("scene"), dict):
        return [("scene", payload["scene"])], "scene"

    if "scene_contract" in payload or payload.get("kind") == "scene":
        return [("$", payload)], "$"

    reporter.error(
        "missing_scene_collection",
        "$",
        "Expected a list, a scenes list, a scene_contracts list, a scene object, or a single scene-card object.",
    )
    return [], ""


def extract_id_map(payload: Any, key: str) -> dict[str, tuple[str, dict[str, Any]]]:
    if not isinstance(payload, dict):
        return {}
    value = payload.get(key)
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return {}
    rows: dict[str, tuple[str, dict[str, Any]]] = {}
    for index, item in enumerate(value):
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            rows[item["id"]] = (f"{key}[{index}]", item)
    return rows


def extract_link_id(value: Any, allowed_keys: tuple[str, ...]) -> str | None:
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return None
    for key in allowed_keys:
        candidate = value.get(key)
        if isinstance(candidate, str):
            return candidate
    return None


def check_required_fields(row: dict[str, Any], path: str, reporter: Reporter) -> None:
    scene_id = row.get("id", path)
    for field, expected_type in REQUIRED_SCENE_FIELDS.items():
        field_path = path_join(path, field)
        if field not in row:
            reporter.error(
                "missing_required_field",
                field_path,
                "Required scene contract field is missing.",
                scene_id,
                field,
            )
            continue
        if not check_type(row[field], expected_type, field_path, reporter, scene_id, field):
            continue
        if expected_type is str and is_blank_or_placeholder(row[field]):
            reporter.error(
                "empty_or_placeholder_field",
                field_path,
                "Required scene contract field is empty or placeholder text.",
                scene_id,
                field,
            )


def check_identity_and_enums(row: dict[str, Any], path: str, reporter: Reporter) -> None:
    scene_id = row.get("id", path)
    if "kind" in row and row.get("kind") != "scene":
        reporter.error("invalid_enum", path_join(path, "kind"), "Scene contract kind must be 'scene'.", scene_id, "kind")
    if "owner_stage" in row and row.get("owner_stage") != "scenes":
        reporter.error(
            "invalid_enum",
            path_join(path, "owner_stage"),
            "Scene contract owner_stage must be 'scenes'.",
            scene_id,
            "owner_stage",
        )
    if "prose_status" in row:
        check_enum(row["prose_status"], ALLOWED_PROSE_STATUSES, path_join(path, "prose_status"), reporter, scene_id, "prose_status")
    if "evidence_status" in row:
        check_enum(
            row["evidence_status"],
            ALLOWED_EVIDENCE_STATUSES,
            path_join(path, "evidence_status"),
            reporter,
            scene_id,
            "evidence_status",
        )
    if "contract_outcome" in row:
        check_enum(
            row["contract_outcome"],
            ALLOWED_CONTRACT_OUTCOMES,
            path_join(path, "contract_outcome"),
            reporter,
            scene_id,
            "contract_outcome",
        )
    if "closure_effect" in row:
        check_enum(
            row["closure_effect"],
            ALLOWED_CLOSURE_EFFECTS,
            path_join(path, "closure_effect"),
            reporter,
            scene_id,
            "closure_effect",
        )


def check_mission_conflict_and_state(row: dict[str, Any], path: str, reporter: Reporter) -> None:
    scene_id = row.get("id", path)
    for field in MISSION_FIELDS:
        if field in row and is_blank_or_placeholder(row[field]):
            reporter.error(
                "missing_scene_mission",
                path_join(path, field),
                "Scene mission is missing, empty, or placeholder text.",
                scene_id,
                field,
            )

    for field in CONFLICT_FIELDS:
        if field in row and is_blank_or_placeholder(row[field]):
            reporter.error(
                "missing_conflict_pressure",
                path_join(path, field),
                "Scene conflict/desire/obstacle field is missing, empty, or placeholder text.",
                scene_id,
                field,
            )

    for field in STATE_CHANGE_FIELDS:
        if field in row and is_blank_or_placeholder(row[field]):
            reporter.error(
                "missing_state_change",
                path_join(path, field),
                "Scene state-change field is missing, empty, or placeholder text.",
                scene_id,
                field,
            )

    entry_state = normalize_text(row.get("entry_state"))
    exit_state = normalize_text(row.get("exit_state"))
    if entry_state and exit_state and entry_state == exit_state:
        reporter.error(
            "invalid_state_change",
            path_join(path, "exit_state"),
            "exit_state must differ from entry_state.",
            scene_id,
            "exit_state",
        )


def check_turning_point(row: dict[str, Any], path: str, reporter: Reporter) -> None:
    scene_id = row.get("id", path)
    turn = row.get("turning_point")
    if isinstance(turn, str):
        if is_blank_or_placeholder(turn):
            reporter.error(
                "missing_new_information",
                path_join(path, "turning_point"),
                "turning_point must name the scene's decision, reveal, reversal, consequence, discovery, commitment, or refusal.",
                scene_id,
                "turning_point",
            )
        return

    if not isinstance(turn, dict):
        return

    required_turn_fields = {"turn_type": str, "turn_text": str, "pressure_change": str}
    for field, expected_type in required_turn_fields.items():
        field_path = f"{path}.turning_point.{field}"
        if field not in turn:
            reporter.error("missing_required_field", field_path, "Required turning_point field is missing.", scene_id, f"turning_point.{field}")
            continue
        if not check_type(turn[field], expected_type, field_path, reporter, scene_id, f"turning_point.{field}"):
            continue
        if is_blank_or_placeholder(turn[field]):
            reporter.error(
                "empty_or_placeholder_field",
                field_path,
                "turning_point field is empty or placeholder text.",
                scene_id,
                f"turning_point.{field}",
            )

    if "turn_type" in turn:
        check_enum(turn["turn_type"], ALLOWED_TURN_TYPES, f"{path}.turning_point.turn_type", reporter, scene_id, "turning_point.turn_type")
    if "pressure_change" in turn:
        check_enum(
            turn["pressure_change"],
            ALLOWED_PRESSURE_CHANGES,
            f"{path}.turning_point.pressure_change",
            reporter,
            scene_id,
            "turning_point.pressure_change",
        )

    if "new_information" in row and is_blank_or_placeholder(row.get("new_information")):
        reporter.error(
            "missing_new_information",
            path_join(path, "new_information"),
            "new_information is present but empty or placeholder text.",
            scene_id,
            "new_information",
        )
    elif "new_information" not in row and is_blank_or_placeholder(turn.get("turn_text")):
        reporter.error(
            "missing_new_information",
            f"{path}.turning_point.turn_text",
            "turning_point.turn_text or new_information must identify the new information or pressure-changing turn.",
            scene_id,
            "turning_point.turn_text",
        )


def check_list_field(
    row: dict[str, Any],
    path: str,
    field: str,
    reporter: Reporter,
    required: bool = True,
) -> list[Any]:
    scene_id = row.get("id", path)
    value = row.get(field)
    field_path = path_join(path, field)
    if value is None:
        if required:
            reporter.error("missing_required_field", field_path, "Required link field is missing.", scene_id, field)
        return []
    if not isinstance(value, list):
        reporter.error("invalid_type", field_path, "Link field must be a list.", scene_id, field)
        return []
    if required and not value:
        reporter.error("empty_required_link_list", field_path, "Required link list is empty.", scene_id, field)
    return value


def check_reference_list(
    row: dict[str, Any],
    path: str,
    field: str,
    allowed_keys: tuple[str, ...],
    reporter: Reporter,
    target_map: dict[str, tuple[str, dict[str, Any]]] | None = None,
    target_collection_name: str = "",
    required: bool = True,
) -> list[str]:
    scene_id = row.get("id", path)
    refs: list[str] = []
    values = check_list_field(row, path, field, reporter, required=required)
    for index, item in enumerate(values):
        item_path = f"{path}.{field}[{index}]"
        ref_id = extract_link_id(item, allowed_keys)
        if ref_id is None:
            reporter.error(
                "malformed_reference",
                item_path,
                f"Reference must be a string or object with one of: {', '.join(allowed_keys)}.",
                scene_id,
                field,
            )
            continue
        if is_blank_or_placeholder(ref_id):
            reporter.error(
                "empty_or_placeholder_reference",
                item_path,
                "Reference id is empty or placeholder text.",
                scene_id,
                field,
            )
            continue
        refs.append(ref_id)
        if target_map is None:
            continue
        if not target_map:
            collection_label = target_collection_name or "target"
            reporter.error(
                "missing_resolver_collection",
                item_path,
                f"Reference {ref_id!r} cannot be resolved because {collection_label} is missing or empty.",
                scene_id,
                field,
            )
        elif ref_id not in target_map:
            reporter.error(
                "unresolved_reference",
                item_path,
                f"Reference {ref_id!r} does not resolve in {target_collection_name or 'the available target collection'}.",
                scene_id,
                field,
            )
    return refs


def check_promise_links(
    row: dict[str, Any],
    path: str,
    reporter: Reporter,
    promise_map: dict[str, tuple[str, dict[str, Any]]],
) -> None:
    scene_id = row.get("id", path)
    values = check_list_field(row, path, "promise_links", reporter, required=True)
    for index, item in enumerate(values):
        item_path = f"{path}.promise_links[{index}]"
        promise_id = extract_link_id(item, ("promise_id", "id"))
        if promise_id is None:
            reporter.error(
                "malformed_reference",
                item_path,
                "Promise link must be a string or object with promise_id or id.",
                scene_id,
                "promise_links",
            )
            continue
        if is_blank_or_placeholder(promise_id):
            reporter.error(
                "empty_or_placeholder_reference",
                item_path,
                "Promise reference id is empty or placeholder text.",
                scene_id,
                "promise_links",
            )
            continue
        if not promise_map:
            reporter.error(
                "missing_resolver_collection",
                item_path,
                f"Promise reference {promise_id!r} cannot be resolved because promises is missing or empty.",
                scene_id,
                "promise_links",
            )
        elif promise_id not in promise_map:
            reporter.error(
                "unresolved_reference",
                item_path,
                f"Promise reference {promise_id!r} does not resolve in promises.",
                scene_id,
                "promise_links",
            )
        if isinstance(item, dict):
            role = item.get("role")
            if not isinstance(role, str) or is_blank_or_placeholder(role):
                reporter.error(
                    "missing_promise_role",
                    f"{item_path}.role",
                    "Promise link objects must name setup, reminder, escalation, payoff, reversal, deferral, or blocker role.",
                    scene_id,
                    "promise_links.role",
                )
            elif role not in ALLOWED_PROMISE_ROLES:
                check_enum(role, ALLOWED_PROMISE_ROLES, f"{item_path}.role", reporter, scene_id, "promise_links.role")


def check_story_function_links(row: dict[str, Any], path: str, reporter: Reporter) -> None:
    scene_id = row.get("id", path)
    is_scoped_out = row.get("closure_effect") == "scoped_out" or row.get("contract_outcome") == "cut"
    has_story_function = any(has_nonempty_list(row, field) for field in STORY_FUNCTION_LINK_FIELDS)
    if not has_story_function and not is_scoped_out:
        reporter.error(
            "missing_story_function_link",
            path,
            "Scene must link to a promise, arc, stake, support row, or WorldGuard claim unless cut or scoped out.",
            scene_id,
            "",
        )


def worldguard_claim_passable(claim: dict[str, Any]) -> bool:
    status = claim.get("worldguard_status")
    adapter_status = claim.get("adapter_status")
    closure_effect = claim.get("closure_effect")
    return (
        status in PASSABLE_WORLDGUARD_STATUSES
        or adapter_status in PASSABLE_WORLDGUARD_ADAPTER_STATUSES
        or closure_effect in PASSABLE_WORLDGUARD_CLOSURE_EFFECTS
    )


def check_worldguard_links(
    row: dict[str, Any],
    path: str,
    reporter: Reporter,
    worldguard_map: dict[str, tuple[str, dict[str, Any]]],
) -> None:
    scene_id = row.get("id", path)
    refs = check_reference_list(
        row,
        path,
        "worldguard_claim_links",
        ("worldguard_claim_id", "claim_id", "id"),
        reporter,
        target_map=worldguard_map,
        target_collection_name="worldguard_claims",
        required=True,
    )
    for ref_id in refs:
        if not worldguard_map or ref_id not in worldguard_map:
            continue
        claim_path, claim = worldguard_map[ref_id]
        if not worldguard_claim_passable(claim):
            outcome = row.get("contract_outcome")
            closure_effect = row.get("closure_effect")
            if outcome == "keep" or closure_effect == "continue" or row.get("prose_status") == "final_candidate":
                reporter.error(
                    "worldguard_claim_not_passable",
                    path_join(path, "worldguard_claim_links"),
                    f"WorldGuard claim {ref_id!r} at {claim_path} is not pass, scoped out, or safely narrowed for a keep/continue scene.",
                    scene_id,
                    "worldguard_claim_links",
                )
            else:
                reporter.warning(
                    "worldguard_claim_non_pass",
                    path_join(path, "worldguard_claim_links"),
                    f"WorldGuard claim {ref_id!r} is non-pass; scene must remain revise/cut/human_review with a return path.",
                    scene_id,
                    "worldguard_claim_links",
                )


def check_cross_references(
    row: dict[str, Any],
    path: str,
    reporter: Reporter,
    structure_map: dict[str, tuple[str, dict[str, Any]]],
    turning_point_map: dict[str, tuple[str, dict[str, Any]]],
    promise_map: dict[str, tuple[str, dict[str, Any]]],
    worldguard_map: dict[str, tuple[str, dict[str, Any]]],
) -> None:
    scene_id = row.get("id", path)
    parent_structure_id = row.get("parent_structure_id")
    if isinstance(parent_structure_id, str) and not is_blank_or_placeholder(parent_structure_id):
        if not structure_map:
            reporter.error(
                "missing_resolver_collection",
                path_join(path, "parent_structure_id"),
                f"Parent structure {parent_structure_id!r} cannot be resolved because structure is missing or empty.",
                scene_id,
                "parent_structure_id",
            )
        elif parent_structure_id not in structure_map:
            reporter.error(
                "unresolved_reference",
                path_join(path, "parent_structure_id"),
                f"Parent structure {parent_structure_id!r} does not resolve in structure.",
                scene_id,
                "parent_structure_id",
            )

    check_reference_list(
        row,
        path,
        "turning_point_links",
        ("turning_point_id", "id"),
        reporter,
        target_map=turning_point_map,
        target_collection_name="turning_points or structure",
        required=True,
    )
    check_promise_links(row, path, reporter, promise_map)
    check_worldguard_links(row, path, reporter, worldguard_map)
    check_story_function_links(row, path, reporter)


def check_outcome_gates(row: dict[str, Any], path: str, reporter: Reporter) -> None:
    scene_id = row.get("id", path)
    outcome = row.get("contract_outcome")
    evidence_status = row.get("evidence_status")
    closure_effect = row.get("closure_effect")
    prose_status = row.get("prose_status")

    if outcome == "keep":
        if evidence_status != "pass":
            reporter.error(
                "keep_requires_pass_evidence",
                path_join(path, "evidence_status"),
                "contract_outcome 'keep' requires evidence_status 'pass'.",
                scene_id,
                "evidence_status",
            )
        if closure_effect != "continue":
            reporter.error(
                "keep_requires_continue",
                path_join(path, "closure_effect"),
                "contract_outcome 'keep' requires closure_effect 'continue'.",
                scene_id,
                "closure_effect",
            )

    if outcome == "revise" and closure_effect == "continue":
        reporter.error(
            "revise_requires_return_path",
            path_join(path, "closure_effect"),
            "contract_outcome 'revise' must return to ledger, structure, scene, promises, WorldGuard, revision, user_decision, or scoped_out.",
            scene_id,
            "closure_effect",
        )

    if outcome == "cut" and prose_status == "final_candidate":
        reporter.error(
            "cut_cannot_be_final_candidate",
            path_join(path, "prose_status"),
            "A cut scene cannot claim final_candidate prose status.",
            scene_id,
            "prose_status",
        )

    if outcome in {"human_review", "human-review"}:
        decision_note = row.get("outcome_reason") or row.get("human_review_question") or row.get("notes")
        if is_blank_or_placeholder(decision_note):
            reporter.error(
                "human_review_requires_decision_note",
                path_join(path, "outcome_reason"),
                "human_review scenes must record the specific decision needed.",
                scene_id,
                "outcome_reason",
            )

    if prose_status == "final_candidate":
        if outcome != "keep" or evidence_status != "pass" or closure_effect != "continue":
            reporter.error(
                "final_candidate_requires_closed_contract",
                path_join(path, "prose_status"),
                "final_candidate prose requires contract_outcome keep, evidence_status pass, and closure_effect continue.",
                scene_id,
                "prose_status",
            )


def check_duplicate_scene_ids(rows: list[tuple[str, dict[str, Any]]], reporter: Reporter) -> None:
    observed: dict[str, str] = {}
    for path, row in rows:
        scene_id = row.get("id")
        if not isinstance(scene_id, str) or is_blank_or_placeholder(scene_id):
            continue
        if scene_id in observed:
            reporter.error(
                "duplicate_scene_id",
                path_join(path, "id"),
                f"Scene id {scene_id!r} duplicates {observed[scene_id]}.",
                scene_id,
                "id",
            )
        else:
            observed[scene_id] = path


def validate_scene_contracts(payload: Any, source_path: str) -> dict[str, Any]:
    reporter = Reporter()
    rows, collection_path = extract_scene_rows(payload, reporter)
    structure_map = extract_id_map(payload, "structure")
    turning_point_map = extract_id_map(payload, "turning_points")
    if not turning_point_map:
        turning_point_map = extract_id_map(payload, "structure")
    promise_map = extract_id_map(payload, "promises")
    worldguard_map = extract_id_map(payload, "worldguard_claims")

    if not rows:
        reporter.error("missing_scene_collection", collection_path or "$", "No scene contract rows were found.")

    check_duplicate_scene_ids(rows, reporter)

    for path, row in rows:
        check_required_fields(row, path, reporter)
        check_identity_and_enums(row, path, reporter)
        check_mission_conflict_and_state(row, path, reporter)
        check_turning_point(row, path, reporter)
        check_cross_references(row, path, reporter, structure_map, turning_point_map, promise_map, worldguard_map)
        check_outcome_gates(row, path, reporter)

    return {
        "schema_version": "storyline-design.scene_contract_check.report.v1",
        "source_path": source_path,
        "collection_path": collection_path,
        "passed": reporter.error_count == 0,
        "summary": {
            "error_count": reporter.error_count,
            "warning_count": reporter.warning_count,
            "issue_count": len(reporter.issues),
            "scene_count": len(rows),
            "worldguard_claim_count": len(worldguard_map),
        },
        "issues": reporter.issues,
    }


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def error_report(source_path: str, code: str, message: str) -> dict[str, Any]:
    return {
        "schema_version": "storyline-design.scene_contract_check.report.v1",
        "source_path": source_path,
        "collection_path": "",
        "passed": False,
        "summary": {
            "error_count": 1,
            "warning_count": 0,
            "issue_count": 1,
            "scene_count": 0,
            "worldguard_claim_count": 0,
        },
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
    print(f"Scene contract check: {'passed' if report['passed'] else 'failed'}")
    print(f"Source: {report['source_path']}")
    print(f"Collection: {report['collection_path']}")
    print(
        "Issues: "
        f"{report['summary']['error_count']} error(s), "
        f"{report['summary']['warning_count']} warning(s)"
    )
    for issue in report["issues"]:
        scene_suffix = f" scene={issue['scene_id']}" if "scene_id" in issue else ""
        field_suffix = f" field={issue['field']}" if "field" in issue else ""
        print(f"- [{issue['severity']}] {issue['code']} at {issue['path']}{scene_suffix}{field_suffix}: {issue['message']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate StorylineDesign scene contract rows.")
    parser.add_argument("input", help="Path to a scene-contract JSON file or StorylineDesign ledger JSON file.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON report.")
    args = parser.parse_args(argv)

    path = Path(args.input)
    try:
        payload = load_json(path)
    except OSError as exc:
        report = error_report(str(path), "read_error", str(exc))
    except json.JSONDecodeError as exc:
        report = error_report(str(path), "json_decode_error", f"{exc.msg} at line {exc.lineno}, column {exc.colno}")
    else:
        report = validate_scene_contracts(payload, str(path))

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_text_report(report)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
