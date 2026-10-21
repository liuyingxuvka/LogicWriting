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


def test_contract_and_route_review_fingerprints_are_filled(monkeypatch, tmp_path):
    from pathlib import Path

    from tests.v2_support import complete_chain

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "skills" / "logic-writing" / "routes" / "investigation" / "scripts"))
    from validate_investigation_artifact import validate_investigation_artifact
    from validate_shared_writing import validate_shared_writing

    chain = complete_chain(tmp_path)
    contract = copy.deepcopy(chain["shared_writing"])
    for field in ("route_decision_fingerprint", "reader_intent_fingerprint", "reader_brief_fingerprint",
                  "composition_plan_fingerprint", "route_extension_fingerprint", "artifact_map_fingerprint",
                  "artifact_fingerprint", "contract_fingerprint"):
        del contract[field]
    for binding in contract["unit_bindings"]:
        for span in binding["artifact_spans"]:
            span.pop("locator", None), span.pop("content_fingerprint", None)
    checked = validate_shared_writing({"contract": contract, "artifact_map": chain["artifact_map"],
                                       "reader_brief": chain["reader_brief"]})
    assert checked["status"] == "current_pass"
    assert checked["shared_writing"] == chain["shared_writing"]

    review = copy.deepcopy(chain["route_review"])
    for field in ("route_extension_fingerprint", "artifact_map_fingerprint", "artifact_fingerprint", "review_fingerprint"):
        del review[field]
    for row in review["dimensions"]:
        for evidence in row["evidence"]:
            evidence.pop("locator", None), evidence.pop("excerpt_fingerprint", None)
    reviewed = validate_investigation_artifact({"review": review, "route_composition": chain["route_composition"],
                                                "artifact_map": chain["artifact_map"]})
    assert reviewed["route_review"] == chain["route_review"]
