"""Build qualitative reader judgment authority from actual artifact excerpts."""

from __future__ import annotations

import argparse
import json
import re
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
    reject_unknown_keys,
    validation_result,
)
from build_source_unit_manifest import fingerprint_bytes, read_text_artifact
from receipt_authority import (
    _commit_managed_receipt,
    _store_content_object,
    resolve_content_object,
    resolve_current_receipt,
)


DIMENSIONS = {"clarity", "coherence", "reader_fit", "evidence_fidelity", "genre_fit"}
REQUEST_FIELDS = {
    "schema_version",
    "judgment_id",
    "artifact_path",
    "reader_brief",
    "reader_brief_receipt_fingerprint",
    "deterministic_receipt_fingerprint",
    "judge_id",
    "judge_kind",
    "judged_at",
    "rubric",
    "observations",
    "run_id",
}
JUDGMENT_FIELDS = {
    "schema_version",
    "judgment_id",
    "artifact_locator",
    "artifact_fingerprint",
    "reader_brief_fingerprint",
    "reader_brief_receipt_fingerprint",
    "deterministic_receipt_fingerprint",
    "actual_text_inspected",
    "genre",
    "judge_id",
    "judge_kind",
    "judged_at",
    "rubric",
    "observations",
    "status",
    "judgment_fingerprint",
}
LOCATOR = re.compile(r"^line:([1-9][0-9]*)(?:-([1-9][0-9]*))?$")


def _derived_judgment_status(rubric: Mapping[str, Any]) -> tuple[str, int]:
    rubric = require_mapping(rubric, "rubric")
    if set(rubric) != DIMENSIONS:
        raise ValidationError(f"rubric must contain exactly {sorted(DIMENSIONS)}")
    scores: list[int] = []
    for dimension, row in rubric.items():
        row = require_mapping(row, f"rubric.{dimension}")
        reject_unknown_keys(row, {"score", "reason"}, f"rubric.{dimension}")
        if set(row) != {"score", "reason"}:
            raise ValidationError(f"rubric.{dimension} has a non-current shape")
        score = row.get("score")
        if not isinstance(score, int) or not 1 <= score <= 5:
            raise ValidationError(f"rubric.{dimension}.score must be an integer from 1 to 5")
        require_string(row, "reason")
        scores.append(score)
    minimum = min(scores)
    return ("passed" if minimum >= 4 else "partial" if minimum >= 3 else "failed"), minimum


def _validate_observations(observations: Any, *, artifact_text: str) -> list[dict[str, Any]]:
    rows = require_list(observations, "observations")
    if not rows:
        raise ValidationError("observations must contain actual-artifact judgments")
    lines = artifact_text.splitlines()
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(rows):
        row = require_mapping(item, f"observation {index}")
        expected = {"observation_id", "dimension", "locator", "excerpt", "assessment"}
        reject_unknown_keys(row, expected, f"observation {index}")
        if set(row) != expected:
            raise ValidationError(f"observation {index} has a non-current shape")
        observation_id = require_string(row, "observation_id")
        if observation_id in seen:
            raise ValidationError("observation_id values must be unique")
        seen.add(observation_id)
        dimension = require_string(row, "dimension")
        if dimension not in DIMENSIONS:
            raise ValidationError(f"unsupported observation dimension: {dimension}")
        locator = require_string(row, "locator")
        match = LOCATOR.fullmatch(locator)
        if match is None:
            raise ValidationError("observation locator must use line:N or line:N-M")
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if end < start or end > len(lines):
            raise ValidationError(f"observation locator is outside the actual artifact: {locator}")
        excerpt = require_string(row, "excerpt")
        selected = "\n".join(lines[start - 1 : end])
        if excerpt not in selected:
            raise ValidationError(
                f"observation excerpt does not occur at its actual locator: {locator}"
            )
        require_string(row, "assessment")
        normalized.append(dict(row))
    covered_dimensions = {item["dimension"] for item in normalized}
    if covered_dimensions != DIMENSIONS:
        raise ValidationError(
            "observations must anchor every qualitative rubric dimension in the actual artifact"
        )
    return normalized


