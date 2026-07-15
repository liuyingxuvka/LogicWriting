from __future__ import annotations

import copy
from pathlib import Path

import pytest

from _common import ValidationError, fingerprint_without
from derive_closure import derive_closure
from provider_preflight import preflight
from receipt_authority import resolve_current_receipt
from select_route import select_route
from tests.support import (
    make_closure_contract,
    make_current_packet,
    make_reader_chain,
    make_revision_chain,
)
from validate_revision_provenance import validate_revision_provenance


def test_academic_route_keeps_final_ownership_when_research_is_needed():
    decision = select_route(
        {
            "request_id": "request:academic-owner",
            "decision_id": "decision:academic-owner",
            "decided_at": "2026-07-14T12:00:00Z",
            "terminal_deliverable": {
                "kind": "thesis_chapter",
                "description": "A revised thesis chapter",
                "acceptance_criteria": ["The evidence gap is resolved."],
            },
            "scope_class": "substantive",
            "substantial_research_required": True,
            "constraints": {},
            "material_assumptions": [],
        }
    )

    assert decision["final_owner"] == "academic-writing"
    assert decision["child_routes"] == ["investigation"]


def test_academic_research_packet_has_gap_identity_and_keeps_owner(receipt_root):
    chain = make_current_packet(receipt_root, final_owner="academic-writing")

    assert chain["packet"]["status"] == "current_pass"
    assert chain["packet"]["gap_id"] == "gap:clinic-evidence"
    assert chain["packet"]["final_owner"] == "academic-writing"


def test_revision_provenance_accounts_for_every_real_source_and_target_unit(revision_chain, receipt_root):
    result = revision_chain["provenance_result"]
    manifest = revision_chain["manifest"]

    assert result["status"] == "current_pass"
    assert set(result["validation"]["accounted_source_units"]) == {
        item["unit_id"] for item in manifest["source"]["units"]
    }
    assert set(result["validation"]["accounted_target_units"]) == {
        item["unit_id"] for item in manifest["target"]["units"]
    }


def test_provenance_cannot_omit_a_visible_source_unit(revision_chain, receipt_root):
    provenance = copy.deepcopy(revision_chain["provenance_result"]["provenance"])
    provenance["entries"] = provenance["entries"][:-1]
    provenance["provenance_fingerprint"] = fingerprint_without(
        provenance, "provenance_fingerprint"
    )

    with pytest.raises(ValidationError, match="source-unit universe mismatch"):
        validate_revision_provenance(
            provenance,
            source_unit_manifest=revision_chain["manifest"],
            source_path=revision_chain["source_path"],
            target_path=revision_chain["target_path"],
            receipt_root=receipt_root,
        )


def test_provenance_rejects_evidence_that_does_not_cover_exact_unit(revision_chain, receipt_root):
    provenance = copy.deepcopy(revision_chain["provenance_result"]["provenance"])
    provenance["entries"][0]["evidence_receipt_fingerprints"] = [
        revision_chain["manifest_result"]["receipt"]["receipt_fingerprint"]
    ]
    provenance["provenance_fingerprint"] = fingerprint_without(
        provenance, "provenance_fingerprint"
    )

    with pytest.raises(ValidationError, match="lacks evidence bound"):
        validate_revision_provenance(
            provenance,
            source_unit_manifest=revision_chain["manifest"],
            source_path=revision_chain["source_path"],
            target_path=revision_chain["target_path"],
            receipt_root=receipt_root,
        )


def test_unresolved_revision_unit_is_visible_as_partial(revision_chain, receipt_root):
    provenance = copy.deepcopy(revision_chain["provenance_result"]["provenance"])
    provenance["entries"][0]["treatment"] = "human_review"
    provenance["entries"][0]["next_owner"] = "human_review"
    provenance["provenance_fingerprint"] = fingerprint_without(
        provenance, "provenance_fingerprint"
    )

    report = validate_revision_provenance(
        provenance,
        source_unit_manifest=revision_chain["manifest"],
        source_path=revision_chain["source_path"],
        target_path=revision_chain["target_path"],
        receipt_root=receipt_root,
    )
    assert report["status"] == "partial"
    assert provenance["entries"][0]["source_unit_id"] in report[
        "incomplete_source_units"
    ]


def test_editing_source_bytes_invalidates_manifest_binding(revision_chain, receipt_root):
    revision_chain["source_path"].write_text(
        "# Changed source\n\nThe bytes changed after the manifest was issued.\n",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="manifest"):
        validate_revision_provenance(
            revision_chain["provenance_result"]["provenance"],
            source_unit_manifest=revision_chain["manifest"],
            source_path=revision_chain["source_path"],
            target_path=revision_chain["target_path"],
            receipt_root=receipt_root,
        )


def test_missing_document_provider_is_visible_not_improvised(tmp_path: Path):
    result = preflight("documents", provider_root=str(tmp_path / "missing"))

    assert result["status"] == "provider_unavailable"
    assert result["claim_boundary"] == "provider or render dependency is not currently available"
    assert str(tmp_path) not in str(result["evidence"])


def test_structure_evidence_cannot_hide_missing_academic_domains(tmp_path: Path):
    receipt_root = tmp_path / "receipts"
    revision = make_revision_chain(receipt_root, tmp_path)
    contract = make_closure_contract(
        receipt_root,
        [revision["provenance_result"]["receipt"]],
        artifact_fingerprint=revision["manifest"]["target"]["artifact_fingerprint"],
        final_owner="academic-writing",
        broad_claim_requested=True,
        decision_id="decision:academic-broad",
    )

    result = derive_closure(
        {
            "contract_receipt_fingerprint": contract["contract_receipt"][
                "receipt_fingerprint"
            ]
        },
        receipt_root=receipt_root,
    )
    missing_domains = {item["evidence_domain"] for item in result["closure"]["residual_risk"]}
    assert result["status"] == "blocked"
    assert {"model_depth", "citation_semantics", "reader_judgment"}.issubset(
        missing_domains
    )


def test_academic_closure_binds_revision_and_reader_chain(tmp_path: Path):
    receipt_root = tmp_path / "receipts"
    reader = make_reader_chain(receipt_root, tmp_path)
    revision = make_revision_chain(receipt_root, tmp_path)
    brief_receipt = resolve_current_receipt(
        reader["brief_result"]["derivation_receipt_fingerprint"], root=receipt_root
    )["receipt"]
    receipts = [
        reader["observation_receipt"],
        reader["semantic_receipt"],
        revision["provenance_result"]["receipt"],
        brief_receipt,
        reader["audit_result"]["receipt"],
        reader["judgment_result"]["receipt"],
    ]
    contract = make_closure_contract(
        receipt_root,
        receipts,
        artifact_fingerprint=reader["artifact_fingerprint"],
        final_owner="academic-writing",
        decision_id="decision:academic-pass",
    )

    result = derive_closure(
        {
            "contract_receipt_fingerprint": contract["contract_receipt"][
                "receipt_fingerprint"
            ]
        },
        receipt_root=receipt_root,
    )
    assert result["status"] == "passed"
    assert result["closure"]["final_owner"] == "academic-writing"
    assert revision["provenance_result"]["receipt"]["receipt_fingerprint"] in result[
        "closure"
    ]["matched_receipt_fingerprints"]
