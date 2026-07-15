"""Validate source identity, access, lineage, role, and support boundaries."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from _common import (
    ValidationError,
    contains_internal_language,
    dump_json,
    fingerprint,
    load_json,
    require_list,
    require_mapping,
    require_schema,
    require_string,
    require_string_list,
    require_unique,
    reject_unknown_keys,
    validation_result,
)
from receipt_authority import resolve_current_receipt


ROLES = {
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
OBSERVATION = {"candidate", "observed", "claim_usable", "rejected", "access_gap"}
ACCESS = {"available", "permission_gated", "unavailable", "not_attempted"}
INDEPENDENCE = {"independent", "same_lineage", "unknown", "not_applicable"}
DATE = re.compile(r"^\d{4}(?:-\d{2}(?:-\d{2})?)?$")
REGISTRY_FIELDS = {"schema_version", "registry_id", "sources"}
SOURCE_FIELDS = {
    "source_id",
    "locator",
    "citation_label",
    "source_date",
    "coverage_period",
    "role",
    "lineage_id",
    "independence",
    "observation_status",
    "access_status",
    "observed_content_fingerprint",
    "observation_receipt_fingerprint",
    "anchors",
    "can_support",
    "cannot_support",
}


def _observation_basis(source):
    return {
        key: item
        for key, item in source.items()
        if key != "observation_receipt_fingerprint"
    }


def _validate_source(source):
    source = require_mapping(source, "source")
    reject_unknown_keys(source, SOURCE_FIELDS, "source")
    missing = sorted(SOURCE_FIELDS - set(source))
    if missing:
        raise ValidationError(f"source is missing required fields: {', '.join(missing)}")
    source_id = require_string(source, "source_id")
    require_string(source, "locator")
    citation_label = require_string(source, "citation_label")
    if contains_internal_language(citation_label):
        raise ValidationError(f"source {source_id}: citation_label contains internal workflow language")
    role = require_string(source, "role")
    if role not in ROLES:
        raise ValidationError(f"source {source_id}: unsupported role {role}")
    observation = require_string(source, "observation_status")
    access = require_string(source, "access_status")
    independence = require_string(source, "independence")
    if observation not in OBSERVATION or access not in ACCESS or independence not in INDEPENDENCE:
        raise ValidationError(f"source {source_id}: invalid observation/access/independence state")
    require_string(source, "lineage_id")
    observed_fingerprint = source.get("observed_content_fingerprint")
    observation_receipt = source.get("observation_receipt_fingerprint")
    for label, value in (
        ("observed_content_fingerprint", observed_fingerprint),
        ("observation_receipt_fingerprint", observation_receipt),
    ):
        if value is not None and (not isinstance(value, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", value)):
            raise ValidationError(f"source {source_id}: {label} must be null or a lowercase sha256 fingerprint")
    anchors = require_list(source.get("anchors"), "anchors")
    anchor_ids = []
    for anchor in anchors:
        anchor = require_mapping(anchor, "source anchor")
        reject_unknown_keys(anchor, {"anchor_id", "locator", "observed_summary"}, "source anchor")
        if set(anchor) != {"anchor_id", "locator", "observed_summary"}:
            raise ValidationError(f"source {source_id}: every anchor requires anchor_id, locator, and observed_summary")
        anchor_ids.append(require_string(anchor, "anchor_id"))
        require_string(anchor, "locator")
        observed_summary = require_string(anchor, "observed_summary")
        if contains_internal_language(observed_summary):
            raise ValidationError(
                f"source {source_id}: anchor observed_summary contains internal workflow language"
            )
    require_unique(anchor_ids, f"source {source_id} anchor ids")
    can_support = require_string_list(source.get("can_support"), "can_support")
    cannot_support = require_string_list(
        source.get("cannot_support"), "cannot_support", nonempty=True
    )
    for label, entries in (("can_support", can_support), ("cannot_support", cannot_support)):
        if any(contains_internal_language(item) for item in entries):
            raise ValidationError(
                f"source {source_id}: {label} contains internal workflow language"
            )
    for field in ("source_date",):
        value = source.get(field)
        if value is not None and (not isinstance(value, str) or not DATE.match(value)):
            raise ValidationError(f"source {source_id}: {field} must be YYYY, YYYY-MM, or YYYY-MM-DD")
    coverage = source.get("coverage_period")
    if coverage is not None:
        coverage = require_mapping(coverage, "coverage_period")
        reject_unknown_keys(coverage, {"start", "end", "description"}, "coverage_period")
        if set(coverage) != {"start", "end", "description"}:
            raise ValidationError("coverage_period requires start, end, and description")
        for edge in ("start", "end"):
            value = coverage.get(edge)
            if value is not None and (not isinstance(value, str) or not DATE.match(value)):
                raise ValidationError(f"source {source_id}: coverage_period.{edge} has invalid date")
        require_string(coverage, "description")
    if observation == "claim_usable" and (
        access != "available"
        or not can_support
        or observed_fingerprint is None
        or observation_receipt is None
        or not anchors
    ):
        raise ValidationError(
            f"source {source_id}: claim_usable requires available observed content, anchors, and a SourceGuard observation receipt"
        )
    if observation != "claim_usable" and can_support:
        raise ValidationError(f"source {source_id}: only a claim_usable record can support claims")
    if access in {"permission_gated", "unavailable", "not_attempted"} and can_support:
        raise ValidationError(f"source {source_id}: inaccessible content cannot be claim-usable")
    return source


def validate_source_registry(
    value,
    *,
    receipt_root: str | Path | None = None,
):
    value = require_mapping(value, "SourceRegistry")
    require_schema("source-registry.schema.json", value, label="SourceRegistry")
    reject_unknown_keys(value, REGISTRY_FIELDS, "SourceRegistry")
    if require_string(value, "schema_version") != "1.0":
        raise ValidationError("schema_version must be 1.0")
    require_string(value, "registry_id")
    sources = [_validate_source(item) for item in require_list(value.get("sources"), "sources")]
    ids = require_unique((item["source_id"] for item in sources), "source ids")
    lineages: dict[str, list[str]] = {}
    for item in sources:
        lineages.setdefault(item["lineage_id"], []).append(item["source_id"])
    invalid_same_lineage = [
        item["source_id"]
        for item in sources
        if item["independence"] == "same_lineage" and len(lineages[item["lineage_id"]]) < 2
    ]
    if invalid_same_lineage:
        raise ValidationError(
            "same_lineage sources must share one lineage_id with another source: "
            + ", ".join(invalid_same_lineage)
        )
    structurally_usable = {
        item["source_id"]
        for item in sources
        if item["observation_status"] == "claim_usable"
        and item["access_status"] == "available"
    }
    findings: list[dict[str, str]] = [
        {"source_id": item["source_id"], "code": "source_not_claim_usable"}
        for item in sources
        if item["source_id"] not in structurally_usable
    ]
    if not sources:
        findings.append({"source_id": "registry", "code": "registry_has_no_sources"})
    observation_receipts: list[str] = []
    observation_basis_fingerprints: dict[str, str] = {}
    authoritative_usable: list[str] = []
    for source in sources:
        if source["observation_status"] != "claim_usable":
            continue
        source_id = source["source_id"]
        reference = source["observation_receipt_fingerprint"]
        basis_fingerprint = fingerprint(_observation_basis(source))
        observation_basis_fingerprints[source_id] = basis_fingerprint
        if receipt_root is None:
            findings.append(
                {"source_id": source_id, "code": "observation_authority_not_resolved"}
            )
            continue
        projection = resolve_current_receipt(
            reference,
            root=receipt_root,
            expected={
                "producer_skill": "sourceguard",
                "evidence_domain": "source_observation",
                "artifact_fingerprint": source["observed_content_fingerprint"],
            },
        )
        receipt = projection["receipt"]
        if receipt["output_fingerprints"].get("source_observation") != basis_fingerprint:
            raise ValidationError(
                f"source {source_id}: observation receipt does not bind the exact source record and support boundary"
            )
        if not projection["current"] or projection["status"] != "current_pass":
            findings.append(
                {"source_id": source_id, "code": "observation_receipt_not_current"}
            )
        else:
            observation_receipts.append(reference)
            authoritative_usable.append(source_id)
    findings = list(
        {
            (item["source_id"], item["code"]): item
            for item in findings
        }.values()
    )
    gap_source_ids = list(
        dict.fromkeys(
            item["source_id"]
            for item in findings
            if item["source_id"] != "registry"
        )
    )
    return validation_result(
        status="current_pass" if authoritative_usable and not findings else "partial",
        registry_id=value["registry_id"],
        registry_fingerprint=fingerprint(value),
        source_ids=list(ids),
        usable_source_ids=authoritative_usable,
        gap_source_ids=gap_source_ids,
        findings=findings,
        independent_lineage_count=len(
            {
                item["lineage_id"]
                for item in sources
                if item["independence"] == "independent"
                and item["source_id"] in authoritative_usable
            }
        ),
        lineage_members=lineages,
        observation_receipt_fingerprints=observation_receipts,
        observation_basis_fingerprints=observation_basis_fingerprints,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--receipt-root")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        result = validate_source_registry(
            load_json(args.input),
            receipt_root=args.receipt_root,
        )
        dump_json(result, args.output)
        raise SystemExit(0 if result["status"] == "current_pass" else 1)
    except (ValidationError, OSError, json.JSONDecodeError) as exc:
        dump_json(validation_result(status="blocked", errors=(str(exc),)), args.output)
        raise SystemExit(1)
