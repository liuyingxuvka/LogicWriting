from __future__ import annotations

import pytest

from _common import ValidationError, fingerprint
from propagate_staleness import propagate_staleness


def _node(receipt_id: str, *, plane: str, inputs: dict, dependencies=()):
    return {
        "receipt_fingerprint": receipt_id,
        "plane": plane,
        "status": "current_pass",
        "input_fingerprints": inputs,
        "dependency_receipt_fingerprints": list(dependencies),
    }


def test_changed_input_stales_only_its_explicit_descendants():
    source = fingerprint({"receipt": "source"})
    argument = fingerprint({"receipt": "argument"})
    release = fingerprint({"receipt": "release"})
    old_source = fingerprint({"source": "old"})
    request = {
        "schema_version": "1.0",
        "current_inputs": {
            "source": fingerprint({"source": "new"}),
            "release-source": fingerprint({"release": "same"}),
        },
        "nodes": [
            _node(source, plane="agent_operation", inputs={"source": old_source}),
            _node(
                argument,
                plane="agent_operation",
                inputs={"source": old_source},
                dependencies=[source],
            ),
            _node(
                release,
                plane="development_process",
                inputs={"release-source": fingerprint({"release": "same"})},
            ),
        ],
    }

    result = propagate_staleness(request)
    assert result["stale_receipt_fingerprints"] == sorted([source, argument])
    assert result["current_receipt_fingerprints"] == [release]
    assert result["cross_plane_stale_edges"] == []


def test_cross_plane_staleness_requires_a_declared_edge():
    operation = fingerprint({"receipt": "operation"})
    release = fingerprint({"receipt": "release"})
    request = {
        "schema_version": "1.0",
        "current_inputs": {"artifact": fingerprint({"artifact": "new"})},
        "nodes": [
            _node(
                operation,
                plane="agent_operation",
                inputs={"artifact": fingerprint({"artifact": "old"})},
            ),
            _node(
                release,
                plane="development_process",
                inputs={"artifact": fingerprint({"artifact": "old"})},
                dependencies=[operation],
            ),
        ],
    }

    result = propagate_staleness(request)
    assert len(result["cross_plane_stale_edges"]) == 1
    assert result["cross_plane_stale_edges"][0]["dependent_receipt_fingerprint"] == release


def test_cycle_blocks_projection_instead_of_guessing():
    left = fingerprint({"receipt": "left"})
    right = fingerprint({"receipt": "right"})
    current = fingerprint({"input": "same"})
    request = {
        "schema_version": "1.0",
        "current_inputs": {"input": current},
        "nodes": [
            _node(left, plane="agent_operation", inputs={"input": current}, dependencies=[right]),
            _node(right, plane="agent_operation", inputs={"input": current}, dependencies=[left]),
        ],
    }

    result = propagate_staleness(request)
    assert result["status"] == "blocked"
    assert result["cycles"]


def test_unknown_dependency_is_rejected():
    value = {
        "schema_version": "1.0",
        "current_inputs": {"input": fingerprint({"input": 1})},
        "nodes": [
            _node(
                fingerprint({"receipt": 1}),
                plane="agent_operation",
                inputs={"input": fingerprint({"input": 1})},
                dependencies=[fingerprint({"missing": 1})],
            )
        ],
    }

    with pytest.raises(ValidationError, match="unknown dependency"):
        propagate_staleness(value)


def test_authority_backed_nodes_must_match_immutable_original(current_packet, receipt_root):
    receipts = [
        current_packet["observation_receipt"],
        current_packet["semantic_receipt"],
    ]
    current_inputs = {
        key: value
        for receipt in receipts
        for key, value in receipt["input_fingerprints"].items()
    }
    value = {
        "schema_version": "1.0",
        "current_inputs": current_inputs,
        "nodes": [
            {
                "receipt_fingerprint": receipt["receipt_fingerprint"],
                "plane": "agent_operation",
                "status": receipt["status"],
                "input_fingerprints": receipt["input_fingerprints"],
                "dependency_receipt_fingerprints": receipt[
                    "dependency_receipt_fingerprints"
                ],
            }
            for receipt in receipts
        ],
    }

    result = propagate_staleness(value, receipt_root=receipt_root)
    assert result["stale_receipt_fingerprints"] == []
    assert set(result["authority_projection_fingerprints"]) == {
        receipt["receipt_fingerprint"] for receipt in receipts
    }


def test_old_receipt_id_shape_has_no_compatibility_reader():
    value = {
        "schema_version": "1.0",
        "current_inputs": {"input": fingerprint({"input": 1})},
        "nodes": [
            {
                "receipt_id": "old-id",
                "plane": "agent_operation",
                "status": "current_pass",
                "input_manifest": {"input": fingerprint({"input": 1})},
                "depends_on": [],
            }
        ],
    }

    with pytest.raises(ValidationError, match="unsupported fields"):
        propagate_staleness(value)
