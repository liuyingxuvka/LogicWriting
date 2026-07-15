"""ReaderBrief, actual-artifact writing, audit, repair, and closure model."""

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
        OperationEvent("build_reader_brief", fingerprint="brief:1"),
        OperationEvent("write_artifact", artifact_fingerprint="artifact:1"),
        OperationEvent("record_revision_provenance", status="current_pass"),
        OperationEvent("audit_artifact", artifact_fingerprint="artifact:1", status="passed+passed"),
        OperationEvent("close_operation"),
    )
    revision = sequence[:4] + (
        OperationEvent("update_artifact", artifact_fingerprint="artifact:2"),
        OperationEvent("record_revision_provenance", status="current_pass"),
        OperationEvent("audit_artifact", artifact_fingerprint="artifact:2", status="passed+passed"),
        OperationEvent("close_operation"),
    )
    return formal_plan(
        model_id="reader_artifact_model",
        workflow=workflow,
        initial_states=(READY_PACKET,),
        external_inputs=sequence + revision,
        invariants=OPERATION_INVARIANTS,
        scenarios=(
            scenario("actual_artifact_closes", "Current deterministic and judged evidence closes actual text", READY_PACKET, sequence, workflow, OPERATION_INVARIANTS),
            scenario("revision_stales_then_repairs", "A material edit stales and then refreshes audits", READY_PACKET, revision, workflow, OPERATION_INVARIANTS),
        ),
        protected_error_classes=("metadata_substitutes_for_artifact_evidence", "stale_evidence_accepted"),
        modeled_state=(
            "brief_fingerprint",
            "artifact_fingerprint",
            "revision_provenance_status",
            "audit_artifact_fingerprint",
            "closure_status",
        ),
        modeled_side_effects=("reader_artifact_written", "final_closure"),
        completion_evidence=("actual_artifact_audited", "operation_closed"),
        known_bad_cases=("metadata_fake_green", "stale_audit_after_artifact_edit"),
        failure_modes=("metadata passes while prose is unread", "an edit preserves old audit status"),
        harms=("AI-internal prose or unsupported conclusions are delivered as final",),
        hard_invariants=(
            "audit binds actual artifact",
            "academic closure requires current revision provenance",
            "closure binds current audit",
        ),
        adversarial_inputs=("metadata-only audit", "artifact edit after audit", "academic artifact without provenance"),
        conformance_status=conformance_status,
        conformance_evidence=conformance_evidence,
    )
