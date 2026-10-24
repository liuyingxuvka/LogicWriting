from __future__ import annotations

import copy

import pytest

from _common import ValidationError, fingerprint_text
from reader_checks import _verify_span_evidence
from world_refs import validate_world_refs, world_ref_unquoted, validate_world_claim_units


def test_world_refs_validate_literal_ids_and_composition_relative_paths(tmp_path):
    directory = tmp_path / "composition"
    directory.mkdir()
    (directory / "world.yaml").write_text(
        "claim: {claim_id: c_access}\ninputs:\n  events:\n    - {event_id: e_unlock, at: t1}\n",
        encoding="utf-8",
    )
    plan = {"planned_units": [{"planned_unit_id": "scene", "world_refs": ["e_unlock", "c_access"]}]}
    assert validate_world_refs(plan, {"world_contract": "world.yaml"}, directory) == {"scene": ("e_unlock", "c_access")}
    with pytest.raises(ValidationError, match="world_contract_missing"):
        validate_world_refs(plan, {}, directory)
    unknown = copy.deepcopy(plan)
    unknown["planned_units"][0]["world_refs"] = ["never_declared"]
    with pytest.raises(ValidationError, match="unknown_world_ref:scene:never_declared"):
        validate_world_refs(unknown, {"world_contract": "world.yaml"}, directory)
    assert validate_world_refs({"planned_units": [{"planned_unit_id": "ordinary"}]}, {}) == {}


def test_unquoted_world_reference_is_risk_and_only_actual_bound_text_counts():
    plan = {"planned_units": [{"planned_unit_id": "scene", "world_refs": ["e_unlock"]}]}
    text = "The key turned and the door opened."
    unit = {"artifact_unit_id": "paragraph", "locator": "paragraph:1", "text": text}
    units = {"paragraph": unit}
    evidence = {"artifact_unit_id": "paragraph", "locator": "paragraph:1", "excerpt": text,
                "excerpt_fingerprint": fingerprint_text(text)}
    shared = {"unit_bindings": [{"planned_unit_id": "scene", "artifact_unit_ids": ["paragraph"]}]}
    verify = lambda span: _verify_span_evidence(span, units)
    assert world_ref_unquoted(plan, {}, shared, verify) == ["world_ref_unquoted:scene:e_unlock"]
    review = {"world_ref_checks": [{"planned_unit_id": "scene", "world_ref": "e_unlock", "evidence": [evidence]}]}
    assert world_ref_unquoted(plan, review, shared, verify) == []
    wrong_text = copy.deepcopy(review)
    wrong_text["world_ref_checks"][0]["evidence"][0]["excerpt"] = "Words absent from the current artifact."
    with pytest.raises(ValidationError, match="absent"):
        world_ref_unquoted(plan, wrong_text, shared, verify)
    other_unit = {"unit_bindings": [{"planned_unit_id": "scene", "artifact_unit_ids": ["elsewhere"]}]}
    with pytest.raises(ValidationError, match="must belong"):
        world_ref_unquoted(plan, review, other_unit, verify)


def test_world_claim_source_row_is_a_plan_unit_with_world_references():
    plan = {"planned_units": [{"planned_unit_id": "scene", "world_refs": ["e_unlock"]},
                              {"planned_unit_id": "ordinary"}]}
    ledger = {"worldguard_claims": [{"id": "world-claim", "source_row_id": "scene"}]}
    assert validate_world_claim_units(ledger, plan) == []
    ledger["worldguard_claims"][0]["source_row_id"] = "ordinary"
    assert validate_world_claim_units(ledger, plan) == ["unit_not_in_plan:worldguard_claims:world-claim"]
