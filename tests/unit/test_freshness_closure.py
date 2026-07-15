from __future__ import annotations

import copy
from pathlib import Path

import pytest

from _common import ValidationError, fingerprint
from derive_closure import derive_closure
from receipt_authority import resolve_current_receipt
from tests.support import (
    commit_adapter,
    make_closure_contract,
    make_obligation,
    make_reader_chain,
)


def _reader_receipts(reader_chain: dict, receipt_root: Path) -> list[dict]:
    brief = resolve_current_receipt(
        reader_chain["brief_result"]["derivation_receipt_fingerprint"],
        root=receipt_root,
    )["receipt"]
    return [
        reader_chain["observation_receipt"],
        reader_chain["semantic_receipt"],
        brief,
        reader_chain["audit_result"]["receipt"],
        reader_chain["judgment_result"]["receipt"],
    ]


def test_current_exact_reader_chain_can_close(reader_chain, receipt_root):
    contract = make_closure_contract(
        receipt_root,
        _reader_receipts(reader_chain, receipt_root),
        artifact_fingerprint=reader_chain["artifact_fingerprint"],
        decision_id="decision:reader-pass",
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
    assert result["closure"]["residual_risk"] == []
    assert result["closure"]["terminal"] is True
    assert result["closure"]["broad_claim_allowed"] is False


def test_caller_cannot_supply_status_receipts_or_prior_attempts(reader_chain, receipt_root):
    contract = make_closure_contract(
        receipt_root,
        [reader_chain["observation_receipt"]],
        artifact_fingerprint=reader_chain["artifact_fingerprint"],
        decision_id="decision:caller-fields",
    )
    request = {
        "contract_receipt_fingerprint": contract["contract_receipt"][
            "receipt_fingerprint"
        ],
        "status": "passed",
        "receipt_fingerprints": [reader_chain["observation_receipt"]["receipt_fingerprint"]],
        "prior_attempt_fingerprints": [],
    }

    with pytest.raises(ValidationError, match="accepts only"):
        derive_closure(request, receipt_root=receipt_root)


def test_missing_semantic_owner_is_not_run_and_blocks_critical_scope(reader_chain, receipt_root):
    obligation = make_obligation(reader_chain["observation_receipt"])
    obligation["semantic_owner_id"] = "source-observation:missing-source"
    obligation["obligation_id"] = "source.missing-observation"
    contract = make_closure_contract(
        receipt_root,
        [],
        artifact_fingerprint=reader_chain["artifact_fingerprint"],
        decision_id="decision:missing-owner",
        obligation_rows=[obligation],
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
    assert result["closure"]["residual_risk"][0]["status"] == "not_run"


def test_broad_investigation_claim_requires_all_baseline_domains(reader_chain, receipt_root):
    contract = make_closure_contract(
        receipt_root,
        [reader_chain["observation_receipt"]],
        artifact_fingerprint=reader_chain["artifact_fingerprint"],
        broad_claim_requested=True,
        decision_id="decision:broad-investigation",
    )

    result = derive_closure(
        {
            "contract_receipt_fingerprint": contract["contract_receipt"][
                "receipt_fingerprint"
            ]
        },
        receipt_root=receipt_root,
    )
    domains = {item["evidence_domain"] for item in result["closure"]["residual_risk"]}
    assert result["status"] == "blocked"
    assert {"source_depth", "argument_model", "reader_judgment"}.issubset(domains)
    assert result["closure"]["broad_claim_allowed"] is False


@pytest.mark.parametrize(
    ("native_status", "critical", "expected"),
    [
        ("bounded", False, "downgraded"),
        ("partial", False, "partial"),
        ("provider_unavailable", True, "blocked"),
    ],
)
def test_weakest_current_obligation_controls_closure(
    tmp_path: Path, native_status: str, critical: bool, expected: str
):
    receipt_root = tmp_path / "receipts"
    reader = make_reader_chain(receipt_root, tmp_path)
    baseline_receipts = _reader_receipts(reader, receipt_root)
    artifact_fingerprint = fingerprint({"artifact": native_status})
    native_outputs = {"depth_result": fingerprint({"status": native_status})}
    _adapter, receipt = commit_adapter(
        receipt_root,
        owner="sourceguard",
        domain="source_depth",
        semantic_owner_id=f"source-depth:{native_status}",
        native_route="review-source-depth",
        artifact_fingerprint=artifact_fingerprint,
        input_fingerprints={"source_portfolio": artifact_fingerprint},
        native_output_fingerprints=native_outputs,
        evidence_payload={
            "observed_artifact_fingerprint": artifact_fingerprint,
            "validated_output_fingerprints": native_outputs,
        },
        covered_obligation_ids=[f"source.depth.{native_status}"],
        status=native_status,
    )
    obligation = make_obligation(receipt)
    obligation["critical"] = critical
    obligation_rows = [make_obligation(item) for item in baseline_receipts]
    obligation_rows.append(obligation)
    contract = make_closure_contract(
        receipt_root,
        [*baseline_receipts, receipt],
        artifact_fingerprint=reader["artifact_fingerprint"],
        decision_id=f"decision:{native_status}",
        obligation_rows=obligation_rows,
    )

    result = derive_closure(
        {
            "contract_receipt_fingerprint": contract["contract_receipt"][
                "receipt_fingerprint"
            ]
        },
        receipt_root=receipt_root,
    )
    assert result["status"] == expected
    assert result["closure"]["residual_risk"][0]["status"] == native_status


def test_partial_reader_chain_cannot_close_without_judgment(reader_chain, receipt_root):
    receipts = _reader_receipts(reader_chain, receipt_root)[:-1]
    contract = make_closure_contract(
        receipt_root,
        receipts,
        artifact_fingerprint=reader_chain["artifact_fingerprint"],
        decision_id="decision:reader-no-judgment",
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
    assert "closure.reader-chain.cardinality" in {
        item["obligation_id"] for item in result["closure"]["residual_risk"]
    }


def test_contract_output_must_match_latest_exact_owner_result(reader_chain, receipt_root):
    old = reader_chain["observation_receipt"]
    contract = make_closure_contract(
        receipt_root,
        [old],
        artifact_fingerprint=reader_chain["artifact_fingerprint"],
        decision_id="decision:old-output",
    )
    old_result = reader_chain["observation_adapter_result"]
    basis = copy.deepcopy(
        old_result["native_receipt"]["payload"]["evidence_payload"]["source_record_basis"]
    )
    changed_artifact = fingerprint({"source": "changed"})
    basis["observed_content_fingerprint"] = changed_artifact
    _new_adapter, new_receipt = commit_adapter(
        receipt_root,
        owner="sourceguard",
        domain="source_observation",
        semantic_owner_id=old["semantic_owner_id"],
        native_route=old["native_route"],
        artifact_fingerprint=changed_artifact,
        input_fingerprints={"source:clinic-evaluation:content": changed_artifact},
        native_output_fingerprints={"source_observation": fingerprint(basis)},
        evidence_payload={"source_record_basis": basis},
        covered_obligation_ids=old["covered_obligation_ids"],
        run_id="run:changed-source",
        request_id="request:changed-source",
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
    assert new_receipt["receipt_fingerprint"] not in result["closure"][
        "matched_receipt_fingerprints"
    ]


def test_repeated_identical_failure_becomes_terminal_no_progress(reader_chain, receipt_root):
    obligation = make_obligation(reader_chain["observation_receipt"])
    obligation["semantic_owner_id"] = "source-observation:never-produced"
    obligation["obligation_id"] = "source.never-produced"
    contract = make_closure_contract(
        receipt_root,
        [],
        artifact_fingerprint=reader_chain["artifact_fingerprint"],
        decision_id="decision:no-progress-unit",
        obligation_rows=[obligation],
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
