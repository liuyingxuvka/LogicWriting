#!/usr/bin/env python3
"""Derive the only current reader-facing closure from the complete v2 chain."""

from __future__ import annotations

import argparse
import copy
import hashlib
from pathlib import Path
from typing import Any, Mapping

from _common import (
    ValidationError,
    dump_json,
    fingerprint,
    fingerprint_without,
    load_json,
    require_mapping,
    require_schema,
)
from reader_pipeline import (
    validate_artifact_map,
    _compare_reader_audit,
    _build_reader_audit_from_current,
    _reader_judgment_from_current,
    validate_revision_provenance,
    _route_review_from_current,
    validate_route_composition,
    _shared_writing_from_current,
)
from reader_receipts import _commit


REQUIRED_DIMENSIONS = {
    "investigation": (
        "recoverable_question", "bounded_answer", "evidence_strength",
        "negative_evidence", "alternatives", "conditions", "limitations",
        "fallback_recheck", "conclusion_scope",
    ),
    "academic-writing": (
        "research_question", "central_contribution", "hierarchy_progression",
        "paragraph_contribution", "evidence_citation", "method_depth",
        "figure_table_jobs", "qualification_implication",
    ),
    "fiction-writing": (
        "output_room", "story_movement", "resistance_cost", "promise_reveal",
        "continuity", "pov_voice", "reader_state", "actual_spans",
    ),
    "travel-guide": (
        "guide_kind", "traveler_fit", "unit_responsibility", "handoffs",
        "narrative_body", "operational_appendix", "risk_fallback",
        "source_recheck", "local_texture",
    ),
}


def _exact(value: Mapping[str, Any], field: str, label: str) -> str:
    actual = value.get(field)
    if not isinstance(actual, str):
        raise ValidationError(f"{label}.{field} is required")
    return actual


