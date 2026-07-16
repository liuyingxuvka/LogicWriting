"""Fiction route ownership, Guard evidence, reader projection, and closure model."""

from __future__ import annotations

from .common import OPERATION_INVARIANTS, OperationEvent, OperationState, operation_workflow
from .plans import formal_plan, scenario


READY_FICTION = OperationState(
    request_fingerprint="request:fiction",
    route_owner="fiction-writing",
    child_routes=("investigation",),
    route_status="current_pass",
    adapter_receipts=(
        "worldguard:current_pass:world_consistency:world:fiction",
        "logicguard:current_pass:argument_model:logic:fiction",
        "sourceguard:current_pass:source_observation:source:fiction",
    ),
    adapter_status="current_pass",
    packet_fingerprint="story-model:1",
    packet_status="current_pass",
    packet_current=True,
    handoff_status="current_pass",
)


def build_plan(*, conformance_status="skipped_with_reason", conformance_evidence=()):
    workflow = operation_workflow("fiction_route_model")
    sequence = (
        OperationEvent("build_reader_brief", fingerprint="fiction-brief:1"),
        OperationEvent("write_artifact", artifact_fingerprint="manuscript:1"),
        OperationEvent("audit_artifact", artifact_fingerprint="manuscript:1", status="passed+passed"),
        OperationEvent("close_operation"),
    )
    return formal_plan(
        model_id="fiction_route_model",
        workflow=workflow,
        initial_states=(READY_FICTION,),
        external_inputs=sequence,
        invariants=OPERATION_INVARIANTS,
        scenarios=(scenario("fiction_actual_manuscript_closes", "Fiction retains final ownership through bounded research and current actual-manuscript review", READY_FICTION, sequence, workflow, OPERATION_INVARIANTS),),
        protected_error_classes=("fiction_sibling_owner_cycle", "fiction_model_artifact_drift"),
        modeled_state=("story_model", "promise_continuity", "reader_state", "manuscript_identity", "model_prose_binding"),
        modeled_side_effects=("fiction_artifact_written", "fiction_closure"),
        completion_evidence=("guard_lifecycle_current", "model_prose_binding_current", "actual_manuscript_reviewed"),
        known_bad_cases=("metadata_fake_green", "stale_audit_after_artifact_edit"),
        failure_modes=("fiction calls a sibling final route", "model rows or prose spans are not mutually bound", "WorldGuard is scoped out because the world is fictional"),
        harms=("a fluent manuscript violates its own world, promises, continuity, or reader contract",),
        hard_invariants=("fiction remains final owner", "WorldGuard authority is preserved", "actual bytes bind model and review"),
        adversarial_inputs=("historical research before fiction", "fiction-only WorldGuard scopeout", "stale manuscript binding"),
        conformance_status=conformance_status,
        conformance_evidence=conformance_evidence,
    )