def validate_judgment_receipt(
    value: Any,
    *,
    artifact_path: str | Path,
    reader_brief: Mapping[str, Any],
    receipt_root: str | Path,
) -> dict[str, Any]:
    judgment = require_mapping(value, "reader judgment")
    if set(judgment) != JUDGMENT_FIELDS:
        raise ValidationError("reader judgment has a non-current shape")
    require_schema("reader-judgment.schema.json", judgment, label="reader judgment")
    artifact_locator, artifact_bytes, artifact_text = read_text_artifact(artifact_path)
    if judgment["artifact_locator"] != str(artifact_locator):
        raise ValidationError("reader judgment artifact locator is not the actual artifact")
    artifact_fingerprint = fingerprint_bytes(artifact_bytes)
    if judgment["artifact_fingerprint"] != artifact_fingerprint:
        raise ValidationError("reader judgment artifact fingerprint does not match actual bytes")
    if judgment.get("actual_text_inspected") is not True:
        raise ValidationError("actual_text_inspected must be true")
    brief = require_mapping(dict(reader_brief), "ReaderBrief")
    require_schema("reader-brief.schema.json", brief, label="ReaderBrief")
    brief_fingerprint = require_string(brief, "brief_fingerprint")
    if brief_fingerprint != fingerprint_without(brief, "brief_fingerprint"):
        raise ValidationError("ReaderBrief fingerprint does not match exact content")
    if judgment["reader_brief_fingerprint"] != brief_fingerprint:
        raise ValidationError("reader judgment does not bind the supplied ReaderBrief")
    if judgment["genre"] != brief["genre"]:
        raise ValidationError("reader judgment genre does not match the ReaderBrief")
    _validate_observations(judgment["observations"], artifact_text=artifact_text)
    derived, minimum = _derived_judgment_status(judgment["rubric"])
    if judgment["status"] != derived:
        raise ValidationError("reader judgment status is not rubric-derived")
    if judgment["judgment_fingerprint"] != fingerprint_without(
        judgment, "judgment_fingerprint"
    ):
        raise ValidationError("judgment_fingerprint does not match exact content")
    brief_receipt_fingerprint = require_string(
        judgment, "reader_brief_receipt_fingerprint"
    )
    brief_projection = resolve_current_receipt(
        brief_receipt_fingerprint,
        root=receipt_root,
        expected={
            "producer_skill": "logic-writing",
            "native_route": "build-reader-brief",
            "evidence_domain": "reader_brief",
            "status": "current_pass",
            "artifact_fingerprint": judgment["reader_brief_fingerprint"],
        },
    )
    if not brief_projection["current"] or brief_projection["status"] != "current_pass":
        raise ValidationError("reader judgment ReaderBrief receipt is not current and passing")
    if brief_projection["receipt"]["output_fingerprints"].get("reader_brief") != judgment["reader_brief_fingerprint"]:
        raise ValidationError("reader judgment ReaderBrief receipt does not bind the brief")
    brief_object_fingerprint = brief_projection["receipt"]["output_fingerprints"].get(
        "reader_brief_object"
    )
    if not isinstance(brief_object_fingerprint, str) or resolve_content_object(
        brief_object_fingerprint, root=receipt_root
    ) != brief:
        raise ValidationError("reader judgment ReaderBrief authority does not preserve this brief")
    deterministic_fingerprint = require_string(
        judgment, "deterministic_receipt_fingerprint"
    )
    deterministic = resolve_current_receipt(
        deterministic_fingerprint,
        root=receipt_root,
        expected={
            "producer_skill": "logic-writing",
            "native_route": "audit-reader-output",
            "evidence_domain": "reader_deterministic",
            "status": "current_pass",
            "artifact_fingerprint": artifact_fingerprint,
        },
    )
    if not deterministic["current"] or deterministic["status"] != "current_pass":
        raise ValidationError(
            "qualitative judgment requires a current passing deterministic audit"
        )
    if brief_receipt_fingerprint not in deterministic["receipt"]["dependency_receipt_fingerprints"]:
        raise ValidationError("deterministic receipt is not bound to the same ReaderBrief receipt")
    expected_brief_input = judgment["reader_brief_fingerprint"]
    if expected_brief_input not in deterministic["receipt"]["input_fingerprints"].values():
        raise ValidationError("deterministic receipt is not bound to the same ReaderBrief content")
    audit_object_fingerprint = deterministic["receipt"]["output_fingerprints"].get(
        "reader_audit_object"
    )
    if not isinstance(audit_object_fingerprint, str):
        raise ValidationError("deterministic receipt does not preserve its audit object")
    audit = require_mapping(
        resolve_content_object(audit_object_fingerprint, root=receipt_root),
        "reader audit object",
    )
    require_schema("reader-audit.schema.json", audit, label="reader audit")
    if (
        audit.get("artifact_fingerprint") != artifact_fingerprint
        or audit.get("reader_brief_fingerprint") != judgment["reader_brief_fingerprint"]
        or audit.get("reader_brief_receipt_fingerprint") != brief_receipt_fingerprint
        or audit.get("status") != "passed"
    ):
        raise ValidationError(
            "deterministic audit object does not bind the same artifact and ReaderBrief pass"
        )
    deterministic_status = deterministic["status"]
    outer_status = {
        "passed": "current_pass",
        "partial": "partial",
        "failed": "failed",
    }[derived]
    return validation_result(
        status=outer_status,
        judgment_status=derived,
        deterministic_status=deterministic_status,
        artifact_fingerprint=artifact_fingerprint,
        reader_brief_fingerprint=judgment["reader_brief_fingerprint"],
        minimum_score=minimum,
        judgment_fingerprint=judgment["judgment_fingerprint"],
    )


