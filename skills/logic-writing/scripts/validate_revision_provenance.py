"""Build authoritative revision provenance from an exact source-unit universe."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from _common import (
    ValidationError,
    dump_json,
    fingerprint,
    fingerprint_without,
    load_json,
    require_list,
    require_mapping,
    require_schema,
    require_string,
    require_unique,
    reject_unknown_keys,
    validation_result,
)
from build_source_unit_manifest import fingerprint_bytes, validate_source_unit_manifest
from receipt_authority import (
    _commit_managed_receipt,
    _store_content_object,
    resolve_content_object,
    resolve_current_receipt,
)


TREATMENTS = {
    "added",
    "rewritten",
    "moved",
    "omitted",
    "unresolved",
    "preserved",
    "source_gap",
    "trace_gap",
    "human_review",
}
INCOMPLETE_TREATMENTS = {"unresolved", "source_gap", "trace_gap", "human_review"}
REVISION_POLICIES = {"tracked_changes", "comments", "marked_changes", "clean_rewrite"}
NEXT_OWNERS = {
    "academic-writing",
    "investigation",
    "sourceguard",
    "logicguard",
    "traceguard",
    "documents",
    "pdf",
    "human_review",
    "user",
}
REQUEST_FIELDS = {
    "schema_version",
    "revision_id",
    "revision_policy",
    "source_unit_manifest_receipt_fingerprint",
    "entries",
}
PROVENANCE_FIELDS = {
    "schema_version",
    "revision_id",
    "source_artifact_fingerprint",
    "target_artifact_fingerprint",
    "source_unit_manifest_fingerprint",
    "source_unit_manifest_receipt_fingerprint",
    "revision_policy",
    "entries",
    "provenance_fingerprint",
}
ENTRY_FIELDS = {
    "source_unit_id",
    "target_unit_id",
    "source_locator",
    "target_locator",
    "treatment",
    "reason",
    "evidence_receipt_fingerprints",
    "next_owner",
}


def _nullable_string(entry: Mapping[str, Any], field: str) -> str | None:
    value = entry.get(field)
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ValidationError(f"{field} must be null or a non-empty string")
    return value


def _sha256(mapping: Mapping[str, Any], field: str) -> str:
    value = require_string(mapping, field)
    if not value.startswith("sha256:") or len(value) != 71:
        raise ValidationError(f"{field} must be a sha256 fingerprint")
    return value


def _validate_entries(
    entries: list[Any],
    *,
    source_units_by_id: Mapping[str, Mapping[str, Any]],
    target_units_by_id: Mapping[str, Mapping[str, Any]],
) -> tuple[list[str], list[str], list[str], list[str]]:
    source_units: list[str] = []
    target_units: list[str] = []
    incomplete: list[str] = []
    evidence_refs: list[str] = []
    for index, item in enumerate(entries):
        entry = require_mapping(item, f"revision entry {index}")
        reject_unknown_keys(entry, ENTRY_FIELDS, f"revision entry {index}")
        if set(entry) != ENTRY_FIELDS:
            raise ValidationError(f"revision entry {index} is missing required fields")
        source_unit = _nullable_string(entry, "source_unit_id")
        target_unit = _nullable_string(entry, "target_unit_id")
        source_locator = _nullable_string(entry, "source_locator")
        target_locator = _nullable_string(entry, "target_locator")
        require_string(entry, "reason")
        refs = require_list(
            entry.get("evidence_receipt_fingerprints"),
            "evidence_receipt_fingerprints",
        )
        if not refs:
            raise ValidationError(
                "every provenance treatment requires authoritative evidence receipts"
            )
        for ref in refs:
            if not isinstance(ref, str) or not ref.startswith("sha256:") or len(ref) != 71:
                raise ValidationError(
                    "evidence_receipt_fingerprints must contain receipt fingerprints only"
                )
        if len(refs) != len(set(refs)):
            raise ValidationError(
                "evidence_receipt_fingerprints contains duplicate values"
            )
        evidence_refs.extend(refs)
        next_owner = _nullable_string(entry, "next_owner")
        if next_owner is not None and next_owner not in NEXT_OWNERS:
            raise ValidationError(f"unsupported revision next_owner: {next_owner}")
        treatment = require_string(entry, "treatment")
        if treatment not in TREATMENTS:
            raise ValidationError(f"unsupported revision treatment: {treatment}")
        if treatment == "added":
            if source_unit is not None or source_locator is not None:
                raise ValidationError("added entries must use null source identity")
            if target_unit is None or target_locator is None:
                raise ValidationError("added entries require target identity")
        elif treatment in {"rewritten", "moved", "preserved"}:
            if None in {source_unit, target_unit, source_locator, target_locator}:
                raise ValidationError(f"{treatment} entries require source and target identities")
        elif treatment == "omitted":
            if source_unit is None or source_locator is None:
                raise ValidationError("omitted entries require source identity")
            if target_unit is not None or target_locator is not None or next_owner is not None:
                raise ValidationError("omitted entries cannot name a target or next owner")
        else:
            if source_unit is None or source_locator is None or next_owner is None:
                raise ValidationError(f"{treatment} entries require source identity and next_owner")
            incomplete.append(source_unit)
        if source_unit is not None:
            expected_source = source_units_by_id.get(source_unit)
            if expected_source is None or expected_source["locator"] != source_locator:
                raise ValidationError(f"source unit/locator is outside the current manifest: {source_unit}")
            source_units.append(source_unit)
        if target_unit is not None:
            expected_target = target_units_by_id.get(target_unit)
            if expected_target is None or expected_target["locator"] != target_locator:
                raise ValidationError(f"target unit/locator is outside the current manifest: {target_unit}")
            target_units.append(target_unit)
    require_unique(source_units, "source_unit_id")
    if set(source_units) != set(source_units_by_id):
        missing = sorted(set(source_units_by_id) - set(source_units))
        extra = sorted(set(source_units) - set(source_units_by_id))
        raise ValidationError(f"provenance source-unit universe mismatch: missing={missing}, extra={extra}")
    if set(target_units) != set(target_units_by_id):
        missing = sorted(set(target_units_by_id) - set(target_units))
        extra = sorted(set(target_units) - set(target_units_by_id))
        raise ValidationError(f"provenance target-unit universe mismatch: missing={missing}, extra={extra}")
    return source_units, target_units, incomplete, list(dict.fromkeys(evidence_refs))


def validate_revision_provenance(
    value: Any,
    *,
    source_unit_manifest: Mapping[str, Any],
    source_path: str | Path,
    target_path: str | Path,
    receipt_root: str | Path,
) -> dict[str, Any]:
    provenance = require_mapping(value, "revision provenance")
    if set(provenance) != PROVENANCE_FIELDS:
        raise ValidationError("revision provenance has a non-current shape")
    require_schema("revision-provenance.schema.json", provenance, label="revision provenance")
    manifest = validate_source_unit_manifest(
        source_unit_manifest,
        source_path=source_path,
        target_path=target_path,
    )
    if provenance["source_artifact_fingerprint"] != manifest["source"]["artifact_fingerprint"]:
        raise ValidationError("provenance source fingerprint does not match real source bytes")
    if provenance["target_artifact_fingerprint"] != manifest["target"]["artifact_fingerprint"]:
        raise ValidationError("provenance target fingerprint does not match real target bytes")
    if provenance["source_unit_manifest_fingerprint"] != manifest["manifest_fingerprint"]:
        raise ValidationError("provenance does not bind the current source-unit manifest")
    manifest_receipt_fingerprint = _sha256(
        provenance, "source_unit_manifest_receipt_fingerprint"
    )
    manifest_projection = resolve_current_receipt(
        manifest_receipt_fingerprint,
        root=receipt_root,
        expected={
            "producer_skill": "logic-writing",
            "semantic_owner_id": f"source-unit-manifest:{manifest['manifest_id']}",
            "native_route": "build-source-unit-manifest",
            "evidence_domain": "revision_provenance",
            "status": "current_pass",
            "artifact_fingerprint": manifest["target"]["artifact_fingerprint"],
        },
    )
    if not manifest_projection["current"] or manifest_projection["status"] != "current_pass":
        raise ValidationError("source-unit manifest receipt is not current and passing")
    manifest_receipt = manifest_projection["receipt"]
    if manifest_receipt["builder_provenance"]["builder_id"] != "logic-writing.source-unit-manifest.v1":
        raise ValidationError("source-unit manifest did not come from its dedicated builder")
    if manifest_receipt["output_fingerprints"].get("source_unit_manifest") != manifest[
        "manifest_fingerprint"
    ]:
        raise ValidationError("source-unit manifest receipt does not bind this manifest")
    object_fingerprint = manifest_receipt["output_fingerprints"].get(
        "source_unit_manifest_object"
    )
    if not isinstance(object_fingerprint, str):
        raise ValidationError("source-unit manifest receipt does not preserve the full object")
    if resolve_content_object(object_fingerprint, root=receipt_root) != manifest:
        raise ValidationError("preserved source-unit manifest differs from the supplied manifest")
    if provenance["provenance_fingerprint"] != fingerprint_without(
        provenance, "provenance_fingerprint"
    ):
        raise ValidationError("provenance_fingerprint does not match exact provenance content")
    if require_string(provenance, "schema_version") != "1.0":
        raise ValidationError("schema_version must be 1.0")
    require_string(provenance, "revision_id")
    if require_string(provenance, "revision_policy") not in REVISION_POLICIES:
        raise ValidationError("unsupported revision policy")
    entries = require_list(provenance.get("entries"), "entries")
    if not entries:
        raise ValidationError("entries must contain at least one revision treatment")
    source_by_id = {item["unit_id"]: item for item in manifest["source"]["units"]}
    target_by_id = {item["unit_id"]: item for item in manifest["target"]["units"]}
    source_units, target_units, incomplete, evidence_refs = _validate_entries(
        entries,
        source_units_by_id=source_by_id,
        target_units_by_id=target_by_id,
    )
    nonpassing_evidence: list[str] = []
    projections: dict[str, dict[str, Any]] = {}
    for receipt_fingerprint in evidence_refs:
        projection = resolve_current_receipt(receipt_fingerprint, root=receipt_root)
        if not projection["current"]:
            raise ValidationError(
                f"provenance evidence receipt is not current: {receipt_fingerprint}"
            )
        projections[receipt_fingerprint] = projection
        if projection["status"] != "current_pass":
            nonpassing_evidence.append(receipt_fingerprint)
    source_by_id = {item["unit_id"]: item for item in manifest["source"]["units"]}
    target_by_id = {item["unit_id"]: item for item in manifest["target"]["units"]}
    revision_id = provenance["revision_id"]
    for entry in entries:
        treatment = entry["treatment"]
        source_unit_id = entry["source_unit_id"]
        target_unit_id = entry["target_unit_id"]
        if treatment == "added":
            expected_obligation = f"revision:{revision_id}:added:{target_unit_id}"
        elif treatment == "omitted":
            expected_obligation = f"revision:{revision_id}:omit:{source_unit_id}"
        else:
            expected_obligation = f"revision:{revision_id}:{source_unit_id}"
        matched = []
        for receipt_fingerprint in entry["evidence_receipt_fingerprints"]:
            projection = projections[receipt_fingerprint]
            receipt = projection["receipt"]
            if expected_obligation not in receipt["covered_obligation_ids"]:
                continue
            unit_fingerprints = {
                source_by_id[source_unit_id]["content_fingerprint"]
                if source_unit_id is not None
                else None,
                target_by_id[target_unit_id]["content_fingerprint"]
                if target_unit_id is not None
                else None,
            }
            unit_fingerprints.discard(None)
            if not (
                receipt["artifact_fingerprint"]
                in {
                    manifest["source"]["artifact_fingerprint"],
                    manifest["target"]["artifact_fingerprint"],
                    *unit_fingerprints,
                }
                or unit_fingerprints.intersection(receipt["input_fingerprints"].values())
            ):
                continue
            matched.append(receipt)
        if not matched:
            raise ValidationError(
                f"revision entry lacks evidence bound to {expected_obligation} and its exact artifact unit"
            )
        if treatment == "omitted" and not any(
            receipt["evidence_domain"]
            in {"argument_model", "structured_artifact", "process_model"}
            for receipt in matched
        ):
            raise ValidationError(
                "omission requires a current policy or argument decision receipt"
            )
        if treatment == "source_gap" and not any(
            receipt["producer_skill"] == "sourceguard" for receipt in matched
        ):
            raise ValidationError("source_gap treatment requires SourceGuard evidence")
        if treatment == "trace_gap" and not any(
            receipt["producer_skill"] == "traceguard" for receipt in matched
        ):
            raise ValidationError("trace_gap treatment requires TraceGuard evidence")
    status = "current_pass" if not incomplete and not nonpassing_evidence else "partial"
    return validation_result(
        status=status,
        revision_id=provenance["revision_id"],
        provenance_fingerprint=provenance["provenance_fingerprint"],
        source_unit_manifest_fingerprint=manifest["manifest_fingerprint"],
        accounted_source_units=source_units,
        accounted_target_units=target_units,
        incomplete_source_units=incomplete,
        evidence_receipt_fingerprints=evidence_refs,
        nonpassing_evidence_receipt_fingerprints=nonpassing_evidence,
    )


def build_revision_provenance_receipt(
    request: Mapping[str, Any],
    *,
    source_unit_manifest: Mapping[str, Any],
    source_path: str | Path,
    target_path: str | Path,
    receipt_root: str | Path,
    run_id: str,
) -> dict[str, Any]:
    request = require_mapping(request, "revision provenance build request")
    reject_unknown_keys(request, REQUEST_FIELDS, "revision provenance build request")
    if set(request) != REQUEST_FIELDS:
        raise ValidationError("revision provenance build request has a non-current shape")
    manifest = validate_source_unit_manifest(
        source_unit_manifest,
        source_path=source_path,
        target_path=target_path,
    )
    provenance: dict[str, Any] = {
        "schema_version": require_string(request, "schema_version"),
        "revision_id": require_string(request, "revision_id"),
        "source_artifact_fingerprint": manifest["source"]["artifact_fingerprint"],
        "target_artifact_fingerprint": manifest["target"]["artifact_fingerprint"],
        "source_unit_manifest_fingerprint": manifest["manifest_fingerprint"],
        "source_unit_manifest_receipt_fingerprint": require_string(
            request, "source_unit_manifest_receipt_fingerprint"
        ),
        "revision_policy": require_string(request, "revision_policy"),
        "entries": require_list(request.get("entries"), "entries"),
    }
    provenance["provenance_fingerprint"] = fingerprint_without(
        provenance, "provenance_fingerprint"
    )
    report = validate_revision_provenance(
        provenance,
        source_unit_manifest=manifest,
        source_path=source_path,
        target_path=target_path,
        receipt_root=receipt_root,
    )
    source_code_fingerprint = fingerprint_bytes(Path(__file__).read_bytes())
    provenance_object_fingerprint = _store_content_object(
        provenance, root=receipt_root
    )
    receipt = _commit_managed_receipt(
        {
            "schema_version": "1.0",
            "producer_skill": "logic-writing",
            "semantic_owner_id": f"revision:{provenance['revision_id']}",
            "native_route": "validate-revision-provenance",
            "run_id": require_string({"run_id": run_id}, "run_id"),
            "covered_obligation_ids": ["revision.provenance.complete"],
            "input_fingerprints": {
                f"revision:{provenance['revision_id']}:source": manifest["source"]["artifact_fingerprint"],
                f"revision:{provenance['revision_id']}:target": manifest["target"]["artifact_fingerprint"],
                f"revision:{provenance['revision_id']}:manifest": manifest["manifest_fingerprint"],
                f"revision:{provenance['revision_id']}:manifest-receipt": provenance["source_unit_manifest_receipt_fingerprint"],
                f"revision:{provenance['revision_id']}:validator": source_code_fingerprint,
            },
            "output_fingerprints": {
                "revision_provenance": provenance["provenance_fingerprint"],
                "source_unit_manifest": manifest["manifest_fingerprint"],
                "revision_provenance_object": provenance_object_fingerprint,
            },
            "artifact_fingerprint": manifest["target"]["artifact_fingerprint"],
            "covered_scope": "every visible source and target unit in the exact artifact bytes",
            "evidence_domain": "revision_provenance",
            "status": report["status"],
            "safe_claim": "Revision treatments are complete for the exact manifest; unresolved rows remain explicit.",
            "unsafe_claim_boundary": "This provenance receipt does not prove reader quality, citation fit, or document rendering.",
            "sequence_id": run_id,
            "dependency_receipt_fingerprints": list(
                dict.fromkeys(
                    [
                        provenance["source_unit_manifest_receipt_fingerprint"],
                        *report["evidence_receipt_fingerprints"],
                    ]
                )
            ),
        },
        root=receipt_root,
        builder_id="logic-writing.revision-provenance.v1",
        source_fingerprint=fingerprint(
            {
                "provenance": provenance["provenance_fingerprint"],
                "validator_source": source_code_fingerprint,
            }
        ),
    )
    return validation_result(
        status=report["status"],
        provenance=provenance,
        validation=report,
        receipt=receipt,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--receipt-root", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        result = build_revision_provenance_receipt(
            load_json(args.input),
            source_unit_manifest=load_json(args.manifest),
            source_path=args.source,
            target_path=args.target,
            receipt_root=args.receipt_root,
            run_id=args.run_id,
        )
        dump_json(result, args.output)
        return 0 if result["status"] == "current_pass" else 1
    except (ValidationError, OSError, json.JSONDecodeError) as exc:
        dump_json(validation_result(status="blocked", errors=(str(exc),)), args.output)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_revision_provenance_receipt", "validate_revision_provenance"]
