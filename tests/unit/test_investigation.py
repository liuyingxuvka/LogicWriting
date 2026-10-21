from __future__ import annotations

import copy

import pytest

from _common import ValidationError, fingerprint
from validate_claim_support import validate_claim_support
from validate_research_packet import assemble_research_packet, validate_research_packet
from validate_source_registry import validate_source_registry


def test_current_source_registry_reports_usable_sources(current_packet):
    report = validate_source_registry(current_packet["registry"])

    assert report["status"] == "current_pass"
    assert report["usable_source_ids"] == ["source:clinic-evaluation"]



def test_candidate_is_never_promoted_to_claim_usable(current_packet):
    registry = copy.deepcopy(current_packet["registry"])
    source = registry["sources"][0]
    source["observation_status"] = "candidate"
    source["observed_content_fingerprint"] = None
    source["anchors"] = []
    source["can_support"] = []

    report = validate_source_registry(registry)
    assert report["status"] == "partial"
    assert report["usable_source_ids"] == []
    assert {item["code"] for item in report["findings"]} == {"source_not_claim_usable"}


def test_claim_support_binds_source_role_and_anchor(current_packet):
    report = validate_claim_support(
        current_packet["ledger"],
        current_packet["registry"],

    )

    assert report["status"] == "current_pass"
    assert report["eligible_principal_claim_ids"] == ["claim:wait-time"]
    assert report["findings"] == []


def test_strong_claim_requires_independent_lineages(current_packet):
    ledger = copy.deepcopy(current_packet["ledger"])
    claim = ledger["claims"][0]
    claim["strength"] = "strong"


    report = validate_claim_support(
        ledger, current_packet["registry"]
    )
    codes = {item["code"] for item in report["findings"]}
    assert "insufficient_independent_lineages" in codes
    assert report["eligible_principal_claim_ids"] == []


def test_every_declared_source_needs_an_observed_anchor(current_packet):
    ledger = copy.deepcopy(current_packet["ledger"])
    ledger["claims"][0]["support_links"] = []

    with pytest.raises(ValidationError, match="support_links|minItems"):
        validate_claim_support(
            ledger, current_packet["registry"]
        )




def test_research_packet_is_derived_from_exact_members(current_packet):
    packet = current_packet["packet"]

    assert packet["status"] == "current_pass"
    assert packet["unresolved_gaps"] == []
    assert validate_research_packet(packet) == packet




def test_academic_handoff_without_gap_identity_remains_partial(current_packet):
    request = {
        "schema_version": "1.0",
        "packet_id": "packet:academic-gap",
        "request_fingerprint": fingerprint({"question": "Evidence for the paper"}),
        "final_owner": "academic-writing",
        "source_registry": current_packet["registry"],
        "claim_support": current_packet["ledger"],
        "additional_unresolved_gaps": [],
    }

    packet = assemble_research_packet(request)
    assert packet["status"] == "partial"
    assert {item["code"] for item in packet["unresolved_gaps"]} == {"missing_gap_id"}
    assert packet["final_owner"] == "academic-writing"


def test_caller_cannot_write_packet_status_or_safe_wording(current_packet):
    request = {
        "schema_version": "1.0",
        "packet_id": "packet:caller-status",
        "request_fingerprint": fingerprint({"question": "Caller status"}),
        "final_owner": "investigation",
        "source_registry": current_packet["registry"],
        "claim_support": current_packet["ledger"],
        "additional_unresolved_gaps": [],
        "status": "current_pass",
        "safe_wording": ["Everything passed."],
    }

    with pytest.raises(ValidationError, match="unsupported fields"):
        assemble_research_packet(request)


@pytest.mark.parametrize("parent", ["fiction-writing", "travel-guide"])
def test_fiction_and_travel_parents_receive_a_bounded_gap_packet(current_packet, parent):
    request = {
        "schema_version": "1.0",
        "packet_id": f"packet:{parent}-gap",
        "request_fingerprint": fingerprint({"question": f"Evidence gap for {parent}"}),
        "final_owner": parent,
        "gap_id": f"gap:{parent}",
        "source_registry": current_packet["registry"],
        "claim_support": current_packet["ledger"],
        "additional_unresolved_gaps": [],
    }

    packet = assemble_research_packet(request)
    assert packet["final_owner"] == parent
    assert packet["status"] == "current_pass"


def test_packet_assembly_fills_request_and_registry_fingerprints(current_packet, tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path

    ledger = copy.deepcopy(current_packet["ledger"])
    del ledger["source_registry_fingerprint"]
    request = {
        "schema_version": "1.0",
        "packet_id": "packet:no-hashes",
        "final_owner": "investigation",
        "source_registry": "registry.json",
        "claim_support": "ledger.json",
        "additional_unresolved_gaps": [],
    }
    (tmp_path / "registry.json").write_text(json.dumps(current_packet["registry"]), encoding="utf-8")
    (tmp_path / "ledger.json").write_text(json.dumps(ledger), encoding="utf-8")
    (tmp_path / "request.json").write_text(json.dumps(request), encoding="utf-8")
    scripts = Path(__file__).resolve().parents[2] / "skills" / "logic-writing" / "scripts"
    run = subprocess.run([sys.executable, str(scripts / "validate_research_packet.py"), "--input", str(tmp_path / "request.json")],
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
    packet = json.loads(run.stdout)
    assert packet["status"] == "current_pass"
    assert packet["claim_support"]["source_registry_fingerprint"] == fingerprint(current_packet["registry"])
    checked = subprocess.run([sys.executable, str(scripts / "validate_claim_support.py"), "--input", str(tmp_path / "ledger.json"),
                              "--source-registry", str(tmp_path / "registry.json")], capture_output=True, text=True)
    assert checked.returncode == 0, checked.stdout + checked.stderr
