from __future__ import annotations

import copy
from pathlib import Path

import pytest

from _common import DEGRADED_STATUSES, ValidationError, fingerprint, fingerprint_without
from tests.support import make_adapter_result, make_closure_contract, make_current_packet
from validate_adapter_request import validate_adapter_request
from validate_adapter_result import validate_adapter_result


def _request(*, owner: str = "logicguard", parent: str = "investigation") -> dict:
    artifact_fingerprint = fingerprint({"artifact": "one"})
    value = {
        "schema_version": "1.0",
        "request_id": "adapter-request:one",
        "task_id": "task:one",
        "parent_route": parent,
        "native_owner": owner,
        "native_route": "review-structure",
        "requested_scope": "Review the declared artifact structure.",
        "input_artifact_refs": [
            {
                "artifact_id": "artifact:one",
                "artifact_kind": "report",
                "fingerprint": artifact_fingerprint,
                "locator": None,
            }
        ],
        "input_fingerprints": {"artifact:one": artifact_fingerprint},
        "claim_scope": "Only the supplied report.",
        "required_output_type": "structured_review",
        "freshness_baseline": {"artifact:one": artifact_fingerprint},
        "user_constraints": [
            {
                "constraint_id": "constraint:language",
                "kind": "language",
                "value": "English",
            }
        ],
        "requested_at": "2026-07-14T12:00:00Z",
    }
    value["request_fingerprint"] = fingerprint(value)
    return value


def _generic_result(
    *,
    owner: str,
    domain: str,
    artifact_path: Path | None = None,
    status: str = "current_pass",
) -> dict:
    artifact_fingerprint = (
        "sha256:" + __import__("hashlib").sha256(artifact_path.read_bytes()).hexdigest()
        if artifact_path is not None
        else fingerprint({"owner": owner, "domain": domain})
    )
    native_outputs = {"native_result": fingerprint({"domain": domain, "status": status})}
    return make_adapter_result(
        owner=owner,
        domain=domain,
        semantic_owner_id=f"semantic-owner:{owner}:{domain}",
        native_route=f"native-route:{domain}",
        artifact_fingerprint=artifact_fingerprint,
        input_fingerprints={"artifact": artifact_fingerprint},
        native_output_fingerprints=native_outputs,
        evidence_payload={
            "observed_artifact_fingerprint": artifact_fingerprint,
            "validated_output_fingerprints": native_outputs,
        },
        covered_obligation_ids=[f"adapter.{owner}.{domain}"],
        artifact_refs=[str(artifact_path)] if artifact_path is not None else [],
        status=status,
    )


def test_adapter_request_accepts_current_exact_shape():
    result = validate_adapter_request(_request())

    assert result["status"] == "current_pass"
    assert result["native_owner"] == "logicguard"


def test_academic_gap_request_preserves_parent_ownership():
    value = _request(owner="sourceguard", parent="academic-writing")
    value["gap_contract"] = {
        "gap_id": "gap:method-evidence",
        "affected_claim_ids": ["claim:method"],
        "affected_artifact_units": ["section:method"],
        "required_evidence_roles": ["method"],
        "required_strength": "supported",
        "access_policy": "public_only",
        "safe_interim_wording": "The method description remains provisional.",
        "unsafe_claim_boundary": "Do not present the method as validated.",
    }
    value["request_fingerprint"] = fingerprint_without(value, "request_fingerprint")

    result = validate_adapter_request(value)
    assert result["parent_route"] == "academic-writing"


def test_adapter_request_rejects_unknown_owner():
    value = _request(owner="invented-guard")
    value["request_fingerprint"] = fingerprint_without(value, "request_fingerprint")

    with pytest.raises(ValidationError, match="native_owner|unsupported"):
        validate_adapter_request(value)


@pytest.mark.parametrize(
    ("owner", "domain"),
    [
        ("sourceguard", "source_depth"),
        ("logicguard", "structured_artifact"),
        ("traceguard", "temporal_trace"),
        ("flowguard", "process_freshness"),
    ],
)
def test_generic_native_owner_envelopes_bind_actual_outputs(owner: str, domain: str):
    result = validate_adapter_result(_generic_result(owner=owner, domain=domain))

    assert result["status"] == "current_pass"
    assert result["native_status"] == "current_pass"


@pytest.mark.parametrize(("owner", "domain"), [("documents", "document_content"), ("pdf", "pdf_content")])
def test_document_adapters_bind_real_artifact_bytes(tmp_path: Path, owner: str, domain: str):
    artifact = tmp_path / ("artifact.docx" if owner == "documents" else "artifact.pdf")
    artifact.write_bytes(b"exact artifact bytes")

    result = validate_adapter_result(
        _generic_result(owner=owner, domain=domain, artifact_path=artifact)
    )
    assert result["contributes_to_pass"] is True


