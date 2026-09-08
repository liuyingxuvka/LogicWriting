"""Operation-plane dependency staleness, monotonic closure, and no-progress model."""

from __future__ import annotations

from dataclasses import replace

from models.common import OPERATION_INVARIANTS, OperationEvent, operation_workflow
from models.plans import formal_plan, scenario
from models.owners.reader_artifact_model.model import READY_PACKET


PASSED = replace(
    READY_PACKET,
    reader_intent_fingerprint="intent:1",
    reader_intent_status="current_pass",
    composition_plan_fingerprint="composition:1",
    composition_plan_status="current_pass",
    route_extension_fingerprint="academic-extension:1",
    brief_fingerprint="brief:1",
    brief_status="current_pass",
    brief_current=True,
    artifact_fingerprint="artifact:1",
    artifact_bound_brief="brief:1",
    artifact_status="current",
    artifact_current=True,
    artifact_mode="create_new",
    integration_status="current_pass",
    artifact_map_fingerprint="map:1",
    artifact_map_status="current_pass",
    shared_binding_fingerprint="binding:1",
    shared_binding_status="current_pass",
    shared_binding_artifact_fingerprint="artifact:1",
    revision_provenance_status="not_applicable",
    deterministic_audit_status="passed",
    route_audit_status="passed",
    judgment_status="passed",
    audit_artifact_fingerprint="artifact:1",
    judgment_artifact_fingerprint="artifact:1",
    producer_id="writer:1",
    judge_id="critic:1",
    closure_status="passed",
    closure_artifact_fingerprint="artifact:1",
    closure_owner="academic-writing",
    terminal=True,
)


def build_plan(*, conformance_status="skipped_with_reason", conformance_evidence=()):
    workflow = operation_workflow("operation_freshness_closure_model")
    source_change = (OperationEvent("source_changed", fingerprint="source:2"), OperationEvent("close_operation"))
    repairable = replace(
        PASSED,
        closure_status="blocked",
        terminal=False,
        judgment_status="repair",
        defect_lineage="defect:cards",
    )
    no_progress = (
        OperationEvent(
            "request_repair",
            fingerprint="repair-request:1",
            artifact_fingerprint="artifact:1",
            defect_lineage="defect:cards",
            owner="academic-writing",
        ),
        OperationEvent("apply_repair", artifact_fingerprint="artifact:1"),
        OperationEvent(
            "record_repair_result",
            related_fingerprint="repair-request:1",
            artifact_fingerprint="artifact:1",
            defect_lineage="defect:cards",
            status="no_progress",
        ),
        OperationEvent("integrate_artifact", artifact_fingerprint="artifact:1"),
        OperationEvent("map_artifact", fingerprint="map:2", artifact_fingerprint="artifact:1"),
        OperationEvent(
            "bind_shared_writing",
            fingerprint="binding:2",
            related_fingerprint="map:2",
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
            defect_lineage="defect:cards",
            status="repair",
        ),
        OperationEvent(
            "request_repair",
            fingerprint="repair-request:2",
            artifact_fingerprint="artifact:1",
            defect_lineage="defect:cards",
            owner="academic-writing",
        ),
        OperationEvent("apply_repair", artifact_fingerprint="artifact:1"),
        OperationEvent(
            "record_repair_result",
            related_fingerprint="repair-request:2",
            artifact_fingerprint="artifact:1",
            defect_lineage="defect:cards",
            status="no_progress",
        ),
        OperationEvent("close_operation"),
    )
    return formal_plan(
        model_id="operation_freshness_closure_model",
        workflow=workflow,
        initial_states=(PASSED, repairable),
        external_inputs=source_change + no_progress,
        invariants=OPERATION_INVARIANTS,
        scenarios=(
            scenario("source_change_stales_chain", "Source changes stale every dependent operation receipt", PASSED, source_change, workflow, OPERATION_INVARIANTS),
            scenario("real_repair_no_progress_terminates", "Two current repair results for one defect lineage stop visibly", repairable, no_progress, workflow, OPERATION_INVARIANTS),
        ),
        protected_error_classes=("stale_evidence_accepted", "infinite_no_progress_loop"),
        modeled_state=(
            "packet_current",
            "brief_current",
            "artifact_current",
            "artifact_map_status",
            "shared_binding_status",
            "revision_provenance_status",
            "closure_status",
            "repair_attempt_count",
            "consecutive_no_progress",
        ),
        modeled_side_effects=("evidence_invalidation", "visible_terminal_block"),
        completion_evidence=("operation_dependents_stale", "repair_no_progress_terminated"),
        known_bad_cases=("stale_audit_after_artifact_edit",),
        failure_modes=("source change leaves closure green", "identical repairs loop forever"),
        harms=("stale claims are delivered or the agent never terminates",),
        hard_invariants=("staleness propagates", "no-progress is bounded"),
        adversarial_inputs=("source edit after closure", "repeated closure without repair results"),
        conformance_status=conformance_status,
        conformance_evidence=conformance_evidence,
    )
