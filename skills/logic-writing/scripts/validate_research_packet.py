"""Assemble and validate the authority-backed cross-route ResearchPacket."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from _common import (
    EVIDENCE_DOMAINS,
    NATIVE_OWNERS,
    ValidationError,
    dump_json,
    fingerprint,
    load_json,
    require_fingerprint,
    require_list,
    require_mapping,
    require_string,
    require_string_list,
    reject_unknown_keys,
    validation_result,
)
from receipt_authority import resolve_current_receipt
from schema_validation import SchemaValidationError, assert_schema_valid
from validate_claim_support import validate_claim_support
from validate_source_registry import validate_source_registry


ASSEMBLY_FIELDS = {
    "schema_version",
    "packet_id",
    "request_fingerprint",
    "final_owner",
    "gap_id",
    "source_registry",
    "claim_support",
    "native_receipt_fingerprints",
    "additional_unresolved_gaps",
}
PACKET_FIELDS = {
    "schema_version",
    "packet_id",
    "request_fingerprint",
    "final_owner",
    "gap_id",
    "source_registry",
    "claim_support",
    "native_receipts",
    "member_fingerprints",
    "unresolved_gaps",
    "safe_wording",
    "unsafe_wording",
    "status",
    "packet_fingerprint",
}
PACKET_DOMAINS = EVIDENCE_DOMAINS - {
    "reader_brief",
    "final_closure",
    "development_validation",
    "installation",
    "global_routing",
    "release",
    "retirement",
}
ADDITIONAL_GAP_CODES = {
    "access_gap",
    "scope_not_covered",
    "source_conflict_unresolved",
    "recency_not_verified",
    "additional_evidence_gap",
}
ADDITIONAL_GAP_FIELDS = {"code", "affected_claim_ids", "affected_source_ids"}


# These are reader-safe explanations, not control-plane diagnostics. Unknown
# codes are rejected instead of leaking raw internal labels into later prose.
GAP_POLICIES: dict[str, tuple[str, str, str, str]] = {
    "registry_has_no_sources": (
        "source",
        "No source has yet been observed for this question.",
        "Do not present an unsupported conclusion as established.",
        "source-research",
    ),
    "source_not_claim_usable": (
        "source",
        "One listed source has not yet been observed closely enough to support a conclusion.",
        "Do not rely on that source as factual support.",
        "source-research",
    ),
    "observation_authority_not_resolved": (
        "source",
        "The underlying source record has not yet been confirmed against the material itself.",
        "Do not treat an unconfirmed source description as observed evidence.",
        "source-research",
    ),
    "observation_receipt_not_current": (
        "source",
        "The source observation belongs to an earlier version of the material.",
        "Do not rely on an observation made against superseded material.",
        "source-research",
    ),
    "observation_receipt_not_in_packet": (
        "source",
        "The source observation has not been included in the evidence package.",
        "Do not use the source until its observation is attached to this package.",
        "source-research",
    ),
    "ledger_has_no_claims": (
        "claim",
        "No conclusion has yet been formulated for evidence review.",
        "Do not imply that the research already supports a conclusion.",
        "argument-review",
    ),
    "claim_without_usable_source": (
        "claim",
        "The available material does not yet provide a source that can support this conclusion.",
        "Do not state this conclusion as evidence-backed.",
        "source-research",
    ),
    "cited_source_not_claim_usable": (
        "claim",
        "At least one cited item cannot currently support the conclusion attributed to it.",
        "Do not use an unavailable or unobserved item as support.",
        "source-research",
    ),
    "source_role_mismatch": (
        "claim",
        "A source is being described in a role that does not match the material.",
        "Do not overstate what kind of evidence the source provides.",
        "argument-review",
    ),
    "principal_claim_without_support_link": (
        "claim",
        "The proposed main conclusion is not connected to a specific observed passage.",
        "Do not present the conclusion without a traceable evidence anchor.",
        "argument-review",
    ),
    "insufficient_independent_lineages": (
        "claim",
        "The apparent sources do not yet provide independent confirmation.",
        "Do not describe repeated reports from one lineage as independent corroboration.",
        "source-research",
    ),
    "safe_wording_not_in_claim_support_boundary": (
        "claim",
        "The proposed wording goes beyond the conclusion that was actually reviewed.",
        "Do not strengthen the conclusion beyond its reviewed wording.",
        "argument-review",
    ),
    "safe_wording_not_anchored_to_source": (
        "claim",
        "The proposed wording is not directly supported by the source passage linked to it.",
        "Do not detach a conclusion from the boundary of its cited source.",
        "argument-review",
    ),
    "causal_mechanism_missing": (
        "causal",
        "The observed sequence does not by itself establish why one event produced the other.",
        "Do not convert timing or association into a causal claim.",
        "trace-review",
    ),
    "execution_or_outcome_evidence_missing": (
        "claim",
        "The material describes an intention or announcement but not what was implemented or observed.",
        "Do not present an announcement as evidence of execution or results.",
        "source-research",
    ),
    "forecast_validation_missing": (
        "forecast",
        "The forward-looking conclusion has not been tested against future or held-out evidence.",
        "Do not present the forecast as validated.",
        "trace-review",
    ),
    "semantic_fit_receipt_missing": (
        "claim",
        "The connection between this conclusion and its cited material has not yet been reviewed.",
        "Do not treat a citation as proof until its relevance is checked.",
        "argument-review",
    ),
    "semantic_fit_authority_not_resolved": (
        "claim",
        "The evidence-to-conclusion review cannot yet be confirmed.",
        "Do not rely on an unconfirmed relevance judgment.",
        "argument-review",
    ),
    "semantic_fit_receipt_not_current": (
        "claim",
        "The evidence-to-conclusion review belongs to an earlier version of the research.",
        "Do not reuse an earlier relevance judgment after the evidence changes.",
        "argument-review",
    ),
    "semantic_fit_receipt_not_in_packet": (
        "claim",
        "The evidence-to-conclusion review has not been included in this package.",
        "Do not use the conclusion until its relevance review is attached.",
        "argument-review",
    ),
    "principal_dependency_not_eligible": (
        "claim",
        "This conclusion depends on an earlier point that is not yet supported.",
        "Do not build a conclusion on an unsupported premise.",
        "argument-review",
    ),
    "missing_gap_id": (
        "handoff",
        "The writing handoff lacks a stable identity for the research question it is meant to close.",
        "Do not revise the document against an ambiguous research request.",
        "research-owner",
    ),
    "missing_causal_trace": (
        "causal",
        "The causal conclusion has not yet been checked against a complete causal chain.",
        "Do not infer causation from chronology alone.",
        "trace-review",
    ),
    "missing_prediction_boundary": (
        "forecast",
        "The forecast does not yet state the conditions under which it could hold or fail.",
        "Do not present the forecast without its prediction boundary.",
        "trace-review",
    ),
    "native_receipt_not_current": (
        "packet",
        "Part of the evidence was produced for an earlier version of the work.",
        "Do not present the package as fully current.",
        "research-owner",
    ),
    "missing_native_receipts": (
        "packet",
        "No specialist evidence has yet been attached to this research package.",
        "Do not present the package as evidence-backed.",
        "research-owner",
    ),
    "access_gap": (
        "source",
        "Relevant material could not yet be accessed.",
        "Do not imply that inaccessible material was reviewed.",
        "source-research",
    ),
    "scope_not_covered": (
        "packet",
        "Part of the question remains outside the material reviewed so far.",
        "Do not extend the conclusion to the uncovered scope.",
        "research-owner",
    ),
    "source_conflict_unresolved": (
        "claim",
        "The available sources disagree and the conflict has not yet been resolved.",
        "Do not hide or prematurely settle the disagreement.",
        "argument-review",
    ),
    "recency_not_verified": (
        "source",
        "The material may not be recent enough for a current-state conclusion.",
        "Do not describe an older observation as the present state without checking it.",
        "source-research",
    ),
    "additional_evidence_gap": (
        "packet",
        "A stated research need has not yet been resolved.",
        "Do not present the affected scope as complete.",
        "research-owner",
    ),
}


def _make_gap(
    code: str,
    *,
    claim_ids: Iterable[str] = (),
    source_ids: Iterable[str] = (),
) -> dict[str, Any]:
    if code not in GAP_POLICIES:
        raise ValidationError(f"unsupported unresolved-gap code: {code}")
    affected_claim_ids = sorted(set(claim_ids))
    affected_source_ids = sorted(set(source_ids))
    scope, safe_wording, unsafe_boundary, next_owner = GAP_POLICIES[code]
    identity = {
        "code": code,
        "affected_claim_ids": affected_claim_ids,
        "affected_source_ids": affected_source_ids,
        "scope": scope,
    }
    return {
        "gap_entry_id": "gap:" + fingerprint(identity).split(":", 1)[1][:24],
        **identity,
        "safe_wording": safe_wording,
        "unsafe_boundary": unsafe_boundary,
        "next_owner": next_owner,
    }


def _dedupe_gaps(gaps: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for raw in gaps:
        gap = dict(raw)
        gap_id = gap["gap_entry_id"]
        if gap_id in by_id and by_id[gap_id] != gap:
            raise ValidationError("unresolved-gap identity collision")
        by_id[gap_id] = gap
    return [by_id[key] for key in sorted(by_id)]


def _latest_projection(
    receipt_fingerprint: str,
    *,
    root: str | Path,
) -> dict[str, Any]:
    projection = resolve_current_receipt(receipt_fingerprint, root=root)
    latest = projection["latest_receipt_fingerprint"]
    if latest != receipt_fingerprint:
        projection = resolve_current_receipt(latest, root=root)
    return projection


def _receipt_ref(projection: Mapping[str, Any]) -> dict[str, Any]:
    receipt = projection["receipt"]
    return {
        "receipt_fingerprint": projection["receipt_fingerprint"],
        "producer_skill": receipt["producer_skill"],
        "native_route": receipt["native_route"],
        "evidence_domain": receipt["evidence_domain"],
        "status": projection["status"],
        "artifact_fingerprint": receipt["artifact_fingerprint"],
        "covered_scope": receipt["covered_scope"],
        "covered_obligation_ids": receipt["covered_obligation_ids"],
        "current": projection["current"],
    }


def _additional_gaps(
    raw_gaps: Any,
    *,
    claim_ids: set[str],
    source_ids: set[str],
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for raw in require_list(raw_gaps, "additional_unresolved_gaps"):
        item = require_mapping(raw, "additional unresolved gap")
        reject_unknown_keys(item, ADDITIONAL_GAP_FIELDS, "additional unresolved gap")
        if set(item) != ADDITIONAL_GAP_FIELDS:
            raise ValidationError("additional unresolved gap has an incomplete shape")
        code = require_string(item, "code")
        if code not in ADDITIONAL_GAP_CODES:
            raise ValidationError("caller may only add a declared research gap class")
        affected_claim_ids = require_string_list(
            item.get("affected_claim_ids"), "affected_claim_ids"
        )
        affected_source_ids = require_string_list(
            item.get("affected_source_ids"), "affected_source_ids"
        )
        if not set(affected_claim_ids).issubset(claim_ids):
            raise ValidationError("additional gap refers to an unknown claim")
        if not set(affected_source_ids).issubset(source_ids):
            raise ValidationError("additional gap refers to an unknown source")
        gaps.append(
            _make_gap(
                code,
                claim_ids=affected_claim_ids,
                source_ids=affected_source_ids,
            )
        )
    return _dedupe_gaps(gaps)


def _trace_gaps(
    claim_support: Mapping[str, Any],
    claim_report: Mapping[str, Any],
    projections: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    basis = claim_report["semantic_basis_fingerprints"]
    for claim in claim_support["claims"]:
        claim_id = claim["claim_id"]
        if claim["claim_type"] == "causal":
            key = f"claim:{claim_id}:causal_trace"
            matched = any(
                projection["receipt"]["producer_skill"] == "traceguard"
                and projection["receipt"]["evidence_domain"] == "causal_trace"
                and projection["current"]
                and projection["status"] == "current_pass"
                and projection["receipt"]["output_fingerprints"].get(key)
                == basis[claim_id]
                for projection in projections
            )
            if not matched:
                gaps.append(_make_gap("missing_causal_trace", claim_ids=[claim_id]))
        if claim["claim_type"] == "forecast":
            key = f"claim:{claim_id}:prediction_boundary"
            matched = any(
                projection["receipt"]["producer_skill"] == "traceguard"
                and projection["receipt"]["evidence_domain"] == "prediction_boundary"
                and projection["current"]
                and projection["status"] == "current_pass"
                and projection["receipt"]["output_fingerprints"].get(key)
                == basis[claim_id]
                for projection in projections
            )
            if not matched:
                gaps.append(
                    _make_gap("missing_prediction_boundary", claim_ids=[claim_id])
                )
    return gaps


def _mandatory_gaps(
    *,
    final_owner: str,
    gap_id: str | None,
    source_report: Mapping[str, Any],
    claim_report: Mapping[str, Any],
    source_registry: Mapping[str, Any],
    claim_support: Mapping[str, Any],
    projections: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for finding in source_report["findings"]:
        gaps.append(
            _make_gap(
                finding["code"],
                source_ids=[]
                if finding["source_id"] == "registry"
                else [finding["source_id"]],
            )
        )
    for finding in claim_report["findings"]:
        gaps.append(
            _make_gap(
                finding["code"],
                claim_ids=[]
                if finding["claim_id"] == "ledger"
                else [finding["claim_id"]],
            )
        )
    receipt_set = {item["receipt_fingerprint"] for item in projections}
    for source in source_registry["sources"]:
        reference = source.get("observation_receipt_fingerprint")
        if reference is not None and reference not in receipt_set:
            gaps.append(
                _make_gap(
                    "observation_receipt_not_in_packet",
                    source_ids=[source["source_id"]],
                )
            )
    for claim in claim_support["claims"]:
        reference = claim.get("semantic_fit_receipt_fingerprint")
        if reference is not None and reference not in receipt_set:
            gaps.append(
                _make_gap(
                    "semantic_fit_receipt_not_in_packet",
                    claim_ids=[claim["claim_id"]],
                )
            )
    if final_owner == "academic-writing" and gap_id is None:
        gaps.append(_make_gap("missing_gap_id"))
    gaps.extend(_trace_gaps(claim_support, claim_report, projections))
    for projection in projections:
        if not projection["current"] or projection["status"] != "current_pass":
            gaps.append(_make_gap("native_receipt_not_current"))
    if not projections:
        gaps.append(_make_gap("missing_native_receipts"))
    return _dedupe_gaps(gaps)


def _derived_wording(
    claim_report: Mapping[str, Any],
    gaps: list[Mapping[str, Any]],
) -> tuple[list[str], list[str]]:
    safe = list(dict.fromkeys(claim_report["safe_claims"]))
    unsafe = list(
        dict.fromkeys(
            [
                *claim_report["unsafe_boundaries"],
                *(gap["unsafe_boundary"] for gap in gaps),
            ]
        )
    )
    if not safe:
        safe = ["The material does not yet support a principal conclusion."]
    if not unsafe:
        unsafe = ["Do not present the available material as complete or conclusive."]
    return safe, unsafe


def _resolve_packet_receipts(
    fingerprints: Iterable[str],
    *,
    receipt_root: str | Path,
) -> list[dict[str, Any]]:
    projections: list[dict[str, Any]] = []
    seen: set[str] = set()
    for receipt_fingerprint in fingerprints:
        projection = _latest_projection(receipt_fingerprint, root=receipt_root)
        receipt = projection["receipt"]
        if receipt["producer_skill"] not in NATIVE_OWNERS:
            raise ValidationError(
                "ResearchPacket receipts must retain a native specialist owner"
            )
        if receipt["evidence_domain"] not in PACKET_DOMAINS:
            raise ValidationError(
                f"unsupported ResearchPacket evidence domain: {receipt['evidence_domain']}"
            )
        current_fingerprint = projection["receipt_fingerprint"]
        if current_fingerprint not in seen:
            projections.append(projection)
            seen.add(current_fingerprint)
    return projections


def assemble_research_packet(
    request: Mapping[str, Any],
    *,
    receipt_root: str | Path,
) -> dict[str, Any]:
    """Build a packet without accepting caller-authored status or wording."""

    request = require_mapping(dict(request), "ResearchPacket assembly request")
    reject_unknown_keys(request, ASSEMBLY_FIELDS, "ResearchPacket assembly request")
    required = ASSEMBLY_FIELDS - {"gap_id", "additional_unresolved_gaps"}
    missing = sorted(required - set(request))
    if missing:
        raise ValidationError(
            "ResearchPacket assembly request is missing fields: " + ", ".join(missing)
        )
    if require_string(request, "schema_version") != "1.0":
        raise ValidationError("schema_version must be 1.0")
    require_string(request, "packet_id")
    require_fingerprint(request, "request_fingerprint")
    final_owner = require_string(request, "final_owner")
    if final_owner not in {"investigation", "academic-writing"}:
        raise ValidationError("final_owner must be investigation or academic-writing")
    gap_id = request.get("gap_id")
    if gap_id is not None and (not isinstance(gap_id, str) or not gap_id.strip()):
        raise ValidationError("gap_id must be null or a non-empty identifier")
    source_registry = require_mapping(request.get("source_registry"), "source_registry")
    claim_support = require_mapping(request.get("claim_support"), "claim_support")
    receipt_fingerprints = require_string_list(
        request.get("native_receipt_fingerprints"),
        "native_receipt_fingerprints",
    )
    projections = _resolve_packet_receipts(
        receipt_fingerprints,
        receipt_root=receipt_root,
    )
    source_report = validate_source_registry(
        source_registry,
        receipt_root=receipt_root,
    )
    claim_report = validate_claim_support(
        claim_support,
        source_registry,
        receipt_root=receipt_root,
    )
    claim_ids = {item["claim_id"] for item in claim_support["claims"]}
    source_ids = {item["source_id"] for item in source_registry["sources"]}
    extras = _additional_gaps(
        request.get("additional_unresolved_gaps", []),
        claim_ids=claim_ids,
        source_ids=source_ids,
    )
    mandatory = _mandatory_gaps(
        final_owner=final_owner,
        gap_id=gap_id,
        source_report=source_report,
        claim_report=claim_report,
        source_registry=source_registry,
        claim_support=claim_support,
        projections=projections,
    )
    gaps = _dedupe_gaps([*mandatory, *extras])
    status = "blocked" if not projections else "partial" if gaps else "current_pass"
    native_receipts = [_receipt_ref(projection) for projection in projections]
    safe_wording, unsafe_wording = _derived_wording(claim_report, gaps)
    member_fingerprints = {
        "source_registry": fingerprint(source_registry),
        "claim_support": fingerprint(claim_support),
        **{
            f"native_receipt:{index}": item["receipt_fingerprint"]
            for index, item in enumerate(native_receipts)
        },
    }
    packet: dict[str, Any] = {
        "schema_version": "1.0",
        "packet_id": request["packet_id"],
        "request_fingerprint": request["request_fingerprint"],
        "final_owner": final_owner,
        "source_registry": source_registry,
        "claim_support": claim_support,
        "native_receipts": native_receipts,
        "member_fingerprints": member_fingerprints,
        "unresolved_gaps": gaps,
        "safe_wording": safe_wording,
        "unsafe_wording": unsafe_wording,
        "status": status,
    }
    if gap_id is not None:
        packet["gap_id"] = gap_id
    packet["packet_fingerprint"] = fingerprint(packet)
    validate_research_packet(packet, receipt_root=receipt_root)
    return packet


def validate_research_packet(
    value: Mapping[str, Any],
    *,
    receipt_root: str | Path,
) -> dict[str, Any]:
    """Validate exact members, current authority, structured gaps, and status."""

    packet = require_mapping(dict(value), "ResearchPacket")
    reject_unknown_keys(packet, PACKET_FIELDS, "ResearchPacket")
    required = PACKET_FIELDS - {"gap_id"}
    missing = sorted(required - set(packet))
    if missing:
        raise ValidationError("ResearchPacket is missing fields: " + ", ".join(missing))
    try:
        assert_schema_valid("research-packet.schema.json", packet)
    except SchemaValidationError as exc:
        raise ValidationError(str(exc)) from exc

    projections: list[dict[str, Any]] = []
    for item in packet["native_receipts"]:
        projection = resolve_current_receipt(
            item["receipt_fingerprint"],
            root=receipt_root,
        )
        if item != _receipt_ref(projection):
            raise ValidationError(
                "ResearchPacket receipt projection does not match authoritative original"
            )
        projections.append(projection)
    source_report = validate_source_registry(
        packet["source_registry"],
        receipt_root=receipt_root,
    )
    claim_report = validate_claim_support(
        packet["claim_support"],
        packet["source_registry"],
        receipt_root=receipt_root,
    )
    expected_members = {
        "source_registry": fingerprint(packet["source_registry"]),
        "claim_support": fingerprint(packet["claim_support"]),
        **{
            f"native_receipt:{index}": item["receipt_fingerprint"]
            for index, item in enumerate(packet["native_receipts"])
        },
    }
    if packet["member_fingerprints"] != expected_members:
        raise ValidationError("member_fingerprints do not match exact packet members")

    mandatory = _mandatory_gaps(
        final_owner=packet["final_owner"],
        gap_id=packet.get("gap_id"),
        source_report=source_report,
        claim_report=claim_report,
        source_registry=packet["source_registry"],
        claim_support=packet["claim_support"],
        projections=projections,
    )
    normalized_actual: list[dict[str, Any]] = []
    for raw in packet["unresolved_gaps"]:
        gap = require_mapping(raw, "unresolved gap")
        normalized = _make_gap(
            require_string(gap, "code"),
            claim_ids=require_string_list(
                gap.get("affected_claim_ids"), "affected_claim_ids"
            ),
            source_ids=require_string_list(
                gap.get("affected_source_ids"), "affected_source_ids"
            ),
        )
        if gap != normalized:
            raise ValidationError(
                "ResearchPacket unresolved gap is not verifier-derived"
            )
        normalized_actual.append(normalized)
    actual = _dedupe_gaps(normalized_actual)
    actual_by_id = {item["gap_entry_id"]: item for item in actual}
    missing_mandatory = [
        item for item in mandatory if item["gap_entry_id"] not in actual_by_id
    ]
    if missing_mandatory:
        raise ValidationError("ResearchPacket omits verifier-derived gaps")
    mandatory_ids = {item["gap_entry_id"] for item in mandatory}
    for item in actual:
        if item["gap_entry_id"] not in mandatory_ids and item["code"] not in ADDITIONAL_GAP_CODES:
            raise ValidationError("ResearchPacket contains an unowned unresolved gap")

    expected_safe, expected_unsafe = _derived_wording(claim_report, actual)
    if packet["safe_wording"] != expected_safe:
        raise ValidationError("ResearchPacket safe_wording is not verifier-derived")
    if packet["unsafe_wording"] != expected_unsafe:
        raise ValidationError("ResearchPacket unsafe_wording is not verifier-derived")
    expected_status = (
        "blocked"
        if not projections
        else "partial"
        if actual
        else "current_pass"
    )
    if packet["status"] != expected_status:
        raise ValidationError("ResearchPacket status is not verifier-derived")
    if require_fingerprint(packet, "packet_fingerprint") != fingerprint(
        {key: item for key, item in packet.items() if key != "packet_fingerprint"}
    ):
        raise ValidationError("packet_fingerprint does not match exact packet content")
    return packet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--receipt-root", required=True)
    parser.add_argument("--validate-packet", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        value = load_json(args.input)
        result = (
            validate_research_packet(value, receipt_root=args.receipt_root)
            if args.validate_packet
            else assemble_research_packet(value, receipt_root=args.receipt_root)
        )
        dump_json(result, args.output)
        return 0 if result["status"] == "current_pass" else 1
    except (ValidationError, SchemaValidationError, OSError, json.JSONDecodeError) as exc:
        dump_json(validation_result(status="blocked", errors=(str(exc),)), args.output)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["assemble_research_packet", "validate_research_packet"]
