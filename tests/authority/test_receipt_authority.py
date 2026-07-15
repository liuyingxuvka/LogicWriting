from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from _common import ValidationError, fingerprint
from derive_closure import derive_closure
from receipt_authority import (
    resolve_content_object,
    resolve_current_receipt,
    resolve_latest_receipt_by_owner,
)
from receipt_store import store_receipt
from tests.support import make_adapter_result, make_closure_contract, make_reader_chain
from validate_adapter_result import build_adapter_receipt


def _failed_successor(chain: dict, receipt_root: Path) -> tuple[dict, dict]:
    prior_result = chain["observation_adapter_result"]
    basis = prior_result["native_receipt"]["payload"]["evidence_payload"]
    result = make_adapter_result(
        owner="sourceguard",
        domain="source_observation",
        semantic_owner_id=prior_result["semantic_owner_id"],
        native_route=prior_result["native_route"],
        artifact_fingerprint=fingerprint({"changed": "source bytes"}),
        input_fingerprints={
            "source:clinic-evaluation:content": fingerprint({"changed": "source bytes"})
        },
        native_output_fingerprints={"source_observation": fingerprint(basis["source_record_basis"])},
        evidence_payload=basis,
        covered_obligation_ids=prior_result["covered_obligation_ids"],
        status="failed",
        run_id="run:sourceguard:source-observation:failed",
        request_id="request:sourceguard:source-observation:failed",
    )
    # A source-observation payload must bind its observed artifact. This failed
    # successor therefore carries a changed, internally consistent basis.
    changed_basis = copy.deepcopy(basis["source_record_basis"])
    changed_basis["observed_content_fingerprint"] = result["artifact_fingerprint"]
    result = make_adapter_result(
        owner="sourceguard",
        domain="source_observation",
        semantic_owner_id=prior_result["semantic_owner_id"],
        native_route=prior_result["native_route"],
        artifact_fingerprint=result["artifact_fingerprint"],
        input_fingerprints=result["input_fingerprints"],
        native_output_fingerprints={"source_observation": fingerprint(changed_basis)},
        evidence_payload={"source_record_basis": changed_basis},
        covered_obligation_ids=prior_result["covered_obligation_ids"],
        status="failed",
        run_id="run:sourceguard:source-observation:failed",
        request_id="request:sourceguard:source-observation:failed",
    )
    return result, build_adapter_receipt(result, root=receipt_root)


def test_managed_receipt_is_authoritative_and_current(current_packet, receipt_root):
    receipt = current_packet["observation_receipt"]
    projection = resolve_current_receipt(receipt["receipt_fingerprint"], root=receipt_root)

    assert projection["authoritative"] is True
    assert projection["current"] is True
    assert projection["status"] == "current_pass"
    assert projection["receipt"] == receipt


def test_preserved_adapter_object_is_content_addressed(current_packet, receipt_root):
    receipt = current_packet["semantic_receipt"]
    object_fingerprint = receipt["output_fingerprints"]["adapter_result_object"]

    assert resolve_content_object(object_fingerprint, root=receipt_root) == current_packet[
        "semantic_adapter_result"
    ]


def test_public_authority_api_does_not_export_generic_commit_or_input_rewind():
    import receipt_authority

    assert "_commit_managed_receipt" not in receipt_authority.__all__
    assert "_record_current_inputs" not in receipt_authority.__all__
    assert "current_inputs" not in resolve_current_receipt.__code__.co_varnames


def test_untrusted_store_cannot_create_authority(current_packet, tmp_path):
    untrusted_root = tmp_path / "untrusted-only"
    failed = copy.deepcopy(current_packet["observation_receipt"])
    failed["status"] = "failed"
    failed["receipt_fingerprint"] = fingerprint(
        {key: value for key, value in failed.items() if key != "receipt_fingerprint"}
    )

    stored = store_receipt(failed, untrusted_root)
    assert stored["authoritative"] is False
    with pytest.raises(ValidationError, match="not registered"):
        resolve_current_receipt(failed["receipt_fingerprint"], root=untrusted_root)


