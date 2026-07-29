from __future__ import annotations

import copy

import pytest

from _common import ValidationError, fingerprint
from derive_closure import derive_closure
from reader_pipeline import validate_revision_provenance, validate_route_composition
from select_route import select_route
from tests.v2_support import closure_input, complete_chain, route_request


def test_academic_route_keeps_final_ownership_when_research_is_needed():
    decision = select_route(route_request("thesis_chapter", research=True))
    assert decision["final_owner"] == "academic-writing"
    assert decision["child_routes"] == ["investigation"]


def test_academic_composition_carries_question_contribution_and_hierarchy(tmp_path):
    chain = complete_chain(tmp_path, "academic-writing")
    route = validate_route_composition(
        chain["route_composition"],
        owner="academic-writing",
        reader_intent_fingerprint=chain["intent"]["intent_fingerprint"],
        composition_plan_fingerprint=chain["plan"]["plan_fingerprint"],
    )
    assert route["research_question"]
    assert route["central_contribution"]
    assert route["hierarchy"][0]["new_claim_or_warrant"]


def test_create_new_provenance_is_explicitly_not_applicable(tmp_path):
    chain = complete_chain(tmp_path, "academic-writing")
    provenance = validate_revision_provenance(
        chain["revision_provenance"],
        target_artifact_fingerprint=chain["artifact_map"]["artifact_fingerprint"],
    )
    assert provenance["applicability"] == "not_applicable"
    assert provenance["unit_treatments"] == []


def test_revision_provenance_must_bind_current_target_bytes(tmp_path):
    chain = complete_chain(tmp_path, "academic-writing")
    provenance = copy.deepcopy(chain["revision_provenance"])
    provenance["target_artifact_fingerprint"] = fingerprint({"old": True})
    provenance["provenance_fingerprint"] = fingerprint({
        key: value for key, value in provenance.items() if key != "provenance_fingerprint"
    })
    with pytest.raises(ValidationError, match="stale"):
        validate_revision_provenance(
            provenance,
            target_artifact_fingerprint=chain["artifact_map"]["artifact_fingerprint"],
        )


def test_academic_closure_binds_revision_and_actual_artifact_chain(tmp_path):
    chain = complete_chain(tmp_path, "academic-writing")
    closure = derive_closure(closure_input(chain))["closure"]
    assert closure["status"] == "passed"
    assert closure["revision_provenance_fingerprint"] == chain["revision_provenance"]["provenance_fingerprint"]


def test_academic_route_review_failure_blocks_final_claim(tmp_path):
    chain = complete_chain(tmp_path, "academic-writing", pass_quality=False)
    closure = derive_closure(closure_input(chain))["closure"]
    assert closure["status"] == "blocked"
