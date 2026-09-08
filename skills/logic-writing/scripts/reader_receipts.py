"""Managed v2 receipt builders for the current reader chain."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from _common import fingerprint
from build_source_unit_manifest import fingerprint_bytes
from reader_pipeline import (
    validate_artifact_map,
    validate_reader_judgment,
    validate_route_artifact_review,
    validate_shared_writing,
)
from receipt_authority import _commit_managed_receipt, _store_content_object


def _source_fingerprint() -> str:
    return fingerprint_bytes(Path(__file__).read_bytes())


def _commit(
    artifact: Mapping[str, Any],
    *,
    root: str | Path,
    builder_id: str,
    native_route: str,
    evidence_domain: str,
    semantic_owner_id: str,
    covered_obligation_ids: list[str],
    input_fingerprints: Mapping[str, str],
    output_field: str,
    artifact_fingerprint: str,
    dependency_receipt_fingerprints: list[str],
    status: str,
    safe_claim: str,
    unsafe_claim_boundary: str,
    run_id: str,
) -> dict[str, Any]:
    object_fp = _store_content_object(artifact, root=root)
    artifact_identity = artifact.get(output_field)
    if not isinstance(artifact_identity, str):
        artifact_identity = fingerprint(dict(artifact))
    outputs = {output_field: artifact_identity, f"{output_field}_object": object_fp}
    return _commit_managed_receipt(
        {
            "schema_version": "2.0",
            "producer_skill": "logic-writing",
            "semantic_owner_id": semantic_owner_id,
            "native_route": native_route,
            "run_id": run_id,
            "covered_obligation_ids": covered_obligation_ids,
            "input_fingerprints": dict(input_fingerprints),
            "output_fingerprints": outputs,
            "artifact_fingerprint": artifact_fingerprint,
            "covered_scope": "the exact current reader-chain inputs and output object",
            "evidence_domain": evidence_domain,
            "status": status,
            "safe_claim": safe_claim,
            "unsafe_claim_boundary": unsafe_claim_boundary,
            "sequence_id": run_id,
            "dependency_receipt_fingerprints": list(dict.fromkeys(dependency_receipt_fingerprints)),
        },
        root=root,
        builder_id=builder_id,
        source_fingerprint=fingerprint(
            {
                "builder_source": _source_fingerprint(),
                "inputs": dict(input_fingerprints),
                "output": artifact_identity,
            }
        ),
    )


def commit_shared_writing_receipt(
    *,
    contract: Mapping[str, Any],
    artifact_map: Mapping[str, Any],
    reader_brief: Mapping[str, Any],
    root: str | Path,
    dependency_receipt_fingerprints: list[str],
) -> dict[str, Any]:
    value = validate_shared_writing(
        contract, artifact_map=artifact_map, reader_brief=reader_brief
    )
    return _commit(
        value,
        root=root,
        builder_id="logic-writing.shared-writing.v2",
        native_route="validate-shared-writing",
        evidence_domain="shared_writing",
        semantic_owner_id=f"shared-writing:{value['contract_id']}",
        covered_obligation_ids=["reader.plan-to-byte-binding"],
        input_fingerprints={
            "reader_brief": value["reader_brief_fingerprint"],
            "composition_plan": value["composition_plan_fingerprint"],
            "artifact_map": value["artifact_map_fingerprint"],
        },
        output_field="contract_fingerprint",
        artifact_fingerprint=value["artifact_fingerprint"],
        dependency_receipt_fingerprints=dependency_receipt_fingerprints,
        status="current_pass",
        safe_claim="The current plan, content, model rows, and route surfaces bind exact artifact units and spans.",
        unsafe_claim_boundary="This binding does not decide semantic or aesthetic quality.",
        run_id=f"shared-writing:{value['contract_id']}",
    )


def commit_reader_audit_receipt(
    *,
    audit: Mapping[str, Any],
    root: str | Path,
    dependency_receipt_fingerprints: list[str],
) -> dict[str, Any]:
    status = "current_pass" if audit["status"] == "passed" else "partial"
    return _commit(
        audit,
        root=root,
        builder_id="logic-writing.reader-deterministic.v2",
        native_route="audit-reader-output",
        evidence_domain="reader_deterministic",
        semantic_owner_id=f"reader-audit:{audit['audit_id']}",
        covered_obligation_ids=["reader.deterministic.actual-bytes"],
        input_fingerprints={
            "reader_brief": audit["reader_brief_fingerprint"],
            "composition_plan": audit["composition_plan_fingerprint"],
            "artifact_map": audit["artifact_map_fingerprint"],
            "shared_writing": audit["shared_writing_contract_fingerprint"],
        },
        output_field="audit_fingerprint",
        artifact_fingerprint=audit["artifact_fingerprint"],
        dependency_receipt_fingerprints=dependency_receipt_fingerprints,
        status=status,
        safe_claim="Deterministic checks inspected the exact current artifact bytes and declared zones.",
        unsafe_claim_boundary="Deterministic checks do not prove coherence, naturalness, reader fit, or route semantics.",
        run_id=f"reader-audit:{audit['audit_id']}",
    )


def commit_route_review_receipt(
    *,
    review: Mapping[str, Any],
    route_composition: Mapping[str, Any],
    artifact_map: Mapping[str, Any],
    required_dimensions: list[str],
    root: str | Path,
    dependency_receipt_fingerprints: list[str],
) -> dict[str, Any]:
    value = validate_route_artifact_review(
        review,
        owner=review["final_owner"],
        route_composition=route_composition,
        artifact_map=artifact_map,
        required_dimensions=required_dimensions,
    )
    return _commit(
        value,
        root=root,
        builder_id="logic-writing.route-artifact-review.v2",
        native_route="review-route-artifact",
        evidence_domain="reader_route_audit",
        semantic_owner_id=f"route-review:{value['review_id']}",
        covered_obligation_ids=[f"reader.route-review.{value['final_owner']}"],
        input_fingerprints={
            "route_extension": value["route_extension_fingerprint"],
            "artifact_map": value["artifact_map_fingerprint"],
        },
        output_field="review_fingerprint",
        artifact_fingerprint=value["artifact_fingerprint"],
        dependency_receipt_fingerprints=dependency_receipt_fingerprints,
        status="current_pass" if value["status"] == "passed" else "partial",
        safe_claim="The selected final route reviewed its semantic obligations in exact current artifact spans.",
        unsafe_claim_boundary="The receipt does not transfer route semantic authority to the shared kernel.",
        run_id=f"route-review:{value['review_id']}",
    )


def commit_reader_judgment_receipt(
    *,
    judgment: Mapping[str, Any],
    artifact_map: Mapping[str, Any],
    reader_brief: Mapping[str, Any],
    shared_writing: Mapping[str, Any],
    deterministic_audit: Mapping[str, Any],
    route_review: Mapping[str, Any],
    execution_record: Mapping[str, Any] | None = None,
    root: str | Path,
    dependency_receipt_fingerprints: list[str],
) -> dict[str, Any]:
    value = validate_reader_judgment(
        judgment,
        artifact_map=artifact_map,
        reader_brief=reader_brief,
        shared_writing=shared_writing,
        deterministic_audit=deterministic_audit,
        route_review=route_review,
        execution_record=execution_record,
    )
    return _commit(
        value,
        root=root,
        builder_id="logic-writing.reader-judgment.v2",
        native_route="judge-reader-output",
        evidence_domain="reader_judgment",
        semantic_owner_id=f"reader-judgment:{value['judgment_id']}",
        covered_obligation_ids=["reader.independent.actual-artifact-judgment"],
        input_fingerprints={
            "artifact_map": value["artifact_map_fingerprint"],
            "shared_writing": value["shared_writing_contract_fingerprint"],
            "deterministic_audit": value["deterministic_audit_fingerprint"],
            "route_audit": value["route_audit_fingerprint"],
            **({"execution_record": value["execution_record_fingerprint"]} if value.get("execution_record_fingerprint") else {}),
        },
        output_field="judgment_fingerprint",
        artifact_fingerprint=value["artifact_fingerprint"],
        dependency_receipt_fingerprints=dependency_receipt_fingerprints,
        status="current_pass" if value["status"] == "passed" else "partial",
        safe_claim="An independent critic bound its structured judgment to actual current excerpts and locators.",
        unsafe_claim_boundary="The schema proves evidence binding and independence, not objective aesthetic truth.",
        run_id=f"reader-judgment:{value['judgment_id']}",
    )


def commit_repair_result_receipt(
    *,
    result: Mapping[str, Any],
    root: str | Path,
    dependency_receipt_fingerprints: list[str],
) -> dict[str, Any]:
    return _commit(
        result,
        root=root,
        builder_id="logic-writing.reader-repair.v2",
        native_route="record-reader-repair",
        evidence_domain="reader_repair",
        semantic_owner_id=f"reader-repair:{result['repair_id']}",
        covered_obligation_ids=["reader.typed-repair-result"],
        input_fingerprints={
            "repair_request": result["request_fingerprint"],
            "input_artifact": result["input_artifact_fingerprint"],
        },
        output_field="result_fingerprint",
        artifact_fingerprint=result["output_artifact_fingerprint"],
        dependency_receipt_fingerprints=dependency_receipt_fingerprints,
        status="blocked" if result["progress_status"] == "blocked" else "current_pass",
        safe_claim="This result records one actual repair attempt, its output bytes, preservation result, and remaining defect identity.",
        unsafe_claim_boundary="A no-progress result does not close the artifact until two consecutive current results share the same defect lineage.",
        run_id=f"reader-repair:{result['repair_id']}:{result['result_fingerprint'][7:19]}",
    )


__all__ = [
    "commit_reader_audit_receipt",
    "commit_reader_judgment_receipt",
    "commit_repair_result_receipt",
    "commit_route_review_receipt",
    "commit_shared_writing_receipt",
]
