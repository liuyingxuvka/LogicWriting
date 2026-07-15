from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from _common import ValidationError, fingerprint_without
from audit_reader_output import build_reader_audit_receipt
from receipt_authority import resolve_current_receipt
from validate_judgment_receipt import build_judgment_receipt, validate_judgment_receipt


def _audit(chain: dict, receipt_root: Path, artifact_path: Path, *, audit_id: str) -> dict:
    return build_reader_audit_receipt(
        {
            "schema_version": "1.0",
            "audit_id": audit_id,
            "artifact_path": str(artifact_path),
            "audited_text_path": None,
            "artifact_extraction_receipt_fingerprint": None,
            "reader_brief": chain["brief"],
            "reader_brief_receipt_fingerprint": chain["brief_result"][
                "derivation_receipt_fingerprint"
            ],
            "run_id": f"run:{audit_id}",
        },
        receipt_root=receipt_root,
    )


def test_reader_brief_contains_reader_content_not_internal_workflow(reader_chain):
    rendered = json.dumps(reader_chain["brief"], ensure_ascii=False)

    for term in ("SourceGuard", "LogicGuard", "TraceGuard", "FlowGuard", "route_id", "current_pass"):
        assert term not in rendered
    assert reader_chain["brief"]["principal_findings"]
    assert reader_chain["brief"]["limitations"]
    assert reader_chain["brief"]["required_citations"]


def test_citation_binds_finding_source_anchor_and_visible_marker(reader_chain):
    brief = reader_chain["brief"]
    citation = brief["required_citations"][0]
    anchor = {
        item["anchor_id"]: item for item in brief["evidence_anchors"]
    }[citation["evidence_anchor_ids"][0]]

    assert citation["target_id"] == brief["principal_findings"][0]["finding_id"]
    assert citation["source_id"] == anchor["source_id"]
    assert citation["marker"] in reader_chain["artifact_text"]
    assert citation["supported_wording"] in reader_chain["artifact_text"]


def test_positive_actual_artifact_passes_deterministic_and_judged_checks(reader_chain):
    assert reader_chain["audit_result"]["status"] == "current_pass"
    assert reader_chain["audit_result"]["audit"]["status"] == "passed"
    assert reader_chain["audit_result"]["audit"]["visible_units"]
    assert reader_chain["audit_result"]["audit"]["reverse_outline"]
    assert reader_chain["judgment_result"]["status"] == "current_pass"
    assert reader_chain["judgment_result"]["judgment"]["actual_text_inspected"] is True


def test_negated_causal_limitation_is_not_a_false_overclaim(reader_chain):
    codes = {item["code"] for item in reader_chain["audit_result"]["audit"]["findings"]}

    assert "scope_escalation" not in codes
    assert "caused" in reader_chain["artifact_text"]
    assert "do not establish" in reader_chain["artifact_text"]


def test_unlicensed_strong_causal_sentence_is_rejected(reader_chain, receipt_root, tmp_path):
    path = tmp_path / "causal-overclaim.md"
    path.write_text(
        reader_chain["artifact_text"] + "\nThe intervention caused the change.\n",
        encoding="utf-8",
    )

    result = _audit(reader_chain, receipt_root, path, audit_id="audit:causal-overclaim")
    assert result["status"] == "failed"
    assert "scope_escalation" in {item["code"] for item in result["audit"]["findings"]}


def test_internal_agent_language_in_actual_prose_is_rejected(reader_chain, receipt_root, tmp_path):
    path = tmp_path / "internal-language.md"
    path.write_text(
        reader_chain["artifact_text"] + "\nFlowGuard reports that route_id reached current_pass.\n",
        encoding="utf-8",
    )

    result = _audit(reader_chain, receipt_root, path, audit_id="audit:internal-language")
    assert result["status"] == "failed"
    assert "internal_language" in {item["code"] for item in result["audit"]["findings"]}


def test_citation_marker_must_be_adjacent_to_supported_wording(reader_chain, receipt_root, tmp_path):
    citation = reader_chain["brief"]["required_citations"][0]
    path = tmp_path / "detached-citation.md"
    path.write_text(
        reader_chain["artifact_text"].replace(
            f" {citation['marker']} ",
            "\n\nThe source marker appears here instead: " + citation["marker"] + " ",
        ),
        encoding="utf-8",
    )

    result = _audit(reader_chain, receipt_root, path, audit_id="audit:detached-citation")
    assert result["status"] == "failed"
    assert "citation_not_adjacent_to_target_wording" in {
        item["code"] for item in result["audit"]["findings"]
    }


