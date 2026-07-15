"""Primary Path Authority for the single public Logic Writing entrypoint.

This model is deliberately design-phase until installed runtime replay exists.
It proves the intended authority topology and rejects fallback-shaped designs;
it does not yet claim material runtime conformance.
"""

from flowguard import (
    FallbackPathCandidate,
    PrimaryPathAuthorityPlan,
    PrimaryPathContract,
    PPA_AUTHORITY_MANUAL_RECOVERY,
    PPA_AUTHORITY_MIGRATION_ONLY,
    PPA_BEHAVIOR_NO_OP,
    PPA_BEHAVIOR_READ_STATE,
    PPA_BEHAVIOR_RETURN_SUCCESS,
    PPA_CANDIDATE_ALIAS,
    PPA_CANDIDATE_LEGACY_PATH,
    PPA_CANDIDATE_MANUAL_RECOVERY,
    PPA_DISPOSITION_BLOCK,
    PPA_DISPOSITION_DELETE,
    PPA_DISPOSITION_MANUAL_ONLY,
    PPA_DISPOSITION_UNKNOWN,
    PPA_FAILURE_POLICY_FAIL_CLOSED,
    PPA_TRIGGER_MISSING_FIELD,
    PPA_TRIGGER_NEVER,
    PPA_TRIGGER_PRIMARY_FAILURE,
)


BUSINESS_INTENT = "run Logic Writing for a reader-facing terminal artifact"
BUSINESS_INTENT_ID = "intent:select-one-final-owner"
BEHAVIOR_COMMITMENT_ID = "C01:select-one-final-owner"
PRIMARY_PATH_ID = "logic_writing.entry"


def design_plan():
    return PrimaryPathAuthorityPlan(
        "logic-writing-primary-path-design",
        primary_paths=(
            PrimaryPathContract(
                PRIMARY_PATH_ID,
                business_intent=BUSINESS_INTENT,
                business_intent_id=BUSINESS_INTENT_ID,
                behavior_commitment_id=BEHAVIOR_COMMITMENT_ID,
                primary_entrypoint_id="skill:logic-writing",
                owner_model_id="model:route-and-guard",
                owner_code_contract_id="contract:select-route",
                expected_terminal="reader_artifact_or_visible_bounded_failure",
                failure_policy=PPA_FAILURE_POLICY_FAIL_CLOSED,
                source_surface_ids=("surface:skill-entry",),
            ),
        ),
        fallback_candidates=(
            FallbackPathCandidate(
                "legacy.research-investigation-workflow",
                fallback_for_path_id=PRIMARY_PATH_ID,
                business_intent=BUSINESS_INTENT,
                business_intent_id=BUSINESS_INTENT_ID,
                behavior_commitment_id=BEHAVIOR_COMMITMENT_ID,
                source_surface_id="surface:legacy-research-skill",
                candidate_surface=PPA_CANDIDATE_LEGACY_PATH,
                candidate_trigger=PPA_TRIGGER_NEVER,
                candidate_behavior=PPA_BEHAVIOR_NO_OP,
                classification=PPA_AUTHORITY_MIGRATION_ONLY,
                disposition=PPA_DISPOSITION_DELETE,
                evidence_refs=("backup:research-bundle", "openspec:retirement-task"),
            ),
            FallbackPathCandidate(
                "legacy.academic-thesis-revision-workflow",
                fallback_for_path_id=PRIMARY_PATH_ID,
                business_intent=BUSINESS_INTENT,
                business_intent_id=BUSINESS_INTENT_ID,
                behavior_commitment_id=BEHAVIOR_COMMITMENT_ID,
                source_surface_id="surface:legacy-academic-skill",
                candidate_surface=PPA_CANDIDATE_LEGACY_PATH,
                candidate_trigger=PPA_TRIGGER_NEVER,
                candidate_behavior=PPA_BEHAVIOR_NO_OP,
                classification=PPA_AUTHORITY_MIGRATION_ONLY,
                disposition=PPA_DISPOSITION_DELETE,
                evidence_refs=("backup:academic-bundle", "openspec:retirement-task"),
            ),
        ),
        metadata={
            "claim_boundary": "design topology only; installed runtime evidence is not yet available",
            "internal_route_boundary": "investigation and academic-writing are selected children of the primary entry, not alternate public entrypoints",
        },
    )


def broken_old_skill_masks_primary_failure():
    return PrimaryPathAuthorityPlan(
        "broken-old-skill-masks-primary-failure",
        primary_paths=design_plan().primary_paths,
        fallback_candidates=(
            FallbackPathCandidate(
                "legacy.research-investigation-workflow",
                fallback_for_path_id=PRIMARY_PATH_ID,
                business_intent=BUSINESS_INTENT,
                candidate_surface=PPA_CANDIDATE_LEGACY_PATH,
                candidate_trigger=PPA_TRIGGER_PRIMARY_FAILURE,
                candidate_behavior=PPA_BEHAVIOR_RETURN_SUCCESS,
                invokes_on_primary_failure=True,
                returns_success_after_primary_failure=True,
                disposition=PPA_DISPOSITION_BLOCK,
            ),
        ),
    )


def broken_alias_unknown_disposition():
    return PrimaryPathAuthorityPlan(
        "broken-alias-unknown-disposition",
        primary_paths=design_plan().primary_paths,
        fallback_candidates=(
            FallbackPathCandidate(
                "alias.logic-writing-old-name",
                fallback_for_path_id=PRIMARY_PATH_ID,
                business_intent=BUSINESS_INTENT,
                candidate_surface=PPA_CANDIDATE_ALIAS,
                candidate_trigger=PPA_TRIGGER_MISSING_FIELD,
                candidate_behavior=PPA_BEHAVIOR_READ_STATE,
                returns_success_after_primary_failure=True,
                disposition=PPA_DISPOSITION_UNKNOWN,
            ),
        ),
    )


def broken_manual_recovery_auto_invoked():
    return PrimaryPathAuthorityPlan(
        "broken-manual-recovery-auto-invoked",
        primary_paths=design_plan().primary_paths,
        fallback_candidates=(
            FallbackPathCandidate(
                "operator.restore-old-skill",
                fallback_for_path_id=PRIMARY_PATH_ID,
                business_intent=BUSINESS_INTENT,
                candidate_surface=PPA_CANDIDATE_MANUAL_RECOVERY,
                candidate_trigger=PPA_TRIGGER_PRIMARY_FAILURE,
                classification=PPA_AUTHORITY_MANUAL_RECOVERY,
                disposition=PPA_DISPOSITION_MANUAL_ONLY,
                invokes_on_primary_failure=True,
                evidence_refs=("backup:restore-receipt",),
            ),
        ),
    )
