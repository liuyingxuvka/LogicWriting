from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from _common import fingerprint
from build_obligation_manifest import build_obligation_manifest
from derive_closure import derive_closure
from receipt_authority import resolve_current_receipt
from schema_validation import SUPPORTED_SCHEMA_NAMES, SchemaValidationError, assert_schema_valid
from tests.support import make_closure_contract, make_reader_chain, make_revision_chain


def _adapter_request() -> dict:
    artifact_fingerprint = fingerprint({"artifact": "schema-example"})
    value = {
        "schema_version": "1.0",
        "request_id": "request:schema-example",
        "task_id": "task:schema-example",
        "parent_route": "investigation",
        "native_owner": "logicguard",
        "native_route": "review-argument",
        "requested_scope": "Review one bounded conclusion.",
        "input_artifact_refs": [
            {
                "artifact_id": "artifact:schema-example",
                "artifact_kind": "research_packet",
                "fingerprint": artifact_fingerprint,
                "locator": None,
            }
        ],
        "input_fingerprints": {"artifact:schema-example": artifact_fingerprint},
        "claim_scope": "One conclusion and its evidence anchors.",
        "required_output_type": "argument_model",
        "freshness_baseline": {"artifact:schema-example": artifact_fingerprint},
        "user_constraints": [],
        "requested_at": "2026-07-14T12:00:00Z",
    }
    value["request_fingerprint"] = fingerprint(value)
    return value


@pytest.fixture(scope="module")
def schema_examples(tmp_path_factory):
    workdir = tmp_path_factory.mktemp("schema-examples")
    receipt_root = workdir / "receipts"
    reader = make_reader_chain(receipt_root, workdir)
    revision = make_revision_chain(receipt_root, workdir)
    brief_receipt = resolve_current_receipt(
        reader["brief_result"]["derivation_receipt_fingerprint"], root=receipt_root
    )["receipt"]
    contracted = [
        reader["observation_receipt"],
        reader["semantic_receipt"],
        brief_receipt,
        reader["audit_result"]["receipt"],
        reader["judgment_result"]["receipt"],
    ]
    contract = make_closure_contract(
        receipt_root,
        contracted,
        artifact_fingerprint=reader["artifact_fingerprint"],
        decision_id="decision:schema-closure",
    )
    manifest = build_obligation_manifest(
        {
            "contract_receipt_fingerprint": contract["contract_receipt"][
                "receipt_fingerprint"
            ]
        },
        root=receipt_root,
    )["manifest"]
    closure_result = derive_closure(
        {
            "contract_receipt_fingerprint": contract["contract_receipt"][
                "receipt_fingerprint"
            ]
        },
        receipt_root=receipt_root,
    )
    shared_path = workdir / "shared-writing.md"
    shared_path.write_text("The observed result narrows the decision boundary.", encoding="utf-8")
    shared_contract = {
        "schema_version": "1.0",
        "contract_id": "contract:schema-shared-writing",
        "final_owner": "investigation",
        "artifact_path": str(shared_path),
        "artifact_fingerprint": "sha256:" + hashlib.sha256(shared_path.read_bytes()).hexdigest(),
        "audience": "A decision maker",
        "purpose": "Explain the supported boundary",
        "incoming_reader_state": "The reader knows the question but not the evidence",
        "artifact_form": "report",
        "units": [{
            "unit_id": "unit:schema",
            "important": True,
            "contribution": "The evidence narrows the decision boundary",
            "incoming_reader_state": "The outcome is still open",
            "outgoing_reader_state": "One unsupported option is excluded",
            "unresolved_or_terminal": "The remaining option needs a later check",
            "downstream_consumer": "unit:decision compares the remaining option",
            "register_owner": "The observed source owns the result wording",
            "variation_effect": "This is the first contribution",
            "model_row_ids": ["row:schema"],
            "artifact_span": shared_path.read_text(encoding="utf-8"),
        }],
        "route_extension": {
            "owner": "investigation",
            "profile": "evidence",
            "required_surface_ids": ["surface:source-support"],
        },
    }
    shared_contract["contract_fingerprint"] = fingerprint(shared_contract)
    return {
        "adapter-request.schema.json": _adapter_request(),
        "adapter-result.schema.json": reader["observation_adapter_result"],
        "claim-support.schema.json": reader["ledger"],
        "closure.schema.json": closure_result["closure"],
        "obligation-manifest.schema.json": manifest,
        "reader-audit.schema.json": reader["audit_result"]["audit"],
        "reader-brief.schema.json": reader["brief"],
        "reader-judgment.schema.json": reader["judgment_result"]["judgment"],
        "evidence-receipt.schema.json": closure_result["receipt"],
        "research-packet.schema.json": reader["packet"],
        "revision-provenance.schema.json": revision["provenance_result"]["provenance"],
        "route-decision.schema.json": contract["route_decision"],
        "shared-writing-contract.schema.json": shared_contract,
        "source-registry.schema.json": reader["registry"],
        "source-unit-manifest.schema.json": revision["manifest"],
    }


def test_one_current_runtime_example_exists_for_every_schema(schema_examples):
    assert set(schema_examples) == set(SUPPORTED_SCHEMA_NAMES)
    for name in SUPPORTED_SCHEMA_NAMES:
        assert_schema_valid(name, schema_examples[name])


@pytest.mark.parametrize("schema_name", SUPPORTED_SCHEMA_NAMES)
def test_every_root_contract_rejects_unknown_fields(schema_examples, schema_name):
    value = copy.deepcopy(schema_examples[schema_name])
    value["former_runtime_alias"] = True

    with pytest.raises(SchemaValidationError, match="additionalProperties"):
        assert_schema_valid(schema_name, value)


def test_receipt_requires_stable_semantic_owner(schema_examples):
    value = copy.deepcopy(schema_examples["evidence-receipt.schema.json"])
    del value["semantic_owner_id"]

    with pytest.raises(SchemaValidationError, match="semantic_owner_id"):
        assert_schema_valid("evidence-receipt.schema.json", value)


def test_reader_brief_has_no_self_attested_reader_native_flag(schema_examples):
    value = copy.deepcopy(schema_examples["reader-brief.schema.json"])
    value["reader_native"] = True

    with pytest.raises(SchemaValidationError):
        assert_schema_valid("reader-brief.schema.json", value)


def test_revision_provenance_rejects_old_evidence_refs_field(schema_examples):
    value = copy.deepcopy(schema_examples["revision-provenance.schema.json"])
    entry = value["entries"][0]
    entry["evidence_refs"] = entry.pop("evidence_receipt_fingerprints")

    with pytest.raises(SchemaValidationError, match="evidence"):
        assert_schema_valid("revision-provenance.schema.json", value)


def test_research_packet_gap_is_structured_not_free_form(schema_examples):
    value = copy.deepcopy(schema_examples["research-packet.schema.json"])
    value["unresolved_gaps"] = ["more research needed"]

    with pytest.raises(SchemaValidationError):
        assert_schema_valid("research-packet.schema.json", value)


def test_all_schema_files_are_utf8_json_and_contain_no_retired_runtime_ids():
    root = (
        Path(__file__).resolve().parents[2]
        / "skills"
        / "logic-writing"
        / "assets"
        / "schemas"
    )
    forbidden = {
        "academic-thesis-revision-workflow",
        "research-investigation-workflow",
        '"receipt_id"',
        '"reader_native"',
    }
    for path in root.glob("*.schema.json"):
        text = path.read_text(encoding="utf-8")
        json.loads(text)
        assert not (forbidden & {item for item in forbidden if item in text})
