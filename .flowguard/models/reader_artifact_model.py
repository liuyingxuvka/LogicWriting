"""Shared reader projection, actual-artifact writing, binding, audit, repair, and closure model."""

from __future__ import annotations

from .common import OPERATION_INVARIANTS, OperationEvent, OperationState, operation_workflow
from .plans import formal_plan, scenario


READY_PACKET = OperationState(
    request_fingerprint="request:academic",
    route_owner="academic-writing",
    child_routes=("investigation",),
    route_status="current_pass",
    adapter_receipts=(
        "sourceguard:current_pass:source_observation:source:1",
        "logicguard:current_pass:argument_model:logic:1",
    ),
    adapter_status="current_pass",
    packet_fingerprint="packet:1",
    packet_status="current_pass",
    packet_current=True,
    handoff_status="current_pass",
)


def build_plan(*, conformance_status="skipped_with_reason", conformance_evidence=()):
    workflow = operation_workflow("reader_artifact_model")
    sequence = (
        OperationEvent("freeze_reader_intent", fingerprint="intent:1"),
        OperationEvent(
            "validate_composition",
            fingerprint="composition:1",
            related_fingerprint="academic-extension:1",
            owner="academic-writing",
        ),
        OperationEvent("build_reader_brief", fingerprint="brief:1"),
        OperationEvent("draft_artifact", artifact_fingerprint="artifact:1", artifact_mode="create_new"),
        OperationEvent("integrate_artifact", artifact_fingerprint="artifact:1"),
        OperationEvent("map_artifact", fingerprint="map:1", artifact_fingerprint="artifact:1"),
        OperationEvent(
            "bind_shared_writing",
            fingerprint="binding:1",
            related_fingerprint="map:1",
            artifact_fingerprint="artifact:1",
        ),
        OperationEvent("record_revision_provenance", status="not_applicable"),
        OperationEvent("deterministic_audit", artifact_fingerprint="artifact:1", status="passed"),
        OperationEvent("route_audit", artifact_fingerprint="artifact:1", owner="academic-writing", status="passed"),
        OperationEvent(
            "judge_artifact",
            artifact_fingerprint="artifact:1",
            producer_id="writer:1",
            judge_id="critic:1",
            status="passed",
        ),
        OperationEvent("close_operation"),
    )
    repair = sequence[:-2] + (
        OperationEvent(
            "judge_artifact",
            artifact_fingerprint="artifact:1",
            producer_id="writer:1",
            judge_id="critic:1",
            defect_lineage="defect:cards",
            status="repair",
        ),
        OperationEvent(
            "request_repair",
            fingerprint="repair-request:1",
            artifact_fingerprint="artifact:1",
            defect_lineage="defect:cards",
            owner="academic-writing",
        ),
        OperationEvent("apply_repair", artifact_fingerprint="artifact:2"),
        OperationEvent("record_revision_provenance", status="not_applicable"),
        OperationEvent("integrate_artifact", artifact_fingerprint="artifact:2"),
        OperationEvent("map_artifact", fingerprint="map:2", artifact_fingerprint="artifact:2"),
        OperationEvent(
            "bind_shared_writing",
            fingerprint="binding:2",
            related_fingerprint="map:2",
            artifact_fingerprint="artifact:2",
        ),
        OperationEvent(
            "record_repair_result",
            related_fingerprint="repair-request:1",
            artifact_fingerprint="artifact:2",
            defect_lineage="defect:cards",
            status="progressed",
        ),
        OperationEvent("deterministic_audit", artifact_fingerprint="artifact:2", status="passed"),
        OperationEvent("route_audit", artifact_fingerprint="artifact:2", owner="academic-writing", status="passed"),
        OperationEvent(
            "judge_artifact",
            artifact_fingerprint="artifact:2",
            producer_id="writer:1",
            judge_id="critic:1",
            status="passed",
        ),
        OperationEvent("close_operation"),
    )
    return formal_plan(
        model_id="reader_artifact_model",
        workflow=workflow,
        initial_states=(READY_PACKET,),
        external_inputs=sequence + repair,
        invariants=OPERATION_INVARIANTS,
        scenarios=(
            scenario("actual_artifact_closes", "Current deterministic and judged evidence closes actual text", READY_PACKET, sequence, workflow, OPERATION_INVARIANTS),
            scenario("typed_repair_rebinds_then_closes", "A real repair stales and rebuilds every affected reader receipt", READY_PACKET, repair, workflow, OPERATION_INVARIANTS),
        ),
        protected_error_classes=("metadata_substitutes_for_artifact_evidence", "stale_evidence_accepted"),
        modeled_state=(
            "brief_fingerprint",
            "reader_intent_fingerprint",
            "composition_plan_fingerprint",
            "artifact_fingerprint",
            "artifact_map_fingerprint",
            "shared_binding_fingerprint",
            "revision_provenance_status",
            "audit_artifact_fingerprint",
            "repair_attempt_count",
            "consecutive_no_progress",
            "closure_status",
            "unit_contribution",
            "reader_state_interface",
            "register_owner",
            "model_artifact_binding",
        ),
        modeled_side_effects=("reader_artifact_written", "final_closure"),
        completion_evidence=("actual_artifact_audited", "operation_closed"),
        known_bad_cases=("metadata_fake_green", "stale_audit_after_artifact_edit"),
        failure_modes=("metadata passes while prose is unread", "an edit preserves old audit status", "a shared projection issues sibling closure", "model and artifact drift apart"),
        harms=("AI-internal prose or unsupported conclusions are delivered as final",),
        hard_invariants=(
            "audit binds actual artifact",
            "academic closure requires current revision provenance",
            "closure binds current audit",
            "shared projection never becomes a final owner",
            "important model rows bind actual artifact spans",
        ),
        adversarial_inputs=("metadata-only audit", "artifact edit after audit", "academic artifact without provenance"),
        conformance_status=conformance_status,
        conformance_evidence=conformance_evidence,
    )
