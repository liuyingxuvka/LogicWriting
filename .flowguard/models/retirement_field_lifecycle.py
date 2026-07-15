"""FieldLifecycleMesh for the remote-retirement visibility contract."""

from __future__ import annotations

from flowguard import (
    FIELD_DISPOSITION_DELETED,
    FIELD_DISPOSITION_MIGRATED,
    FIELD_IMPACT_EXTERNAL_CONTRACT,
    FIELD_IMPACT_SIDE_EFFECT,
    FIELD_IMPACT_STATE,
    FIELD_LIFECYCLE_ACTIVE,
    FIELD_LIFECYCLE_REPLACED,
    FIELD_ROLE_STATE,
    TEST_KIND_FAILURE_PATH,
    TEST_KIND_HAPPY_PATH,
    TEST_KIND_NEGATIVE_PATH,
    TEST_KIND_REPLAY,
    FieldLifecycleGroup,
    FieldLifecyclePlan,
    FieldLifecycleRow,
    FieldProjection,
    review_field_lifecycle,
)


_TEST_REF = "test:tests/flowguard/test_model_contracts.py"
_REPLAY_REF = "replay:.flowguard/models/release_retirement_model.py"


def _projection(
    field_id: str,
    *,
    obligation_id: str,
    contract_id: str,
    reads: tuple[str, ...] = (),
    writes: tuple[str, ...] = (),
    side_effects: tuple[str, ...] = (),
) -> FieldProjection:
    return FieldProjection(
        f"projection:{field_id}",
        field_id,
        model_obligation_id=obligation_id,
        code_contract_id=contract_id,
        external_inputs=("repository_visibility", "anonymous_api_status"),
        external_outputs=("retirement_state",),
        state_reads=reads,
        state_writes=writes,
        side_effects=side_effects,
        error_paths=("remote_retirement_gate_or_order_failed",),
        required_test_kinds=(
            TEST_KIND_HAPPY_PATH,
            TEST_KIND_FAILURE_PATH,
            TEST_KIND_NEGATIVE_PATH,
            TEST_KIND_REPLAY,
        ),
        evidence_refs=(
            "gate:.flowguard/models/common.py",
            _TEST_REF,
            _REPLAY_REF,
        ),
        rationale="remote visibility fields control externally observable repository state and retirement closure",
    )


