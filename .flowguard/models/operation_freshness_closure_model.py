"""Operation-plane dependency staleness, monotonic closure, and no-progress model."""

from __future__ import annotations

from dataclasses import replace

from .common import OPERATION_INVARIANTS, OperationEvent, operation_workflow
from .plans import formal_plan, scenario
from .reader_artifact_model import READY_PACKET


PASSED = replace(
    READY_PACKET,
    brief_fingerprint="brief:1",
    brief_status="current_pass",
    brief_current=True,
    artifact_fingerprint="artifact:1",
    artifact_bound_brief="brief:1",
    artifact_status="current",
    artifact_current=True,
    revision_provenance_status="current_pass",
    deterministic_audit_status="passed",
    judgment_status="passed",
    audit_artifact_fingerprint="artifact:1",
    closure_status="passed",
    closure_artifact_fingerprint="artifact:1",
    closure_owner="academic-writing",
    terminal=True,
)


def build_plan(*, conformance_status="skipped_with_reason", conformance_evidence=()):
    workflow = operation_workflow("operation_freshness_closure_model")
    source_change = (OperationEvent("source_changed", fingerprint="source:2"), OperationEvent("close_operation"), OperationEvent("close_operation"))
    artifact_change = (OperationEvent("update_artifact", artifact_fingerprint="artifact:2"), OperationEvent("close_operation"), OperationEvent("close_operation"))
    return formal_plan(
        model_id="operation_freshness_closure_model",
        workflow=workflow,
        initial_states=(PASSED,),
        external_inputs=source_change + artifact_change,
        invariants=OPERATION_INVARIANTS,
        scenarios=(
            scenario("source_change_stales_chain", "Source changes stale every dependent operation receipt", PASSED, source_change, workflow, OPERATION_INVARIANTS),
            scenario("repeated_no_progress_terminates", "Repeated identical failed closure stops visibly", PASSED, artifact_change, workflow, OPERATION_INVARIANTS),
        ),
        protected_error_classes=("stale_evidence_accepted", "infinite_no_progress_loop"),
        modeled_state=(
            "packet_current",
            "brief_current",
            "artifact_current",
            "revision_provenance_status",
            "closure_status",
            "no_progress_count",
        ),
        modeled_side_effects=("evidence_invalidation", "visible_terminal_block"),
        completion_evidence=("operation_dependents_stale", "no_progress_terminated"),
        known_bad_cases=("stale_audit_after_artifact_edit",),
        failure_modes=("source change leaves closure green", "identical repairs loop forever"),
        harms=("stale claims are delivered or the agent never terminates",),
        hard_invariants=("staleness propagates", "no-progress is bounded"),
        adversarial_inputs=("source edit after closure", "repeated closure without new evidence"),
        conformance_status=conformance_status,
        conformance_evidence=conformance_evidence,
    )