def test_concept_must_be_explained_at_its_introduction(reader_chain, receipt_root, tmp_path):
    path = tmp_path / "missing-concept-explanation.md"
    path.write_text(
        reader_chain["artifact_text"].replace(
            "the period covered by the available records",
            "an important period",
        ),
        encoding="utf-8",
    )

    result = _audit(reader_chain, receipt_root, path, audit_id="audit:concept-gap")
    assert result["status"] == "failed"
    assert "concept_not_explained_at_introduction" in {
        item["code"] for item in result["audit"]["findings"]
    }


def test_outline_does_not_count_as_finished_report(reader_chain, receipt_root, tmp_path):
    paragraph = reader_chain["artifact_text"].splitlines()[2]
    path = tmp_path / "outline.md"
    path.write_text(
        "# Outline\n\n- " + paragraph + "\n- Additional context belongs here.\n",
        encoding="utf-8",
    )

    result = _audit(reader_chain, receipt_root, path, audit_id="audit:outline")
    assert result["status"] == "partial"
    assert "outline_as_final" in {item["code"] for item in result["audit"]["findings"]}


def test_caller_cannot_self_attest_reader_native_quality(reader_chain, receipt_root):
    request = {
        "schema_version": "1.0",
        "audit_id": "audit:self-attested",
        "artifact_path": str(reader_chain["artifact_path"]),
        "audited_text_path": None,
        "artifact_extraction_receipt_fingerprint": None,
        "reader_brief": reader_chain["brief"],
        "reader_brief_receipt_fingerprint": reader_chain["brief_result"][
            "derivation_receipt_fingerprint"
        ],
        "run_id": "run:self-attested",
        "reader_native": True,
    }

    with pytest.raises(ValidationError, match="unsupported fields"):
        build_reader_audit_receipt(request, receipt_root=receipt_root)


def test_judgment_excerpt_must_exist_at_actual_locator(reader_chain, receipt_root):
    judgment = copy.deepcopy(reader_chain["judgment_result"]["judgment"])
    judgment["observations"][0]["excerpt"] = "Text that is not in the artifact"
    judgment["judgment_fingerprint"] = fingerprint_without(
        judgment, "judgment_fingerprint"
    )

    with pytest.raises(ValidationError, match="does not occur"):
        validate_judgment_receipt(
            judgment,
            artifact_path=reader_chain["artifact_path"],
            reader_brief=reader_chain["brief"],
            receipt_root=receipt_root,
        )


def test_material_edit_supersedes_prior_audit_for_same_owner(reader_chain, receipt_root, tmp_path):
    prior = reader_chain["audit_result"]["receipt"]
    path = tmp_path / "edited-reader-report.md"
    path.write_text(
        reader_chain["artifact_text"] + "\nFlowGuard route_id leaked into the prose.\n",
        encoding="utf-8",
    )
    edited = _audit(
        reader_chain,
        receipt_root,
        path,
        audit_id="audit:clinic-study:investigation",
    )

    prior_projection = resolve_current_receipt(prior["receipt_fingerprint"], root=receipt_root)
    assert edited["status"] == "failed"
    assert prior_projection["current"] is False
    assert prior_projection["status"] == "stale"


def test_judgment_cannot_override_failed_deterministic_audit(reader_chain, receipt_root, tmp_path):
    path = tmp_path / "bad-reader-report.md"
    path.write_text(
        reader_chain["artifact_text"] + "\nThe intervention caused the change.\n",
        encoding="utf-8",
    )
    audit = _audit(reader_chain, receipt_root, path, audit_id="audit:bad-for-judgment")
    request = {
        "schema_version": "1.0",
        "judgment_id": "judgment:bad-artifact",
        "artifact_path": str(path),
        "reader_brief": reader_chain["brief"],
        "reader_brief_receipt_fingerprint": reader_chain["brief_result"][
            "derivation_receipt_fingerprint"
        ],
        "deterministic_receipt_fingerprint": audit["receipt"]["receipt_fingerprint"],
        "judge_id": "judge:reader-review",
        "judge_kind": "model",
        "judged_at": "2026-07-14T12:05:00Z",
        "rubric": reader_chain["judgment_result"]["judgment"]["rubric"],
        "observations": [
            {
                **item,
                "locator": "line:3",
            }
            for item in reader_chain["judgment_result"]["judgment"]["observations"]
        ],
        "run_id": "run:judgment:bad-artifact",
    }

    with pytest.raises(ValidationError, match="deterministic|status"):
        build_judgment_receipt(request, receipt_root=receipt_root)
