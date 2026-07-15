"""External-contract tests for Logic Writing's FlowGuard behavior models."""

from __future__ import annotations

import sys
from pathlib import Path


FLOWGUARD_ROOT = Path(__file__).resolve().parents[2] / ".flowguard"
if str(FLOWGUARD_ROOT) not in sys.path:
    sys.path.insert(0, str(FLOWGUARD_ROOT))

from models.common import (  # noqa: E402
    DevelopmentEvent,
    DevelopmentState,
    OperationEvent,
    OperationState,
    development_workflow,
    operation_workflow,
)
from models.frozen_source_contract_exhaustion import (  # noqa: E402
    CASE_IDS,
    review_frozen_source_name_family,
)


def _step(workflow, state, event):
    run = workflow.execute(state, event)
    assert not run.dead_branches
    assert not run.exception_branches
    assert len(run.completed_paths) == 1
    return run.completed_paths[0].state


def test_router_selects_one_owner_and_preserves_bounded_child():
    workflow = operation_workflow("test_router_owner")
    selected = _step(
        workflow,
        OperationState(),
        OperationEvent(
            "select_route",
            fingerprint="request:academic",
            owner="academic-writing",
            child_routes=("investigation",),
        ),
    )
    assert selected.route_status == "current_pass"
    assert selected.route_owner == "academic-writing"
    assert selected.child_routes == ("investigation",)

    blocked = _step(
        workflow,
        OperationState(),
        OperationEvent("select_route", fingerprint="request:ambiguous", owner="both"),
    )
    assert blocked.route_status == "blocked"
    assert blocked.route_owner == ""


def test_adapter_requires_a_native_owner_domain_pair():
    workflow = operation_workflow("test_adapter_authority")
    state = OperationState(route_owner="investigation", route_status="current_pass")

    blocked = _step(
        workflow,
        state,
        OperationEvent(
            "invoke_adapter",
            fingerprint="receipt:wrong",
            native_owner="sourceguard",
            evidence_domain="argument_model",
            status="current_pass",
        ),
    )
    assert blocked.adapter_status == "blocked"

    current = _step(
        workflow,
        state,
        OperationEvent(
            "invoke_adapter",
            fingerprint="receipt:source",
            native_owner="sourceguard",
            evidence_domain="source_observation",
            status="current_pass",
        ),
    )
    assert current.adapter_status == "current_pass"
    assert current.adapter_receipts == (
        "sourceguard:current_pass:source_observation:receipt:source",
    )


def test_packet_rejects_process_green_without_core_content():
    workflow = operation_workflow("test_packet_minimum_content")
    partial = OperationState(
        route_owner="investigation",
        route_status="current_pass",
        adapter_status="current_pass",
        adapter_receipts=(
            "sourceguard:current_pass:source_observation:source:1",
            "flowguard:current_pass:process_model:process:1",
        ),
    )
    blocked = _step(
        workflow,
        partial,
        OperationEvent("assemble_packet", fingerprint="packet:blocked"),
    )
    assert blocked.packet_status == "blocked"
    assert not blocked.packet_current
    assert "missing_core_content_evidence:logicguard:argument_model" in blocked.residual_risk

    complete = OperationState(
        route_owner="investigation",
        route_status="current_pass",
        adapter_status="current_pass",
        adapter_receipts=partial.adapter_receipts
        + ("logicguard:current_pass:argument_model:argument:1",),
    )
    current = _step(
        workflow,
        complete,
        OperationEvent("assemble_packet", fingerprint="packet:current"),
    )
    assert current.packet_status == "current_pass"
    assert current.packet_current


def test_academic_closure_requires_revision_provenance_and_actual_artifact_audits():
    workflow = operation_workflow("test_academic_closure")
    ready_except_provenance = OperationState(
        route_owner="academic-writing",
        route_status="current_pass",
        packet_current=True,
        packet_status="current_pass",
        brief_current=True,
        brief_status="current_pass",
        brief_fingerprint="brief:1",
        artifact_current=True,
        artifact_status="current",
        artifact_fingerprint="artifact:1",
        artifact_bound_brief="brief:1",
        deterministic_audit_status="passed",
        judgment_status="passed",
        audit_artifact_fingerprint="artifact:1",
    )
    blocked = _step(
        workflow,
        ready_except_provenance,
        OperationEvent("close_operation"),
    )
    assert blocked.closure_status == "blocked"

    with_provenance = _step(
        workflow,
        ready_except_provenance,
        OperationEvent("record_revision_provenance", status="current_pass"),
    )
    closed = _step(workflow, with_provenance, OperationEvent("close_operation"))
    assert closed.closure_status == "passed"
    assert closed.closure_owner == "academic-writing"
    assert closed.closure_artifact_fingerprint == "artifact:1"


def test_material_artifact_change_stales_reader_evidence():
    workflow = operation_workflow("test_artifact_staleness")
    state = OperationState(
        route_owner="investigation",
        route_status="current_pass",
        artifact_current=True,
        artifact_status="current",
        artifact_fingerprint="artifact:old",
        deterministic_audit_status="passed",
        judgment_status="passed",
        audit_artifact_fingerprint="artifact:old",
        closure_status="passed",
        closure_artifact_fingerprint="artifact:old",
    )
    updated = _step(
        workflow,
        state,
        OperationEvent("update_artifact", artifact_fingerprint="artifact:new"),
    )
    assert updated.artifact_fingerprint == "artifact:new"
    assert updated.deterministic_audit_status == "stale"
    assert updated.judgment_status == "stale"
    assert updated.closure_status == "stale"


