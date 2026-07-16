"""Validate one bounded request to a native specialist owner."""

from __future__ import annotations

from datetime import datetime

from _common import (
    NATIVE_OWNERS,
    ValidationError,
    cli_validate,
    fingerprint_without,
    require_fingerprint,
    require_list,
    require_mapping,
    require_schema,
    require_string,
    require_string_list,
    reject_unknown_keys,
    validation_result,
)


REQUEST_FIELDS = {
    "schema_version",
    "request_id",
    "task_id",
    "parent_route",
    "native_owner",
    "native_route",
    "requested_scope",
    "input_artifact_refs",
    "input_fingerprints",
    "claim_scope",
    "required_output_type",
    "freshness_baseline",
    "user_constraints",
    "gap_contract",
    "requested_at",
    "request_fingerprint",
}
REQUIRED_REQUEST_FIELDS = REQUEST_FIELDS - {"gap_contract"}
ARTIFACT_FIELDS = {"artifact_id", "artifact_kind", "fingerprint", "locator"}
CONSTRAINT_FIELDS = {"constraint_id", "kind", "value"}
CONSTRAINT_KINDS = {
    "access_policy",
    "privacy",
    "language",
    "output_format",
    "length",
    "deadline",
    "provider",
    "other",
}
GAP_FIELDS = {
    "gap_id",
    "affected_claim_ids",
    "affected_artifact_units",
    "required_evidence_roles",
    "required_strength",
    "access_policy",
    "safe_interim_wording",
    "unsafe_claim_boundary",
}
SOURCE_ROLES = {
    "primary",
    "official",
    "implementation",
    "outcome",
    "method",
    "context",
    "counterevidence",
    "critique",
    "data",
    "secondary",
}


def _fingerprint_map(value, label):
    value = require_mapping(value, label)
    if not value:
        raise ValidationError(f"{label} cannot be empty")
    for key in value:
        require_fingerprint(value, key)
    return value


def _date_time(value, field):
    text = require_string(value, field)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(f"{field} must be an ISO 8601 date-time") from exc
    return text


def validate_adapter_request(value):
    value = require_mapping(value, "adapter request")
    require_schema("adapter-request.schema.json", value, label="adapter request")
    reject_unknown_keys(value, REQUEST_FIELDS, "adapter request")
    missing = sorted(REQUIRED_REQUEST_FIELDS - set(value))
    if missing:
        raise ValidationError(f"adapter request is missing required fields: {', '.join(missing)}")
    if require_string(value, "schema_version") != "1.0":
        raise ValidationError("schema_version must be 1.0")
    for field in ("request_id", "task_id", "native_route", "requested_scope", "claim_scope", "required_output_type"):
        require_string(value, field)
    parent_route = require_string(value, "parent_route")
    if parent_route not in {
        "investigation", "academic-writing", "fiction-writing", "travel-guide"
    }:
        raise ValidationError("parent_route must be one of the four Logic Writing routes")
    native_owner = require_string(value, "native_owner")
    if native_owner not in NATIVE_OWNERS:
        raise ValidationError(f"unsupported native_owner: {native_owner}")

    artifact_ids: list[str] = []
    for index, item in enumerate(require_list(value.get("input_artifact_refs"), "input_artifact_refs")):
        artifact = require_mapping(item, f"input_artifact_refs[{index}]")
        reject_unknown_keys(artifact, ARTIFACT_FIELDS, f"input_artifact_refs[{index}]")
        if set(artifact) != ARTIFACT_FIELDS:
            raise ValidationError(f"input_artifact_refs[{index}] is missing required fields")
        artifact_ids.append(require_string(artifact, "artifact_id"))
        require_string(artifact, "artifact_kind")
        require_fingerprint(artifact, "fingerprint")
        locator = artifact.get("locator")
        if locator is not None and (not isinstance(locator, str) or not locator.strip()):
            raise ValidationError("artifact locator must be null or non-empty text")
    if len(artifact_ids) != len(set(artifact_ids)):
        raise ValidationError("input_artifact_refs contains duplicate artifact ids")
    _fingerprint_map(value.get("input_fingerprints"), "input_fingerprints")
    _fingerprint_map(value.get("freshness_baseline"), "freshness_baseline")

    constraint_ids: list[str] = []
    for index, item in enumerate(require_list(value.get("user_constraints"), "user_constraints")):
        constraint = require_mapping(item, f"user_constraints[{index}]")
        reject_unknown_keys(constraint, CONSTRAINT_FIELDS, f"user_constraints[{index}]")
        if set(constraint) != CONSTRAINT_FIELDS:
            raise ValidationError(f"user_constraints[{index}] is missing required fields")
        constraint_ids.append(require_string(constraint, "constraint_id"))
        if require_string(constraint, "kind") not in CONSTRAINT_KINDS:
            raise ValidationError("unsupported user constraint kind")
        require_string(constraint, "value")
    if len(constraint_ids) != len(set(constraint_ids)):
        raise ValidationError("user_constraints contains duplicate ids")

    gap = value.get("gap_contract")
    if gap is not None:
        gap = require_mapping(gap, "gap_contract")
        reject_unknown_keys(gap, GAP_FIELDS, "gap_contract")
        if set(gap) != GAP_FIELDS:
            raise ValidationError("gap_contract is missing required fields")
        require_string(gap, "gap_id")
        require_string_list(gap.get("affected_claim_ids"), "affected_claim_ids")
        require_string_list(gap.get("affected_artifact_units"), "affected_artifact_units")
        roles = require_string_list(gap.get("required_evidence_roles"), "required_evidence_roles", nonempty=True)
        if not set(roles).issubset(SOURCE_ROLES):
            raise ValidationError("gap_contract contains an unsupported evidence role")
        if require_string(gap, "required_strength") not in {"tentative", "qualified", "supported", "strong"}:
            raise ValidationError("gap_contract has an unsupported required_strength")
        if require_string(gap, "access_policy") not in {
            "public_only",
            "local_allowed",
            "internal_allowed",
            "permission_gated_allowed",
        }:
            raise ValidationError("gap_contract has an unsupported access_policy")
        require_string(gap, "safe_interim_wording")
        require_string(gap, "unsafe_claim_boundary")

    _date_time(value, "requested_at")
    expected = fingerprint_without(value, "request_fingerprint")
    if require_fingerprint(value, "request_fingerprint") != expected:
        raise ValidationError("request_fingerprint does not match the adapter request")
    return validation_result(
        status="current_pass",
        request_id=value["request_id"],
        parent_route=parent_route,
        native_owner=native_owner,
        request_fingerprint=expected,
    )


if __name__ == "__main__":
    raise SystemExit(cli_validate(validate_adapter_request, __doc__))
