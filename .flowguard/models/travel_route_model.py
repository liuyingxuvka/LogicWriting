"""Travel route evidence, feasibility, fit, fallback, reader projection, and closure model."""

from __future__ import annotations

from .common import OPERATION_INVARIANTS, OperationEvent, OperationState, operation_workflow
from .plans import formal_plan, scenario


READY_TRAVEL = OperationState(
    request_fingerprint="request:travel",
    route_owner="travel-guide",
    child_routes=("investigation",),
    route_status="current_pass",
    adapter_receipts=(
        "worldguard:current_pass:world_consistency:world:travel",
        "traceguard:current_pass:temporal_trace:trace:travel",
        "logicguard:current_pass:argument_model:logic:travel",
        "sourceguard:current_pass:source_observation:source:travel",
    ),
    adapter_status="current_pass",
    packet_fingerprint="travel-plan:1",
    packet_status="current_pass",
    packet_current=True,
    handoff_status="current_pass",
)


def build_plan(*, conformance_status="skipped_with_reason", conformance_evidence=()):
    workflow = operation_workflow("travel_route_model")
    sequence = (
        OperationEvent("freeze_reader_intent", fingerprint="travel-intent:1"),
        OperationEvent(
            "validate_composition",
            fingerprint="travel-composition:1",
            related_fingerprint="travel-extension:1",
            owner="travel-guide",
        ),
        OperationEvent("build_reader_brief", fingerprint="travel-reader-projection:1"),
        OperationEvent("draft_artifact", artifact_fingerprint="travel-guide:1", artifact_mode="create_new"),
        OperationEvent("integrate_artifact", artifact_fingerprint="travel-guide:1"),
        OperationEvent("map_artifact", fingerprint="guide-map:1", artifact_fingerprint="travel-guide:1"),
        OperationEvent(
            "bind_shared_writing",
            fingerprint="travel-binding:1",
            related_fingerprint="guide-map:1",
            artifact_fingerprint="travel-guide:1",
        ),
        OperationEvent("record_revision_provenance", status="not_applicable"),
        OperationEvent("deterministic_audit", artifact_fingerprint="travel-guide:1", status="passed"),
        OperationEvent("route_audit", artifact_fingerprint="travel-guide:1", owner="travel-guide", status="passed"),
        OperationEvent(
            "judge_artifact",
            artifact_fingerprint="travel-guide:1",
            producer_id="travel-writer:1",
            judge_id="travel-critic:1",
            status="passed",
        ),
        OperationEvent("close_operation"),
    )
    return formal_plan(
        model_id="travel_route_model",
        workflow=workflow,
        initial_states=(READY_TRAVEL,),
        external_inputs=sequence,
        invariants=OPERATION_INVARIANTS,
        scenarios=(scenario("travel_actual_guide_closes", "Travel retains final ownership through shared projection and current reverse-guide review", READY_TRAVEL, sequence, workflow, OPERATION_INVARIANTS),),
        protected_error_classes=("travel_fiction_owner_cycle", "travel_feasibility_overclaim", "travel_artifact_drift"),
        modeled_state=("guide_kind", "guide_zone", "source_time_mode", "candidate_feasibility", "route_mesh", "traveler_fit", "reachable_fallbacks", "guide_identity", "artifact_map"),
        modeled_side_effects=("travel_guide_written", "travel_closure"),
        completion_evidence=("source_time_current", "feasibility_and_fit_current", "fallbacks_reachable", "actual_guide_reverse_reviewed"),
        known_bad_cases=("metadata_fake_green", "stale_audit_after_artifact_edit"),
        failure_modes=("travel invokes fiction as a child", "polished prose strengthens non-pass feasibility", "fallback cannot be reached from the failed route"),
        harms=("a persuasive guide is unsafe, stale, infeasible, or unsuitable for the traveler",),
        hard_invariants=("travel remains final owner", "shared projection has no closure path", "actual guide bytes bind reverse review"),
        adversarial_inputs=("story-shaped itinerary", "upstream non-pass overwritten", "unreachable fallback"),
        conformance_status=conformance_status,
        conformance_evidence=conformance_evidence,
    )
