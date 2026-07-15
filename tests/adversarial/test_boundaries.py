from __future__ import annotations

import copy
from pathlib import Path

import pytest

import provider_preflight
from _common import ValidationError, fingerprint
from audit_reader_output import build_reader_audit_receipt
from derive_closure import derive_closure
from tests.support import (
    commit_adapter,
    make_closure_contract,
    rebind_claim_semantics,
)
from validate_claim_support import validate_claim_support
from validate_research_packet import assemble_research_packet, validate_research_packet


def _audit(reader_chain: dict, receipt_root: Path, path: Path, audit_id: str) -> dict:
    return build_reader_audit_receipt(
        {
            "schema_version": "1.0",
            "audit_id": audit_id,
            "artifact_path": str(path),
            "audited_text_path": None,
            "artifact_extraction_receipt_fingerprint": None,
            "reader_brief": reader_chain["brief"],
            "reader_brief_receipt_fingerprint": reader_chain["brief_result"][
                "derivation_receipt_fingerprint"
            ],
            "run_id": f"run:{audit_id}",
        },
        receipt_root=receipt_root,
    )


def test_candidate_source_cannot_be_promoted_into_a_principal_fact(current_packet, receipt_root):
    registry = copy.deepcopy(current_packet["registry"])
    source = registry["sources"][0]
    source["observation_status"] = "candidate"
    source["can_support"] = []
    ledger = copy.deepcopy(current_packet["ledger"])
    ledger["source_registry_fingerprint"] = fingerprint(registry)
    rebind_claim_semantics(
        receipt_root,
        claim=ledger["claims"][0],
        registry=registry,
        observation_receipt_fingerprint=current_packet["observation_receipt"][
            "receipt_fingerprint"
        ],
    )

    report = validate_claim_support(ledger, registry, receipt_root=receipt_root)
    codes = {item["code"] for item in report["findings"]}
    assert report["status"] == "partial"
    assert report["eligible_principal_claim_ids"] == []
    assert {"claim_without_usable_source", "safe_wording_not_anchored_to_source"}.issubset(
        codes
    )


def test_chronology_cannot_be_relabelled_as_causality_without_trace(current_packet, receipt_root):
    ledger = copy.deepcopy(current_packet["ledger"])
    claim = ledger["claims"][0]
    claim["claim_type"] = "causal"
    claim["mechanism_source_ids"] = [claim["source_ids"][0]]
    _result, semantic = rebind_claim_semantics(
        receipt_root,
        claim=claim,
        registry=current_packet["registry"],
        observation_receipt_fingerprint=current_packet["observation_receipt"][
            "receipt_fingerprint"
        ],
    )
    packet = assemble_research_packet(
        {
            "schema_version": "1.0",
            "packet_id": "packet:chronology-not-causality",
            "request_fingerprint": fingerprint({"question": "Did A cause B?"}),
            "final_owner": "investigation",
            "source_registry": current_packet["registry"],
            "claim_support": ledger,
            "native_receipt_fingerprints": [
                current_packet["observation_receipt"]["receipt_fingerprint"],
                semantic["receipt_fingerprint"],
            ],
            "additional_unresolved_gaps": [],
        },
        receipt_root=receipt_root,
    )

    assert "missing_causal_trace" in {item["code"] for item in packet["unresolved_gaps"]}
    assert "Do not infer causation from chronology alone." in packet["unsafe_wording"]


def test_reader_native_metadata_cannot_make_bad_prose_pass(reader_chain, receipt_root, tmp_path):
    path = tmp_path / "metadata-false-positive.md"
    path.write_text(
        reader_chain["artifact_text"] + "\nThe reader_native flag says this route_id is complete.\n",
        encoding="utf-8",
    )
    result = _audit(reader_chain, receipt_root, path, "audit:metadata-false-positive")

    assert result["status"] == "failed"
    assert "internal_language" in {item["code"] for item in result["audit"]["findings"]}


