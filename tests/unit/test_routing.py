from __future__ import annotations

import copy

import pytest

from _common import ValidationError, fingerprint
from select_route import select_route, validate_request
from tests.v2_support import route_request


@pytest.mark.parametrize(
    ("kind", "owner"),
    [
        ("research_report", "investigation"),
        ("paper", "academic-writing"),
        ("novel", "fiction-writing"),
        ("itinerary", "travel-guide"),
    ],
)
def test_terminal_deliverable_selects_exactly_one_owner(kind, owner):
    decision = select_route(route_request(kind))
    assert decision["final_owner"] == owner
    assert decision["reader_intent"] == route_request(kind)["writing_request"]["reader_intent"]


@pytest.mark.parametrize("kind", ["paper", "novel", "itinerary"])
def test_bounded_research_is_child_not_final_owner(kind):
    decision = select_route(route_request(kind, research=True))
    assert decision["final_owner"] != "investigation"
    assert decision["child_routes"] == ["investigation"]


def test_ambiguous_deliverable_blocks_without_guessing_owner():
    result = validate_request(route_request("unresolved"))
    assert result["status"] == "blocked"
    assert result["route_decision"]["final_owner"] is None


def test_trivial_terminal_kind_skips_logic_writing():
    decision = select_route(route_request("grammar_only"))
    assert decision["status"] == "skipped"
    assert decision["final_owner"] is None


def test_material_reader_intent_conflict_blocks_drafting():
    request = route_request("paper")
    request["intent_conflicts"] = [{
        "conflict_id": "conflict:structure",
        "fields": ["structure"],
        "reason": "Two incompatible fixed outlines were supplied.",
        "material": True,
    }]
    decision = select_route(request)
    assert decision["status"] == "blocked"


def test_legacy_flat_request_has_no_runtime_fallback():
    with pytest.raises(ValidationError, match="unknown current fields"):
        select_route({"request_id": "legacy", "terminal_deliverable": {}})


def test_request_identity_changes_with_reader_intent():
    first = route_request("paper")
    second = copy.deepcopy(first)
    second["writing_request"]["reader_intent"]["purpose"] = "Different purpose"
    second["writing_request"]["reader_intent"]["intent_fingerprint"] = fingerprint({
        k: v for k, v in second["writing_request"]["reader_intent"].items()
        if k != "intent_fingerprint"
    })
    second["writing_request"]["request_fingerprint"] = fingerprint({
        k: v for k, v in second["writing_request"].items()
        if k != "request_fingerprint"
    })
    assert select_route(first)["request_fingerprint"] != select_route(second)["request_fingerprint"]