@pytest.mark.parametrize("status", sorted(DEGRADED_STATUSES))
def test_every_degraded_state_remains_visible(status: str):
    value = _generic_result(owner="sourceguard", domain="source_depth", status=status)

    report = validate_adapter_result(value)
    assert report["status"] == "current_pass"
    assert report["native_status"] == status
    assert report["contributes_to_pass"] is False


def test_opaque_native_payload_is_rejected():
    value = _generic_result(owner="logicguard", domain="structured_artifact")
    value["native_receipt"]["payload"]["evidence_payload"] = {"opaque": fingerprint({"x": 1})}
    value["native_receipt"]["fingerprint"] = fingerprint_without(
        value["native_receipt"], "fingerprint"
    )
    value["output_fingerprints"]["native_receipt"] = value["native_receipt"]["fingerprint"]
    value["adapter_result_fingerprint"] = fingerprint_without(
        value, "adapter_result_fingerprint"
    )

    with pytest.raises(ValidationError, match="payload|bind"):
        validate_adapter_result(value)


def test_owner_cannot_claim_another_specialist_domain():
    value = _generic_result(owner="logicguard", domain="structured_artifact")
    value["evidence_domain"] = "source_depth"
    value["native_receipt"]["receipt_type"] = "logicguard.source_depth.v1"
    value["native_receipt"]["payload"]["evidence_domain"] = "source_depth"
    value["native_receipt"]["fingerprint"] = fingerprint_without(
        value["native_receipt"], "fingerprint"
    )
    value["output_fingerprints"]["native_receipt"] = value["native_receipt"]["fingerprint"]
    value["adapter_result_fingerprint"] = fingerprint_without(
        value, "adapter_result_fingerprint"
    )

    with pytest.raises(ValidationError, match="does not own"):
        validate_adapter_result(value)


def test_document_receipt_rejects_different_bytes(tmp_path: Path):
    artifact = tmp_path / "artifact.docx"
    artifact.write_bytes(b"first bytes")
    value = _generic_result(
        owner="documents", domain="document_content", artifact_path=artifact
    )
    artifact.write_bytes(b"changed bytes")

    with pytest.raises(ValidationError, match="actual artifact bytes"):
        validate_adapter_result(value)


def test_source_observation_cannot_be_an_arbitrary_self_hash(current_packet):
    value = copy.deepcopy(current_packet["observation_adapter_result"])
    value["native_receipt"]["payload"]["output_fingerprints"]["source_observation"] = fingerprint(
        {"unrelated": True}
    )
    value["native_receipt"]["fingerprint"] = fingerprint_without(
        value["native_receipt"], "fingerprint"
    )
    value["output_fingerprints"] = {
        **value["native_receipt"]["payload"]["output_fingerprints"],
        "native_receipt": value["native_receipt"]["fingerprint"],
    }
    value["adapter_result_fingerprint"] = fingerprint_without(
        value, "adapter_result_fingerprint"
    )

    with pytest.raises(ValidationError, match="exact source record"):
        validate_adapter_result(value)


def test_claim_semantics_must_consume_exact_registry(current_packet):
    value = copy.deepcopy(current_packet["semantic_adapter_result"])
    value["native_receipt"]["payload"]["evidence_payload"][
        "source_registry_fingerprint"
    ] = fingerprint({"different": "registry"})
    value["native_receipt"]["fingerprint"] = fingerprint_without(
        value["native_receipt"], "fingerprint"
    )
    value["output_fingerprints"]["native_receipt"] = value["native_receipt"]["fingerprint"]
    value["adapter_result_fingerprint"] = fingerprint_without(
        value, "adapter_result_fingerprint"
    )

    with pytest.raises(ValidationError, match="SourceRegistry"):
        validate_adapter_result(value)


def test_flowguard_closure_contract_binds_route_and_obligations(receipt_root, current_packet):
    contract = make_closure_contract(
        receipt_root,
        [current_packet["observation_receipt"]],
        artifact_fingerprint=fingerprint({"artifact": "closure"}),
    )

    report = validate_adapter_result(contract["adapter_result"])
    assert report["native_owner"] == "flowguard"
    assert contract["adapter_result"]["native_receipt"]["payload"]["evidence_payload"][
        "route_decision"
    ]["final_owner"] == "investigation"
