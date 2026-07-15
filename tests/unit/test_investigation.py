from __future__ import annotations

import copy

import pytest

from _common import ValidationError, fingerprint
from validate_claim_support import validate_claim_support
from validate_research_packet import assemble_research_packet, validate_research_packet
from validate_source_registry import validate_source_registry
from tests.support import rebind_claim_semantics


def test_current_source_registry_requires_observed_native_authority(current_packet, receipt_root):
    report = validate_source_registry(current_packet["registry"], receipt_root=receipt_root)

    assert report["status"] == "current_pass"
    assert report["usable_source_ids"] == ["source:clinic-evaluation"]
    assert report["observation_receipt_fingerprints"] == [
        current_packet["observation_receipt"]["receipt_fingerprint"]
    ]


def test_candidate_is_never_promoted_to_claim_usable(current_packet, receipt_root):
    registry = copy.deepcopy(current_packet["registry"])
    source = registry["sources"][0]
    source["observation_status"] = "candidate"
    source["observed_content_fingerprint"] = None
    source["observation_receipt_fingerprint"] = None
    source["anchors"] = []
    source["can_support"] = []

    report = validate_source_registry(registry, receipt_root=receipt_root)
    assert report["status"] == "partial"
    assert report["usable_source_ids"] == []
    assert {item["code"] for item in report["findings"]} == {"source_not_claim_usable"}


def test_claim_support_binds_source_role_anchor_and_semantic_receipt(current_packet, receipt_root):
    report = validate_claim_support(
        current_packet["ledger"],
        current_packet["registry"],
        receipt_root=receipt_root,
    )

    assert report["status"] == "current_pass"
    assert report["eligible_principal_claim_ids"] == ["claim:wait-time"]
    assert report["findings"] == []


def test_strong_claim_requires_independent_lineages(current_packet, receipt_root):
    ledger = copy.deepcopy(current_packet["ledger"])
    claim = ledger["claims"][0]
    claim["strength"] = "strong"
    rebind_claim_semantics(
        receipt_root,
        claim=claim,
        registry=current_packet["registry"],
        observation_receipt_fingerprint=current_packet["observation_receipt"][
            "receipt_fingerprint"
        ],
    )

    report = validate_claim_support(
        ledger, current_packet["registry"], receipt_root=receipt_root
    )
    codes = {item["code"] for item in report["findings"]}
    assert "insufficient_independent_lineages" in codes
    assert report["eligible_principal_claim_ids"] == []


def test_every_declared_source_needs_an_observed_anchor(current_packet, receipt_root):
    ledger = copy.deepcopy(current_packet["ledger"])
    ledger["claims"][0]["support_links"] = []

    with pytest.raises(ValidationError, match="support_links|minItems"):
        validate_claim_support(
            ledger, current_packet["registry"], receipt_root=receipt_root
        )


def test_causal_claim_without_trace_is_a_structured_gap(current_packet, receipt_root):
    ledger = copy.deepcopy(current_packet["ledger"])
    claim = ledger["claims"][0]
    claim["claim_type"] = "causal"
    claim["mechanism_source_ids"] = ["source:clinic-evaluation"]
    _semantic_result, semantic_receipt = rebind_claim_semantics(
        receipt_root,
        claim=claim,
        registry=current_packet["registry"],
        observation_receipt_fingerprint=current_packet["observation_receipt"][
            "receipt_fingerprint"
        ],
    )
    request = {
        "schema_version": "1.0",
        "packet_id": "packet:causal-gap",
        "request_fingerprint": fingerprint({"question": "Did it cause the change?"}),
        "final_owner": "investigation",
        "source_registry": current_packet["registry"],
        "claim_support": ledger,
        "native_receipt_fingerprints": [
            current_packet["observation_receipt"]["receipt_fingerprint"],
            semantic_receipt["receipt_fingerprint"],
        ],
        "additional_unresolved_gaps": [],
    }

    packet = assemble_research_packet(request, receipt_root=receipt_root)
    codes = {item["code"] for item in packet["unresolved_gaps"]}
    assert packet["status"] == "partial"
    assert "missing_causal_trace" in codes


def test_research_packet_is_derived_from_exact_members(current_packet, receipt_root):
    packet = current_packet["packet"]

    assert packet["status"] == "current_pass"
    assert packet["unresolved_gaps"] == []
    assert validate_research_packet(packet, receipt_root=receipt_root) == packet


def test_packet_cannot_hide_an_observation_receipt(current_packet, receipt_root):
    packet = copy.deepcopy(current_packet["packet"])
    packet["native_receipts"] = packet["native_receipts"][1:]
    packet["member_fingerprints"] = {
        "source_registry": fingerprint(packet["source_registry"]),
        "claim_support": fingerprint(packet["claim_support"]),
        "native_receipt:0": packet["native_receipts"][0]["receipt_fingerprint"],
    }
    packet["packet_fingerprint"] = fingerprint(
        {key: value for key, value in packet.items() if key != "packet_fingerprint"}
    )

    with pytest.raises(ValidationError, match="omits verifier-derived gaps"):
        validate_research_packet(packet, receipt_root=receipt_root)


def test_academic_handoff_without_gap_identity_remains_partial(current_packet, receipt_root):
    request = {
        "schema_version": "1.0",
        "packet_id": "packet:academic-gap",
        "request_fingerprint": fingerprint({"question": "Evidence for the paper"}),
        "final_owner": "academic-writing",
        "source_registry": current_packet["registry"],
        "claim_support": current_packet["ledger"],
        "native_receipt_fingerprints": [
            current_packet["observation_receipt"]["receipt_fingerprint"],
            current_packet["semantic_receipt"]["receipt_fingerprint"],
        ],
        "additional_unresolved_gaps": [],
    }

    packet = assemble_research_packet(request, receipt_root=receipt_root)
    assert packet["status"] == "partial"
    assert {item["code"] for item in packet["unresolved_gaps"]} == {"missing_gap_id"}
    assert packet["final_owner"] == "academic-writing"


def test_caller_cannot_write_packet_status_or_safe_wording(current_packet, receipt_root):
    request = {
        "schema_version": "1.0",
        "packet_id": "packet:caller-status",
        "request_fingerprint": fingerprint({"question": "Caller status"}),
        "final_owner": "investigation",
        "source_registry": current_packet["registry"],
        "claim_support": current_packet["ledger"],
        "native_receipt_fingerprints": [],
        "additional_unresolved_gaps": [],
        "status": "current_pass",
        "safe_wording": ["Everything passed."],
    }

    with pytest.raises(ValidationError, match="unsupported fields"):
        assemble_research_packet(request, receipt_root=receipt_root)