def test_packet_becomes_invalid_when_source_owner_is_superseded(current_packet, receipt_root):
    old = current_packet["observation_adapter_result"]
    basis = copy.deepcopy(
        old["native_receipt"]["payload"]["evidence_payload"]["source_record_basis"]
    )
    changed = fingerprint({"source": "new bytes"})
    basis["observed_content_fingerprint"] = changed
    commit_adapter(
        receipt_root,
        owner="sourceguard",
        domain="source_observation",
        semantic_owner_id=old["semantic_owner_id"],
        native_route=old["native_route"],
        artifact_fingerprint=changed,
        input_fingerprints={"source:clinic-evaluation:content": changed},
        native_output_fingerprints={"source_observation": fingerprint(basis)},
        evidence_payload={"source_record_basis": basis},
        covered_obligation_ids=old["covered_obligation_ids"],
        run_id="run:source-superseded",
        request_id="request:source-superseded",
    )

    with pytest.raises(ValidationError, match="projection|authoritative"):
        validate_research_packet(current_packet["packet"], receipt_root=receipt_root)


def test_material_edit_makes_same_owner_audit_stale(reader_chain, receipt_root, tmp_path):
    prior = reader_chain["audit_result"]["receipt"]
    changed = tmp_path / "changed.md"
    changed.write_text(
        reader_chain["artifact_text"] + "\nThe intervention caused the change.\n",
        encoding="utf-8",
    )
    latest = _audit(
        reader_chain,
        receipt_root,
        changed,
        "audit:clinic-study:investigation",
    )

    from receipt_authority import resolve_current_receipt

    projection = resolve_current_receipt(prior["receipt_fingerprint"], root=receipt_root)
    assert latest["status"] == "failed"
    assert projection["current"] is False
    assert projection["status"] == "stale"


def test_missing_renderer_stays_render_not_run(monkeypatch, tmp_path):
    skill_root = tmp_path / "documents"
    skill_root.mkdir()
    (skill_root / "SKILL.md").write_text(
        "---\nname: documents\ndescription: Work with docx files and render pages.\n---\n\n# Documents\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(provider_preflight.shutil, "which", lambda _name: None)

    result = provider_preflight.preflight(
        "documents", provider_root=str(skill_root), require_render=True
    )
    assert result["status"] == "render_not_run"
    assert result["evidence"]["renderer_available"] is False


def test_outline_with_all_keywords_still_is_not_finished_prose(reader_chain, receipt_root, tmp_path):
    paragraph = reader_chain["artifact_text"].splitlines()[2]
    path = tmp_path / "keyword-complete-outline.md"
    path.write_text(
        "# Draft outline\n\n- " + paragraph + "\n- A second bullet keeps this as an outline.\n",
        encoding="utf-8",
    )
    result = _audit(reader_chain, receipt_root, path, "audit:outline-adversarial")

    assert result["status"] == "partial"
    assert "outline_as_final" in {item["code"] for item in result["audit"]["findings"]}


def test_process_green_content_not_run_cannot_issue_final_closure(tmp_path):
    receipt_root = tmp_path / "receipts"
    artifact = fingerprint({"artifact": "not-reviewed"})
    outputs = {"process_complete": fingerprint({"process": "green"})}
    _adapter, process_receipt = commit_adapter(
        receipt_root,
        owner="flowguard",
        domain="process_model",
        semantic_owner_id="process:green-only",
        native_route="simulate-process",
        artifact_fingerprint=artifact,
        input_fingerprints={"process_input": artifact},
        native_output_fingerprints=outputs,
        evidence_payload={
            "observed_artifact_fingerprint": artifact,
            "validated_output_fingerprints": outputs,
        },
        covered_obligation_ids=["process.green"],
    )
    contract = make_closure_contract(
        receipt_root,
        [process_receipt],
        artifact_fingerprint=artifact,
        decision_id="decision:process-green-only",
    )

    result = derive_closure(
        {
            "contract_receipt_fingerprint": contract["contract_receipt"][
                "receipt_fingerprint"
            ]
        },
        receipt_root=receipt_root,
    )
    assert result["status"] == "blocked"
    assert {item["obligation_id"] for item in result["closure"]["residual_risk"]} >= {
        "final.source_observation",
        "final.argument_model",
        "final.reader_judgment",
    }


def test_old_research_packet_shape_has_no_fallback_reader(receipt_root):
    old = {
        "schema_version": "0.9",
        "research_packet_id": "legacy-packet",
        "sources": [],
        "claims": [],
        "complete": True,
    }

    with pytest.raises(ValidationError, match="unsupported fields"):
        validate_research_packet(old, receipt_root=receipt_root)