def retirement_visibility_field_plan() -> FieldLifecyclePlan:
    old_fields = (
        "field:retired_remote",
        "field:first_deletion_health_rechecked",
        "field:deletion_receipts",
    )
    new_fields = (
        "field:privatized_remote",
        "field:first_privatization_health_rechecked",
        "field:visibility_receipts",
        "field:user_deletion_handoff_status",
    )
    all_fields = old_fields + new_fields
    old_to_new = {
        "field:retired_remote": "field:privatized_remote",
        "field:first_deletion_health_rechecked": "field:first_privatization_health_rechecked",
        "field:deletion_receipts": "field:visibility_receipts",
    }

    rows = []
    for field_id, replacement_id in old_to_new.items():
        rows.append(
            FieldLifecycleRow(
                field_id,
                field_name=field_id.removeprefix("field:"),
                locations=("historical DevelopmentState contract",),
                group_id="remote-retirement-fields:leaf",
                role=FIELD_ROLE_STATE,
                lifecycle=FIELD_LIFECYCLE_REPLACED,
                behavior_impacts=(FIELD_IMPACT_STATE, FIELD_IMPACT_EXTERNAL_CONTRACT),
                replacement_field_id=replacement_id,
                disposition=FIELD_DISPOSITION_DELETED,
                disposition_evidence_refs=(
                    "test:deleted_remote_fields_and_events_have_no_compatibility_alias",
                ),
                projection=_projection(
                    field_id,
                    obligation_id="obligation:no-deletion-state-aliases",
                    contract_id="contract:no-deletion-state-aliases",
                ),
            )
        )

    rows.extend(
        (
            FieldLifecycleRow(
                "field:privatized_remote",
                field_name="privatized_remote",
                locations=(".flowguard/models/common.py:DevelopmentState",),
                group_id="remote-retirement-fields:leaf",
                role=FIELD_ROLE_STATE,
                lifecycle=FIELD_LIFECYCLE_ACTIVE,
                behavior_impacts=(FIELD_IMPACT_STATE, FIELD_IMPACT_SIDE_EFFECT, FIELD_IMPACT_EXTERNAL_CONTRACT),
                reader_ids=("PrivatizeLegacyRemote", "RecordRemoteDeletionHandoff"),
                writer_ids=("PrivatizeLegacyRemote",),
                old_field_ids=("field:retired_remote",),
                disposition=FIELD_DISPOSITION_MIGRATED,
                disposition_evidence_refs=(
                    "test:deleted_remote_fields_and_events_have_no_compatibility_alias",
                ),
                projection=_projection(
                    "field:privatized_remote",
                    obligation_id="obligation:sequential-retirement",
                    contract_id="contract:retirement-gate",
                    reads=("privatized_remote",),
                    writes=("privatized_remote",),
                    side_effects=("github_repository_visibility_private",),
                ),
            ),
            FieldLifecycleRow(
                "field:first_privatization_health_rechecked",
                field_name="first_privatization_health_rechecked",
                locations=(".flowguard/models/common.py:DevelopmentState",),
                group_id="remote-retirement-fields:leaf",
                role=FIELD_ROLE_STATE,
                lifecycle=FIELD_LIFECYCLE_ACTIVE,
                behavior_impacts=(FIELD_IMPACT_STATE,),
                reader_ids=("PrivatizeLegacyRemote",),
                writer_ids=("RecheckAfterFirstPrivatization",),
                old_field_ids=("field:first_deletion_health_rechecked",),
                disposition=FIELD_DISPOSITION_MIGRATED,
                disposition_evidence_refs=(
                    "test:deleted_remote_fields_and_events_have_no_compatibility_alias",
                ),
                projection=_projection(
                    "field:first_privatization_health_rechecked",
                    obligation_id="obligation:sequential-retirement",
                    contract_id="contract:retirement-gate",
                    reads=("privatized_remote",),
                    writes=("first_privatization_health_rechecked",),
                ),
            ),
            FieldLifecycleRow(
                "field:visibility_receipts",
                field_name="visibility_receipts",
                locations=(".flowguard/models/common.py:DevelopmentState",),
                group_id="remote-retirement-fields:leaf",
                role=FIELD_ROLE_STATE,
                lifecycle=FIELD_LIFECYCLE_ACTIVE,
                behavior_impacts=(FIELD_IMPACT_STATE, FIELD_IMPACT_EXTERNAL_CONTRACT),
                reader_ids=("RecordRemoteDeletionHandoff",),
                writer_ids=("PrivatizeLegacyRemote",),
                old_field_ids=("field:deletion_receipts",),
                disposition=FIELD_DISPOSITION_MIGRATED,
                disposition_evidence_refs=(
                    "test:deleted_remote_fields_and_events_have_no_compatibility_alias",
                ),
                projection=_projection(
                    "field:visibility_receipts",
                    obligation_id="obligation:sequential-retirement",
                    contract_id="contract:retirement-gate",
                    reads=("privatized_remote",),
                    writes=("visibility_receipts",),
                ),
            ),
            FieldLifecycleRow(
                "field:user_deletion_handoff_status",
                field_name="user_deletion_handoff_status",
                locations=(".flowguard/models/common.py:DevelopmentState",),
                group_id="remote-retirement-fields:leaf",
                role=FIELD_ROLE_STATE,
                lifecycle=FIELD_LIFECYCLE_ACTIVE,
                behavior_impacts=(FIELD_IMPACT_STATE, FIELD_IMPACT_EXTERNAL_CONTRACT),
                reader_ids=("development progress and closure",),
                writer_ids=("RecordRemoteDeletionHandoff",),
                projection=_projection(
                    "field:user_deletion_handoff_status",
                    obligation_id="obligation:sequential-retirement",
                    contract_id="contract:retirement-gate",
                    reads=("privatized_remote", "visibility_receipts"),
                    writes=("user_deletion_handoff_status", "terminal"),
                    side_effects=("user_deletion_handoff",),
                ),
            ),
        )
    )

    return FieldLifecyclePlan(
        "logic-writing-remote-retirement-fields",
        discovered_field_ids=all_fields,
        claim_scope="full",
        groups=(
            FieldLifecycleGroup(
                "remote-retirement-fields",
                boundary_kind="development_process_state",
                field_ids=all_fields,
                child_group_ids=("remote-retirement-fields:leaf",),
                owner_route="field_lifecycle_mesh",
                rationale="one parent groups the visibility and handoff state while leaf rows close every old-field disposition",
            ),
            FieldLifecycleGroup(
                "remote-retirement-fields:leaf",
                boundary_kind="leaf_fields",
                parent_group_id="remote-retirement-fields",
                field_ids=all_fields,
                owner_route="field_lifecycle_mesh",
            ),
        ),
        fields=tuple(rows),
        allow_scoped_confidence=False,
        notes=(
            "Deletion-named fields are removed, not aliased. The replacement contract records private visibility, "
            "anonymous inaccessibility, replacement health, and the user's ownership of any later deletion."
        ),
    )


def review_retirement_visibility_fields():
    return review_field_lifecycle(retirement_visibility_field_plan())
