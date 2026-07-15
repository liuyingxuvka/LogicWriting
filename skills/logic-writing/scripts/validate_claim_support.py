"""Validate claim/source semantics and exact LogicGuard receipt authority."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from _common import (
    ValidationError,
    contains_internal_language,
    dump_json,
    fingerprint,
    load_json,
    require_fingerprint,
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
from validate_source_registry import ROLES, validate_source_registry


CLAIM_TYPES = {
    "fact",
    "number",
    "interpretation",
    "causal",
    "execution",
    "outcome",
    "forecast",
}
STRENGTHS = {"tentative", "qualified", "supported", "strong"}
READER_JOBS = {
    "background",
    "evidence",
    "interpretation",
    "comparison",
    "conclusion",
    "forecast",
}
DISPOSITIONS = {"principal", "alternative", "limitation", "excluded"}
RELATIONS = {"support", "limit", "counter", "context"}
TREATMENTS = {"live", "qualified", "rejected", "unsupported"}
LEDGER_FIELDS = {"schema_version", "ledger_id", "source_registry_fingerprint", "claims"}
CLAIM_FIELDS = {
    "claim_id",
    "text",
    "claim_type",
    "critical",
    "strength",
    "reader_order",
    "reader_job",
    "reader_disposition",
    "depends_on_claim_ids",
    "source_ids",
    "source_roles",
    "support_links",
    "can_support",
    "cannot_support",
    "alternatives",
    "safe_wording",
    "unsafe_wording",
    "semantic_fit_receipt_fingerprint",
    "requires_independent_support",
    "mechanism_source_ids",
    "forecast_validation_source_ids",
}


def _semantic_basis(claim: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in claim.items()
        if key != "semantic_fit_receipt_fingerprint"
    }


def _reader_text(text: str, label: str) -> str:
    if contains_internal_language(text):
        raise ValidationError(f"{label} contains internal workflow language")
    return text


def _finding(findings: list[dict[str, str]], claim_id: str, code: str) -> None:
    item = {"claim_id": claim_id, "code": code}
    if item not in findings:
        findings.append(item)


def _validate_support_links(
    claim: Mapping[str, Any],
    *,
    source_by_id: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], set[str]]:
    claim_id = claim["claim_id"]
    source_ids = set(claim["source_ids"])
    links: list[dict[str, Any]] = []
    linked_sources: set[str] = set()
    for raw in require_list(claim.get("support_links"), "support_links"):
        link = require_mapping(raw, f"claim {claim_id} support link")
        reject_unknown_keys(
            link,
            {"source_id", "anchor_ids", "relation"},
            f"claim {claim_id} support link",
        )
        if set(link) != {"source_id", "anchor_ids", "relation"}:
            raise ValidationError(f"claim {claim_id}: support link shape is incomplete")
        source_id = require_string(link, "source_id")
        if source_id not in source_ids:
            raise ValidationError(
                f"claim {claim_id}: support link references an undeclared source"
            )
        relation = require_string(link, "relation")
        if relation not in RELATIONS:
            raise ValidationError(f"claim {claim_id}: unsupported support-link relation")
        anchor_ids = require_string_list(link.get("anchor_ids"), "anchor_ids", nonempty=True)
        available_anchors = {
            item["anchor_id"] for item in source_by_id[source_id]["anchors"]
        }
        unknown = sorted(set(anchor_ids) - available_anchors)
        if unknown:
            raise ValidationError(
                f"claim {claim_id}: support link contains anchors not observed for {source_id}"
            )
        links.append(dict(link))
        linked_sources.add(source_id)
    if linked_sources != source_ids:
        raise ValidationError(
            f"claim {claim_id}: every declared source must have an explicit support link"
        )
    return links, linked_sources


def _validate_alternatives(
    claim: Mapping[str, Any],
    *,
    source_by_id: Mapping[str, Mapping[str, Any]],
    authoritative_source_ids: set[str],
) -> None:
    claim_id = claim["claim_id"]
    declared_sources = set(claim["source_ids"])
    alternatives = require_list(claim.get("alternatives"), "alternatives")
    alternative_ids: list[str] = []
    for raw in alternatives:
        alternative = require_mapping(raw, f"claim {claim_id} alternative")
        reject_unknown_keys(
            alternative,
            {"alternative_id", "text", "treatment", "source_ids", "anchor_ids"},
            f"claim {claim_id} alternative",
        )
        if set(alternative) != {
            "alternative_id",
            "text",
            "treatment",
            "source_ids",
            "anchor_ids",
        }:
            raise ValidationError(f"claim {claim_id}: alternative shape is incomplete")
        alternative_ids.append(require_string(alternative, "alternative_id"))
        _reader_text(require_string(alternative, "text"), f"claim {claim_id} alternative")
        treatment = require_string(alternative, "treatment")
        if treatment not in TREATMENTS:
            raise ValidationError(f"claim {claim_id}: unsupported alternative treatment")
        source_ids = require_string_list(alternative.get("source_ids"), "source_ids")
        anchor_ids = require_string_list(alternative.get("anchor_ids"), "anchor_ids")
        if not set(source_ids).issubset(declared_sources):
            raise ValidationError(
                f"claim {claim_id}: alternative uses a source outside the claim"
            )
        observed_anchors = {
            anchor["anchor_id"]
            for source_id in source_ids
            for anchor in source_by_id[source_id]["anchors"]
        }
        if not set(anchor_ids).issubset(observed_anchors):
            raise ValidationError(
                f"claim {claim_id}: alternative uses an anchor outside its sources"
            )
        if treatment in {"qualified", "rejected"}:
            if not source_ids or not anchor_ids:
                raise ValidationError(
                    f"claim {claim_id}: qualified or rejected alternative needs anchored evidence"
                )
            if not set(source_ids).issubset(authoritative_source_ids):
                raise ValidationError(
                    f"claim {claim_id}: qualified or rejected alternative uses non-current evidence"
                )
        if treatment == "unsupported" and (source_ids or anchor_ids):
            raise ValidationError(
                f"claim {claim_id}: unsupported alternative cannot claim evidence anchors"
            )
    require_unique(alternative_ids, f"claim {claim_id} alternative ids")


def validate_claim_support(
    value: Mapping[str, Any],
    source_registry: Mapping[str, Any] | None = None,
    *,
    receipt_root: str | Path | None = None,
) -> dict[str, Any]:
    value = require_mapping(dict(value), "ClaimSupport ledger")
    require_schema("claim-support.schema.json", value, label="ClaimSupport ledger")
    reject_unknown_keys(value, LEDGER_FIELDS, "ClaimSupport ledger")
    if require_string(value, "schema_version") != "1.0":
        raise ValidationError("schema_version must be 1.0")
    require_string(value, "ledger_id")
    registry = require_mapping(source_registry, "source_registry")
    declared_registry_fingerprint = require_fingerprint(
        value, "source_registry_fingerprint"
    )
    actual_registry_fingerprint = fingerprint(registry)
    if declared_registry_fingerprint != actual_registry_fingerprint:
        raise ValidationError(
            "source_registry_fingerprint does not match the supplied SourceRegistry"
        )
    registry_report = validate_source_registry(registry, receipt_root=receipt_root)
    source_by_id = {source["source_id"]: source for source in registry["sources"]}
    authoritative_source_ids = set(registry_report["usable_source_ids"])

    claims = [require_mapping(item, "claim") for item in require_list(value.get("claims"), "claims")]
    claim_ids = list(
        require_unique((require_string(item, "claim_id") for item in claims), "claim ids")
    )
    claim_id_set = set(claim_ids)
    findings: list[dict[str, str]] = []
    semantic_receipts: list[str] = []
    semantic_basis_fingerprints: dict[str, str] = {}
    order_by_claim: dict[str, int] = {}

    if not claims:
        _finding(findings, "ledger", "ledger_has_no_claims")

    for claim in claims:
        claim_id = claim["claim_id"]
        reject_unknown_keys(claim, CLAIM_FIELDS, f"claim {claim_id}")
        if set(claim) != CLAIM_FIELDS:
            missing = sorted(CLAIM_FIELDS - set(claim))
            raise ValidationError(
                f"claim {claim_id} is missing required fields: {', '.join(missing)}"
            )
        require_string(claim, "text")
        claim_type = require_string(claim, "claim_type")
        strength = require_string(claim, "strength")
        if claim_type not in CLAIM_TYPES or strength not in STRENGTHS:
            raise ValidationError(f"claim {claim_id}: invalid type or strength")
        if not isinstance(claim.get("critical"), bool):
            raise ValidationError(f"claim {claim_id}: critical must be boolean")
        if not isinstance(claim.get("requires_independent_support"), bool):
            raise ValidationError(
                f"claim {claim_id}: requires_independent_support must be boolean"
            )
        reader_order = claim.get("reader_order")
        if not isinstance(reader_order, int) or isinstance(reader_order, bool) or reader_order < 1:
            raise ValidationError(f"claim {claim_id}: reader_order must be a positive integer")
        order_by_claim[claim_id] = reader_order
        if require_string(claim, "reader_job") not in READER_JOBS:
            raise ValidationError(f"claim {claim_id}: invalid reader_job")
        disposition = require_string(claim, "reader_disposition")
        if disposition not in DISPOSITIONS:
            raise ValidationError(f"claim {claim_id}: invalid reader_disposition")

        dependencies = require_string_list(
            claim.get("depends_on_claim_ids"), "depends_on_claim_ids"
        )
        if claim_id in dependencies:
            raise ValidationError(f"claim {claim_id}: a claim cannot depend on itself")
        unknown_dependencies = sorted(set(dependencies) - claim_id_set)
        if unknown_dependencies:
            raise ValidationError(f"claim {claim_id}: unknown claim dependencies")

        source_ids = require_string_list(claim.get("source_ids"), "source_ids")
        unknown_sources = sorted(set(source_ids) - set(source_by_id))
        if unknown_sources:
            raise ValidationError(f"claim {claim_id}: unknown source ids")
        source_roles = require_string_list(claim.get("source_roles"), "source_roles")
        if not set(source_roles).issubset(ROLES):
            raise ValidationError(f"claim {claim_id}: unsupported source role")
        actual_roles = {source_by_id[item]["role"] for item in source_ids}
        if set(source_roles) != actual_roles:
            _finding(findings, claim_id, "source_role_mismatch")

        links, _ = _validate_support_links(claim, source_by_id=source_by_id)
        link_by_source = {item["source_id"]: item for item in links}
        claim_can_support = require_string_list(claim.get("can_support"), "can_support")
        cannot_support = require_string_list(
            claim.get("cannot_support"), "cannot_support", nonempty=True
        )
        safe_wording = _reader_text(
            require_string(claim, "safe_wording"), f"claim {claim_id} safe wording"
        )
        _reader_text(
            require_string(claim, "unsafe_wording"), f"claim {claim_id} unsafe wording"
        )
        for label, entries in (
            ("can_support", claim_can_support),
            ("cannot_support", cannot_support),
        ):
            if any(contains_internal_language(item) for item in entries):
                raise ValidationError(
                    f"claim {claim_id}: {label} contains internal workflow language"
                )

        _validate_alternatives(
            claim,
            source_by_id=source_by_id,
            authoritative_source_ids=authoritative_source_ids,
        )

        mechanism = require_string_list(
            claim.get("mechanism_source_ids"), "mechanism_source_ids"
        )
        forecast = require_string_list(
            claim.get("forecast_validation_source_ids"),
            "forecast_validation_source_ids",
        )
        if not set((*mechanism, *forecast)).issubset(source_ids):
            raise ValidationError(
                f"claim {claim_id}: mechanism and forecast evidence must also appear in source_ids"
            )

        usable_ids = [item for item in source_ids if item in authoritative_source_ids]
        support_required = (
            disposition == "principal"
            or bool(claim["critical"])
            or strength in {"supported", "strong"}
            or claim_type
            in {"fact", "number", "causal", "execution", "outcome", "forecast"}
        )
        if support_required and not usable_ids:
            _finding(findings, claim_id, "claim_without_usable_source")
        if set(source_ids) - set(usable_ids):
            _finding(findings, claim_id, "cited_source_not_claim_usable")
        if disposition == "principal" and not any(
            link_by_source[source_id]["relation"] == "support"
            for source_id in usable_ids
        ):
            _finding(findings, claim_id, "principal_claim_without_support_link")

        independent_lineages = {
            source_by_id[item]["lineage_id"]
            for item in usable_ids
            if source_by_id[item]["independence"] == "independent"
        }
        if (claim["requires_independent_support"] or strength == "strong") and len(
            independent_lineages
        ) < 2:
            _finding(findings, claim_id, "insufficient_independent_lineages")
        if support_required and safe_wording not in claim_can_support:
            _finding(findings, claim_id, "safe_wording_not_in_claim_support_boundary")
        supporting_sources = [
            source_by_id[source_id]
            for source_id in usable_ids
            if link_by_source[source_id]["relation"] == "support"
        ]
        if support_required and not any(
            safe_wording in source["can_support"] for source in supporting_sources
        ):
            _finding(findings, claim_id, "safe_wording_not_anchored_to_source")

        roles = {source_by_id[item]["role"] for item in usable_ids}
        if claim_type == "causal":
            if not mechanism or not set(mechanism).issubset(usable_ids):
                _finding(findings, claim_id, "causal_mechanism_missing")
        if claim_type in {"execution", "outcome"} and not (
            {"implementation", "outcome", "data"} & roles
        ):
            _finding(findings, claim_id, "execution_or_outcome_evidence_missing")
        if claim_type == "forecast":
            if not forecast or not set(forecast).issubset(usable_ids):
                _finding(findings, claim_id, "forecast_validation_missing")

        semantic_reference = claim.get("semantic_fit_receipt_fingerprint")
        semantic_basis = fingerprint(_semantic_basis(claim))
        semantic_basis_fingerprints[claim_id] = semantic_basis
        if semantic_reference is None:
            if support_required:
                _finding(findings, claim_id, "semantic_fit_receipt_missing")
        else:
            require_fingerprint(
                {"semantic_fit_receipt_fingerprint": semantic_reference},
                "semantic_fit_receipt_fingerprint",
            )
            if receipt_root is None:
                _finding(findings, claim_id, "semantic_fit_authority_not_resolved")
            else:
                projection = resolve_current_receipt(
                    semantic_reference,
                    root=receipt_root,
                    expected={"producer_skill": "logicguard"},
                )
                receipt = projection["receipt"]
                if receipt["evidence_domain"] not in {
                    "argument_model",
                    "citation_semantics",
                }:
                    raise ValidationError(
                        f"claim {claim_id}: semantic-fit receipt has the wrong evidence domain"
                    )
                if (
                    receipt["input_fingerprints"].get("source_registry")
                    != actual_registry_fingerprint
                ):
                    raise ValidationError(
                        f"claim {claim_id}: semantic-fit receipt does not bind this SourceRegistry"
                    )
                if (
                    receipt["output_fingerprints"].get("claim_semantic_fit")
                    != semantic_basis
                ):
                    raise ValidationError(
                        f"claim {claim_id}: semantic-fit receipt does not bind the exact claim boundary"
                    )
                if not projection["current"] or projection["status"] != "current_pass":
                    _finding(findings, claim_id, "semantic_fit_receipt_not_current")
                else:
                    semantic_receipts.append(semantic_reference)

    orders = sorted(order_by_claim.values())
    if orders != list(range(1, len(claims) + 1)):
        raise ValidationError("reader_order values must be unique and contiguous from 1")
    for claim in claims:
        for dependency in claim["depends_on_claim_ids"]:
            if order_by_claim[dependency] >= order_by_claim[claim["claim_id"]]:
                raise ValidationError(
                    f"claim {claim['claim_id']}: dependencies must appear earlier in reader order"
                )

    ineligible = {item["claim_id"] for item in findings}
    changed = True
    while changed:
        changed = False
        for claim in claims:
            claim_id = claim["claim_id"]
            if claim["reader_disposition"] != "principal" or claim_id in ineligible:
                continue
            if any(item in ineligible for item in claim["depends_on_claim_ids"]):
                _finding(findings, claim_id, "principal_dependency_not_eligible")
                ineligible.add(claim_id)
                changed = True

    eligible = [
        claim["claim_id"]
        for claim in sorted(claims, key=lambda item: item["reader_order"])
        if claim["reader_disposition"] == "principal"
        and claim["claim_id"] not in ineligible
    ]
    status = (
        "current_pass"
        if claims and eligible and not findings and registry_report["status"] == "current_pass"
        else "partial"
    )
    return validation_result(
        status=status,
        ledger_id=value["ledger_id"],
        ledger_fingerprint=fingerprint(value),
        claim_ids=claim_ids,
        eligible_principal_claim_ids=eligible,
        findings=findings,
        safe_claims=[
            claim["safe_wording"]
            for claim in sorted(claims, key=lambda item: item["reader_order"])
            if claim["claim_id"] in eligible
        ],
        unsafe_boundaries=[claim["unsafe_wording"] for claim in claims],
        semantic_receipt_fingerprints=list(dict.fromkeys(semantic_receipts)),
        semantic_basis_fingerprints=semantic_basis_fingerprints,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--source-registry", required=True)
    parser.add_argument("--receipt-root")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        result = validate_claim_support(
            load_json(args.input),
            load_json(args.source_registry),
            receipt_root=args.receipt_root,
        )
        dump_json(result, args.output)
        raise SystemExit(0 if result["status"] == "current_pass" else 1)
    except (ValidationError, OSError, json.JSONDecodeError) as exc:
        dump_json(validation_result(status="blocked", errors=(str(exc),)), args.output)
        raise SystemExit(1)
