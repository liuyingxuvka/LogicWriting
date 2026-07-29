from __future__ import annotations

import copy

import pytest

from _common import ValidationError, fingerprint_without
from reader_pipeline import validate_shared_writing
from tests.v2_support import make_reader_chain


def test_current_plan_to_byte_binding_passes(tmp_path):
    chain = make_reader_chain(tmp_path, "fiction-writing")
    value = validate_shared_writing(
        chain["shared_writing"],
        artifact_map=chain["artifact_map"],
        reader_brief=chain["reader_brief"],
    )
    assert value["artifact_fingerprint"] == chain["artifact_map"]["artifact_fingerprint"]


def test_material_byte_change_stales_artifact_map(tmp_path):
    chain = make_reader_chain(tmp_path)
    chain["artifact_path"].write_text("changed", encoding="utf-8")
    with pytest.raises(ValidationError, match="stale"):
        validate_shared_writing(
            chain["shared_writing"],
            artifact_map=chain["artifact_map"],
            reader_brief=chain["reader_brief"],
        )


def test_required_plan_unit_must_bind_actual_span(tmp_path):
    chain = make_reader_chain(tmp_path)
    contract = copy.deepcopy(chain["shared_writing"])
    contract["unit_bindings"] = []
    contract["contract_fingerprint"] = fingerprint_without(contract, "contract_fingerprint")
    with pytest.raises(ValidationError):
        validate_shared_writing(
            contract,
            artifact_map=chain["artifact_map"],
            reader_brief=chain["reader_brief"],
        )


def test_sibling_route_contract_is_rejected(tmp_path):
    chain = make_reader_chain(tmp_path, "travel-guide")
    contract = copy.deepcopy(chain["shared_writing"])
    contract["final_owner"] = "fiction-writing"
    contract["contract_fingerprint"] = fingerprint_without(contract, "contract_fingerprint")
    with pytest.raises(ValidationError, match="final_owner"):
        validate_shared_writing(
            contract,
            artifact_map=chain["artifact_map"],
            reader_brief=chain["reader_brief"],
        )
