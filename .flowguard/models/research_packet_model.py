"""ResearchPacket assembly, rejection, handoff, and bounded recovery model."""

from __future__ import annotations

from .common import OPERATION_INVARIANTS, OperationEvent, OperationState, operation_workflow
from .plans import formal_plan, scenario


def build_plan(*, conformance_status="skipped_with_reason", conformance_evidence=()):
    workflow = operation_workflow("research_packet_model")
    sequence = (
        OperationEvent("select_route", fingerprint="request:investigate", owner="investigation"),
        OperationEvent(
            "invoke_adapter",
            fingerprint="source:1",
            native_owner="sourceguard",
            evidence_domain="source_observation",
            status="current_pass",
        ),
        OperationEvent(
            "invoke_adapter",
            fingerprint="logic:1",
            native_owner="logicguard",
            evidence_domain="argument_model",
            status="current_pass",
        ),
        OperationEvent("assemble_packet", fingerprint="packet:1"),
        OperationEvent("handoff_packet", fingerprint="packet:1"),
    )
    partial = (
        OperationEvent("select_route", fingerprint="request:gap", owner="investigation"),
        OperationEvent(
            "invoke_adapter",
            fingerprint="source:gap",
            native_owner="sourceguard",
            evidence_domain="source_observation",
            status="access_gap",
        ),
        OperationEvent("assemble_packet", fingerprint="packet:gap"),
    )
    process_only = (
        OperationEvent("select_route", fingerprint="request:process-only", owner="investigation"),
        OperationEvent(
            "invoke_adapter",
            fingerprint="process:green",
            native_owner="flowguard",
            evidence_domain="process_model",
            status="current_pass",
        ),
        OperationEvent("assemble_packet", fingerprint="packet:process-only"),
    )
    return formal_plan(
        model_id="research_packet_model",
        workflow=workflow,
        initial_states=(OperationState(),),
        external_inputs=sequence + partial + process_only,
        invariants=OPERATION_INVARIANTS,
        scenarios=(
            scenario("current_packet_handoff", "Current native receipts yield an exact packet handoff", OperationState(), sequence, workflow, OPERATION_INVARIANTS),
            scenario("access_gap_remains_partial", "Access gaps cannot become passing packets", OperationState(), partial, workflow, OPERATION_INVARIANTS),
            scenario(
                "process_green_content_not_run_blocks",
                "Green process evidence cannot replace source observation and argument evidence",
                OperationState(),
                process_only,
                workflow,
                OPERATION_INVARIANTS,
            ),
        ),
        protected_error_classes=(
            "candidate_or_gap_promoted_to_evidence",
            "packet_identity_mismatch",
            "process_evidence_substitutes_for_content_evidence",
        ),
        modeled_state=("adapter_receipts", "packet_status", "packet_fingerprint", "handoff_status"),
        modeled_side_effects=("research_packet_created", "packet_handoff"),
        completion_evidence=("packet_current", "packet_handoff_verified"),
        known_bad_cases=("metadata_fake_green", "process_green_content_not_run"),
        failure_modes=(
            "nonpassing receipts aggregate to pass",
            "a receiver accepts a different packet",
            "process evidence passes while source and argument work never ran",
        ),
        harms=("unsupported claims reach reader prose",),
        hard_invariants=(
            "packet status is verifier-derived",
            "handoff identity is exact",
            "passing packets contain current source observation and argument-model evidence",
        ),
        adversarial_inputs=("access gap", "stale packet fingerprint", "process-only green evidence"),
        conformance_status=conformance_status,
        conformance_evidence=conformance_evidence,
    )