def _canonical_ids(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValidationError(f"{label} must be a sorted string array")
    if any(not isinstance(item, str) or not item for item in value):
        raise ValidationError(f"{label} must contain non-empty strings")
    if value != sorted(value) or len(value) != len(set(value)):
        raise ValidationError(f"{label} must be unique and sorted")
    return list(value)


def _validate_repair_request(value: Any) -> dict[str, Any]:
    request = require_mapping(value, "ReaderRepairRequest")
    require_schema("reader-repair-request.schema.json", request, label="ReaderRepairRequest")
    if request["request_fingerprint"] != fingerprint_without(dict(request), "request_fingerprint"):
        raise ValidationError("ReaderRepairRequest request_fingerprint is stale")
    initial = _canonical_ids(request["initial_defect_ids"], "initial_defect_ids")
    if request["defect_set_fingerprint"] != fingerprint(initial):
        raise ValidationError("ReaderRepairRequest defect set fingerprint is stale")
    return request


def _validate_repair_result(
    value: Any,
    *,
    previous_output_fingerprint: str | None = None,
    expected_request: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    result = require_mapping(value, "ReaderRepairResult")
    require_schema("reader-repair-result.schema.json", result, label="ReaderRepairResult")
    if result["result_fingerprint"] != fingerprint_without(dict(result), "result_fingerprint"):
        raise ValidationError("ReaderRepairResult result_fingerprint is stale")
    remaining = _canonical_ids(result["remaining_defect_ids"], "remaining_defect_ids")
    if result["remaining_defect_set_fingerprint"] != fingerprint(remaining):
        raise ValidationError("ReaderRepairResult remaining defect set fingerprint is stale")
    evidence = require_mapping(result["verification_evidence"], "repair verification evidence")
    if evidence["status"] not in {"current", "missing"}:
        raise ValidationError("ReaderRepairResult verification evidence has an invalid status")
    if evidence["status"] == "missing" and result["progress_status"] != "blocked":
        raise ValidationError("missing repair verification evidence cannot report progress")
    if evidence["artifact_fingerprint"] != result["output_artifact_fingerprint"]:
        raise ValidationError("repair verification evidence is stale for the output artifact")
    if previous_output_fingerprint is not None and result["input_artifact_fingerprint"] != previous_output_fingerprint:
        raise ValidationError("repair results do not form an artifact chain")
    if expected_request is not None:
        initial = set(expected_request["initial_defect_ids"])
        if result["request_fingerprint"] != expected_request["request_fingerprint"]:
            raise ValidationError("ReaderRepairResult belongs to a foreign request")
        if result["repair_id"] != expected_request["repair_id"]:
            raise ValidationError("ReaderRepairResult belongs to a foreign repair")
        if result["defect_lineage"] != expected_request["defect_lineage"]:
            raise ValidationError("ReaderRepairResult defect lineage changed")
        if result["input_artifact_fingerprint"] != expected_request["source_artifact_fingerprint"]:
            raise ValidationError("ReaderRepairResult input is not the request artifact")
        if not set(remaining).issubset(initial):
            raise ValidationError("ReaderRepairResult introduces or renames defect ids")
    return result


def _no_progress_terminal(results: list[Mapping[str, Any]], artifact_fingerprint: str) -> bool:
    if not results:
        return False
    no_progress_indexes = [
        index for index, result in enumerate(results)
        if result["progress_status"] == "no_progress"
    ]
    if not no_progress_indexes:
        return False
    first = no_progress_indexes[0]
    if first != len(results) - 1:
        raise ValidationError(
            "a real no_progress result is terminal; later repair attempts are not allowed"
        )
    return results[-1]["output_artifact_fingerprint"] == artifact_fingerprint


def derive_closure(
    value: Any,
    *,
    receipt_root: str | Path | None = None,
    execution_resolver=None,
) -> dict[str, Any]:
    request = copy.deepcopy(require_mapping(value, "closure input"))
    required = (
        "closure_id", "route_decision", "reader_brief", "route_composition",
        "artifact_map", "shared_writing", "deterministic_audit", "route_review",
        "judgment", "revision_provenance", "native_receipt_fingerprints",
    )
    missing = [field for field in required if field not in request]
    if missing:
        raise ValidationError(f"closure input is missing current v2 fields: {missing}")

    decision = require_mapping(request["route_decision"], "RouteDecision")
    require_schema("route-decision.schema.json", decision, label="RouteDecision")
    owner = decision["final_owner"]
    if decision["schema_version"] != "2.0" or decision["status"] != "current":
        raise ValidationError("closure requires one current v2 RouteDecision")
    brief = require_mapping(request["reader_brief"], "ReaderBrief")
    require_schema("reader-brief.schema.json", brief, label="ReaderBrief")
    if brief["route_decision_fingerprint"] != decision["decision_fingerprint"]:
        raise ValidationError("ReaderBrief is stale for RouteDecision")
    if brief["final_owner"] != owner:
        raise ValidationError("ReaderBrief belongs to a sibling route")

    route = validate_route_composition(
        request["route_composition"],
        owner=owner,
        reader_intent_fingerprint=brief["reader_intent_fingerprint"],
        composition_plan_fingerprint=brief["composition_plan"]["plan_fingerprint"],
        composition_plan=brief["composition_plan"],
        content_boundaries=brief["content_boundaries"],
    )
    amap = validate_artifact_map(request["artifact_map"])
    shared = _shared_writing_from_current(request["shared_writing"], amap=amap, reader_brief=brief)
    audit = require_mapping(request["deterministic_audit"], "ReaderAudit")
    require_schema("reader-audit.schema.json", audit, label="ReaderAudit")
    current_audit = _build_reader_audit_from_current(
        audit_id=audit["audit_id"], amap=amap, brief=brief, contract=shared, audited_at=audit.get("audited_at"))
    audit = _compare_reader_audit(audit, current_audit)
    route_review = _route_review_from_current(
        request["route_review"],
        owner=owner,
        route=route,
        amap=amap,
        required_dimensions=REQUIRED_DIMENSIONS[owner],
    )
    execution_records = [require_mapping(row, "ReaderExecutionRecord") for row in request.get("reader_execution_records", [])]
    judges = [row for row in execution_records if row.get("role") == "judge"]
    if len(judges) > 1:
        raise ValidationError("exactly one judge ReaderExecutionRecord is required")
    judge_execution = judges[0] if judges else None
    judgment = _reader_judgment_from_current(
        request["judgment"],
        amap=amap,
        brief=brief,
        contract=shared,
        audit=audit,
        route_review=route_review,
        execution_record=judge_execution,
    )
    provenance = validate_revision_provenance(
        request["revision_provenance"],
        target_artifact_fingerprint=amap["artifact_fingerprint"],
    )
    if provenance["reader_intent_fingerprint"] != brief["reader_intent_fingerprint"]:
        raise ValidationError("revision provenance is stale for ReaderIntent")
    if provenance["final_owner"] != owner:
        raise ValidationError("revision provenance belongs to a sibling route")

    native_receipts = list(request["native_receipt_fingerprints"])
    if not native_receipts or len(native_receipts) != len(set(native_receipts)):
        raise ValidationError("closure requires unique current native route receipt fingerprints")
    if native_receipts != brief["native_dependency_receipt_fingerprints"]:
        raise ValidationError("closure native receipts differ from the frozen ReaderBrief")

    repair_requests = [
        _validate_repair_request(row)
        for row in request.get("repair_requests", [])
    ]
    if len({row["request_fingerprint"] for row in repair_requests}) != len(repair_requests):
        raise ValidationError("repair requests must have unique fingerprints")
    requests_by_fingerprint = {
        row["request_fingerprint"]: row for row in repair_requests
    }
    repair_results: list[dict[str, Any]] = []
    previous_output: str | None = None
    for row in request.get("repair_results", []):
        result_input = require_mapping(row, "ReaderRepairResult")
        repair_request = (
            requests_by_fingerprint.get(result_input["request_fingerprint"])
            if requests_by_fingerprint
            else None
        )
        if requests_by_fingerprint and repair_request is None:
            raise ValidationError("ReaderRepairResult has no matching repair request")
        current = _validate_repair_result(
            result_input,
            previous_output_fingerprint=previous_output,
            expected_request=repair_request,
        )
        repair_results.append(current)
        previous_output = current["output_artifact_fingerprint"]
    if repair_requests and len(repair_results) != len(repair_requests):
        raise ValidationError("repair requests and results must be paired")
    if repair_results and repair_results[-1]["output_artifact_fingerprint"] != amap["artifact_fingerprint"]:
        raise ValidationError("last repair result does not bind the current artifact")
    if repair_results and repair_results[-1]["verification_evidence"]["status"] == "current":
        evidence = repair_results[-1]["verification_evidence"]
        expected_evidence = {
            "artifact_fingerprint": amap["artifact_fingerprint"],
            "artifact_map_fingerprint": amap["map_fingerprint"],
            "audit_fingerprint": audit["audit_fingerprint"],
            "route_audit_fingerprint": route_review["review_fingerprint"],
            "judgment_fingerprint": judgment["judgment_fingerprint"],
        }
        for key, expected_value in expected_evidence.items():
            if evidence[key] != expected_value:
                raise ValidationError(
                    f"repair verification evidence {key} is stale or foreign"
                )
    all_passed = audit["status"] == route_review["status"] == judgment["status"] == "passed"
    no_progress = _no_progress_terminal(repair_results, amap["artifact_fingerprint"])
    repair_blocked = any(row["progress_status"] == "blocked" for row in repair_results)
    status = "no_progress_blocked" if no_progress else ("passed" if all_passed and not repair_blocked else "blocked")

    defect_ids = [
        *(row["finding_id"] for row in audit["findings"]),
        *(row["finding_id"] for row in route_review["findings"]),
        *(row["observation_id"] for row in judgment["defects"]),
    ]
    if not defect_ids and status != "passed":
        defect_ids = ["reader.quality-gate"]
    residual = [
        {
            "defect_id": defect_id,
            "owner": owner,
            "reason": "The current actual-artifact quality chain has not passed.",
        }
        for defect_id in dict.fromkeys(defect_ids)
    ]
    next_actions = (
        []
        if status == "passed"
        else [{
            "owner": "human_review" if no_progress else owner,
            "action": "human_review" if no_progress else "repair_and_rerun",
        }]
    )
    # A same-call snapshot is useful only while the underlying bytes remain
    # current. Re-read once before emitting or committing any closure receipt.
    try:
        final_bytes = Path(amap["artifact_path"]).read_bytes()
    except OSError as exc:
        raise ValidationError("ArtifactMap artifact is missing before closure") from exc
    if "sha256:" + hashlib.sha256(final_bytes).hexdigest() != amap["artifact_fingerprint"]:
        raise ValidationError("ArtifactMap became stale during closure")
    closure = {
        "schema_version": "2.0",
        "closure_id": request["closure_id"],
        "final_owner": owner,
        "artifact_fingerprint": amap["artifact_fingerprint"],
        "reader_intent_fingerprint": brief["reader_intent_fingerprint"],
        "composition_plan_fingerprint": brief["composition_plan"]["plan_fingerprint"],
        "route_extension_fingerprint": route["extension_fingerprint"],
        "artifact_map_fingerprint": amap["map_fingerprint"],
        "shared_writing_contract_fingerprint": shared["contract_fingerprint"],
        "deterministic_audit_fingerprint": audit["audit_fingerprint"],
        "route_audit_fingerprint": route_review["review_fingerprint"],
        "judgment_fingerprint": judgment["judgment_fingerprint"],
        "reader_execution_record_fingerprints": [row["record_fingerprint"] for row in execution_records],
        "revision_provenance_fingerprint": provenance["provenance_fingerprint"],
        "repair_result_fingerprints": [row["result_fingerprint"] for row in repair_results],
        "native_receipt_fingerprints": native_receipts,
        "status": status,
        "residual_risk": [] if status == "passed" else residual,
        "next_actions": next_actions,
        "safe_claim": (
            "The exact current artifact passed composition coverage, deterministic checks, "
            "route-semantic review, and independent reader judgment."
            if status == "passed"
            else "The exact current artifact is preserved with explicit unresolved reader-facing defects."
        ),
        "unsafe_claim_boundary": (
            "Structural licensing and actual-artifact review do not establish universal factual or aesthetic truth."
        ),
        "broad_claim_allowed": status == "passed",
        "terminal": status in {"passed", "no_progress_blocked"},
    }
    closure["closure_fingerprint"] = fingerprint(closure)
    require_schema("closure.schema.json", closure, label="closure")

    result: dict[str, Any] = {"closure": closure}
    if receipt_root is not None:
        receipt = _commit(
            closure,
            root=receipt_root,
            builder_id="logic-writing.final-closure.v2",
            native_route="derive-final-closure",
            evidence_domain="final_closure",
            semantic_owner_id=f"reader-closure:{closure['closure_id']}",
            covered_obligation_ids=["reader.full-current-chain"],
            input_fingerprints={
                "reader_intent": closure["reader_intent_fingerprint"],
                "composition_plan": closure["composition_plan_fingerprint"],
                "artifact_map": closure["artifact_map_fingerprint"],
                "judgment": closure["judgment_fingerprint"],
            },
            output_field="closure_fingerprint",
            artifact_fingerprint=closure["artifact_fingerprint"],
            dependency_receipt_fingerprints=native_receipts,
            status="current_pass" if status == "passed" else "blocked",
            safe_claim=closure["safe_claim"],
            unsafe_claim_boundary=closure["unsafe_claim_boundary"],
            run_id=f"reader-closure:{closure['closure_id']}:{closure['closure_fingerprint'][7:19]}",
        )
        result["receipt"] = receipt
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    parser.add_argument("--receipt-root")
    args = parser.parse_args()
    try:
        result = derive_closure(load_json(args.input), receipt_root=args.receipt_root)
    except (OSError, ValueError, ValidationError) as exc:
        print(f"ERROR: {exc}")
        return 2
    dump_json(result, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["REQUIRED_DIMENSIONS", "derive_closure"]
