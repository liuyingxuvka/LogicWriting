"""Investigation report composition and actual-artifact closure model."""

from __future__ import annotations

from models.common import OPERATION_INVARIANTS, OperationEvent, OperationState, operation_workflow
from models.plans import formal_plan, scenario


READY_INVESTIGATION = OperationState(
    request_fingerprint="request:investigation",
    route_owner="investigation",
    route_status="current_pass",
    adapter_receipts=(
        "sourceguard:current_pass:source_observation:source:investigation",
        "logicguard:current_pass:argument_model:logic:investigation",
        "traceguard:current_pass:competing_storyline:trace:investigation",
    ),
    adapter_status="current_pass",
    packet_fingerprint="investigation-packet:1",
    packet_status="current_pass",
    packet_current=True,
    handoff_status="current_pass",
)


def build_plan(*, conformance_status="skipped_with_reason", conformance_evidence=()):
    workflow = operation_workflow("investigation_route_model")
    sequence = (
        OperationEvent("freeze_reader_intent", fingerprint="investigation-intent:1"),
        OperationEvent(
            "validate_composition",
            fingerprint="investigation-composition:1",
            related_fingerprint="investigation-extension:1",
            owner="investigation",
        ),
        OperationEvent("build_reader_brief", fingerprint="investigation-brief:1"),
        OperationEvent("draft_artifact", artifact_fingerprint="investigation-report:1", artifact_mode="create_new"),
        OperationEvent("integrate_artifact", artifact_fingerprint="investigation-report:1"),
        OperationEvent("map_artifact", fingerprint="investigation-map:1", artifact_fingerprint="investigation-report:1"),
        OperationEvent(
            "bind_shared_writing",
            fingerprint="investigation-binding:1",
            related_fingerprint="investigation-map:1",
            artifact_fingerprint="investigation-report:1",
        ),
        OperationEvent("record_revision_provenance", status="not_applicable"),
        OperationEvent("deterministic_audit", artifact_fingerprint="investigation-report:1", status="passed"),
        OperationEvent("route_audit", artifact_fingerprint="investigation-report:1", owner="investigation", status="passed"),
        OperationEvent(
            "judge_artifact",
            artifact_fingerprint="investigation-report:1",
            producer_id="investigation-writer:1",
            judge_id="investigation-critic:1",
            status="passed",
        ),
        OperationEvent("close_operation"),
    )
    return formal_plan(
        model_id="investigation_route_model",
        workflow=workflow,
        initial_states=(READY_INVESTIGATION,),
        external_inputs=sequence,
        invariants=OPERATION_INVARIANTS,
        scenarios=(
            scenario(
                "investigation_report_closes",
                "A bounded answer, live alternatives, limitations, and recheck conditions bind real report spans",
                READY_INVESTIGATION,
                sequence,
                workflow,
                OPERATION_INVARIANTS,
            ),
        ),
        protected_error_classes=("research_packet_substitutes_for_report", "investigation_scope_overclaim"),
        modeled_state=("report_profile", "bounded_answer", "alternatives", "limitations", "artifact_map"),
        modeled_side_effects=("investigation_report_written", "investigation_closure"),
        completion_evidence=("actual_investigation_report_reviewed", "independent_reader_judgment"),
        known_bad_cases=("metadata_fake_green", "stale_audit_after_artifact_edit"),
        failure_modes=("research rows become visible report order", "negative evidence is omitted"),
        harms=("a fluent report overstates an unresolved conclusion",),
        hard_invariants=("investigation remains final owner", "actual report spans bind every material conclusion"),
        adversarial_inputs=("complete packet plus disconnected report", "unsupported definitive conclusion"),
        conformance_status=conformance_status,
        conformance_evidence=conformance_evidence,
    )
