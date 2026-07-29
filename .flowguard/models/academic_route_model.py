"""Academic hierarchy, contribution, provenance, and actual-artifact closure model."""

from __future__ import annotations

from .common import OPERATION_INVARIANTS, OperationEvent, OperationState, operation_workflow
from .plans import formal_plan, scenario


READY_ACADEMIC = OperationState(
    request_fingerprint="request:academic",
    route_owner="academic-writing",
    child_routes=("investigation",),
    route_status="current_pass",
    adapter_receipts=(
        "sourceguard:current_pass:source_observation:source:academic",
        "logicguard:current_pass:argument_model:logic:academic",
    ),
    adapter_status="current_pass",
    packet_fingerprint="academic-packet:1",
    packet_status="current_pass",
    packet_current=True,
    handoff_status="current_pass",
)


def build_plan(*, conformance_status="skipped_with_reason", conformance_evidence=()):
    workflow = operation_workflow("academic_route_model")
    sequence = (
        OperationEvent("freeze_reader_intent", fingerprint="academic-intent:1"),
        OperationEvent(
            "validate_composition",
            fingerprint="academic-composition:1",
            related_fingerprint="academic-extension:1",
            owner="academic-writing",
        ),
        OperationEvent("build_reader_brief", fingerprint="academic-brief:1"),
        OperationEvent("draft_artifact", artifact_fingerprint="academic-paper:1", artifact_mode="revise_existing"),
        OperationEvent("integrate_artifact", artifact_fingerprint="academic-paper:1"),
        OperationEvent("map_artifact", fingerprint="academic-map:1", artifact_fingerprint="academic-paper:1"),
        OperationEvent(
            "bind_shared_writing",
            fingerprint="academic-binding:1",
            related_fingerprint="academic-map:1",
            artifact_fingerprint="academic-paper:1",
        ),
        OperationEvent("record_revision_provenance", status="current_pass"),
        OperationEvent("deterministic_audit", artifact_fingerprint="academic-paper:1", status="passed"),
        OperationEvent("route_audit", artifact_fingerprint="academic-paper:1", owner="academic-writing", status="passed"),
        OperationEvent(
            "judge_artifact",
            artifact_fingerprint="academic-paper:1",
            producer_id="academic-writer:1",
            judge_id="academic-critic:1",
            status="passed",
        ),
        OperationEvent("close_operation"),
    )
    return formal_plan(
        model_id="academic_route_model",
        workflow=workflow,
        initial_states=(READY_ACADEMIC,),
        external_inputs=sequence,
        invariants=OPERATION_INVARIANTS,
        scenarios=(
            scenario(
                "academic_revision_closes",
                "A hierarchical academic revision binds source provenance, paragraph contribution, and real artifact spans",
                READY_ACADEMIC,
                sequence,
                workflow,
                OPERATION_INVARIANTS,
            ),
        ),
        protected_error_classes=("author_list_literature_review", "academic_orphan_section"),
        modeled_state=("academic_profile", "artifact_hierarchy", "paragraph_contribution", "revision_provenance", "artifact_map"),
        modeled_side_effects=("academic_artifact_written", "academic_closure"),
        completion_evidence=("current_revision_provenance", "actual_academic_artifact_reviewed"),
        known_bad_cases=("metadata_fake_green", "stale_audit_after_artifact_edit"),
        failure_modes=("one author becomes one paragraph", "method does not answer the research question"),
        harms=("a polished paper lacks a recoverable contribution or silently rewrites source structure",),
        hard_invariants=("academic remains final owner", "revision provenance is conditional and current"),
        adversarial_inputs=("fluent section without parent contribution", "figure with no argumentative consumer"),
        conformance_status=conformance_status,
        conformance_evidence=conformance_evidence,
    )
