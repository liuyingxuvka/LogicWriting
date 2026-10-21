"""Map a ResearchGuard LogicGuard synthesis plan into the reader workspace.

The native plan remains provider-owned.  This module validates the small,
versioned handoff surface that Logic Writing is allowed to consume and keeps
the native result and receipt as opaque references.  It deliberately does not
invoke ResearchGuard, manufacture a receipt, or decide whether prose is good.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import copy
import re
from typing import Any

from _common import (
    ValidationError,
    fingerprint,
    fingerprint_without,
    require_fingerprint,
    require_mapping,
    require_schema,
    require_string,
    require_string_list,
)


HANDOFF_SCHEMA = "researchguard-logic-handoff.schema.json"
NATIVE_PLAN_SCHEMA = "researchguard.logic.synthesis-plan.v1"
NATIVE_REQUEST_SCHEMA = "researchguard.logic.synthesis-request.v1"
PROVIDER_ID = "researchguard"
MEMBER_ID = "logicguard"
PRIMARY_PATH_ID = "primary:researchguard:logic"
READY_STATUS = "research_handoff_ready"
BLOCKED_STATUSES = {"blocked_invalid_request", "blocked_budget", "blocked_support_gap"}
NATIVE_STATUSES = {READY_STATUS, *BLOCKED_STATUSES}
PROGRESSIONS = {
    "establishes",
    "explains",
    "contrasts",
    "narrows",
    "applies",
    "concludes",
    "background",
}
PLACEMENTS = {"body", "note", "appendix", "omit"}
PROMINENCE = {"lead", "normal", "brief"}
_NATIVE_RAW_FINGERPRINT = re.compile(r"[a-f0-9]{64}")


def _canonical_native_fingerprint(value: Any, key: str) -> str:
    """Normalize ResearchGuard's raw SHA-256 strings at the adapter boundary.

    ResearchGuard's native model and request fingerprint functions currently
    return the lowercase digest without the ``sha256:`` label used by the
    LogicWriting schemas.  The raw native plan remains hashed separately as
    ``native_result_fingerprint``; only the typed handoff fields are
    normalized here.
    """

    text = require_string({key: value}, key)
    if text.startswith("sha256:"):
        require_fingerprint({key: text}, key)
        return text
    if _NATIVE_RAW_FINGERPRINT.fullmatch(text):
        return f"sha256:{text}"
    raise ValidationError(
        f"{key} must be a lowercase sha256 fingerprint or a 64-character native digest"
    )


def _native_plan(value: Any) -> dict[str, Any]:
    native = require_mapping(value, "ResearchGuard synthesis plan")
    plan = dict(native)
    required = {
        "schema",
        "model_id",
        "target_goal",
        "profile",
        "units",
        "body_unit_order",
        "candidate_dispositions",
        "open_gaps",
        "status",
        "claim_boundary",
        "model_fingerprint",
        "selection_request_fingerprint",
        "request_schema",
    }
    missing = sorted(required - set(plan))
    if missing:
        raise ValidationError("ResearchGuard synthesis plan is missing " + ", ".join(missing))
    if plan["schema"] != NATIVE_PLAN_SCHEMA:
        raise ValidationError("ResearchGuard handoff requires the current synthesis-plan schema")
    if plan["request_schema"] != NATIVE_REQUEST_SCHEMA:
        raise ValidationError("ResearchGuard handoff requires the current synthesis-request schema")
    for field in ("model_id", "target_goal", "profile", "claim_boundary"):
        require_string(plan, field)
    plan["model_fingerprint"] = _canonical_native_fingerprint(
        plan["model_fingerprint"], "model_fingerprint"
    )
    plan["selection_request_fingerprint"] = _canonical_native_fingerprint(
        plan["selection_request_fingerprint"], "selection_request_fingerprint"
    )
    status = require_string(plan, "status")
    if status not in NATIVE_STATUSES:
        raise ValidationError(f"unsupported ResearchGuard synthesis status: {status}")

    units = plan["units"]
    if not isinstance(units, list):
        raise ValidationError("ResearchGuard synthesis plan units must be an array")
    unit_ids: list[str] = []
    for index, row in enumerate(units):
        unit = require_mapping(row, f"ResearchGuard synthesis unit {index}")
        for field in (
            "unit_id",
            "reader_question",
            "unit_job",
            "claim_ids",
            "predecessor_unit_ids",
            "progression_relation",
            "editorial_prominence",
            "placement",
            "placement_reason",
            "required",
            "argument_closure",
            "role_bindings",
            "source_branch_ids",
            "research_importance",
        ):
            if field not in unit:
                raise ValidationError(f"ResearchGuard synthesis unit {index} is missing {field}")
        unit_id = require_string(unit, "unit_id")
        unit_ids.append(unit_id)
        if unit.get("parent_unit_id") is not None:
            if not isinstance(unit["parent_unit_id"], str) or not unit["parent_unit_id"].strip():
                raise ValidationError(f"ResearchGuard unit {unit_id} has an invalid parent_unit_id")
        for field in ("reader_question", "unit_job", "placement_reason"):
            require_string(unit, field)
        for field in ("claim_ids", "predecessor_unit_ids", "argument_closure", "source_branch_ids"):
            require_string_list(unit[field], f"unit {unit_id}.{field}")
        if unit["progression_relation"] not in PROGRESSIONS:
            raise ValidationError(f"ResearchGuard unit {unit_id} has an unsupported progression relation")
        if unit["editorial_prominence"] not in PROMINENCE:
            raise ValidationError(f"ResearchGuard unit {unit_id} has an unsupported editorial prominence")
        if unit["placement"] not in PLACEMENTS:
            raise ValidationError(f"ResearchGuard unit {unit_id} has an unsupported placement")
        if not isinstance(unit["required"], bool):
            raise ValidationError(f"ResearchGuard unit {unit_id}.required must be boolean")
        if unit["required"] and unit["placement"] == "omit":
            raise ValidationError(f"required ResearchGuard unit {unit_id} cannot be omitted")
        if not isinstance(unit["role_bindings"], dict):
            raise ValidationError(f"ResearchGuard unit {unit_id}.role_bindings must be an object")
        for role, refs in unit["role_bindings"].items():
            if not isinstance(role, str) or not role.strip():
                raise ValidationError(f"ResearchGuard unit {unit_id} has an invalid role binding")
            require_string_list(refs, f"unit {unit_id}.role_bindings.{role}")
        if not isinstance(unit["research_importance"], dict):
            raise ValidationError(f"ResearchGuard unit {unit_id}.research_importance must be an object")
        if any(not isinstance(key, str) or not isinstance(value, (int, float)) for key, value in unit["research_importance"].items()):
            raise ValidationError(f"ResearchGuard unit {unit_id}.research_importance must map ids to numbers")
        if "source_branch_candidate_ids" in unit:
            require_string_list(unit["source_branch_candidate_ids"], f"unit {unit_id}.source_branch_candidate_ids")
    if len(unit_ids) != len(set(unit_ids)):
        raise ValidationError("ResearchGuard synthesis unit ids must be unique")
    known_units = set(unit_ids)
    by_id = {row["unit_id"]: row for row in units}
    # Parent links are part of the native hierarchy and must be closed before
    # the plan is exposed to ReaderBrief.  Checking only that a parent is a
    # string would allow a dangling branch or a parent cycle to reach the
    # writer projection.
    for unit_id, row in by_id.items():
        parent = row.get("parent_unit_id")
        if parent is None:
            continue
        if parent not in known_units:
            raise ValidationError(f"ResearchGuard unit {unit_id} has an unknown parent {parent}")
        if parent == unit_id:
            raise ValidationError(f"ResearchGuard unit {unit_id} cannot parent itself")
    for start in by_id:
        seen: set[str] = set()
        current = start
        while True:
            if current in seen:
                raise ValidationError(f"ResearchGuard parent hierarchy contains a cycle at {current}")
            seen.add(current)
            parent = by_id[current].get("parent_unit_id")
            if parent is None:
                break
            current = parent
    body_order = require_string_list(plan["body_unit_order"], "body_unit_order")
    body_ids = {row["unit_id"] for row in units if row["placement"] == "body"}
    if set(body_order) != body_ids or len(body_order) != len(body_ids):
        raise ValidationError("body_unit_order must exactly cover the native body units")
    order = {unit_id: index for index, unit_id in enumerate(body_order)}
    for unit_id, row in by_id.items():
        for predecessor in row["predecessor_unit_ids"]:
            if predecessor not in known_units:
                raise ValidationError(f"ResearchGuard unit {unit_id} has an unknown predecessor {predecessor}")
            if predecessor in order and unit_id in order and order[predecessor] >= order[unit_id]:
                raise ValidationError(f"ResearchGuard unit {unit_id} violates predecessor order for {predecessor}")

    # A predecessor outside the body order (for example a note or appendix)
    # still forms a directed dependency graph.  Close that graph explicitly;
    # body order alone cannot detect a cycle that never enters the body.
    predecessor_state: dict[str, int] = {}

    def visit_predecessors(unit_id: str) -> None:
        state = predecessor_state.get(unit_id, 0)
        if state == 1:
            raise ValidationError(f"ResearchGuard predecessor graph contains a cycle at {unit_id}")
        if state == 2:
            return
        predecessor_state[unit_id] = 1
        for predecessor in by_id[unit_id]["predecessor_unit_ids"]:
            visit_predecessors(predecessor)
        predecessor_state[unit_id] = 2

    for unit_id in by_id:
        visit_predecessors(unit_id)

    dispositions = plan["candidate_dispositions"]
    if not isinstance(dispositions, list):
        raise ValidationError("candidate_dispositions must be an array")
    candidate_ids: list[str] = []
    for index, row in enumerate(dispositions):
        disposition = require_mapping(row, f"candidate disposition {index}")
        for field in ("candidate_id", "candidate_kind", "placement", "reason", "selected_unit_ids"):
            if field not in disposition:
                raise ValidationError(f"candidate disposition {index} is missing {field}")
        candidate_ids.append(require_string(disposition, "candidate_id"))
        require_string(disposition, "candidate_kind")
        if disposition["placement"] not in PLACEMENTS:
            raise ValidationError("candidate disposition has an unsupported placement")
        require_string(disposition, "reason")
        selected = require_string_list(disposition["selected_unit_ids"], "selected_unit_ids")
        unknown = sorted(set(selected) - known_units)
        if unknown:
            raise ValidationError(f"candidate disposition references unknown units: {unknown}")
        if "unit_placements" in disposition:
            placements = disposition["unit_placements"]
            if not isinstance(placements, dict):
                raise ValidationError(f"candidate disposition {candidate_ids[-1]} unit_placements must be an object")
            for unit_id, placement in placements.items():
                if unit_id not in known_units:
                    raise ValidationError(f"candidate disposition references unknown placement unit: {unit_id}")
                if not isinstance(unit_id, str) or not isinstance(placement, str) or placement not in PLACEMENTS:
                    raise ValidationError("candidate disposition unit_placements must map unit ids to placements")
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValidationError("candidate disposition ids must be unique")
    raw_bindings = plan.get("source_branch_bindings", [])
    if not isinstance(raw_bindings, list):
        raise ValidationError("source_branch_bindings must be an array")
    binding_keys: set[tuple[str, str, str]] = set()
    for index, binding in enumerate(raw_bindings):
        if not isinstance(binding, Mapping):
            raise ValidationError(f"source branch binding {index} must be an object")
        for field in ("branch_id", "source_id", "destination_unit_id", "current_native_evidence_ref"):
            require_string(binding, field)
        if binding["destination_unit_id"] not in known_units:
            raise ValidationError(f"source branch binding {index} references an unknown destination unit")
        claims = binding.get("claim_ids", [])
        require_string_list(claims, f"source branch binding {index}.claim_ids")
        key = (binding["source_id"], binding["branch_id"], binding["destination_unit_id"])
        if key in binding_keys:
            raise ValidationError("source branch bindings must be unique")
        binding_keys.add(key)
    gaps = require_string_list(plan["open_gaps"], "open_gaps")
    if status == READY_STATUS:
        if not body_order:
            raise ValidationError("a ready ResearchGuard handoff must contain a body unit")
        if gaps:
            raise ValidationError("a ready ResearchGuard handoff cannot contain open gaps")
    elif not gaps:
        raise ValidationError("a blocked ResearchGuard handoff must preserve at least one open gap")
    return plan


def _unit_projection(unit: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "unit_id": unit["unit_id"],
        "parent_unit_id": unit.get("parent_unit_id"),
        "reader_question": unit["reader_question"],
        "unit_job": unit["unit_job"],
        "claim_ids": list(unit["claim_ids"]),
        "predecessor_unit_ids": list(unit["predecessor_unit_ids"]),
        "progression_relation": unit["progression_relation"],
        "editorial_prominence": unit["editorial_prominence"],
        "placement": unit["placement"],
        "placement_reason": unit["placement_reason"],
        "required": unit["required"],
        "argument_closure": list(unit["argument_closure"]),
        "role_bindings": {key: list(value) for key, value in unit["role_bindings"].items()},
        "source_branch_ids": list(unit["source_branch_ids"]),
        "source_branch_candidate_ids": list(unit.get("source_branch_candidate_ids", [])),
        "research_importance": dict(unit["research_importance"]),
    }


def _disposition_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": row["candidate_id"],
        "candidate_kind": row["candidate_kind"],
        "placement": row["placement"],
        "reason": row["reason"],
        "selected_unit_ids": list(row["selected_unit_ids"]),
        "unit_placements": dict(row.get("unit_placements", {})),
    }


def build_researchguard_handoff(
    native_plan: Mapping[str, Any],
    *,
    reader_intent_fingerprint: str,
    composition_plan_fingerprint: str | None = None,
    writer_input_fingerprint: str | None = None,
    native_result_locator: str,
    native_receipt_fingerprint: str | None = None,
    native_receipt_locator: str | None = None,
) -> dict[str, Any]:
    """Create the current LW handoff projection for one native plan."""

    native = require_mapping(native_plan, "ResearchGuard synthesis plan")
    plan = _native_plan(native)
    inputs = {
        "reader_intent_fingerprint": reader_intent_fingerprint,
        "composition_plan_fingerprint": composition_plan_fingerprint,
        "writer_input_fingerprint": writer_input_fingerprint,
    }
    for field, value in inputs.items():
        if value is not None:
            require_fingerprint({field: value}, field)
    if not isinstance(native_result_locator, str) or not native_result_locator.strip():
        raise ValidationError("native_result_locator must identify the opaque native result")
    if native_receipt_fingerprint is not None:
        require_fingerprint({"native_receipt_fingerprint": native_receipt_fingerprint}, "native_receipt_fingerprint")
    if native_receipt_locator is not None and (not isinstance(native_receipt_locator, str) or not native_receipt_locator.strip()):
        raise ValidationError("native_receipt_locator must be null or non-empty")

    ready = plan["status"] == READY_STATUS
    units = [_unit_projection(row) for row in plan["units"]] if ready else []
    body_order = list(plan["body_unit_order"]) if ready else []
    handoff = {
        "schema_version": "1.0",
        "provider_id": PROVIDER_ID,
        "member_id": MEMBER_ID,
        "primary_path_id": PRIMARY_PATH_ID,
        "native_result_schema_version": NATIVE_PLAN_SCHEMA,
        # Hash the exact native payload before adapter-only fingerprint
        # normalization so the opaque provider result remains byte/identity
        # bound to what ResearchGuard actually returned.
        "native_result_fingerprint": fingerprint(dict(native)),
        "native_result_locator": native_result_locator,
        "native_request_schema_version": plan["request_schema"],
        "native_request_fingerprint": plan["selection_request_fingerprint"],
        "model_id": plan["model_id"],
        "model_fingerprint": plan["model_fingerprint"],
        **inputs,
        "status": "current_pass" if ready else "blocked",
        "native_status": plan["status"],
        "blocking_gaps": [] if ready else list(plan["open_gaps"]),
        "body_unit_order": body_order,
        "units": units,
        "candidate_dispositions": [_disposition_projection(row) for row in plan["candidate_dispositions"]],
        "native_receipt_fingerprint": native_receipt_fingerprint,
        "native_receipt_locator": native_receipt_locator,
        "stage": "consumption_ready" if composition_plan_fingerprint and writer_input_fingerprint else "semantic",
        "source_branch_bindings": [copy.deepcopy(row) for row in native.get("source_branch_bindings", [])],
        "claim_boundary": "This is a LogicGuard unit handoff into the Logic Writing reader workspace. It does not prove factual truth, prose quality, or final closure.",
    }
    handoff["handoff_fingerprint"] = fingerprint_without(handoff, "handoff_fingerprint")
    require_schema(HANDOFF_SCHEMA, handoff, label="ResearchGuard Logic handoff")
    return handoff


def validate_researchguard_handoff(
    value: Mapping[str, Any],
    native_plan: Mapping[str, Any],
    *,
    reader_intent_fingerprint: str,
    composition_plan_fingerprint: str | None = None,
    writer_input_fingerprint: str | None = None,
    native_receipt_fingerprint: str | None = None,
    native_receipt_locator: str | None = None,
) -> dict[str, Any]:
    """Rebuild and compare a handoff so stale or caller-authored fields fail."""

    handoff = require_mapping(value, "ResearchGuard Logic handoff")
    require_schema(HANDOFF_SCHEMA, handoff, label="ResearchGuard Logic handoff")
    require_fingerprint(handoff, "handoff_fingerprint")
    if handoff["handoff_fingerprint"] != fingerprint_without(handoff, "handoff_fingerprint"):
        raise ValidationError("ResearchGuard Logic handoff fingerprint is stale")
    expected = build_researchguard_handoff(
        native_plan,
        reader_intent_fingerprint=reader_intent_fingerprint,
        composition_plan_fingerprint=composition_plan_fingerprint,
        writer_input_fingerprint=writer_input_fingerprint,
        native_result_locator=handoff["native_result_locator"],
        native_receipt_fingerprint=(
            native_receipt_fingerprint
            if native_receipt_fingerprint is not None
            else handoff.get("native_receipt_fingerprint")
        ),
        native_receipt_locator=(
            native_receipt_locator
            if native_receipt_locator is not None
            else handoff.get("native_receipt_locator")
        ),
    )
    left = {key: item for key, item in handoff.items() if key != "handoff_fingerprint"}
    right = {key: item for key, item in expected.items() if key != "handoff_fingerprint"}
    if left != right:
        raise ValidationError("ResearchGuard Logic handoff is stale or foreign")
    return handoff


__all__ = [
    "HANDOFF_SCHEMA",
    "build_researchguard_handoff",
    "validate_researchguard_handoff",
]
