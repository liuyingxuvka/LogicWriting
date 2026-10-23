from __future__ import annotations

import copy

from reader_pipeline import build_writer_input, fill_plan_defaults, fill_brief_fingerprints
from build_reader_brief import validate_request
from _common import ValidationError, fingerprint_without
import pytest
from tests.v2_support import make_reader_chain


def test_internal_semantic_material_is_not_projected_to_the_writer(tmp_path):
    chain = make_reader_chain(tmp_path)
    boundaries = copy.deepcopy(chain["reader_brief"]["content_boundaries"])
    boundaries["content_units"].append({
        "content_unit_id": "content:internal",
        "safe_meaning": "internal audit metadata for the planner",
        "required": False,
        "evidence_anchor_ids": [],
        "alternative_ids": [],
        "limitation_ids": [],
        "model_row_ids": [],
    })
    writer = build_writer_input(
        owner="investigation", intent=chain["intent"], plan=chain["plan"],
        route=chain["route_composition"], boundaries=boundaries,
    )
    assert "content:internal" not in {row["content_unit_id"] for row in writer["selected_content"]}


def test_body_dispositions_are_derived_from_planned_units():
    request = {"content_boundaries": {"content_units": [{"content_unit_id": "cu-a"}],
        "limitations": [{"limitation_id": "lim-a", "affected_content_unit_ids": ["cu-a"], "required_placement": "near the claim"}]},
        "composition_plan": {"planned_units": [{"planned_unit_id": "u-first", "content_unit_ids": ["cu-a"], "limitation_ids": ["lim-a"]},
            {"planned_unit_id": "u-last", "content_unit_ids": ["cu-a"], "limitation_ids": []}]}}
    fill_plan_defaults(request)
    plan = request["composition_plan"]
    assert plan["content_dispositions"] == [{"content_unit_id": "cu-a", "disposition": "body", "planned_unit_ids": ["u-first", "u-last"], "reason": "placed in planned unit(s) u-first, u-last"}]
    assert plan["limitation_dispositions"] == [{"limitation_id": "lim-a", "affected_claim_ids": ["cu-a"],
        "materiality": "changes_strength", "materiality_reason": "default for a limitation placed in the body", "disposition": "body",
        "destination_unit_ids": ["u-first"], "merged_into_id": None, "realization_requirement": "near the claim", "native_boundary_refs": []}]
    first = copy.deepcopy(request)
    fill_plan_defaults(request)
    assert request == first


def test_defaults_preserve_explicit_rows_and_do_not_invent_hidden_dispositions():
    row = {"content_unit_id": "placed", "disposition": "deferred", "planned_unit_ids": [], "reason": "explicit decision"}
    request = {"content_boundaries": {"content_units": [{"content_unit_id": "placed"}, {"content_unit_id": "unplaced"}], "limitations": []},
        "composition_plan": {"planned_units": [{"planned_unit_id": "u-one", "content_unit_ids": ["placed"]}], "content_dispositions": [row]}}
    fill_plan_defaults(request)
    assert request["composition_plan"]["content_dispositions"] == [row]
    assert "limitation_dispositions" not in request["composition_plan"]


def test_an_unplaced_content_unit_names_itself(tmp_path):
    chain = make_reader_chain(tmp_path)
    request = {"route_decision": copy.deepcopy(chain["route_decision"]), "content_boundaries": copy.deepcopy(chain["reader_brief"]["content_boundaries"]),
        "composition_plan": copy.deepcopy(chain["plan"]), "route_composition": copy.deepcopy(chain["route_composition"]), "brief_id": "brief:defaults"}
    request["composition_plan"].pop("content_dispositions")
    request["composition_plan"].pop("plan_fingerprint")
    request["composition_plan"]["planned_units"][0]["content_unit_ids"] = []
    request["route_composition"].pop("extension_fingerprint")
    request["route_composition"].pop("composition_plan_fingerprint")
    with pytest.raises(ValidationError, match="content unit content:answer is in no planned unit; add a content_dispositions row"):
        validate_request(request)


def test_plan_defaults_precede_fingerprints_and_supplied_fingerprints_are_checked(tmp_path):
    chain = make_reader_chain(tmp_path)
    request = {"route_decision": copy.deepcopy(chain["route_decision"]), "content_boundaries": copy.deepcopy(chain["reader_brief"]["content_boundaries"]),
        "composition_plan": copy.deepcopy(chain["plan"]), "route_composition": copy.deepcopy(chain["route_composition"]), "brief_id": "brief:defaults"}
    request["composition_plan"].pop("content_dispositions")
    request["composition_plan"].pop("plan_fingerprint")
    request["route_composition"].pop("extension_fingerprint")
    request["route_composition"].pop("composition_plan_fingerprint")
    filled = fill_brief_fingerprints(request)
    assert filled["composition_plan"]["plan_fingerprint"] == fingerprint_without(filled["composition_plan"], "plan_fingerprint")
    assert validate_request(filled)["status"] == "current_pass"
    filled["composition_plan"]["content_dispositions"][0]["reason"] = "changed after fingerprint"
    with pytest.raises(ValidationError, match="plan_fingerprint"):
        validate_request(filled)