def build_judgment_receipt(
    request: Mapping[str, Any],
    *,
    receipt_root: str | Path,
) -> dict[str, Any]:
    request = require_mapping(request, "reader judgment build request")
    reject_unknown_keys(request, REQUEST_FIELDS, "reader judgment build request")
    if set(request) != REQUEST_FIELDS:
        raise ValidationError("reader judgment build request has a non-current shape")
    if require_string(request, "schema_version") != "1.0":
        raise ValidationError("schema_version must be 1.0")
    artifact_locator, artifact_bytes, artifact_text = read_text_artifact(
        require_string(request, "artifact_path")
    )
    brief = require_mapping(request.get("reader_brief"), "ReaderBrief")
    require_schema("reader-brief.schema.json", brief, label="ReaderBrief")
    brief_fingerprint = require_string(brief, "brief_fingerprint")
    if brief_fingerprint != fingerprint_without(brief, "brief_fingerprint"):
        raise ValidationError("ReaderBrief fingerprint does not match exact content")
    observations = _validate_observations(
        request.get("observations"), artifact_text=artifact_text
    )
    judgment_status, _minimum = _derived_judgment_status(
        require_mapping(request.get("rubric"), "rubric")
    )
    judgment: dict[str, Any] = {
        "schema_version": "1.0",
        "judgment_id": require_string(request, "judgment_id"),
        "artifact_locator": str(artifact_locator),
        "artifact_fingerprint": fingerprint_bytes(artifact_bytes),
        "reader_brief_fingerprint": brief_fingerprint,
        "reader_brief_receipt_fingerprint": require_string(
            request, "reader_brief_receipt_fingerprint"
        ),
        "deterministic_receipt_fingerprint": require_string(
            request, "deterministic_receipt_fingerprint"
        ),
        "actual_text_inspected": True,
        "genre": require_string(brief, "genre"),
        "judge_id": require_string(request, "judge_id"),
        "judge_kind": require_string(request, "judge_kind"),
        "judged_at": require_string(request, "judged_at"),
        "rubric": require_mapping(request.get("rubric"), "rubric"),
        "observations": observations,
        "status": judgment_status,
    }
    judgment["judgment_fingerprint"] = fingerprint_without(
        judgment, "judgment_fingerprint"
    )
    report = validate_judgment_receipt(
        judgment,
        artifact_path=artifact_locator,
        reader_brief=brief,
        receipt_root=receipt_root,
    )
    evaluator_source = fingerprint_bytes(Path(__file__).read_bytes())
    judgment_object_fingerprint = _store_content_object(
        judgment, root=receipt_root
    )
    run_id = require_string(request, "run_id")
    receipt = _commit_managed_receipt(
        {
            "schema_version": "1.0",
            "producer_skill": "logic-writing",
            "semantic_owner_id": f"reader-judgment:{judgment['judgment_id']}",
            "native_route": "judge-reader-output",
            "run_id": run_id,
            "covered_obligation_ids": ["reader.actual-artifact.judgment"],
            "input_fingerprints": {
                f"reader-judgment:{judgment['judgment_id']}:artifact": judgment["artifact_fingerprint"],
                f"reader-judgment:{judgment['judgment_id']}:brief": brief_fingerprint,
                f"reader-judgment:{judgment['judgment_id']}:deterministic": judgment["deterministic_receipt_fingerprint"],
                f"reader-judgment:{judgment['judgment_id']}:evaluator": evaluator_source,
            },
            "output_fingerprints": {
                "reader_judgment": judgment["judgment_fingerprint"],
                "reader_judgment_object": judgment_object_fingerprint,
            },
            "artifact_fingerprint": judgment["artifact_fingerprint"],
            "covered_scope": "the actual artifact excerpts, current ReaderBrief, deterministic audit, and qualitative rubric",
            "evidence_domain": "reader_judgment",
            "status": report["status"],
            "safe_claim": "The qualitative judgment is limited to the recorded actual excerpts and rubric.",
            "unsafe_claim_boundary": "A qualitative pass cannot override deterministic failure or stale evidence.",
            "sequence_id": run_id,
            "dependency_receipt_fingerprints": [
                judgment["reader_brief_receipt_fingerprint"],
                judgment["deterministic_receipt_fingerprint"],
            ],
        },
        root=receipt_root,
        builder_id="logic-writing.reader-judgment.v1",
        source_fingerprint=fingerprint(
            {
                "judgment": judgment["judgment_fingerprint"],
                "evaluator_source": evaluator_source,
            }
        ),
    )
    return validation_result(
        status=report["status"],
        judgment=judgment,
        validation=report,
        receipt=receipt,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--receipt-root", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        result = build_judgment_receipt(
            load_json(args.input), receipt_root=args.receipt_root
        )
        dump_json(result, args.output)
        return 0 if result["status"] == "current_pass" else 1
    except (ValidationError, OSError, json.JSONDecodeError) as exc:
        dump_json(validation_result(status="blocked", errors=(str(exc),)), args.output)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_judgment_receipt", "validate_judgment_receipt"]
