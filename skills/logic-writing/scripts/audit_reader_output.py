"""Audit exact delivered bytes against a current authoritative ReaderBrief."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping

from _common import (
    ValidationError,
    contains_internal_language,
    dump_json,
    fingerprint,
    fingerprint_without,
    load_json,
    require_list,
    require_mapping,
    require_schema,
    require_string,
    reject_unknown_keys,
    validation_result,
)
from build_source_unit_manifest import extract_visible_units, fingerprint_bytes
from receipt_authority import (
    _commit_managed_receipt,
    _store_content_object,
    resolve_content_object,
    resolve_current_receipt,
)


VAGUE_OPENERS = re.compile(r"^(?:this|that|it|these|those)\b", re.IGNORECASE)
MECHANICAL = re.compile(r"\b(?:firstly|secondly|thirdly|in conclusion)\b", re.IGNORECASE)
SENTENCE = re.compile(r"(?<=[.!?。！？])\s+")
PROSE_GENRES = re.compile(
    r"\b(?:narrative|report|paper|article|essay|chapter|brief)\b|报告|论文|文章|章节|简报",
    re.IGNORECASE,
)
DRAFT_PLACEHOLDER = re.compile(
    r"\b(?:TBD|TODO|should eventually|will be discussed later|insert (?:evidence|citation|analysis))\b|"
    r"\[(?:insert|todo|tbd)[^\]]*\]",
    re.IGNORECASE,
)
META_PROSE = re.compile(
    r"\b(?:this (?:section|paragraph|chapter) (?:will|aims to|seeks to)|the following section will)\b|"
    r"(?:本节|本段|本章)(?:将|旨在)",
    re.IGNORECASE,
)
STRONG_CAUSAL = re.compile(
    r"\b(?:proves?|proved|definitively establishes?|caused|causes|led to|results? in|guarantees?)\b|"
    r"(?:确凿证明|充分证明|必然导致|直接导致|证明了?因果|毫无疑问)",
    re.IGNORECASE,
)
QUALIFIED = re.compile(
    r"\b(?:may|might|suggests?|is associated with|could|appears to|within the observed scope)\b|"
    r"(?:可能|或许|表明|提示|相关|在观察范围内|尚不能)",
    re.IGNORECASE,
)
NEGATED_CAUSAL = re.compile(
    r"\b(?:does not|did not|do not|cannot|can't|could not|is not|was not|no evidence (?:that )?)\b|"
    r"(?:不能|并非|不是|未能|没有证据(?:表明|证明)?|不足以)",
    re.IGNORECASE,
)
TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".rst", ".tex", ".csv"}
REQUEST_FIELDS = {
    "schema_version",
    "audit_id",
    "artifact_path",
    "audited_text_path",
    "artifact_extraction_receipt_fingerprint",
    "reader_brief",
    "reader_brief_receipt_fingerprint",
    "run_id",
}


def _first_sentence(text: str) -> str:
    return SENTENCE.split(text.strip(), maxsplit=1)[0].strip()


def _finding(unit: Mapping[str, Any] | None, code: str, details: Any) -> dict[str, Any]:
    return {
        "unit_id": unit["unit_id"] if unit is not None else None,
        "locator": unit["locator"] if unit is not None else None,
        "code": code,
        "details": details,
    }


def _artifact_bytes(path_value: Any) -> tuple[Path, bytes]:
    if not isinstance(path_value, str) or not path_value.strip():
        raise ValidationError("artifact_path must be a non-empty path")
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        raise ValidationError("delivered artifact is not a file")
    data = path.read_bytes()
    if not data:
        raise ValidationError("delivered artifact is empty")
    return path, data


def _audited_text(
    request: Mapping[str, Any],
    *,
    receipt_root: str | Path,
) -> tuple[Path, bytes, bytes, str | None]:
    artifact_path, artifact_bytes = _artifact_bytes(request.get("artifact_path"))
    extraction_reference = request.get("artifact_extraction_receipt_fingerprint")
    text_path_value = request.get("audited_text_path")
    if artifact_path.suffix.lower() in TEXT_SUFFIXES:
        if extraction_reference is not None or text_path_value is not None:
            raise ValidationError(
                "plain-text artifacts are audited directly and cannot use a second text projection"
            )
        try:
            artifact_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValidationError("plain-text artifact must be valid UTF-8") from exc
        return artifact_path, artifact_bytes, artifact_bytes, None

    if not isinstance(text_path_value, str) or not text_path_value.strip():
        raise ValidationError(
            "binary document audit requires an exact UTF-8 visible-text projection"
        )
    text_path, text_bytes = _artifact_bytes(text_path_value)
    try:
        text_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError("audited text projection must be valid UTF-8") from exc
    if not isinstance(extraction_reference, str):
        raise ValidationError(
            "binary document audit requires a native content-extraction receipt"
        )
    producer = "pdf" if artifact_path.suffix.lower() == ".pdf" else "documents"
    domain = "pdf_content" if producer == "pdf" else "document_content"
    projection = resolve_current_receipt(
        extraction_reference,
        root=receipt_root,
        expected={
            "producer_skill": producer,
            "evidence_domain": domain,
            "status": "current_pass",
            "artifact_fingerprint": fingerprint_bytes(artifact_bytes),
        },
    )
    if not projection["current"] or projection["status"] != "current_pass":
        raise ValidationError("content extraction receipt is not current and passing")
    if projection["receipt"]["output_fingerprints"].get("audited_text") != fingerprint_bytes(
        text_bytes
    ):
        raise ValidationError(
            "content extraction receipt does not bind the supplied visible text"
        )
    return artifact_path, artifact_bytes, text_bytes, extraction_reference


def _visible_units(data: bytes) -> list[dict[str, Any]]:
    rows = extract_visible_units(data, namespace="artifact")
    units: list[dict[str, Any]] = []
    for row in rows:
        raw = data[row["byte_start"] : row["byte_end"]]
        units.append(
            {
                "unit_id": row["unit_id"],
                "kind": row["kind"],
                "locator": row["locator"],
                "content_fingerprint": row["content_fingerprint"],
                "text": raw.decode("utf-8").strip(),
            }
        )
    return units


def _text_position(units: list[Mapping[str, Any]], phrase: str) -> tuple[int, int] | None:
    needle = phrase.casefold()
    offset = 0
    for index, unit in enumerate(units):
        text = unit["text"]
        local = text.casefold().find(needle)
        if local >= 0:
            return index, offset + local
        offset += len(text) + 1
    return None


def _derive_audit(
    *,
    audit_id: str,
    artifact_locator: str,
    artifact_fingerprint: str,
    audited_text_fingerprint: str,
    artifact_extraction_receipt_fingerprint: str | None,
    audited_text_bytes: bytes,
    reader_brief: Mapping[str, Any],
    reader_brief_receipt_fingerprint: str,
) -> dict[str, Any]:
    brief = require_mapping(dict(reader_brief), "ReaderBrief")
    require_schema("reader-brief.schema.json", brief, label="ReaderBrief")
    brief_fingerprint = require_string(brief, "brief_fingerprint")
    if brief_fingerprint != fingerprint_without(brief, "brief_fingerprint"):
        raise ValidationError("ReaderBrief fingerprint does not match exact content")
    genre = require_string(brief, "genre")
    units = _visible_units(audited_text_bytes)
    full_text = "\n".join(item["text"] for item in units)
    findings: list[dict[str, Any]] = []
    reverse_outline: list[dict[str, Any]] = []
    for index, unit in enumerate(units):
        text = unit["text"]
        first = _first_sentence(text) or text[:240]
        next_text = units[index + 1]["text"] if index + 1 < len(units) else "terminal"
        carried = (
            "explicit"
            if re.search(
                r"\b(?:however|therefore|because|by contrast|in turn|因此|然而|相比之下|这意味着)\b",
                first,
                re.IGNORECASE,
            )
            else "implicit"
        )
        reverse_outline.append(
            {
                "unit_id": unit["unit_id"],
                "kind": unit["kind"],
                "purpose": first[:240],
                "old_information_link": carried,
                "next_handoff": (_first_sentence(next_text) or next_text)[:160],
            }
        )
        internal = set(contains_internal_language(text))
        internal.discard("snake_case")
        if internal:
            findings.append(_finding(unit, "internal_language", sorted(internal)))
        if index > 0 and VAGUE_OPENERS.search(first):
            findings.append(_finding(unit, "vague_referent_opener", "ambiguous opener"))
        if MECHANICAL.search(text):
            findings.append(_finding(unit, "mechanical_enumeration", "mechanical transition"))
        if DRAFT_PLACEHOLDER.search(text):
            findings.append(_finding(unit, "draft_placeholder", "unresolved visible placeholder"))
        if META_PROSE.search(text):
            findings.append(
                _finding(unit, "meta_prose", "artifact describes future writing instead of content")
            )
        if unit["kind"] == "paragraph" and len(text.split()) > 220:
            findings.append(_finding(unit, "overloaded_paragraph", "more than 220 words"))
        if unit["kind"] == "paragraph" and len(text) < 45:
            findings.append(
                _finding(unit, "underdeveloped_paragraph", "fewer than 45 characters")
            )

    nonheadings = [item for item in units if item["kind"] != "heading"]
    list_items = [item for item in nonheadings if item["kind"] == "list_item"]
    if nonheadings and PROSE_GENRES.search(genre) and len(list_items) / len(nonheadings) >= 0.5:
        findings.append(
            _finding(None, "outline_as_final", "prose genre is dominated by list items")
        )

    finding_by_id = {
        item["finding_id"]: item for item in brief["principal_findings"]
    }
    alternative_by_id = {
        item["alternative_id"]: item for item in brief["alternatives"]
    }
    limitation_by_id = {
        item["limitation_id"]: item for item in brief["limitations"]
    }
    target_text = {
        "finding": {key: item["text"] for key, item in finding_by_id.items()},
        "alternative": {key: item["text"] for key, item in alternative_by_id.items()},
        "limitation": {key: item["text"] for key, item in limitation_by_id.items()},
    }
    for citation in require_list(brief.get("required_citations"), "required_citations"):
        citation = require_mapping(citation, "required citation")
        marker = require_string(citation, "marker")
        supported = require_string(citation, "supported_wording")
        target_kind = require_string(citation, "target_kind")
        target_id = require_string(citation, "target_id")
        target = target_text.get(target_kind, {}).get(target_id)
        if target is None:
            raise ValidationError("ReaderBrief citation has an unknown target")
        adjacent = any(
            marker in unit["text"]
            and supported.casefold() in unit["text"].casefold()
            and target.casefold() in unit["text"].casefold()
            for unit in units
        )
        if not adjacent:
            findings.append(
                _finding(None, "citation_not_adjacent_to_target_wording", marker)
            )

    for phrase in require_list(brief.get("prohibited_wording"), "prohibited_wording"):
        if isinstance(phrase, str) and phrase.strip() and phrase.casefold() in full_text.casefold():
            findings.append(_finding(None, "prohibited_wording_used", phrase))
    for phrase in require_list(brief.get("allowed_wording"), "allowed_wording"):
        if not isinstance(phrase, str) or not phrase.strip():
            raise ValidationError("ReaderBrief allowed_wording contains an empty value")
        if phrase.casefold() not in full_text.casefold():
            findings.append(_finding(None, "allowed_boundary_missing", phrase))
    finding_positions: dict[str, tuple[int, int]] = {}
    for finding in finding_by_id.values():
        position = _text_position(units, require_string(finding, "text"))
        if position is None:
            findings.append(
                _finding(None, "principal_finding_missing", finding["finding_id"])
            )
        else:
            finding_positions[finding["finding_id"]] = position

    for limitation in limitation_by_id.values():
        position = _text_position(units, require_string(limitation, "text"))
        if position is None:
            findings.append(
                _finding(None, "limitation_missing", limitation["limitation_id"])
            )
            continue
        if limitation["placement"] == "near_claim":
            affected_positions = [
                finding_positions[item][0]
                for item in limitation["affected_finding_ids"]
                if item in finding_positions
            ]
            if affected_positions and min(
                abs(position[0] - item) for item in affected_positions
            ) > 1:
                findings.append(
                    _finding(
                        None,
                        "limitation_not_near_affected_claim",
                        limitation["limitation_id"],
                    )
                )

    sequence_positions: list[tuple[int, int]] = []
    for item in require_list(brief.get("information_sequence"), "information_sequence"):
        item = require_mapping(item, "information sequence item")
        if item.get("item_kind") != "finding":
            continue
        finding = finding_by_id.get(item.get("item_id"))
        if finding is None:
            raise ValidationError("information sequence refers to an unknown finding")
        position = _text_position(units, finding["text"])
        if position is None:
            findings.append(
                _finding(None, "information_sequence_item_missing", item.get("order"))
            )
        else:
            sequence_positions.append((item["order"], position[1]))
    ordered = [row[1] for row in sorted(sequence_positions)]
    if ordered != sorted(ordered):
        findings.append(
            _finding(None, "information_sequence_order_mismatch", "declared order differs")
        )

    licensed_strong_wording = [
        item.casefold()
        for item in brief.get("allowed_wording", [])
        if isinstance(item, str) and STRONG_CAUSAL.search(item)
    ]
    for unit in units:
        for sentence in SENTENCE.split(unit["text"]):
            if not STRONG_CAUSAL.search(sentence):
                continue
            normalized_sentence = sentence.casefold()
            licensed = any(
                wording in normalized_sentence for wording in licensed_strong_wording
            )
            if licensed or QUALIFIED.search(sentence) or NEGATED_CAUSAL.search(sentence):
                continue
            findings.append(
                _finding(
                    unit,
                    "scope_escalation",
                    "unlicensed causal certainty exceeds the ReaderBrief",
                )
            )

    concept_positions: list[tuple[int, int]] = []
    for concept in require_list(brief.get("concepts"), "concepts"):
        concept = require_mapping(concept, "concept")
        term = require_string(concept, "term")
        explanation = require_string(concept, "explanation")
        matching_units = [
            (index, unit)
            for index, unit in enumerate(units)
            if term.casefold() in unit["text"].casefold()
            and explanation.casefold() in unit["text"].casefold()
        ]
        if not matching_units:
            findings.append(
                _finding(None, "concept_not_explained_at_introduction", concept["concept_id"])
            )
        else:
            concept_positions.append(
                (concept["introduction_order"], matching_units[0][0])
            )
    ordered_concepts = [row[1] for row in sorted(concept_positions)]
    if ordered_concepts != sorted(ordered_concepts):
        findings.append(_finding(None, "concept_order_mismatch", "concept order differs"))

    hard_codes = {
        "internal_language",
        "draft_placeholder",
        "prohibited_wording_used",
        "principal_finding_missing",
        "allowed_boundary_missing",
        "limitation_missing",
        "citation_not_adjacent_to_target_wording",
        "limitation_not_near_affected_claim",
        "scope_escalation",
        "concept_not_explained_at_introduction",
    }
    status = (
        "passed"
        if not findings
        else "failed"
        if any(item["code"] in hard_codes for item in findings)
        else "partial"
    )
    audit: dict[str, Any] = {
        "schema_version": "1.0",
        "audit_id": audit_id,
        "artifact_locator": artifact_locator,
        "artifact_fingerprint": artifact_fingerprint,
        "audited_text_fingerprint": audited_text_fingerprint,
        "artifact_extraction_receipt_fingerprint": artifact_extraction_receipt_fingerprint,
        "reader_brief_fingerprint": brief_fingerprint,
        "reader_brief_receipt_fingerprint": reader_brief_receipt_fingerprint,
        "genre": genre,
        "visible_units": units,
        "reverse_outline": reverse_outline,
        "findings": findings,
        "status": status,
    }
    audit["audit_fingerprint"] = fingerprint_without(audit, "audit_fingerprint")
    require_schema("reader-audit.schema.json", audit, label="reader audit")
    return audit


def build_reader_audit_receipt(
    request: Mapping[str, Any],
    *,
    receipt_root: str | Path,
) -> dict[str, Any]:
    request = require_mapping(dict(request), "reader audit request")
    reject_unknown_keys(request, REQUEST_FIELDS, "reader audit request")
    if set(request) != REQUEST_FIELDS:
        raise ValidationError("reader audit request has a non-current shape")
    if require_string(request, "schema_version") != "1.0":
        raise ValidationError("schema_version must be 1.0")
    audit_id = require_string(request, "audit_id")
    brief = require_mapping(request.get("reader_brief"), "ReaderBrief")
    require_schema("reader-brief.schema.json", brief, label="ReaderBrief")
    brief_fingerprint = require_string(brief, "brief_fingerprint")
    if brief_fingerprint != fingerprint_without(brief, "brief_fingerprint"):
        raise ValidationError("ReaderBrief fingerprint does not match exact content")
    brief_receipt_fingerprint = require_string(
        request, "reader_brief_receipt_fingerprint"
    )
    projection = resolve_current_receipt(
        brief_receipt_fingerprint,
        root=receipt_root,
        expected={
            "producer_skill": "logic-writing",
            "semantic_owner_id": f"reader-brief:{require_string(brief, 'brief_id')}",
            "native_route": "build-reader-brief",
            "evidence_domain": "reader_brief",
            "status": "current_pass",
            "artifact_fingerprint": brief_fingerprint,
        },
    )
    if not projection["current"] or projection["status"] != "current_pass":
        raise ValidationError("ReaderBrief derivation receipt is not current and passing")
    if projection["receipt"]["output_fingerprints"].get("reader_brief") != brief_fingerprint:
        raise ValidationError("ReaderBrief receipt does not bind the supplied brief")
    brief_object_fingerprint = projection["receipt"]["output_fingerprints"].get(
        "reader_brief_object"
    )
    if not isinstance(brief_object_fingerprint, str) or resolve_content_object(
        brief_object_fingerprint, root=receipt_root
    ) != brief:
        raise ValidationError("ReaderBrief authority does not preserve this exact brief")

    artifact_path, artifact_bytes, text_bytes, extraction_reference = _audited_text(
        request,
        receipt_root=receipt_root,
    )
    artifact_fingerprint = fingerprint_bytes(artifact_bytes)
    audited_text_fingerprint = fingerprint_bytes(text_bytes)
    audit = _derive_audit(
        audit_id=audit_id,
        artifact_locator=str(artifact_path),
        artifact_fingerprint=artifact_fingerprint,
        audited_text_fingerprint=audited_text_fingerprint,
        artifact_extraction_receipt_fingerprint=extraction_reference,
        audited_text_bytes=text_bytes,
        reader_brief=brief,
        reader_brief_receipt_fingerprint=brief_receipt_fingerprint,
    )
    receipt_status = {
        "passed": "current_pass",
        "partial": "partial",
        "failed": "failed",
        "blocked": "blocked",
    }[audit["status"]]
    auditor_source = fingerprint_bytes(Path(__file__).read_bytes())
    audit_object_fingerprint = _store_content_object(audit, root=receipt_root)
    run_id = require_string(request, "run_id")
    dependencies = [brief_receipt_fingerprint]
    if extraction_reference is not None:
        dependencies.append(extraction_reference)
    receipt = _commit_managed_receipt(
        {
            "schema_version": "1.0",
            "producer_skill": "logic-writing",
            "semantic_owner_id": f"reader-audit:{audit_id}",
            "native_route": "audit-reader-output",
            "run_id": run_id,
            "covered_obligation_ids": ["reader.actual-artifact.deterministic"],
            "input_fingerprints": {
                f"reader-audit:{audit_id}:artifact": artifact_fingerprint,
                f"reader-audit:{audit_id}:audited-text": audited_text_fingerprint,
                f"reader-audit:{audit_id}:brief": brief_fingerprint,
                f"reader-audit:{audit_id}:brief-receipt": brief_receipt_fingerprint,
                f"reader-audit:{audit_id}:auditor": auditor_source,
            },
            "output_fingerprints": {
                "reader_audit": audit["audit_fingerprint"],
                "reader_audit_object": audit_object_fingerprint,
            },
            "artifact_fingerprint": artifact_fingerprint,
            "covered_scope": "all visible headings, paragraphs, list items, tables, and blockquotes in the exact delivered artifact",
            "evidence_domain": "reader_deterministic",
            "status": receipt_status,
            "safe_claim": "Deterministic reader findings apply only to this exact artifact and ReaderBrief.",
            "unsafe_claim_boundary": "This audit does not substitute for qualitative reader judgment.",
            "sequence_id": run_id,
            "dependency_receipt_fingerprints": dependencies,
        },
        root=receipt_root,
        builder_id="logic-writing.reader-deterministic.v1",
        source_fingerprint=fingerprint(
            {"audit": audit["audit_fingerprint"], "auditor_source": auditor_source}
        ),
    )
    return validation_result(status=receipt_status, audit=audit, receipt=receipt)


def audit_reader_output(
    value: Mapping[str, Any],
    *,
    receipt_root: str | Path,
) -> dict[str, Any]:
    return build_reader_audit_receipt(value, receipt_root=receipt_root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--receipt-root", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        result = build_reader_audit_receipt(
            load_json(args.input), receipt_root=args.receipt_root
        )
        dump_json(result, args.output)
        return 0 if result["status"] == "current_pass" else 1
    except (ValidationError, OSError, json.JSONDecodeError) as exc:
        dump_json(validation_result(status="blocked", errors=(str(exc),)), args.output)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["audit_reader_output", "build_reader_audit_receipt"]
