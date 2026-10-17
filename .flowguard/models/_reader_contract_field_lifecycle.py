"""FieldLifecycleMesh for the direct-current reader contract replacement."""

from __future__ import annotations

from flowguard import (
    FIELD_DISPOSITION_DELETED,
    FIELD_DISPOSITION_SAME_CONTRACT_REPAIRED,
    FIELD_IMPACT_EXTERNAL_CONTRACT,
    FIELD_IMPACT_STATE,
    FIELD_LIFECYCLE_NEW,
    FIELD_LIFECYCLE_REPLACED,
    FIELD_ROLE_PERSISTED,
    FIELD_ROLE_SCHEMA_VERSION,
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


_TEST_REF = "test:tests/unit/test_reader_pipeline_v2.py"
_REPLAY_REF = "replay:.flowguard/models/reader_artifact_model.py"

_REPLACED = {
    "field:constraints": "field:reader_intent",
    "field:information_sequence": "field:composition_plan",
    "field:principal_findings": "field:content_units",
    "field:allowed_wording": "field:safe_meaning",
    "field:supported_wording": "field:safe_meaning",
    "field:prohibited_wording": "field:prohibited_overclaims",
    "field:artifact_span": "field:artifact_map_span",
    "field:caller_quality_score": "field:independent_reader_judgment",
    "field:closure_no_progress_count": "field:repair_result_lineage",
    "field:academic_only_revision_provenance": "field:artifact_mode_revision_provenance",
}

_CURRENT = (
    "field:reader_intent",
    "field:composition_plan",
    "field:content_units",
    "field:safe_meaning",
    "field:prohibited_overclaims",
    "field:artifact_map_span",
    "field:independent_reader_judgment",
    "field:repair_result_lineage",
    "field:artifact_mode_revision_provenance",
)


def _projection(field_id: str) -> FieldProjection:
    return FieldProjection(
        f"projection:{field_id}",
        field_id,
        model_obligation_id="obligation:reader-contract-v2",
        code_contract_id="contract:reader-pipeline-v2",
        external_inputs=("writing_request", "route_content", "current_artifact_bytes"),
        external_outputs=("reader_contract_receipt", "artifact_quality_receipt", "closure"),
        state_reads=("reader_intent_fingerprint", "composition_plan_fingerprint", "artifact_fingerprint"),
        state_writes=("reader_intent_status", "composition_plan_status", "shared_binding_status"),
        error_paths=("legacy_contract_rejected", "identity_mismatch", "typed_repair_required"),
        required_test_kinds=(
            TEST_KIND_HAPPY_PATH,
            TEST_KIND_FAILURE_PATH,
            TEST_KIND_NEGATIVE_PATH,
            TEST_KIND_REPLAY,
        ),
        evidence_refs=(
            "gate:skills/logic-writing/scripts/schema_validation.py",
            _TEST_REF,
            _REPLAY_REF,
        ),
        rationale="reader-facing behavior changes only through the declared current schemas and exact identity chain",
    )


def reader_contract_field_plan() -> FieldLifecyclePlan:
    rows = []
    for old_id, replacement_id in _REPLACED.items():
        rows.append(
            FieldLifecycleRow(
                old_id,
                field_name=old_id.removeprefix("field:"),
                locations=("Logic Writing reader contracts v1",),
                group_id="reader-contract-fields:leaf",
                role=FIELD_ROLE_SCHEMA_VERSION,
                lifecycle=FIELD_LIFECYCLE_REPLACED,
                behavior_impacts=(FIELD_IMPACT_STATE, FIELD_IMPACT_EXTERNAL_CONTRACT),
                replacement_field_id=replacement_id,
                disposition=FIELD_DISPOSITION_DELETED,
                disposition_evidence_refs=(
                    "test:legacy_reader_contracts_are_rejected_without_fallback",
                ),
                projection=_projection(old_id),
            )
        )

    for field_id in _CURRENT:
        role = FIELD_ROLE_PERSISTED if field_id in {
            "field:reader_intent",
            "field:composition_plan",
            "field:artifact_map_span",
            "field:repair_result_lineage",
        } else FIELD_ROLE_STATE
        rows.append(
            FieldLifecycleRow(
                field_id,
                field_name=field_id.removeprefix("field:"),
                locations=("skills/logic-writing/assets/schemas", "skills/logic-writing/scripts"),
                group_id="reader-contract-fields:leaf",
                role=role,
                lifecycle=FIELD_LIFECYCLE_NEW,
                behavior_impacts=(FIELD_IMPACT_STATE, FIELD_IMPACT_EXTERNAL_CONTRACT),
                old_field_ids=tuple(old for old, new in _REPLACED.items() if new == field_id),
                reader_ids=("shared reader kernel", "selected final route", "closure"),
                writer_ids=("current reader builders", "selected final route"),
                disposition=FIELD_DISPOSITION_SAME_CONTRACT_REPAIRED,
                disposition_evidence_refs=(
                    "test:reader_pipeline_v2_current_contract",
                    "test:legacy_reader_contracts_are_rejected_without_fallback",
                ),
                projection=_projection(field_id),
            )
        )

    all_fields = tuple(_REPLACED) + _CURRENT
    return FieldLifecyclePlan(
        "logic-writing-reader-contract-v2-fields",
        discovered_field_ids=all_fields,
        claim_scope="full",
        groups=(
            FieldLifecycleGroup(
                "reader-contract-fields",
                boundary_kind="reader_contract",
                field_ids=all_fields,
                child_group_ids=("reader-contract-fields:leaf",),
                owner_route="field_lifecycle_mesh",
                rationale="one parent owns the direct-current reader contract replacement",
            ),
            FieldLifecycleGroup(
                "reader-contract-fields:leaf",
                boundary_kind="leaf_fields",
                parent_group_id="reader-contract-fields",
                field_ids=all_fields,
                owner_route="field_lifecycle_mesh",
            ),
        ),
        fields=tuple(rows),
        allow_scoped_confidence=False,
        notes=(
            "The v1 fields are deleted from normal runtime. Current v2 fields are direct replacements; "
            "there is no alias, converter, dual emission, compatibility reader, or fallback path."
        ),
    )


def review_reader_contract_fields():
    return review_field_lifecycle(reader_contract_field_plan())
