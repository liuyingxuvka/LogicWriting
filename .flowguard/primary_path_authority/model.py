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
RESEARCHGUARD_MEMBER_PATHS = {
    "logicguard": ("logic", "primary:researchguard:logic"),
    "sourceguard": ("source", "primary:researchguard:source"),
    "traceguard": ("trace", "primary:researchguard:trace"),
}


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
                "legacy.travel-story-planner-workflow",
                fallback_for_path_id=PRIMARY_PATH_ID,
                business_intent=BUSINESS_INTENT,
                business_intent_id=BUSINESS_INTENT_ID,
                behavior_commitment_id=BEHAVIOR_COMMITMENT_ID,
                source_surface_id="surface:legacy-travel-skill",
                candidate_surface=PPA_CANDIDATE_LEGACY_PATH,
                candidate_trigger=PPA_TRIGGER_NEVER,
                candidate_behavior=PPA_BEHAVIOR_NO_OP,
                classification=PPA_AUTHORITY_MIGRATION_ONLY,
                disposition=PPA_DISPOSITION_DELETE,
                evidence_refs=("backup:travel-bundle", "openspec:retirement-task"),
            ),
            FallbackPathCandidate(
                "legacy.storyline-design-workflow",
                fallback_for_path_id=PRIMARY_PATH_ID,
                business_intent=BUSINESS_INTENT,
                business_intent_id=BUSINESS_INTENT_ID,
                behavior_commitment_id=BEHAVIOR_COMMITMENT_ID,
                source_surface_id="surface:legacy-storyline-skill",
                candidate_surface=PPA_CANDIDATE_LEGACY_PATH,
                candidate_trigger=PPA_TRIGGER_NEVER,
                candidate_behavior=PPA_BEHAVIOR_NO_OP,
                classification=PPA_AUTHORITY_MIGRATION_ONLY,
                disposition=PPA_DISPOSITION_DELETE,
                evidence_refs=("backup:storyline-bundle", "openspec:retirement-task"),
            ),
        ),
        metadata={
            "claim_boundary": "design topology only; installed runtime evidence is not yet available",
            "internal_route_boundary": "investigation, academic-writing, fiction-writing, and travel-guide are selected children of the primary entry, not alternate public entrypoints",
        },
    )


def researchguard_member_plan():
    """Model one console with three fail-closed semantic member paths."""

    return PrimaryPathAuthorityPlan(
        "logic-writing-researchguard-member-topology",
        primary_paths=(
            PrimaryPathContract(
                "logic_writing.researchguard.console",
                business_intent="invoke one selected ResearchGuard semantic owner",
                business_intent_id="intent:researchguard:selected-member",
                behavior_commitment_id="C02:preserve-specialist-authority",
                primary_entrypoint_id="console:researchguard",
                owner_model_id="model:route-and-guard",
                owner_code_contract_id="contract:researchguard-single-console",
                expected_terminal="native_member_result_or_visible_provider_unavailable",
                failure_policy=PPA_FAILURE_POLICY_FAIL_CLOSED,
                source_surface_ids=("surface:logic-writing-adapter",),
                metadata={
                    "provider_console_id": "researchguard",
                    "member_bindings": {
                        member_id: {
                            "member_command": member_command,
                            "primary_path_id": primary_path_id,
                        }
                        for member_id, (
                            member_command,
                            primary_path_id,
                        ) in RESEARCHGUARD_MEMBER_PATHS.items()
                    },
                    "alternate_success_path": False,
                },
            ),
        ),
        fallback_candidates=(),
        metadata={
            "claim_boundary": (
                "design authority for Logic Writing provider routing; native "
                "ResearchGuard work and installation evidence remain separate"
            ),
            "compatibility_policy": "direct-current-only",
        },
    )


def broken_old_skill_masks_primary_failure():
    return PrimaryPathAuthorityPlan(
        "broken-old-skill-masks-primary-failure",
        primary_paths=design_plan().primary_paths,
        fallback_candidates=(
            FallbackPathCandidate(
                "legacy.travel-story-planner-workflow",
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
