"""Validate a native specialist result and commit its exact generic Receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from _common import (
    ALL_STATUSES,
    EVIDENCE_DOMAINS,
    NATIVE_OWNERS,
    ValidationError,
    dump_json,
    fingerprint,
    fingerprint_without,
    load_json,
    require_fingerprint,
    require_mapping,
    require_schema,
    require_string,
    require_string_list,
    reject_unknown_keys,
    validation_result,
)
from build_source_unit_manifest import fingerprint_bytes
from receipt_authority import _commit_managed_receipt, _store_content_object
from schema_validation import SchemaValidationError


ALLOWED = {
    "schema_version",
    "request_id",
    "native_owner",
    "semantic_owner_id",
    "native_route",
    "run_id",
    "status",
    "covered_obligation_ids",
    "input_fingerprints",
    "output_fingerprints",
    "artifact_fingerprint",
    "covered_scope",
    "evidence_domain",
    "safe_claim",
    "unsafe_claim_boundary",
    "native_receipt",
    "next_route",
    "artifact_refs",
    "unresolved_gaps",
    "stale_inputs",
    "dependency_receipt_fingerprints",
    "adapter_result_fingerprint",
}
NATIVE_PAYLOAD_FIELDS = {
    "producer_skill",
    "semantic_owner_id",
    "native_route",
    "run_id",
    "status",
    "covered_obligation_ids",
    "input_fingerprints",
    "output_fingerprints",
    "artifact_fingerprint",
    "covered_scope",
    "evidence_domain",
    "safe_claim",
    "unsafe_claim_boundary",
    "next_route",
    "unresolved_gaps",
    "stale_inputs",
    "dependency_receipt_fingerprints",
    "evidence_payload",
}
NEXT_ROUTES = {
    "investigation",
    "academic-writing",
    "sourceguard",
    "logicguard",
    "traceguard",
    "worldguard",
    "flowguard",
    "documents",
    "pdf",
    "fiction-writing",
    "travel-guide",
    "human_review",
    "none",
}
OWNER_DOMAINS = {
    "sourceguard": {
        "source_discovery",
        "source_observation",
        "source_depth",
        "source_library",
    },
    "logicguard": {
        "argument_model",
        "structured_artifact",
        "model_depth",
        "artifact_synthesis",
        "citation_semantics",
    },
    "traceguard": {
        "temporal_trace",
        "causal_trace",
        "competing_storyline",
        "prediction_boundary",
    },
    "worldguard": {"world_consistency"},
    "flowguard": {"process_model", "process_freshness", "development_validation"},
    "documents": {
        "document_content",
        "document_mutation",
        "document_render",
        "document_visual",
    },
    "pdf": {"pdf_content", "pdf_render", "pdf_visual"},
}


def _fingerprint_map(value: Any, label: str) -> dict[str, str]:
    mapping = require_mapping(value, label)
    if not mapping:
        raise ValidationError(f"{label} must contain at least one fingerprint")
    for key, item in mapping.items():
        if not isinstance(key, str) or not key.strip():
            raise ValidationError(f"{label} keys must be non-empty strings")
        require_fingerprint({key: item}, key)
    return dict(mapping)


def _native_fields(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "producer_skill": value["native_owner"],
        "semantic_owner_id": value["semantic_owner_id"],
        "native_route": value["native_route"],
        "run_id": value["run_id"],
        "status": value["status"],
        "covered_obligation_ids": value["covered_obligation_ids"],
        "input_fingerprints": value["input_fingerprints"],
        "artifact_fingerprint": value["artifact_fingerprint"],
        "covered_scope": value["covered_scope"],
        "evidence_domain": value["evidence_domain"],
        "safe_claim": value["safe_claim"],
        "unsafe_claim_boundary": value["unsafe_claim_boundary"],
        "next_route": value["next_route"],
        "unresolved_gaps": value["unresolved_gaps"],
        "stale_inputs": value["stale_inputs"],
        "dependency_receipt_fingerprints": value[
            "dependency_receipt_fingerprints"
        ],
    }


def _validate_domain_payload(
    *,
    owner: str,
    semantic_owner_id: str,
    native_route: str,
    evidence_domain: str,
    artifact_fingerprint: str,
    inputs: Mapping[str, str],
    outputs: Mapping[str, str],
    evidence_payload: Mapping[str, Any],
) -> None:
    if evidence_domain == "source_observation":
        if set(evidence_payload) != {"source_record_basis"}:
            raise ValidationError(
                "source observation payload must contain the exact source_record_basis"
            )
        basis = require_mapping(
            evidence_payload.get("source_record_basis"), "source_record_basis"
        )
        source_id = require_string(basis, "source_id")
        if semantic_owner_id != f"source-observation:{source_id}":
            raise ValidationError("source observation semantic owner is not stable")
        if basis.get("observed_content_fingerprint") != artifact_fingerprint:
            raise ValidationError(
                "source observation artifact does not match the observed content"
            )
        if outputs.get("source_observation") != fingerprint(basis):
            raise ValidationError(
                "source observation output does not bind the exact source record"
            )
        return

    if evidence_domain in {"argument_model", "citation_semantics"} and (
        "claim_semantic_fit" in outputs
    ):
        if set(evidence_payload) != {
            "claim_semantic_basis",
            "source_registry_fingerprint",
        }:
            raise ValidationError(
                "claim semantic payload must bind one claim basis and SourceRegistry"
            )
        basis = require_mapping(
            evidence_payload.get("claim_semantic_basis"), "claim_semantic_basis"
        )
        claim_id = require_string(basis, "claim_id")
        if semantic_owner_id != f"claim-semantic:{claim_id}":
            raise ValidationError("claim semantic owner is not stable")
        registry_fingerprint = evidence_payload.get("source_registry_fingerprint")
        require_fingerprint(
            {"source_registry_fingerprint": registry_fingerprint},
            "source_registry_fingerprint",
        )
        if inputs.get("source_registry") != registry_fingerprint:
            raise ValidationError(
                "claim semantic native result does not consume the exact SourceRegistry"
            )
        if outputs.get("claim_semantic_fit") != fingerprint(basis):
            raise ValidationError(
                "claim semantic output does not bind the exact claim boundary"
            )
        return

    if evidence_domain in {"causal_trace", "prediction_boundary"}:
        if set(evidence_payload) != {
            "claim_id",
            "claim_semantic_basis_fingerprint",
        }:
            raise ValidationError(
                "claim trace payload must identify the exact modeled claim basis"
            )
        claim_id = require_string(dict(evidence_payload), "claim_id")
        claim_basis = evidence_payload.get("claim_semantic_basis_fingerprint")
        require_fingerprint(
            {"claim_semantic_basis_fingerprint": claim_basis},
            "claim_semantic_basis_fingerprint",
        )
        expected_owner = f"trace:{claim_id}:{evidence_domain}"
        if semantic_owner_id != expected_owner:
            raise ValidationError("claim trace semantic owner is not stable")
        suffix = (
            "causal_trace" if evidence_domain == "causal_trace" else "prediction_boundary"
        )
        if outputs.get(f"claim:{claim_id}:{suffix}") != claim_basis:
            raise ValidationError("claim trace output does not bind the modeled claim")
        return

    if owner == "flowguard" and native_route == "closure-obligation-contract":
        expected = {
            "obligations",
            "broad_claim_requested",
            "route_decision",
        }
        if set(evidence_payload) != expected:
            raise ValidationError(
                "closure obligation contract payload has a non-current shape"
            )
        obligations = evidence_payload.get("obligations")
        if not isinstance(obligations, list) or not obligations:
            raise ValidationError("closure obligation contract must contain obligations")
        route_decision = require_mapping(
            evidence_payload.get("route_decision"), "route_decision"
        )
        require_schema("route-decision.schema.json", route_decision, label="route decision")
        if route_decision.get("decision_fingerprint") != fingerprint_without(
            route_decision, "decision_fingerprint"
        ):
            raise ValidationError("closure contract route decision fingerprint is invalid")
        if route_decision.get("status") != "current":
            raise ValidationError("closure contract requires a current route decision")
        final_owner = route_decision.get("final_owner")
        if final_owner not in {
            "investigation", "academic-writing", "fiction-writing", "travel-guide"
        }:
            raise ValidationError("closure obligation contract final owner is invalid")
        if not isinstance(evidence_payload.get("broad_claim_requested"), bool):
            raise ValidationError("closure broad-claim class must be boolean")
        if inputs.get("route_decision") != route_decision["decision_fingerprint"]:
            raise ValidationError("closure contract does not consume its route decision")
        if semantic_owner_id != f"closure-contract:{route_decision['decision_id']}":
            raise ValidationError("closure contract semantic owner is not stable")
        if outputs.get("obligation_manifest") != fingerprint(obligations):
            raise ValidationError(
                "closure contract output does not bind its complete obligation rows"
            )
        if outputs.get("closure_contract") != fingerprint(dict(evidence_payload)):
            raise ValidationError(
                "closure contract output does not bind route, owner, and claim class"
            )
        return

    expected = {"observed_artifact_fingerprint", "validated_output_fingerprints"}
    if set(evidence_payload) != expected:
        raise ValidationError(
            "native evidence payload must bind the observed artifact and validated outputs"
        )
    if evidence_payload.get("observed_artifact_fingerprint") != artifact_fingerprint:
        raise ValidationError("native evidence payload observes a different artifact")
    if evidence_payload.get("validated_output_fingerprints") != dict(outputs):
        raise ValidationError("native evidence payload does not bind exact outputs")


def validate_adapter_result(value: Mapping[str, Any]) -> dict[str, Any]:
    value = require_mapping(dict(value), "adapter result")
    require_schema("adapter-result.schema.json", value, label="AdapterResult")
    reject_unknown_keys(value, ALLOWED, "adapter result")
    if set(value) != ALLOWED:
        raise ValidationError(
            "adapter result is missing required fields: "
            + ", ".join(sorted(ALLOWED - set(value)))
        )
    if require_string(value, "schema_version") != "1.0":
        raise ValidationError("schema_version must be 1.0")
    owner = require_string(value, "native_owner").lower()
    if owner not in NATIVE_OWNERS:
        raise ValidationError(f"unsupported native_owner: {owner}")
    require_string(value, "request_id")
    semantic_owner_id = require_string(value, "semantic_owner_id")
    native_route = require_string(value, "native_route")
    require_string(value, "run_id")
    status = require_string(value, "status")
    if status not in ALL_STATUSES:
        raise ValidationError(f"unsupported adapter status: {status}")
    require_string_list(
        value.get("covered_obligation_ids"),
        "covered_obligation_ids",
        nonempty=True,
    )
    inputs = _fingerprint_map(value.get("input_fingerprints"), "input_fingerprints")
    outputs = _fingerprint_map(value.get("output_fingerprints"), "output_fingerprints")
    artifact_fingerprint = require_fingerprint(value, "artifact_fingerprint")
    require_string(value, "covered_scope")
    evidence_domain = require_string(value, "evidence_domain")
    if evidence_domain not in EVIDENCE_DOMAINS - {"final_closure"}:
        raise ValidationError(f"unsupported adapter evidence_domain: {evidence_domain}")
    if evidence_domain not in OWNER_DOMAINS[owner]:
        raise ValidationError(
            f"{owner} does not own the {evidence_domain} evidence domain"
        )
    require_string(value, "safe_claim")
    require_string(value, "unsafe_claim_boundary")
    next_route = require_string(value, "next_route")
    if next_route not in NEXT_ROUTES:
        raise ValidationError(f"unsupported next_route: {next_route}")
    collections = {
        field: require_string_list(value.get(field), field)
        for field in ("artifact_refs", "unresolved_gaps", "stale_inputs")
    }
    dependencies = require_string_list(
        value.get("dependency_receipt_fingerprints"),
        "dependency_receipt_fingerprints",
    )
    for index, dependency in enumerate(dependencies):
        require_fingerprint({"dependency": dependency}, "dependency")
    if status == "current_pass" and (
        collections["unresolved_gaps"] or collections["stale_inputs"]
    ):
        raise ValidationError(
            "current_pass cannot carry unresolved_gaps or stale_inputs"
        )
    if status != "current_pass" and not (
        collections["unresolved_gaps"] or collections["stale_inputs"]
    ):
        raise ValidationError(
            "non-pass adapter results require an unresolved gap or stale input"
        )

    native_receipt = require_mapping(value.get("native_receipt"), "native_receipt")
    if set(native_receipt) != {
        "receipt_type",
        "schema_version",
        "payload",
        "fingerprint",
    }:
        raise ValidationError("native_receipt has a non-current shape")
    expected_type = f"{owner}.{evidence_domain}.v1"
    if require_string(native_receipt, "receipt_type") != expected_type:
        raise ValidationError("native receipt type does not match owner and domain")
    if require_string(native_receipt, "schema_version") != "1.0":
        raise ValidationError("native receipt schema_version must be 1.0")
    payload = require_mapping(native_receipt.get("payload"), "native_receipt.payload")
    reject_unknown_keys(payload, NATIVE_PAYLOAD_FIELDS, "native_receipt.payload")
    if set(payload) != NATIVE_PAYLOAD_FIELDS:
        raise ValidationError("native receipt payload has a non-current shape")
    expected_native = _native_fields(value)
    for field, expected in expected_native.items():
        if payload.get(field) != expected:
            raise ValidationError(
                f"native receipt payload {field} does not match the adapter envelope"
            )
    native_outputs = _fingerprint_map(
        payload.get("output_fingerprints"), "native output_fingerprints"
    )
    expected_adapter_outputs = {
        **native_outputs,
        "native_receipt": native_receipt["fingerprint"],
    }
    if outputs != expected_adapter_outputs:
        raise ValidationError(
            "adapter outputs must contain the exact native outputs and native receipt fingerprint"
        )
    require_fingerprint(native_receipt, "fingerprint")
    if native_receipt["fingerprint"] != fingerprint_without(
        native_receipt, "fingerprint"
    ):
        raise ValidationError(
            "native_receipt fingerprint does not match its exact wrapper content"
        )
    _validate_domain_payload(
        owner=owner,
        semantic_owner_id=semantic_owner_id,
        native_route=native_route,
        evidence_domain=evidence_domain,
        artifact_fingerprint=artifact_fingerprint,
        inputs=inputs,
        outputs=native_outputs,
        evidence_payload=require_mapping(
            payload.get("evidence_payload"), "native evidence_payload"
        ),
    )
    if owner in {"documents", "pdf"} and status == "current_pass":
        if len(collections["artifact_refs"]) != 1:
            raise ValidationError(
                "passing document or PDF evidence must identify one exact artifact path"
            )
        artifact_path = Path(collections["artifact_refs"][0]).expanduser().resolve()
        if not artifact_path.is_file():
            raise ValidationError("document or PDF artifact path is not a file")
        if fingerprint_bytes(artifact_path.read_bytes()) != artifact_fingerprint:
            raise ValidationError(
                "document or PDF native result does not match the actual artifact bytes"
            )

    declared = require_fingerprint(value, "adapter_result_fingerprint")
    if declared != fingerprint_without(value, "adapter_result_fingerprint"):
        raise ValidationError(
            "adapter_result_fingerprint does not match the adapter envelope"
        )
    return validation_result(
        status="current_pass",
        native_owner=owner,
        native_status=status,
        semantic_owner_id=semantic_owner_id,
        adapter_result_fingerprint=declared,
        contributes_to_pass=status == "current_pass",
    )


def build_adapter_receipt(
    value: Mapping[str, Any],
    *,
    root: str | Path,
) -> dict[str, Any]:
    """Commit only after the provider-specific native payload passes validation."""

    validate_adapter_result(value)
    adapter_object_fingerprint = _store_content_object(dict(value), root=root)
    return _commit_managed_receipt(
        {
            "schema_version": "1.0",
            "producer_skill": value["native_owner"],
            "semantic_owner_id": value["semantic_owner_id"],
            "native_route": value["native_route"],
            "run_id": value["run_id"],
            "covered_obligation_ids": value["covered_obligation_ids"],
            "input_fingerprints": value["input_fingerprints"],
            "output_fingerprints": {
                **value["output_fingerprints"],
                "adapter_result_object": adapter_object_fingerprint,
            },
            "artifact_fingerprint": value["artifact_fingerprint"],
            "covered_scope": value["covered_scope"],
            "evidence_domain": value["evidence_domain"],
            "status": value["status"],
            "safe_claim": value["safe_claim"],
            "unsafe_claim_boundary": value["unsafe_claim_boundary"],
            "sequence_id": value["request_id"],
            "dependency_receipt_fingerprints": value[
                "dependency_receipt_fingerprints"
            ],
        },
        root=root,
        builder_id="logic-writing.adapter-result.v1",
        source_fingerprint=value["adapter_result_fingerprint"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--receipt-root")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        value = load_json(args.input)
        result = (
            build_adapter_receipt(value, root=args.receipt_root)
            if args.receipt_root
            else validate_adapter_result(value)
        )
        dump_json(result, args.output)
        status = result.get("status")
        return 0 if status in {"current_pass", None} else 1
    except (ValidationError, SchemaValidationError, OSError, json.JSONDecodeError) as exc:
        dump_json(validation_result(status="blocked", errors=(str(exc),)), args.output)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_adapter_receipt", "validate_adapter_result"]
