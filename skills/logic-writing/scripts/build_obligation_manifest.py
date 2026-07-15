"""Derive closure obligations only from current managed FlowGuard authority."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from _common import (
    EVIDENCE_DOMAINS,
    ValidationError,
    dump_json,
    fingerprint,
    fingerprint_without,
    load_json,
    require_fingerprint,
    require_list,
    require_mapping,
    require_schema,
    require_string,
    reject_unknown_keys,
    validation_result,
)
from receipt_authority import (
    _store_content_object,
    resolve_content_object,
    resolve_current_receipt,
)
from validate_adapter_result import validate_adapter_result


REQUEST_FIELDS = {"contract_receipt_fingerprint"}
OBLIGATION_FIELDS = {
    "obligation_id",
    "producer_skill",
    "semantic_owner_id",
    "native_route",
    "evidence_domain",
    "required_input_fingerprints",
    "required_output_fingerprints",
    "critical",
    "next_owner",
    "affected_scope",
    "safe_claim",
    "unsafe_claim_boundary",
    "action",
}


def _fingerprint_map(value: Any, label: str) -> dict[str, str]:
    mapping = require_mapping(value, label)
    if not mapping:
        raise ValidationError(f"{label} must contain at least one exact fingerprint")
    for key, item in mapping.items():
        if not isinstance(key, str) or not key.strip():
            raise ValidationError(f"{label} keys must be non-empty strings")
        require_fingerprint({key: item}, key)
    return dict(mapping)


def _validate_obligations(value: Any) -> list[dict[str, Any]]:
    rows = require_list(value, "obligations")
    if not rows:
        raise ValidationError("obligations must not be empty")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(rows):
        row = require_mapping(item, f"obligation {index}")
        reject_unknown_keys(row, OBLIGATION_FIELDS, f"obligation {index}")
        if set(row) != OBLIGATION_FIELDS:
            raise ValidationError(f"obligation {index} has a non-current shape")
        for field in OBLIGATION_FIELDS - {
            "critical",
            "required_input_fingerprints",
            "required_output_fingerprints",
        }:
            require_string(row, field)
        if not isinstance(row["critical"], bool):
            raise ValidationError("obligation critical must be boolean")
        if row["evidence_domain"] not in EVIDENCE_DOMAINS - {"final_closure"}:
            raise ValidationError("obligation uses an unsupported evidence domain")
        _fingerprint_map(
            row.get("required_input_fingerprints"),
            f"obligation {index} required_input_fingerprints",
        )
        _fingerprint_map(
            row.get("required_output_fingerprints"),
            f"obligation {index} required_output_fingerprints",
        )
        obligation_id = row["obligation_id"]
        if obligation_id in seen:
            raise ValidationError("obligation_id values must be unique")
        seen.add(obligation_id)
        normalized.append(dict(row))
    return normalized


def build_obligation_manifest(
    request: Mapping[str, Any],
    *,
    root: str | Path,
) -> dict[str, Any]:
    request = require_mapping(dict(request), "obligation manifest request")
    reject_unknown_keys(request, REQUEST_FIELDS, "obligation manifest request")
    if set(request) != REQUEST_FIELDS:
        raise ValidationError("obligation manifest request has a non-current shape")
    contract_fingerprint = require_fingerprint(
        request, "contract_receipt_fingerprint"
    )
    projection = resolve_current_receipt(
        contract_fingerprint,
        root=root,
        expected={
            "producer_skill": "flowguard",
            "native_route": "closure-obligation-contract",
            "evidence_domain": "process_model",
            "status": "current_pass",
        },
    )
    if not projection["current"] or projection["status"] != "current_pass":
        raise ValidationError(
            "FlowGuard obligation contract receipt is not current and passing"
        )
    receipt = projection["receipt"]
    if receipt["builder_provenance"]["builder_id"] != "logic-writing.adapter-result.v1":
        raise ValidationError(
            "obligation contract must enter through the managed FlowGuard adapter"
        )
    if "closure.obligation-contract" not in receipt["covered_obligation_ids"]:
        raise ValidationError(
            "FlowGuard receipt does not own the closure obligation contract"
        )
    adapter_object_fingerprint = receipt["output_fingerprints"].get(
        "adapter_result_object"
    )
    if not isinstance(adapter_object_fingerprint, str):
        raise ValidationError("contract receipt does not preserve its native adapter result")
    adapter_result = require_mapping(
        resolve_content_object(adapter_object_fingerprint, root=root),
        "contract adapter result",
    )
    validate_adapter_result(adapter_result)
    if adapter_result["adapter_result_fingerprint"] != receipt[
        "builder_provenance"
    ]["source_fingerprint"]:
        raise ValidationError("contract receipt and preserved adapter result disagree")
    evidence_payload = require_mapping(
        adapter_result["native_receipt"]["payload"]["evidence_payload"],
        "FlowGuard contract evidence payload",
    )
    obligations = _validate_obligations(evidence_payload.get("obligations"))
    route_decision = require_mapping(
        evidence_payload.get("route_decision"), "route_decision"
    )
    require_schema("route-decision.schema.json", route_decision, label="route decision")
    if route_decision["decision_fingerprint"] != fingerprint_without(
        route_decision, "decision_fingerprint"
    ):
        raise ValidationError("contract route decision fingerprint is invalid")
    final_owner = route_decision.get("final_owner")
    if final_owner not in {"investigation", "academic-writing"}:
        raise ValidationError("contract route decision has no active final owner")
    broad_claim_requested = evidence_payload.get("broad_claim_requested")
    if not isinstance(broad_claim_requested, bool):
        raise ValidationError("contract broad-claim class must be boolean")
    if receipt["output_fingerprints"].get("obligation_manifest") != fingerprint(
        obligations
    ):
        raise ValidationError(
            "obligations do not match the managed FlowGuard contract output"
        )
    if receipt["output_fingerprints"].get("closure_contract") != fingerprint(
        evidence_payload
    ):
        raise ValidationError(
            "FlowGuard contract output does not bind its route and claim class"
        )
    owner = require_string(receipt, "semantic_owner_id")
    manifest: dict[str, Any] = {
        "schema_version": "1.0",
        "manifest_id": f"obligation-manifest:{route_decision['decision_id']}",
        "contract_receipt_fingerprint": contract_fingerprint,
        "contract_semantic_owner_id": owner,
        "artifact_fingerprint": receipt["artifact_fingerprint"],
        "route_decision": route_decision,
        "final_owner": final_owner,
        "broad_claim_requested": broad_claim_requested,
        "obligations": obligations,
        "contract_projection_fingerprint": projection["projection_fingerprint"],
    }
    manifest["manifest_fingerprint"] = fingerprint_without(
        manifest, "manifest_fingerprint"
    )
    require_schema("obligation-manifest.schema.json", manifest, label="obligation manifest")
    object_fingerprint = _store_content_object(manifest, root=root)
    return validation_result(
        status="current_pass",
        manifest=manifest,
        manifest_object_fingerprint=object_fingerprint,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--receipt-root", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        result = build_obligation_manifest(load_json(args.input), root=args.receipt_root)
        dump_json(result, args.output)
        return 0
    except (ValidationError, OSError, json.JSONDecodeError) as exc:
        dump_json(validation_result(status="blocked", errors=(str(exc),)), args.output)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_obligation_manifest"]
