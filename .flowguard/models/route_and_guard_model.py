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
    return formal_plan(
        model_id="route_and_guard_model",
        workflow=workflow,
        initial_states=(OperationState(),),
        external_inputs=good + blocked,
        invariants=OPERATION_INVARIANTS,
        scenarios=(
            scenario("academic_with_bounded_research_child", "Academic writing remains final owner", OperationState(), good, workflow, OPERATION_INVARIANTS),
            scenario("ambiguous_route_blocks", "Ambiguity remains explicit", OperationState(), blocked, workflow, OPERATION_INVARIANTS),
        ),
        protected_error_classes=("duplicate_final_owner", "native_authority_substitution"),
        modeled_state=("route_owner", "child_routes", "adapter_receipts"),
        modeled_side_effects=("route_activation", "native_receipt_import"),
        completion_evidence=("route_selected", "adapter_receipt_recorded"),
        known_bad_cases=("metadata_fake_green",),
        failure_modes=("two routes both claim final ownership", "a missing specialist is silently reimplemented"),
        harms=("conflicting artifacts and false closure",),
        hard_invariants=("exactly one final owner", "specialist authority is preserved"),
        adversarial_inputs=("ambiguous owner", "unknown adapter owner"),
        conformance_status=conformance_status,
        conformance_evidence=conformance_evidence,
    )