def test_identical_no_progress_attempts_terminate_visibly():
    workflow = operation_workflow("test_no_progress")
    state = OperationState(route_owner="investigation", route_status="current_pass")
    first = _step(workflow, state, OperationEvent("close_operation"))
    second = _step(workflow, first, OperationEvent("close_operation"))
    assert first.closure_status == "blocked"
    assert second.closure_status == "no_progress_blocked"
    assert second.terminal


def test_release_requires_frozen_install_and_global_route():
    workflow = development_workflow("test_release_gate")
    blocked = _step(
        workflow,
        DevelopmentState(),
        DevelopmentEvent("publish_release", fingerprint="release:1"),
    )
    assert blocked.release_status == "blocked"

    state = DevelopmentState()
    for event in (
        DevelopmentEvent("freeze_validation", fingerprint="release:1", status="current_pass"),
        DevelopmentEvent("stage_install", fingerprint="release:1"),
        DevelopmentEvent("activate_install", fingerprint="release:1"),
        DevelopmentEvent("project_global_route", fingerprint="release:1"),
        DevelopmentEvent("publish_release", fingerprint="release:1"),
    ):
        state = _step(workflow, state, event)
    assert state.release_status == "current_pass"
    assert state.release_fingerprint == "release:1"


def test_remote_retirement_privatizes_sequentially_and_records_handoff():
    workflow = development_workflow("test_retirement_order")
    state = DevelopmentState(
        validation_fingerprint="release:1",
        validation_status="current_pass",
        validation_current=True,
        stage_fingerprint="release:1",
        stage_status="current_pass",
        active_fingerprint="release:1",
        install_status="current_pass",
        global_route_status="current_pass",
        release_status="current_pass",
        release_fingerprint="release:1",
        backups_verified=True,
        retired_local=("research", "academic"),
    )
    research = _step(
        workflow,
        state,
        DevelopmentEvent("privatize_legacy_remote", target="research", fingerprint="private+anon404:research"),
    )
    assert research.privatized_remote == ("research",)
    assert research.visibility_receipts == ("private:research:private+anon404:research",)
    assert not research.terminal

    premature = _step(
        workflow,
        research,
        DevelopmentEvent("privatize_legacy_remote", target="academic", fingerprint="private+anon404:academic"),
    )
    assert premature.privatized_remote == ("research",)
    assert "remote_retirement_gate_or_order_failed" in premature.errors

    rechecked = _step(
        workflow,
        research,
        DevelopmentEvent("recheck_after_first_privatization", status="current_pass"),
    )
    academic = _step(
        workflow,
        rechecked,
        DevelopmentEvent("privatize_legacy_remote", target="academic", fingerprint="private+anon404:academic"),
    )
    assert academic.privatized_remote == ("research", "academic")
    assert not academic.terminal

    handed_off = _step(
        workflow,
        academic,
        DevelopmentEvent("record_remote_deletion_handoff", status="current_pass"),
    )
    assert handed_off.user_deletion_handoff_status == "current_pass"
    assert handed_off.terminal


def test_deleted_remote_fields_and_events_have_no_compatibility_alias():
    state_fields = set(DevelopmentState.__dataclass_fields__)
    assert {"retired_remote", "first_deletion_health_rechecked", "deletion_receipts"}.isdisjoint(state_fields)
    from models.common import DEVELOPMENT_ACTIONS

    assert {"retire_legacy_remote", "recheck_after_first_deletion"}.isdisjoint(DEVELOPMENT_ACTIONS)

    from models.retirement_field_lifecycle import review_retirement_visibility_fields

    review = review_retirement_visibility_fields()
    assert review.ok, review.summary
    assert len(review.projections) == 7


def test_operation_artifact_change_does_not_stale_release_without_an_explicit_edge():
    workflow = development_workflow("test_plane_separation")
    state = DevelopmentState(
        validation_fingerprint="release:1",
        validation_status="current_pass",
        validation_current=True,
        stage_fingerprint="release:1",
        stage_status="current_pass",
        active_fingerprint="release:1",
        install_status="current_pass",
        global_route_status="current_pass",
        release_status="current_pass",
        release_fingerprint="release:1",
    )
    unchanged = _step(
        workflow,
        state,
        DevelopmentEvent("operation_artifact_changed", fingerprint="artifact:new"),
    )
    assert unchanged == state


def test_frozen_source_name_family_covers_observed_and_same_class_collisions():
    report = review_frozen_source_name_family()

    assert report.ok, report.summary
    assert report.confidence == "full"
    assert set(CASE_IDS).issubset({case.case_id for case in report.generated_cases})
    assert report.observed_problem_backfeed_report is not None
    assert report.observed_problem_backfeed_report.ok
    assert report.observed_problem_backfeed_report.mapped_problem_ids == (
        "problem:frozen-source-schema-omitted",
    )
    assert {item.acceptance_id for item in report.composite_handoff_acceptances} >= {
        f"composite_handoff:{case_id}" for case_id in CASE_IDS
    }
