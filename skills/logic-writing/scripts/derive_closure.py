#!/usr/bin/env python3
"""Derive the only current reader-facing closure from the complete v2 chain."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping

from _common import ValidationError, dump_json, fingerprint, load_json, require_mapping, require_schema
from reader_pipeline import (
    validate_artifact_map,
    validate_reader_judgment,
    validate_revision_provenance,
    validate_route_artifact_review,
    validate_route_composition,
    validate_shared_writing,
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


def _no_progress_terminal(results: list[Mapping[str, Any]], artifact_fingerprint: str) -> bool:
    if len(results) < 2:
        return False
    left, right = results[-2:]
    for result in (left, right):
        require_schema("reader-repair-result.schema.json", result, label="ReaderRepairResult")
    return (
        left["progress_status"] == right["progress_status"] == "no_progress"
        and left["defect_lineage"] == right["defect_lineage"]
        and left["remaining_defect_set_fingerprint"] == right["remaining_defect_set_fingerprint"]
        and right["output_artifact_fingerprint"] == artifact_fingerprint
        and left["output_artifact_fingerprint"] == right["input_artifact_fingerprint"]
    )


def derive_closure(
    value: Any,
    *,
    receipt_root: str | Path | None = None,
) -> dict[str, Any]:
    request = require_mapping(value, "closure input")
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
    )
    amap = validate_artifact_map(request["artifact_map"])
    shared = validate_shared_writing(
        request["shared_writing"], artifact_map=amap, reader_brief=brief
    )
    audit = require_mapping(request["deterministic_audit"], "ReaderAudit")
    require_schema("reader-audit.schema.json", audit, label="ReaderAudit")
    route_review = validate_route_artifact_review(
        request["route_review"],
        owner=owner,
        route_composition=route,
        artifact_map=amap,
        required_dimensions=REQUIRED_DIMENSIONS[owner],
    )
    judgment = validate_reader_judgment(
        request["judgment"],
        artifact_map=amap,
        reader_brief=brief,
        shared_writing=shared,
        deterministic_audit=audit,
        route_review=route_review,
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

    repair_results = [
        require_mapping(row, "ReaderRepairResult")
        for row in request.get("repair_results", [])
    ]
    all_passed = audit["status"] == route_review["status"] == judgment["status"] == "passed"
    no_progress = _no_progress_terminal(repair_results, amap["artifact_fingerprint"])
    status = "passed" if all_passed else ("no_progress_blocked" if no_progress else "blocked")

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
            native_route="derive-reader-closure",
            evidence_domain="process_freshness",
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
