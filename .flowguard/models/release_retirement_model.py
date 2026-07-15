"""Frozen validation, install, release, rollback, and sequential retirement model."""

from __future__ import annotations

from .common import DEVELOPMENT_INVARIANTS, DevelopmentEvent, DevelopmentState, development_workflow
from .plans import formal_plan, scenario


def build_plan(*, conformance_status="skipped_with_reason", conformance_evidence=()):
    workflow = development_workflow("release_retirement_model")
    sequence = (
        DevelopmentEvent("freeze_validation", fingerprint="release:abc", status="current_pass"),
        DevelopmentEvent("stage_install", fingerprint="release:abc"),
        DevelopmentEvent("activate_install", fingerprint="release:abc"),
        DevelopmentEvent("project_global_route", fingerprint="release:abc"),
        DevelopmentEvent("publish_release", fingerprint="release:abc"),
        DevelopmentEvent("verify_backups", status="current_pass"),
        DevelopmentEvent("quarantine_legacy_local", target="research"),
        DevelopmentEvent("quarantine_legacy_local", target="academic"),
        DevelopmentEvent("retire_legacy_remote", fingerprint="404:research", target="research"),
        DevelopmentEvent("recheck_after_first_deletion", status="current_pass"),
        DevelopmentEvent("retire_legacy_remote", fingerprint="404:academic", target="academic"),
    )
    early = (DevelopmentEvent("retire_legacy_remote", fingerprint="bad", target="research"),)
    plane_separation = (DevelopmentEvent("operation_artifact_changed", fingerprint="operation-artifact"),)
    return formal_plan(
        model_id="release_retirement_model",
        workflow=workflow,
        initial_states=(DevelopmentState(),),
        external_inputs=sequence + early + plane_separation,
        invariants=DEVELOPMENT_INVARIANTS,
        scenarios=(
            scenario("recoverable_sequential_retirement", "Install and release precede recoverable sequential deletion", DevelopmentState(), sequence, workflow, DEVELOPMENT_INVARIANTS),
            scenario("early_retirement_is_blocked", "Remote deletion before cutover remains blocked", DevelopmentState(), early, workflow, DEVELOPMENT_INVARIANTS),
            scenario("operation_change_keeps_release_identity", "User artifact work cannot stale development receipts", DevelopmentState(), plane_separation, workflow, DEVELOPMENT_INVARIANTS),
        ),
        protected_error_classes=("irreversible_retirement_before_cutover", "cross_plane_staleness_leak"),
        modeled_state=("validation_current", "install_status", "global_route_status", "release_status", "retired_remote"),
        modeled_side_effects=("active_install", "github_release", "legacy_repository_deletion"),
        completion_evidence=("validation_frozen", "release_published", "legacy_remote_retired"),
        known_bad_cases=("retire_legacy_before_installed_validation",),
        failure_modes=("legacy repository deleted before the replacement is recoverable", "operation edits invalidate release receipts"),
        harms=("both old and new routes become unavailable",),
        hard_invariants=("release consumes frozen validation", "retirement is sequential and recoverable"),
        adversarial_inputs=("delete first", "academic deletion before health recheck"),
        conformance_status=conformance_status,
        conformance_evidence=conformance_evidence,
    )
