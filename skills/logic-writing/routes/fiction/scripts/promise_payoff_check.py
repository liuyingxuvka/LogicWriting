#!/usr/bin/env python3
"""Deterministic StorylineDesign promise/payoff validator.

This checks promise ledger structure, payoff handling, and closure status. It
does not judge prose style or narrative quality.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ALLOWED_PROMISE_TYPES = {
    "dramatic_question",
    "mystery",
    "clue",
    "threat",
    "desire",
    "emotional_contract",
    "relationship",
    "norm",
    "thematic_setup",
    "stakes",
    "genre",
    "support",
}
ALLOWED_SOURCE_KINDS = {
    "premise",
    "structure",
    "scene",
    "character_arc",
    "relationship_arc",
    "support",
    "user_constraint",
}
ALLOWED_IMPORTANCE = {"key", "major", "supporting", "optional", "background"}
ALLOWED_PAYOFF_TYPES = {
    "answer",
    "emotional_release",
    "consequence",
    "reveal",
    "choice",
    "reversal",
    "recognition",
    "deferral",
    "absence",
    "answer_and_cost",
}
ALLOWED_PROMISE_STATUSES = {
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
}
ALLOWED_CURRENT_PAYOFF_STATUSES = ALLOWED_PROMISE_STATUSES | {"not_started", "planned", "not_applicable"}
ALLOWED_CLOSURE_EFFECTS = {
    "continue",
    "return_to_ledger",
    "return_to_structure",
    "return_to_scene",
    "return_to_promises",
    "return_to_worldguard",
    "return_to_revision",
    "user_decision",
    "scoped_out",
    "blocks_full_closure_until_paid_or_deferred",
}
ALLOWED_INVERSION_STATUSES = {
    "not_used",
    "planned",
    "supported",
    "unsupported",
    "blocked",
    "stale",
    "human_review",
    "human-review",
}
ALLOWED_ABANDONMENT_REASONS = {
    "out_of_scope_for_current_artifact",
    "intentionally_unresolved_ending",
    "genre_appropriate_ambiguity",
    "superseded_by_stronger_promise",
    "merged_into_other_payoff",
    "removed_with_scene_cut",
    "user_requested_omission",
    "human_review_decision",
}
BLOCKED_ABANDONMENT_REASONS = {
    "forgotten",
    "no_space",
    "prose_sounds_fine",
    "assumed_resolved",
    "left_for_later",
    "generated_assumption_without_user_or_model_support",
}
ALLOWED_DECISION_SOURCES = {
    "user",
    "reviewer",
    "genre_convention",
    "artifact_boundary",
    "revision_plan",
    "human_review_decision",
}
ALLOWED_LATE_KEY_GUARDRAILS = {
    "not_applicable",
    "accept_with_setup_patch",
    "defer_with_boundary",
    "downgrade_to_supporting",
    "convert_to_inversion",
    "reject_or_cut",
    "human_review",
    "human-review",
}
PENDING_STATUSES = {
    "open",
    "setup",
    "escalated",
    "payoff_planned",
    "partial",
    "blocked",
    "stale",
    "unsupported",
    "human_review",
    "human-review",
}
LONGFORM_DEFERRED_STATUSES = {"volume_deferred", "book_deferred", "series_deferred"}
RESOLVED_STATUSES = {"paid", "inverted", "abandoned_with_reason", "deferred"} | LONGFORM_DEFERRED_STATUSES
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

REQUIRED_PROMISE_FIELDS = {
    "id": str,
    "kind": str,
    "promise_type": str,
    "source_row_id": str,
    "source_row_kind": str,
    "introduced_by": list,
    "promise_text": str,
    "reader_expectation": str,
    "importance": str,
    "expected_payoff": dict,
    "current_payoff": dict,
    "status": str,
    "closure_effect": str,
    "evidence_refs": list,
}
REQUIRED_EXPECTED_PAYOFF_FIELDS = {
    "payoff_type": str,
    "target_rows": list,
    "minimum_evidence": list,
}
REQUIRED_CURRENT_PAYOFF_FIELDS = {
    "status": str,
    "payoff_rows": list,
    "payoff_text": str,
    "payoff_evidence_refs": list,
}


class Reporter:
    def __init__(self) -> None:
        self.issues: list[dict[str, str]] = []

    def issue(
        self,
        severity: str,
        code: str,
        path: str,
        message: str,
        promise_id: Any = "",
        field: str = "",
    ) -> None:
        issue = {
            "severity": severity,
            "code": code,
            "path": path,
            "message": message,
        }
        if promise_id:
            issue["promise_id"] = str(promise_id)
        if field:
            issue["field"] = field
        self.issues.append(issue)

    def error(self, code: str, path: str, message: str, promise_id: Any = "", field: str = "") -> None:
        self.issue("error", code, path, message, promise_id, field)

    def warning(self, code: str, path: str, message: str, promise_id: Any = "", field: str = "") -> None:
        self.issue("warning", code, path, message, promise_id, field)

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


def path_join(path: str, field: str) -> str:
    return f"{path}.{field}" if path else field


def normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().lower().split())


def normalize_code(value: Any) -> str:
    return normalize_text(value).replace("-", "_").replace(" ", "_")


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
    promise_id: Any = "",
    field: str = "",
) -> bool:
    if isinstance(value, expected):
        return True
    reporter.error(
        "invalid_type",
        path,
        f"Expected {type_name(expected)}, got {type(value).__name__}.",
        promise_id,
        field,
    )
    return False


def check_enum(
    value: Any,
    allowed: set[str],
    path: str,
    reporter: Reporter,
    promise_id: Any = "",
    field: str = "",
) -> None:
    if isinstance(value, str) and value in allowed:
        return
    reporter.error(
        "invalid_enum",
        path,
        f"Value {value!r} is not one of: {', '.join(sorted(allowed))}.",
        promise_id,
        field,
    )


def has_nonempty_list(row: dict[str, Any], field: str) -> bool:
    return isinstance(row.get(field), list) and bool(row[field])


def check_required_fields(
    row: dict[str, Any],
    fields: dict[str, type | tuple[type, ...]],
    path: str,
    reporter: Reporter,
    promise_id: Any,
    field_prefix: str = "",
    allow_blank_fields: set[str] | None = None,
) -> None:
    allow_blank_fields = allow_blank_fields or set()
    for field, expected_type in fields.items():
        full_field = f"{field_prefix}.{field}" if field_prefix else field
        field_path = path_join(path, field)
        if field not in row:
            reporter.error("missing_required_field", field_path, "Required promise/payoff field is missing.", promise_id, full_field)
            continue
        if not check_type(row[field], expected_type, field_path, reporter, promise_id, full_field):
            continue
        if expected_type is str and field not in allow_blank_fields and is_blank_or_placeholder(row[field]):
            reporter.error(
                "empty_or_placeholder_field",
                field_path,
                "Required promise/payoff field is empty or placeholder text.",
                promise_id,
                full_field,
            )


def check_nonempty_list(
    value: Any,
    path: str,
    reporter: Reporter,
    promise_id: Any,
    field: str,
    code: str = "empty_required_list",
) -> list[Any]:
    if not isinstance(value, list):
        reporter.error("invalid_type", path, "Expected list.", promise_id, field)
        return []
    if not value:
        reporter.error(code, path, "Required list is empty.", promise_id, field)
        return []
    for index, item in enumerate(value):
        if isinstance(item, str) and is_blank_or_placeholder(item):
            reporter.error(
                "empty_or_placeholder_reference",
                f"{path}[{index}]",
                "Reference entry is empty or placeholder text.",
                promise_id,
                field,
            )
    return value


def extract_rows_from_list(items: list[Any], path: str, reporter: Reporter) -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    for index, item in enumerate(items):
        item_path = f"{path}[{index}]"
        if isinstance(item, dict):
            rows.append((item_path, item))
        else:
            reporter.error("invalid_row_type", item_path, "Promise row must be an object.")
    return rows


def extract_promise_rows(payload: Any, reporter: Reporter) -> tuple[list[tuple[str, dict[str, Any]]], str]:
    if isinstance(payload, list):
        return extract_rows_from_list(payload, "promises", reporter), "promises"

    if not isinstance(payload, dict):
        reporter.error("invalid_root_type", "$", "Input must be a JSON object or list.")
        return [], ""

    for key in ("promises", "promise_payoffs", "promise_payoff"):
        if key in payload:
            value = payload[key]
            if not isinstance(value, list):
                reporter.error("invalid_type", key, f"{key} must be a list.")
                return [], key
            return extract_rows_from_list(value, key, reporter), key

    if isinstance(payload.get("promise"), dict):
        return [("promise", payload["promise"])], "promise"

    if "promise_text" in payload or payload.get("kind") == "promise":
        return [("$", payload)], "$"

    reporter.error(
        "missing_promise_collection",
        "$",
        "Expected a list, a promises list, a promise_payoffs list, a promise object, or a single promise row.",
    )
    return [], ""


def check_duplicate_promise_ids(rows: list[tuple[str, dict[str, Any]]], reporter: Reporter) -> None:
    observed: dict[str, str] = {}
    for path, row in rows:
        promise_id = row.get("id")
        if not isinstance(promise_id, str) or is_blank_or_placeholder(promise_id):
            continue
        if promise_id in observed:
            reporter.error(
                "duplicate_promise_id",
                path_join(path, "id"),
                f"Promise id {promise_id!r} duplicates {observed[promise_id]}.",
                promise_id,
                "id",
            )
        else:
            observed[promise_id] = path


def check_top_level_enums(row: dict[str, Any], path: str, reporter: Reporter) -> None:
    promise_id = row.get("id", path)
    if "kind" in row and row.get("kind") != "promise":
        reporter.error("invalid_enum", path_join(path, "kind"), "Promise row kind must be 'promise'.", promise_id, "kind")
    enum_checks = [
        ("promise_type", ALLOWED_PROMISE_TYPES),
        ("source_row_kind", ALLOWED_SOURCE_KINDS),
        ("importance", ALLOWED_IMPORTANCE),
        ("status", ALLOWED_PROMISE_STATUSES),
        ("closure_effect", ALLOWED_CLOSURE_EFFECTS),
    ]
    for field, allowed in enum_checks:
        if field in row:
            check_enum(row[field], allowed, path_join(path, field), reporter, promise_id, field)


def check_expected_payoff(row: dict[str, Any], path: str, reporter: Reporter) -> None:
    promise_id = row.get("id", path)
    expected = row.get("expected_payoff")
    if not isinstance(expected, dict):
        return
    expected_path = path_join(path, "expected_payoff")
    check_required_fields(expected, REQUIRED_EXPECTED_PAYOFF_FIELDS, expected_path, reporter, promise_id, "expected_payoff")

    if "payoff_type" in expected:
        check_enum(
            expected["payoff_type"],
            ALLOWED_PAYOFF_TYPES,
            path_join(expected_path, "payoff_type"),
            reporter,
            promise_id,
            "expected_payoff.payoff_type",
        )
    if "target_rows" in expected:
        check_nonempty_list(expected["target_rows"], path_join(expected_path, "target_rows"), reporter, promise_id, "expected_payoff.target_rows")
    if "minimum_evidence" in expected:
        check_nonempty_list(
            expected["minimum_evidence"],
            path_join(expected_path, "minimum_evidence"),
            reporter,
            promise_id,
            "expected_payoff.minimum_evidence",
        )


def check_current_payoff(row: dict[str, Any], path: str, reporter: Reporter) -> None:
    promise_id = row.get("id", path)
    current = row.get("current_payoff")
    if not isinstance(current, dict):
        return
    current_path = path_join(path, "current_payoff")
    check_required_fields(
        current,
        REQUIRED_CURRENT_PAYOFF_FIELDS,
        current_path,
        reporter,
        promise_id,
        "current_payoff",
        allow_blank_fields={"payoff_text"},
    )

    if "status" in current:
        check_enum(
            current["status"],
            ALLOWED_CURRENT_PAYOFF_STATUSES,
            path_join(current_path, "status"),
            reporter,
            promise_id,
            "current_payoff.status",
        )


def check_paid_handling(row: dict[str, Any], path: str, reporter: Reporter) -> None:
    promise_id = row.get("id", path)
    status = row.get("status")
    current = row.get("current_payoff") if isinstance(row.get("current_payoff"), dict) else {}
    if status not in {"paid", "inverted", "partial"}:
        return

    if not has_nonempty_list(current, "payoff_rows"):
        reporter.error(
            "missing_required_payoff_handling",
            path_join(path, "current_payoff.payoff_rows"),
            f"Status {status!r} requires payoff_rows.",
            promise_id,
            "current_payoff.payoff_rows",
        )
    if is_blank_or_placeholder(current.get("payoff_text")):
        reporter.error(
            "missing_required_payoff_handling",
            path_join(path, "current_payoff.payoff_text"),
            f"Status {status!r} requires concrete payoff_text.",
            promise_id,
            "current_payoff.payoff_text",
        )
    if status in {"paid", "inverted"} and not has_nonempty_list(current, "payoff_evidence_refs"):
        reporter.error(
            "missing_payoff_evidence",
            path_join(path, "current_payoff.payoff_evidence_refs"),
            f"Status {status!r} requires payoff_evidence_refs.",
            promise_id,
            "current_payoff.payoff_evidence_refs",
        )
    if status in {"paid", "inverted"} and not has_nonempty_list(row, "evidence_refs"):
        reporter.error(
            "missing_payoff_evidence",
            path_join(path, "evidence_refs"),
            f"Status {status!r} requires evidence_refs for terminal replay.",
            promise_id,
            "evidence_refs",
        )


def check_inversion(row: dict[str, Any], path: str, reporter: Reporter) -> None:
    promise_id = row.get("id", path)
    if row.get("status") != "inverted":
        return
    inversion = row.get("inversion")
    inversion_path = path_join(path, "inversion")
    if not isinstance(inversion, dict):
        reporter.error("missing_required_field", inversion_path, "Inverted promises require an inversion object.", promise_id, "inversion")
        return

    required = {
        "inversion_rule": str,
        "requires_setup_rows": list,
        "inverted_expectation": str,
        "actual_payoff": str,
        "affected_rows": list,
        "status": str,
    }
    check_required_fields(inversion, required, inversion_path, reporter, promise_id, "inversion")
    for field in ("inversion_rule", "inverted_expectation", "actual_payoff"):
        if field in inversion and is_blank_or_placeholder(inversion[field]):
            reporter.error(
                "empty_or_placeholder_field",
                path_join(inversion_path, field),
                "Inversion evidence must not be empty or placeholder text.",
                promise_id,
                f"inversion.{field}",
            )
    for field in ("requires_setup_rows", "affected_rows"):
        if field in inversion:
            check_nonempty_list(inversion[field], path_join(inversion_path, field), reporter, promise_id, f"inversion.{field}")
    if "status" in inversion:
        check_enum(inversion["status"], ALLOWED_INVERSION_STATUSES, path_join(inversion_path, "status"), reporter, promise_id, "inversion.status")
        if inversion["status"] != "supported":
            reporter.error(
                "unsupported_inversion",
                path_join(inversion_path, "status"),
                "Inverted promises require inversion.status 'supported' before closure.",
                promise_id,
                "inversion.status",
            )


def check_abandonment(row: dict[str, Any], path: str, reporter: Reporter) -> None:
    promise_id = row.get("id", path)
    status = row.get("status")
    abandonment = row.get("abandonment")
    abandonment_path = path_join(path, "abandonment")

    if status != "abandoned_with_reason":
        return
    if not isinstance(abandonment, dict):
        reporter.error(
            "missing_required_field",
            abandonment_path,
            "abandoned_with_reason promises require an abandonment object.",
            promise_id,
            "abandonment",
        )
        return

    required = {
        "allowed": bool,
        "reason_required": bool,
        "abandoned_with_reason": bool,
        "reason": str,
        "decision_source": str,
        "affected_rows": list,
        "claim_boundary": str,
    }
    check_required_fields(abandonment, required, abandonment_path, reporter, promise_id, "abandonment")

    if abandonment.get("abandoned_with_reason") is not True:
        reporter.error(
            "abandonment_not_confirmed",
            path_join(abandonment_path, "abandoned_with_reason"),
            "abandoned_with_reason status requires abandonment.abandoned_with_reason=true.",
            promise_id,
            "abandonment.abandoned_with_reason",
        )
    reason_code = normalize_code(abandonment.get("reason"))
    if is_blank_or_placeholder(abandonment.get("reason")):
        reporter.error(
            "missing_abandonment_reason",
            path_join(abandonment_path, "reason"),
            "Abandoned promises require a concrete reason.",
            promise_id,
            "abandonment.reason",
        )
    elif reason_code in BLOCKED_ABANDONMENT_REASONS:
        reporter.error(
            "blocked_abandonment_reason",
            path_join(abandonment_path, "reason"),
            f"Abandonment reason {abandonment.get('reason')!r} is explicitly blocked.",
            promise_id,
            "abandonment.reason",
        )
    elif reason_code not in ALLOWED_ABANDONMENT_REASONS:
        reporter.error(
            "invalid_abandonment_reason",
            path_join(abandonment_path, "reason"),
            f"Abandonment reason must be one of: {', '.join(sorted(ALLOWED_ABANDONMENT_REASONS))}.",
            promise_id,
            "abandonment.reason",
        )

    decision_source = abandonment.get("decision_source")
    if isinstance(decision_source, str):
        check_enum(
            decision_source,
            ALLOWED_DECISION_SOURCES,
            path_join(abandonment_path, "decision_source"),
            reporter,
            promise_id,
            "abandonment.decision_source",
        )
    if "affected_rows" in abandonment:
        check_nonempty_list(abandonment["affected_rows"], path_join(abandonment_path, "affected_rows"), reporter, promise_id, "abandonment.affected_rows")
    if is_blank_or_placeholder(abandonment.get("claim_boundary")):
        reporter.error(
            "missing_claim_boundary",
            path_join(abandonment_path, "claim_boundary"),
            "Abandoned promises require a concrete claim boundary.",
            promise_id,
            "abandonment.claim_boundary",
        )


def check_deferred_handling(row: dict[str, Any], path: str, reporter: Reporter) -> None:
    promise_id = row.get("id", path)
    if row.get("status") not in {"deferred"} | LONGFORM_DEFERRED_STATUSES:
        return
    boundary = row.get("claim_boundary") or row.get("deferral_reason")
    current = row.get("current_payoff") if isinstance(row.get("current_payoff"), dict) else {}
    if is_blank_or_placeholder(boundary) and is_blank_or_placeholder(current.get("payoff_text")):
        reporter.error(
            "missing_deferral_boundary",
            path_join(path, "claim_boundary"),
            "Deferred promises require a deferral reason or claim boundary.",
            promise_id,
            "claim_boundary",
        )
    if row.get("status") in LONGFORM_DEFERRED_STATUSES:
        expected_level = row["status"].replace("_deferred", "")
        if row.get("deferral_level") != expected_level:
            reporter.error(
                "missing_longform_deferral_level",
                path_join(path, "deferral_level"),
                f"{row['status']} requires deferral_level {expected_level!r}.",
                promise_id,
                "deferral_level",
            )
        for field in ("next_expected_surface", "reader_fairness_note"):
            if is_blank_or_placeholder(row.get(field)):
                reporter.error(
                    "missing_longform_deferral_field",
                    path_join(path, field),
                    f"{row['status']} requires {field}.",
                    promise_id,
                    field,
                )


def check_pending_handling(row: dict[str, Any], path: str, reporter: Reporter) -> None:
    promise_id = row.get("id", path)
    status = row.get("status")
    if status not in PENDING_STATUSES:
        return
    importance = row.get("importance")
    expected = row.get("expected_payoff") if isinstance(row.get("expected_payoff"), dict) else {}
    current = row.get("current_payoff") if isinstance(row.get("current_payoff"), dict) else {}

    if row.get("closure_effect") == "continue" and importance in {"key", "major"}:
        reporter.error(
            "pending_promise_cannot_continue_closure",
            path_join(path, "closure_effect"),
            f"Key or major promise status {status!r} cannot use closure_effect 'continue'.",
            promise_id,
            "closure_effect",
        )

    if status == "payoff_planned":
        if not has_nonempty_list(expected, "target_rows") and not has_nonempty_list(current, "payoff_rows"):
            reporter.error(
                "missing_required_payoff_handling",
                path_join(path, "current_payoff.payoff_rows"),
                "payoff_planned promises require target_rows or payoff_rows.",
                promise_id,
                "current_payoff.payoff_rows",
            )
    elif status in {"open", "setup", "escalated"} and importance in {"key", "major"}:
        if not has_nonempty_list(expected, "target_rows"):
            reporter.error(
                "missing_required_payoff_handling",
                path_join(path, "expected_payoff.target_rows"),
                f"Key or major status {status!r} requires expected payoff target rows or a defer/abandon/human-review boundary.",
                promise_id,
                "expected_payoff.target_rows",
            )


def check_late_key_promise(row: dict[str, Any], path: str, reporter: Reporter) -> None:
    promise_id = row.get("id", path)
    late = row.get("late_key_promise")
    if not isinstance(late, dict):
        return
    late_path = path_join(path, "late_key_promise")
    if late.get("is_late_key_promise") is True:
        guardrail = late.get("guardrail_status")
        if not isinstance(guardrail, str):
            reporter.error("missing_required_field", path_join(late_path, "guardrail_status"), "Late key promises require guardrail_status.", promise_id, "late_key_promise.guardrail_status")
        else:
            check_enum(guardrail, ALLOWED_LATE_KEY_GUARDRAILS, path_join(late_path, "guardrail_status"), reporter, promise_id, "late_key_promise.guardrail_status")
            if guardrail == "not_applicable":
                reporter.error(
                    "missing_late_key_guardrail",
                    path_join(late_path, "guardrail_status"),
                    "Late key promises require a concrete guardrail outcome.",
                    promise_id,
                    "late_key_promise.guardrail_status",
                )
        if late.get("human_review_required") is True and row.get("status") not in {"human_review", "human-review", "deferred", "abandoned_with_reason"}:
            reporter.warning(
                "late_key_human_review_open",
                path_join(late_path, "human_review_required"),
                "Late key promise marks human review required; status should preserve or resolve that decision.",
                promise_id,
                "late_key_promise.human_review_required",
            )


def check_status_alignment(row: dict[str, Any], path: str, reporter: Reporter) -> None:
    promise_id = row.get("id", path)
    status = row.get("status")
    current = row.get("current_payoff") if isinstance(row.get("current_payoff"), dict) else {}
    current_status = current.get("status")
    if isinstance(status, str) and isinstance(current_status, str):
        if status in RESOLVED_STATUSES and current_status not in {status, "planned", "not_applicable"}:
            reporter.warning(
                "current_payoff_status_mismatch",
                path_join(path, "current_payoff.status"),
                f"current_payoff.status {current_status!r} does not match promise status {status!r}.",
                promise_id,
                "current_payoff.status",
            )
    if status == "unsupported" and row.get("closure_effect") == "continue":
        reporter.error(
            "unsupported_promise_cannot_continue_closure",
            path_join(path, "closure_effect"),
            "Unsupported promises cannot use closure_effect 'continue'.",
            promise_id,
            "closure_effect",
        )


def validate_row(row: dict[str, Any], path: str, reporter: Reporter) -> None:
    promise_id = row.get("id", path)
    check_required_fields(row, REQUIRED_PROMISE_FIELDS, path, reporter, promise_id)
    check_top_level_enums(row, path, reporter)

    if "introduced_by" in row:
        check_nonempty_list(row["introduced_by"], path_join(path, "introduced_by"), reporter, promise_id, "introduced_by")
    if "evidence_refs" in row and row.get("status") in {"paid", "inverted"}:
        check_nonempty_list(row["evidence_refs"], path_join(path, "evidence_refs"), reporter, promise_id, "evidence_refs")

    check_expected_payoff(row, path, reporter)
    check_current_payoff(row, path, reporter)
    check_paid_handling(row, path, reporter)
    check_inversion(row, path, reporter)
    check_abandonment(row, path, reporter)
    check_deferred_handling(row, path, reporter)
    check_pending_handling(row, path, reporter)
    check_late_key_promise(row, path, reporter)
    check_status_alignment(row, path, reporter)


def validate_promises(payload: Any, source_path: str) -> dict[str, Any]:
    reporter = Reporter()
    rows, collection_path = extract_promise_rows(payload, reporter)
    if not rows:
        reporter.error("missing_promise_collection", collection_path or "$", "No promise rows were found.")

    check_duplicate_promise_ids(rows, reporter)
    for path, row in rows:
        validate_row(row, path, reporter)

    observed_statuses = [
        row.get("status")
        for _, row in rows
        if isinstance(row.get("status"), str)
    ]
    status_counts = {status: observed_statuses.count(status) for status in sorted(set(observed_statuses))}
    return {
        "schema_version": "storyline-design.promise_payoff_check.report.v1",
        "source_path": source_path,
        "collection_path": collection_path,
        "passed": reporter.error_count == 0,
        "summary": {
            "error_count": reporter.error_count,
            "warning_count": reporter.warning_count,
            "issue_count": len(reporter.issues),
            "promise_count": len(rows),
        },
        "status_counts": status_counts,
        "issues": reporter.issues,
    }


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def error_report(source_path: str, code: str, message: str) -> dict[str, Any]:
    return {
        "schema_version": "storyline-design.promise_payoff_check.report.v1",
        "source_path": source_path,
        "collection_path": "",
        "passed": False,
        "summary": {
            "error_count": 1,
            "warning_count": 0,
            "issue_count": 1,
            "promise_count": 0,
        },
        "status_counts": {},
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
    print(f"Promise payoff check: {'passed' if report['passed'] else 'failed'}")
    print(f"Source: {report['source_path']}")
    print(f"Collection: {report['collection_path']}")
    print(
        "Issues: "
        f"{report['summary']['error_count']} error(s), "
        f"{report['summary']['warning_count']} warning(s)"
    )
    for issue in report["issues"]:
        promise_suffix = f" promise={issue['promise_id']}" if "promise_id" in issue else ""
        field_suffix = f" field={issue['field']}" if "field" in issue else ""
        print(f"- [{issue['severity']}] {issue['code']} at {issue['path']}{promise_suffix}{field_suffix}: {issue['message']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate StorylineDesign promise/payoff rows.")
    parser.add_argument("input", help="Path to a promise/payoff JSON file or StorylineDesign ledger JSON file.")
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
        report = validate_promises(payload, str(path))

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_text_report(report)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
