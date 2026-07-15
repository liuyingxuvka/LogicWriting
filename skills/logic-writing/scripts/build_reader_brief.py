"""Derive a plain-language ReaderBrief from a verified ResearchPacket."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping

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
    require_unique,
    reject_unknown_keys,
    validation_result,
)
from validate_claim_support import validate_claim_support
from validate_research_packet import validate_research_packet


CONTEXT_FIELDS = {"brief_id", "question", "audience", "genre", "purpose", "concepts"}
CONCEPT_FIELDS = {"concept_id", "term", "explanation", "introduction_order"}
ROLE_WORDING = {
    "primary": "first-hand source",
    "official": "official account",
    "implementation": "evidence of implementation",
    "outcome": "evidence about observed results",
    "method": "method or measurement source",
    "context": "background context",
    "counterevidence": "evidence that limits or challenges the claim",
    "critique": "critical assessment",
    "data": "data source",
    "secondary": "secondary analysis",
}
PURPOSE_WORDING = {
    "background": "Give the reader the minimum context needed for what follows.",
    "evidence": "Show the observed evidence before drawing the conclusion.",
    "interpretation": "Explain what the evidence means without exceeding its limits.",
    "comparison": "Make the competing explanations and their differences visible.",
    "conclusion": "State the conclusion that the preceding evidence can support.",
    "forecast": "Present the forward-looking conclusion together with its conditions and limits.",
}


def _normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r"\s+", " ", value.strip()).casefold()
    return re.sub(r"[.!?。！？]+$", "", value)


def _stable_id(prefix: str, value: Any) -> str:
    return f"{prefix}:" + fingerprint(value).split(":", 1)[1][:24]


def _reader_text(value: Any, label: str, *, locator: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{label} must be a non-empty string")
    text = re.sub(r"\s+", " ", value.strip())
    hits = set(contains_internal_language(text))
    if locator:
        hits.discard("snake_case")
    if hits:
        raise ValidationError(f"{label} contains internal workflow language")
    return text


def _reader_context(value: Mapping[str, Any]) -> dict[str, Any]:
    value = require_mapping(dict(value), "reader context")
    reject_unknown_keys(value, CONTEXT_FIELDS, "reader context")
    if set(value) != CONTEXT_FIELDS:
        missing = sorted(CONTEXT_FIELDS - set(value))
        raise ValidationError("reader context is missing fields: " + ", ".join(missing))
    concepts: list[dict[str, Any]] = []
    concept_ids: list[str] = []
    orders: list[int] = []
    for raw in require_list(value.get("concepts"), "concepts"):
        concept = require_mapping(raw, "reader concept")
        reject_unknown_keys(concept, CONCEPT_FIELDS, "reader concept")
        if set(concept) != CONCEPT_FIELDS:
            raise ValidationError("reader concept has an incomplete shape")
        concept_id = require_string(concept, "concept_id")
        order = concept.get("introduction_order")
        if not isinstance(order, int) or isinstance(order, bool) or order < 1:
            raise ValidationError("introduction_order must be a positive integer")
        concept_ids.append(concept_id)
        orders.append(order)
        concepts.append(
            {
                "concept_id": concept_id,
                "term": _reader_text(concept.get("term"), "concept term"),
                "explanation": _reader_text(
                    concept.get("explanation"), "concept explanation"
                ),
                "introduction_order": order,
            }
        )
    require_unique(concept_ids, "concept ids")
    if sorted(orders) != list(range(1, len(orders) + 1)):
        raise ValidationError(
            "concept introduction_order values must be unique and contiguous from 1"
        )
    return {
        "brief_id": require_string(value, "brief_id"),
        "question": _reader_text(value.get("question"), "reader question"),
        "audience": _reader_text(value.get("audience"), "audience"),
        "genre": _reader_text(value.get("genre"), "genre"),
        "purpose": _reader_text(value.get("purpose"), "purpose"),
        "concepts": sorted(concepts, key=lambda item: item["introduction_order"]),
    }


def _boundary(claim: Mapping[str, Any], source: Mapping[str, Any]) -> str:
    limits = list(
        dict.fromkeys([*claim["cannot_support"], *source["cannot_support"]])
    )
    return _reader_text(
        "This evidence does not establish: " + "; ".join(limits),
        "evidence boundary",
    )


def _derive_anchors(
    claims: Iterable[Mapping[str, Any]],
    source_by_id: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[tuple[str, str, str], str]]:
    anchors: list[dict[str, Any]] = []
    lookup: dict[tuple[str, str, str], str] = {}
    for claim in claims:
        for link in claim["support_links"]:
            source = source_by_id[link["source_id"]]
            source_anchors = {item["anchor_id"]: item for item in source["anchors"]}
            for source_anchor_id in link["anchor_ids"]:
                observed = source_anchors[source_anchor_id]
                identity = {
                    "claim_id": claim["claim_id"],
                    "source_id": source["source_id"],
                    "source_anchor_id": source_anchor_id,
                    "relation": link["relation"],
                }
                anchor_id = _stable_id("anchor", identity)
                key = (claim["claim_id"], source["source_id"], source_anchor_id)
                if key in lookup and lookup[key] != anchor_id:
                    raise ValidationError("evidence anchor identity collision")
                lookup[key] = anchor_id
                supported_wording = (
                    claim["safe_wording"]
                    if link["relation"] == "support"
                    else observed["observed_summary"]
                )
                anchors.append(
                    {
                        "anchor_id": anchor_id,
                        **identity,
                        "locator": _reader_text(
                            observed["locator"], "evidence locator", locator=True
                        ),
                        "observed_summary": _reader_text(
                            observed["observed_summary"], "observed summary"
                        ),
                        "source_role": source["role"],
                        "reader_role": ROLE_WORDING[source["role"]],
                        "supported_wording": _reader_text(
                            supported_wording, "supported wording"
                        ),
                        "boundary": _boundary(claim, source),
                    }
                )
    by_id: dict[str, dict[str, Any]] = {}
    for anchor in anchors:
        anchor_id = anchor["anchor_id"]
        if anchor_id in by_id and by_id[anchor_id] != anchor:
            raise ValidationError("evidence anchor hash collision")
        by_id[anchor_id] = anchor
    return [by_id[key] for key in sorted(by_id)], lookup


def _derive_findings(
    claims: list[Mapping[str, Any]],
    anchor_lookup: Mapping[tuple[str, str, str], str],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    grouped: dict[str, dict[str, Any]] = {}
    claim_to_finding: dict[str, str] = {}
    for claim in claims:
        key = _normalize_text(claim["safe_wording"])
        support_anchor_ids = [
            anchor_lookup[(claim["claim_id"], link["source_id"], anchor_id)]
            for link in claim["support_links"]
            if link["relation"] == "support"
            for anchor_id in link["anchor_ids"]
        ]
        if not support_anchor_ids:
            raise ValidationError(
                f"eligible claim {claim['claim_id']} has no supporting evidence anchor"
            )
        if key not in grouped:
            grouped[key] = {
                "claim_ids": [],
                "text": _reader_text(claim["safe_wording"], "principal finding"),
                "evidence_anchor_ids": [],
            }
        grouped[key]["claim_ids"].append(claim["claim_id"])
        grouped[key]["evidence_anchor_ids"].extend(support_anchor_ids)
    findings: list[dict[str, Any]] = []
    for group in grouped.values():
        claim_ids = list(dict.fromkeys(group["claim_ids"]))
        anchor_ids = list(dict.fromkeys(group["evidence_anchor_ids"]))
        finding_id = _stable_id(
            "finding",
            {"claim_ids": claim_ids, "text": _normalize_text(group["text"])},
        )
        finding = {
            "finding_id": finding_id,
            "claim_ids": claim_ids,
            "text": group["text"],
            "evidence_anchor_ids": anchor_ids,
            "limitation_ids": [],
        }
        findings.append(finding)
        for claim_id in claim_ids:
            claim_to_finding[claim_id] = finding_id
    return findings, claim_to_finding


def _derive_alternatives(
    claims: Iterable[Mapping[str, Any]],
    anchor_lookup: Mapping[tuple[str, str, str], str],
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for claim in claims:
        for alternative in claim["alternatives"]:
            key = _normalize_text(alternative["text"])
            anchor_ids: list[str] = []
            for source_id in alternative["source_ids"]:
                for source_anchor_id in alternative["anchor_ids"]:
                    lookup_key = (claim["claim_id"], source_id, source_anchor_id)
                    if lookup_key in anchor_lookup:
                        anchor_ids.append(anchor_lookup[lookup_key])
            if alternative["treatment"] in {"qualified", "rejected"} and not anchor_ids:
                raise ValidationError(
                    "qualified or rejected alternative is not connected to a derived evidence anchor"
                )
            if key not in grouped:
                grouped[key] = {
                    "alternative_id": _stable_id(
                        "alternative",
                        {"text": key, "treatment": alternative["treatment"]},
                    ),
                    "text": _reader_text(alternative["text"], "alternative"),
                    "treatment": alternative["treatment"],
                    "claim_ids": [],
                    "evidence_anchor_ids": [],
                }
            elif grouped[key]["treatment"] != alternative["treatment"]:
                raise ValidationError(
                    "the same alternative has conflicting evidence treatments"
                )
            grouped[key]["claim_ids"].append(claim["claim_id"])
            grouped[key]["evidence_anchor_ids"].extend(anchor_ids)
    alternatives: list[dict[str, Any]] = []
    for item in grouped.values():
        item["claim_ids"] = list(dict.fromkeys(item["claim_ids"]))
        item["evidence_anchor_ids"] = list(
            dict.fromkeys(item["evidence_anchor_ids"])
        )
        alternatives.append(item)
    return sorted(alternatives, key=lambda item: item["alternative_id"])


def _derive_limitations(
    *,
    packet: Mapping[str, Any],
    eligible_claims: list[Mapping[str, Any]],
    source_by_id: Mapping[str, Mapping[str, Any]],
    findings: list[dict[str, Any]],
    claim_to_finding: Mapping[str, str],
    anchors: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    anchor_by_id = {item["anchor_id"]: item for item in anchors}
    finding_ids = {item["finding_id"] for item in findings}
    grouped: dict[str, dict[str, Any]] = {}

    def add(
        text: str,
        affected_finding_ids: Iterable[str],
        evidence_anchor_ids: Iterable[str] = (),
        *,
        placement: str = "near_claim",
    ) -> None:
        clean = _reader_text(text, "limitation")
        key = _normalize_text(clean)
        if key not in grouped:
            grouped[key] = {
                "limitation_id": _stable_id("limitation", key),
                "text": clean,
                "affected_finding_ids": [],
                "evidence_anchor_ids": [],
                "placement": placement,
            }
        item = grouped[key]
        if item["placement"] != placement and placement == "conclusion":
            item["placement"] = "conclusion"
        item["affected_finding_ids"].extend(
            entry for entry in affected_finding_ids if entry in finding_ids
        )
        item["evidence_anchor_ids"].extend(
            entry for entry in evidence_anchor_ids if entry in anchor_by_id
        )

    for claim in eligible_claims:
        finding_id = claim_to_finding[claim["claim_id"]]
        claim_anchor_ids = [
            anchor["anchor_id"]
            for anchor in anchors
            if anchor["claim_id"] == claim["claim_id"]
        ]
        for text in claim["cannot_support"]:
            add(text, [finding_id], claim_anchor_ids)
        for source_id in claim["source_ids"]:
            source_anchor_ids = [
                anchor["anchor_id"]
                for anchor in anchors
                if anchor["claim_id"] == claim["claim_id"]
                and anchor["source_id"] == source_id
            ]
            for text in source_by_id[source_id]["cannot_support"]:
                add(text, [finding_id], source_anchor_ids)

    for gap in packet["unresolved_gaps"]:
        affected = {
            claim_to_finding[claim_id]
            for claim_id in gap["affected_claim_ids"]
            if claim_id in claim_to_finding
        }
        if gap["affected_source_ids"]:
            affected.update(
                claim_to_finding[anchor["claim_id"]]
                for anchor in anchors
                if anchor["source_id"] in gap["affected_source_ids"]
                and anchor["claim_id"] in claim_to_finding
            )
        if not affected:
            affected = set(finding_ids)
        placement = "conclusion" if gap["scope"] in {"packet", "handoff"} else "near_claim"
        add(gap["safe_wording"], affected, placement=placement)

    limitations = []
    for item in grouped.values():
        item["affected_finding_ids"] = list(
            dict.fromkeys(item["affected_finding_ids"])
        )
        item["evidence_anchor_ids"] = list(
            dict.fromkeys(item["evidence_anchor_ids"])
        )
        limitations.append(item)
    limitations.sort(key=lambda item: item["limitation_id"])
    limitation_ids_by_finding: dict[str, list[str]] = {item: [] for item in finding_ids}
    for limitation in limitations:
        for finding_id in limitation["affected_finding_ids"]:
            limitation_ids_by_finding[finding_id].append(limitation["limitation_id"])
    for finding in findings:
        finding["limitation_ids"] = limitation_ids_by_finding[finding["finding_id"]]
    return limitations


def _derive_sequence(
    findings: list[Mapping[str, Any]],
    claim_by_id: Mapping[str, Mapping[str, Any]],
    claim_to_finding: Mapping[str, str],
) -> list[dict[str, Any]]:
    sequence: list[dict[str, Any]] = []
    for index, finding in enumerate(findings):
        claims = [claim_by_id[item] for item in finding["claim_ids"]]
        prior_ids = list(
            dict.fromkeys(
                claim_to_finding[dependency]
                for claim in claims
                for dependency in claim["depends_on_claim_ids"]
                if dependency in claim_to_finding
                and claim_to_finding[dependency] != finding["finding_id"]
            )
        )
        handoff = (
            "Next, explain how this point supports: " + findings[index + 1]["text"]
            if index + 1 < len(findings)
            else "Close by restating this conclusion together with its limitations."
        )
        sequence.append(
            {
                "order": index + 1,
                "item_kind": "finding",
                "item_id": finding["finding_id"],
                "prior_item_ids": prior_ids,
                "purpose": PURPOSE_WORDING[claims[0]["reader_job"]],
                "handoff": _reader_text(handoff, "information handoff"),
            }
        )
    return sequence


def _derive_citations(
    *,
    anchors: list[Mapping[str, Any]],
    findings: list[Mapping[str, Any]],
    alternatives: list[Mapping[str, Any]],
    limitations: list[Mapping[str, Any]],
    source_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    finding_by_anchor = {
        anchor_id: finding["finding_id"]
        for finding in findings
        for anchor_id in finding["evidence_anchor_ids"]
    }
    alternative_by_anchor = {
        anchor_id: alternative["alternative_id"]
        for alternative in alternatives
        for anchor_id in alternative["evidence_anchor_ids"]
    }
    limitation_by_anchor = {
        anchor_id: limitation["limitation_id"]
        for limitation in limitations
        for anchor_id in limitation["evidence_anchor_ids"]
    }
    source_markers = {
        source_id: f"[S{index}]"
        for index, source_id in enumerate(
            sorted({anchor["source_id"] for anchor in anchors}),
            start=1,
        )
    }
    citations: list[dict[str, Any]] = []

    def add(anchor: Mapping[str, Any], target_kind: str, target_id: str) -> None:
        identity = {
            "anchor_id": anchor["anchor_id"],
            "target_kind": target_kind,
            "target_id": target_id,
        }
        source = source_by_id[anchor["source_id"]]
        citations.append(
            {
                "citation_id": _stable_id("citation", identity),
                "target_kind": target_kind,
                "target_id": target_id,
                "evidence_anchor_ids": [anchor["anchor_id"]],
                "source_id": anchor["source_id"],
                "citation_label": _reader_text(
                    source["citation_label"], "citation label"
                ),
                "locator": anchor["locator"],
                "marker": source_markers[anchor["source_id"]],
                "supported_wording": anchor["supported_wording"],
            }
        )

    for anchor in anchors:
        anchor_id = anchor["anchor_id"]
        if anchor_id in finding_by_anchor:
            add(anchor, "finding", finding_by_anchor[anchor_id])
        if anchor_id in alternative_by_anchor:
            add(anchor, "alternative", alternative_by_anchor[anchor_id])
        if anchor_id in limitation_by_anchor and anchor["relation"] != "support":
            add(anchor, "limitation", limitation_by_anchor[anchor_id])
    if not citations:
        raise ValidationError("ReaderBrief has no citation bound to a supporting anchor")
    return sorted(citations, key=lambda item: item["citation_id"])


def _validate_cross_links(brief: Mapping[str, Any]) -> None:
    findings = {item["finding_id"]: item for item in brief["principal_findings"]}
    anchors = {item["anchor_id"]: item for item in brief["evidence_anchors"]}
    alternatives = {item["alternative_id"]: item for item in brief["alternatives"]}
    limitations = {item["limitation_id"]: item for item in brief["limitations"]}
    if len(findings) != len(brief["principal_findings"]):
        raise ValidationError("ReaderBrief contains duplicate finding ids")
    if len(anchors) != len(brief["evidence_anchors"]):
        raise ValidationError("ReaderBrief contains duplicate evidence-anchor ids")
    for finding in findings.values():
        if not set(finding["evidence_anchor_ids"]).issubset(anchors):
            raise ValidationError("finding refers to an unknown evidence anchor")
        if not set(finding["limitation_ids"]).issubset(limitations):
            raise ValidationError("finding refers to an unknown limitation")
    for limitation in limitations.values():
        if not set(limitation["affected_finding_ids"]).issubset(findings):
            raise ValidationError("limitation refers to an unknown finding")
        if not set(limitation["evidence_anchor_ids"]).issubset(anchors):
            raise ValidationError("limitation refers to an unknown evidence anchor")
    for alternative in alternatives.values():
        if not set(alternative["evidence_anchor_ids"]).issubset(anchors):
            raise ValidationError("alternative refers to an unknown evidence anchor")
    target_sets = {
        "finding": set(findings),
        "alternative": set(alternatives),
        "limitation": set(limitations),
    }
    citation_anchors: set[str] = set()
    markers_by_source: dict[str, str] = {}
    for citation in brief["required_citations"]:
        if citation["target_id"] not in target_sets[citation["target_kind"]]:
            raise ValidationError("citation refers to an unknown target")
        if not set(citation["evidence_anchor_ids"]).issubset(anchors):
            raise ValidationError("citation refers to an unknown evidence anchor")
        if any(
            anchors[anchor_id]["source_id"] != citation["source_id"]
            for anchor_id in citation["evidence_anchor_ids"]
        ):
            raise ValidationError("citation source does not match its evidence anchor")
        prior = markers_by_source.setdefault(citation["source_id"], citation["marker"])
        if prior != citation["marker"]:
            raise ValidationError("one source has inconsistent citation markers")
        citation_anchors.update(citation["evidence_anchor_ids"])
    supporting_anchors = {
        item["anchor_id"] for item in anchors.values() if item["relation"] == "support"
    }
    if not supporting_anchors.issubset(citation_anchors):
        raise ValidationError("a supporting evidence anchor has no citation")
    sequence = brief["information_sequence"]
    if [item["order"] for item in sequence] != list(range(1, len(sequence) + 1)):
        raise ValidationError("information sequence must be contiguous from 1")
    sequence_ids = [item["item_id"] for item in sequence]
    if sequence_ids != list(findings):
        raise ValidationError("information sequence must contain each finding once in order")
    seen: set[str] = set()
    for item in sequence:
        if not set(item["prior_item_ids"]).issubset(seen):
            raise ValidationError("information sequence depends on an item not yet introduced")
        seen.add(item["item_id"])
    allowed = {_normalize_text(item) for item in brief["allowed_wording"]}
    prohibited = {_normalize_text(item) for item in brief["prohibited_wording"]}
    if allowed & prohibited:
        raise ValidationError("allowed and prohibited wording conflict")


def build_reader_brief(
    research_packet: Mapping[str, Any],
    *,
    receipt_root: str | Path,
    brief_id: str,
    question: str,
    audience: str,
    genre: str,
    purpose: str,
    concepts: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Derive a brief; caller controls only reader context, never findings."""

    context = _reader_context(
        {
            "brief_id": brief_id,
            "question": question,
            "audience": audience,
            "genre": genre,
            "purpose": purpose,
            "concepts": concepts,
        }
    )
    packet = validate_research_packet(
        research_packet,
        receipt_root=receipt_root,
    )
    if packet["status"] == "blocked":
        return validation_result(status="blocked", errors=("ResearchPacket is blocked",))
    claim_report = validate_claim_support(
        packet["claim_support"],
        packet["source_registry"],
        receipt_root=receipt_root,
    )
    eligible_ids = set(claim_report["eligible_principal_claim_ids"])
    eligible_claims = sorted(
        [
            claim
            for claim in packet["claim_support"]["claims"]
            if claim["claim_id"] in eligible_ids
        ],
        key=lambda item: item["reader_order"],
    )
    if not eligible_claims:
        return validation_result(
            status="blocked",
            errors=("ResearchPacket contains no evidence-backed principal finding",),
        )
    source_by_id = {
        source["source_id"]: source for source in packet["source_registry"]["sources"]
    }
    anchors, anchor_lookup = _derive_anchors(eligible_claims, source_by_id)
    findings, claim_to_finding = _derive_findings(eligible_claims, anchor_lookup)
    alternatives = _derive_alternatives(eligible_claims, anchor_lookup)
    limitations = _derive_limitations(
        packet=packet,
        eligible_claims=eligible_claims,
        source_by_id=source_by_id,
        findings=findings,
        claim_to_finding=claim_to_finding,
        anchors=anchors,
    )
    claim_by_id = {
        claim["claim_id"]: claim for claim in packet["claim_support"]["claims"]
    }
    sequence = _derive_sequence(findings, claim_by_id, claim_to_finding)
    citations = _derive_citations(
        anchors=anchors,
        findings=findings,
        alternatives=alternatives,
        limitations=limitations,
        source_by_id=source_by_id,
    )
    context_fingerprint = fingerprint(context)
    prohibited_wording = list(dict.fromkeys(packet["unsafe_wording"]))
    brief: dict[str, Any] = {
        "schema_version": "1.0",
        "brief_id": context["brief_id"],
        "packet_fingerprint": packet["packet_fingerprint"],
        "reader_context_fingerprint": context_fingerprint,
        "reader_question": context["question"],
        "audience": context["audience"],
        "genre": context["genre"],
        "purpose": context["purpose"],
        "concepts": context["concepts"],
        "principal_findings": findings,
        "evidence_anchors": anchors,
        "alternatives": alternatives,
        "limitations": limitations,
        "information_sequence": sequence,
        "required_citations": citations,
        "allowed_wording": [item["text"] for item in findings],
        "prohibited_wording": prohibited_wording,
    }
    brief["brief_fingerprint"] = fingerprint(brief)
    require_schema("reader-brief.schema.json", brief, label="ReaderBrief")
    _validate_cross_links(brief)

    from build_reader_brief_receipt import build_reader_brief_receipt

    receipt = build_reader_brief_receipt(
        reader_brief=brief,
        packet_fingerprint=packet["packet_fingerprint"],
        reader_context_fingerprint=context_fingerprint,
        dependency_receipt_fingerprints=[
            item["receipt_fingerprint"] for item in packet["native_receipts"]
        ],
        root=receipt_root,
    )
    return validation_result(
        status=packet["status"],
        packet_fingerprint=packet["packet_fingerprint"],
        reader_context_fingerprint=context_fingerprint,
        brief_fingerprint=brief["brief_fingerprint"],
        derivation_receipt_fingerprint=receipt["receipt_fingerprint"],
        reader_brief=brief,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", required=True)
    parser.add_argument("--receipt-root", required=True)
    parser.add_argument("--input", required=True, help="Reader context JSON")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        context = _reader_context(load_json(args.input))
        result = build_reader_brief(
            load_json(args.packet),
            receipt_root=args.receipt_root,
            brief_id=context["brief_id"],
            question=context["question"],
            audience=context["audience"],
            genre=context["genre"],
            purpose=context["purpose"],
            concepts=context["concepts"],
        )
        dump_json(result, args.output)
        return 0 if result["status"] == "current_pass" else 1
    except (ValidationError, OSError, json.JSONDecodeError) as exc:
        dump_json(validation_result(status="blocked", errors=(str(exc),)), args.output)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_reader_brief"]
