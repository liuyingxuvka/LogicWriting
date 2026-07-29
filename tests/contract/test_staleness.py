from __future__ import annotations

import pytest

from _common import ValidationError, fingerprint
from propagate_staleness import propagate_staleness


def request(*, changed: str | None = None):
    current = {
        "reader_intent": fingerprint({"intent": 1}),
        "artifact_bytes": fingerprint({"artifact": 1}),
        "native_receipts": fingerprint({"native": 1}),
    }
    observed = dict(current)
    if changed:
        observed[changed] = fingerprint({changed: 2})
    return {
        "schema_version": "2.0",
        "current_inputs": current,
        "observed_inputs": observed,
        "records": [
            {"record_id": "composition", "consumes": ["reader_intent"], "depends_on": []},
            {"record_id": "artifact_map", "consumes": ["artifact_bytes"], "depends_on": []},
            {"record_id": "shared_writing", "consumes": [], "depends_on": ["composition", "artifact_map"]},
            {"record_id": "audit", "consumes": [], "depends_on": ["shared_writing"]},
            {"record_id": "route_review", "consumes": ["native_receipts"], "depends_on": ["artifact_map"]},
            {"record_id": "judgment", "consumes": [], "depends_on": ["audit", "route_review"]},
            {"record_id": "closure", "consumes": [], "depends_on": ["judgment"]},
        ],
    }


def test_material_artifact_edit_stales_every_byte_bound_consumer():
    result = propagate_staleness(request(changed="artifact_bytes"))
    assert set(result["stale_record_ids"]) == {
        "artifact_map", "shared_writing", "audit", "route_review", "judgment", "closure"
    }


def test_reader_intent_change_stales_composition_and_downstream_only():
    result = propagate_staleness(request(changed="reader_intent"))
    assert set(result["stale_record_ids"]) == {
        "composition", "shared_writing", "audit", "judgment", "closure"
    }
    assert "artifact_map" not in result["stale_record_ids"]


def test_unchanged_exact_chain_remains_current():
    assert propagate_staleness(request())["stale_record_ids"] == []


def test_legacy_staleness_request_has_no_fallback():
    with pytest.raises(ValidationError, match="2.0"):
        propagate_staleness({"schema_version": "1.0", "current_inputs": {}, "observed_inputs": {}, "records": []})


def test_unknown_dependency_blocks_instead_of_guessing():
    value = request()
    value["records"][0]["depends_on"] = ["missing"]
    with pytest.raises(ValidationError, match="unknown dependency"):
        propagate_staleness(value)


def test_dependency_cycles_are_visible():
    value = request()
    value["records"][0]["depends_on"] = ["closure"]
    with pytest.raises(ValidationError, match="cycle"):
        propagate_staleness(value)