def test_latest_failed_attempt_supersedes_older_pass(current_packet, receipt_root):
    old_receipt = current_packet["observation_receipt"]
    _result, failed = _failed_successor(current_packet, receipt_root)

    old_projection = resolve_current_receipt(old_receipt["receipt_fingerprint"], root=receipt_root)
    latest = resolve_latest_receipt_by_owner(
        producer_skill="sourceguard",
        semantic_owner_id=old_receipt["semantic_owner_id"],
        evidence_domain="source_observation",
        root=receipt_root,
    )

    assert old_projection["current"] is False
    assert old_projection["status"] == "stale"
    assert latest["receipt_fingerprint"] == failed["receipt_fingerprint"]
    assert latest["current"] is True
    assert latest["status"] == "failed"


def test_dependency_becomes_stale_when_owner_is_superseded(current_packet, receipt_root):
    semantic = current_packet["semantic_receipt"]
    _failed_result, _failed = _failed_successor(current_packet, receipt_root)

    projection = resolve_current_receipt(semantic["receipt_fingerprint"], root=receipt_root)
    assert projection["current"] is False
    assert any(reason.startswith("dependency_not_current:") for reason in projection["reasons"])


def test_attestation_tampering_is_rejected(current_packet, receipt_root):
    fingerprint_value = current_packet["observation_receipt"]["receipt_fingerprint"]
    digest = fingerprint_value.split(":", 1)[1]
    path = receipt_root / "authority" / "attestations" / f"{digest}.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["receipt_content_fingerprint"] = fingerprint({"tampered": True})
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ValidationError, match="attestation"):
        resolve_current_receipt(fingerprint_value, root=receipt_root)


def test_receipt_object_tampering_is_rejected(current_packet, receipt_root):
    fingerprint_value = current_packet["observation_receipt"]["receipt_fingerprint"]
    digest = fingerprint_value.split(":", 1)[1]
    path = receipt_root / "objects" / f"{digest}.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["safe_claim"] = "Tampered claim"
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ValidationError, match="fingerprint"):
        resolve_current_receipt(fingerprint_value, root=receipt_root)


def test_index_rollback_with_extra_objects_is_rejected(current_packet, receipt_root):
    index_path = receipt_root / "authority" / "index.json"
    old_index = index_path.read_text(encoding="utf-8")
    _failed_result, _failed = _failed_successor(current_packet, receipt_root)
    index_path.write_text(old_index, encoding="utf-8")

    with pytest.raises(ValidationError, match="rollback|omission"):
        resolve_current_receipt(
            current_packet["observation_receipt"]["receipt_fingerprint"],
            root=receipt_root,
        )


def test_closure_resolves_latest_owner_not_caller_selected_old_pass(tmp_path):
    receipt_root = tmp_path / "receipts"
    chain = make_reader_chain(receipt_root, tmp_path)
    from receipt_authority import resolve_current_receipt as resolve

    brief_receipt = resolve(
        chain["brief_result"]["derivation_receipt_fingerprint"], root=receipt_root
    )["receipt"]
    contracted = [
        chain["observation_receipt"],
        chain["semantic_receipt"],
        brief_receipt,
        chain["audit_result"]["receipt"],
        chain["judgment_result"]["receipt"],
    ]
    contract = make_closure_contract(
        receipt_root,
        contracted,
        artifact_fingerprint=chain["artifact_fingerprint"],
    )
    _failed_result, failed = _failed_successor(chain, receipt_root)

    result = derive_closure(
        {
            "contract_receipt_fingerprint": contract["contract_receipt"][
                "receipt_fingerprint"
            ]
        },
        receipt_root=receipt_root,
    )

    assert result["status"] == "blocked"
    assert chain["observation_receipt"]["receipt_fingerprint"] not in result["closure"][
        "matched_receipt_fingerprints"
    ]
    assert failed["receipt_fingerprint"] not in result["closure"][
        "matched_receipt_fingerprints"
    ]


def test_identical_failed_closure_stops_with_no_progress(tmp_path):
    receipt_root = tmp_path / "receipts"
    chain = make_reader_chain(receipt_root, tmp_path)
    contract = make_closure_contract(
        receipt_root,
        [chain["observation_receipt"]],
        artifact_fingerprint=chain["artifact_fingerprint"],
        broad_claim_requested=True,
        decision_id="decision:no-progress",
    )
    request = {
        "contract_receipt_fingerprint": contract["contract_receipt"][
            "receipt_fingerprint"
        ]
    }

    first = derive_closure(request, receipt_root=receipt_root)
    second = derive_closure(request, receipt_root=receipt_root)

    assert first["status"] == "blocked"
    assert second["status"] == "no_progress_blocked"
    assert second["closure"]["terminal"] is True
