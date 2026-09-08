from __future__ import annotations

import copy

import pytest

from _common import ValidationError, fingerprint
from reader_pipeline import build_writer_input, validate_writer_input
from tests.v2_support import complete_chain, make_reader_chain


def test_writer_input_uses_the_composition_projection(tmp_path):
    chain = complete_chain(tmp_path)
    plan = copy.deepcopy(chain["plan"])
    plan["planned_units"][0]["internal_review_note"] = "judge-only metadata"
    plan["plan_fingerprint"] = fingerprint({k: v for k, v in plan.items() if k != "plan_fingerprint"})
    # The writer view intentionally omits plan metadata outside its allowlist.
    validate_writer_input(chain["reader_brief"]["writer_input"], composition_plan=plan)


def test_writer_input_has_a_single_canonical_body_order(tmp_path):
    chain = make_reader_chain(tmp_path)
    writer = chain["reader_brief"]["writer_input"]
    assert writer["composition"]["body_unit_order"] == ["unit:answer"]
    forged = copy.deepcopy(writer)
    forged["composition"]["body_unit_order"] = []
    with pytest.raises(ValidationError, match="body_unit_order"):
        validate_writer_input(forged, composition_plan=chain["plan"])


def test_hidden_disposition_is_not_reintroduced_by_route_projection(tmp_path):
    chain = make_reader_chain(tmp_path)
    plan = copy.deepcopy(chain["plan"])
    plan["content_dispositions"][0]["disposition"] = "omitted"
    plan["content_dispositions"][0]["planned_unit_ids"] = []
    plan["plan_fingerprint"] = fingerprint({k: v for k, v in plan.items() if k != "plan_fingerprint"})
    writer = build_writer_input(
        owner="investigation", intent=chain["intent"], plan=plan,
        route=chain["route_composition"], boundaries=chain["reader_brief"]["content_boundaries"],
    )
    assert writer["selected_content"] == []
    assert writer["route_semantics"]["answer"] == []
    assert any(row["subject_id"] == "content:answer" for row in writer["gaps"])


@pytest.mark.parametrize("owner", ["academic-writing", "fiction-writing", "travel-guide"])
def test_route_projection_keeps_route_specific_reader_jobs(tmp_path, owner):
    chain = make_reader_chain(tmp_path / owner, owner)
    projection = chain["reader_brief"]["writer_input"]["route_semantics"]
    if owner == "academic-writing":
        assert projection["hierarchy"][0]["new_claim_or_warrant"]
        assert "qualification" in projection["hierarchy"][0]
    elif owner == "fiction-writing":
        plan = projection["unit_plans"][0]
        assert plan["entry_state"] and plan["exit_state"]
        assert plan["open_questions_in"]
        assert projection["realization_boundaries"]
    else:
        assert projection["traveler_conditions"][0]["section_role"]
        assert projection["local_names"][0]["local_name"]
        assert projection["reachable_fallbacks"][0]["affected_travelers"]
        assert projection["source_and_recheck_placement"]["appendix_jobs"]
