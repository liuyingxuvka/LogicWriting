"""Exactly-one-owner routing and typed specialist adapter model."""

from __future__ import annotations

from .common import OPERATION_INVARIANTS, OperationEvent, OperationState, operation_workflow
from .plans import formal_plan, scenario


def build_plan(*, conformance_status="skipped_with_reason", conformance_evidence=()):
    workflow = operation_workflow("route_and_guard_model")
    good = (
        OperationEvent("select_route", fingerprint="request:r1", owner="academic-writing", child_routes=("investigation",)),
        OperationEvent(
            "invoke_adapter",
            fingerprint="logic:r1",
            native_owner="logicguard",
            evidence_domain="argument_model",
            status="current_pass",
        ),
    )
    blocked = (OperationEvent("select_route", fingerprint="request:r2", owner="ambiguous"),)
    fiction = (
        OperationEvent("select_route", fingerprint="request:r3", owner="fiction-writing", child_routes=("investigation",)),
        OperationEvent("invoke_adapter", fingerprint="world:r3", native_owner="worldguard", evidence_domain="world_consistency", status="current_pass"),
    )
    travel = (
        OperationEvent("select_route", fingerprint="request:r4", owner="travel-guide", child_routes=("investigation",)),
        OperationEvent("invoke_adapter", fingerprint="trace:r4", native_owner="traceguard", evidence_domain="temporal_trace", status="current_pass"),
    )
    return formal_plan(
        model_id="route_and_guard_model",
        workflow=workflow,
        initial_states=(OperationState(),),
        external_inputs=good + blocked + fiction + travel,
        invariants=OPERATION_INVARIANTS,
        scenarios=(
            scenario("academic_with_bounded_research_child", "Academic writing remains final owner", OperationState(), good, workflow, OPERATION_INVARIANTS),
            scenario("ambiguous_route_blocks", "Ambiguity remains explicit", OperationState(), blocked, workflow, OPERATION_INVARIANTS),
            scenario("researched_fiction_keeps_owner", "Fiction remains final owner while WorldGuard preserves world consistency", OperationState(), fiction, workflow, OPERATION_INVARIANTS),
            scenario("story_shaped_travel_keeps_owner", "Travel remains final owner and uses shared reader projection rather than fiction", OperationState(), travel, workflow, OPERATION_INVARIANTS),
        ),
        protected_error_classes=("duplicate_final_owner", "native_authority_substitution"),
        modeled_state=(
            "route_owner",
            "child_routes",
            "adapter_receipts",
            "researchguard_member_primary_path",
        ),
        modeled_side_effects=(
            "route_activation",
            "researchguard_console_member_execution",
            "native_receipt_import",
        ),
        completion_evidence=(
            "route_selected",
            "single_researchguard_console_preflight",
            "adapter_receipt_recorded",
        ),
        known_bad_cases=("metadata_fake_green",),
        failure_modes=("two routes both claim final ownership", "a missing specialist is silently reimplemented"),
        harms=("conflicting artifacts and false closure",),
        hard_invariants=(
            "exactly one final owner",
            "specialist authority is preserved",
            "logicguard sourceguard and traceguard use one researchguard console",
            "member failure has no alternate success path",
        ),
        adversarial_inputs=("ambiguous owner", "unknown adapter owner", "travel subject paper", "story-shaped itinerary", "fiction-only WorldGuard scopeout"),
        conformance_status=conformance_status,
        conformance_evidence=conformance_evidence,
    )
