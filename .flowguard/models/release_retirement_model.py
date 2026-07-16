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
        DevelopmentEvent("quarantine_legacy_local", target="travel"),
        DevelopmentEvent("quarantine_legacy_local", target="storyline"),
        DevelopmentEvent("privatize_legacy_remote", fingerprint="private+anon404:travel", target="travel"),
        DevelopmentEvent("recheck_after_first_privatization", status="current_pass"),
        DevelopmentEvent("privatize_legacy_remote", fingerprint="private+anon404:storyline", target="storyline"),
        DevelopmentEvent("record_remote_deletion_handoff", status="current_pass"),
    )
    early = (DevelopmentEvent("privatize_legacy_remote", fingerprint="bad", target="travel"),)
    plane_separation = (DevelopmentEvent("operation_artifact_changed", fingerprint="operation-artifact"),)
    return formal_plan(
        model_id="release_retirement_model",
        workflow=workflow,
        initial_states=(DevelopmentState(),),
        external_inputs=sequence + early + plane_separation,
        invariants=DEVELOPMENT_INVARIANTS,
        scenarios=(
            scenario("recoverable_sequential_retirement", "Install and release precede sequential privatization and a user-owned deletion handoff", DevelopmentState(), sequence, workflow, DEVELOPMENT_INVARIANTS),
            scenario("early_retirement_is_blocked", "Remote privatization before cutover remains blocked", DevelopmentState(), early, workflow, DEVELOPMENT_INVARIANTS),
            scenario("operation_change_keeps_release_identity", "User artifact work cannot stale development receipts", DevelopmentState(), plane_separation, workflow, DEVELOPMENT_INVARIANTS),
        ),
        protected_error_classes=("remote_visibility_retirement_before_cutover", "cross_plane_staleness_leak"),
        modeled_state=("validation_current", "install_status", "global_route_status", "release_status", "privatized_remote", "user_deletion_handoff_status"),
        modeled_side_effects=("active_install", "github_release", "legacy_repository_visibility_private", "user_deletion_handoff"),
        completion_evidence=("validation_frozen", "release_published", "legacy_remote_private", "user_deletion_handoff_recorded"),
        known_bad_cases=("privatize_legacy_before_installed_validation",),
        failure_modes=("legacy repository privatized before the replacement is recoverable", "anonymous 404 mislabeled as deletion", "operation edits invalidate release receipts"),
        harms=("both old and new routes become unavailable",),
        hard_invariants=("release consumes frozen validation", "retirement is sequential and recoverable"),
        adversarial_inputs=("privatize first", "Storyline privatization before Travel health recheck", "claim deletion from anonymous 404"),
        conformance_status=conformance_status,
        conformance_evidence=conformance_evidence,
    )
