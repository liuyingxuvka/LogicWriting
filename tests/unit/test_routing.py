from __future__ import annotations

import copy

import pytest

from _common import ValidationError, fingerprint
from select_route import complete_request, select_route, validate_request
from reader_plan import build_reader_brief
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


def test_route_selection_fills_missing_request_fingerprints():
    request = route_request("paper")
    writing = request["writing_request"]
    expected = (
        writing["reader_intent"]["intent_fingerprint"],
        writing["terminal_deliverable"]["fingerprint"],
        writing["request_fingerprint"],
    )
    del writing["reader_intent"]["intent_fingerprint"]
    del writing["terminal_deliverable"]["fingerprint"]
    del writing["request_fingerprint"]
    result = validate_request(request)
    decision = result["route_decision"]
    assert result["status"] == "current_pass"
    assert (
        decision["reader_intent_fingerprint"],
        decision["terminal_deliverable"]["fingerprint"],
        decision["request_fingerprint"],
    ) == expected


def test_a_given_wrong_request_fingerprint_is_still_rejected():
    request = route_request("paper")
    request["writing_request"]["request_fingerprint"] = "sha256:" + "0" * 64
    with pytest.raises(ValidationError):
        validate_request(request)


def _with_open_choices(request, *, material=True):
    intent = request["writing_request"]["reader_intent"]
    intent["unresolved_choices"] = [
        {"choice_id": "ch-lang", "question": "English or Chinese?", "material": material},
        {"choice_id": "ch-tone", "question": "Formal or informal?", "material": False},
        {"choice_id": "ch-audience", "question": "Who is the reader?", "material": material},
    ]
    intent.pop("intent_fingerprint")
    request["writing_request"].pop("request_fingerprint")
    return complete_request(request)


def test_open_material_choice_asks_the_user_first():
    result = validate_request(_with_open_choices(route_request("paper", research=True)))
    decision = result["route_decision"]
    assert result["status"] == decision["status"] == "needs_user_choice"
    assert decision["final_owner"] is None
    assert decision["child_routes"] == []
    assert decision["reason"] == "a material reader choice is still open: English or Chinese?"
    assert decision["open_choices"] == [
        {"choice_id": "ch-lang", "question": "English or Chinese?"},
        {"choice_id": "ch-audience", "question": "Who is the reader?"},
    ]


def test_open_choice_that_is_not_material_does_not_block():
    decision = select_route(_with_open_choices(route_request("paper"), material=False))
    assert decision["status"] == "current"
    assert decision["final_owner"] == "academic-writing"
    assert "open_choices" not in decision


def test_brief_refuses_an_open_material_choice():
    decision = select_route(route_request("paper"))
    # Deliberately preserve the earlier decision fingerprint: the question must
    # be surfaced before stale identity or current-owner/planning checks.
    decision["reader_intent"]["unresolved_choices"] = [
        {"choice_id": "ch-lang", "question": "English or Chinese?", "material": True},
    ]
    decision["status"], decision["final_owner"] = "ambiguous", None
    with pytest.raises(ValidationError, match=(
        "ReaderIntent has an open material choice ch-lang: English or Chinese"
    )) as error:
        build_reader_brief(route_decision=decision, content_boundaries={},
                           composition_plan={}, route_composition={}, brief_id="brief:choice")
    assert str(error.value) == (
        "ReaderIntent has an open material choice ch-lang: English or Chinese?; ask the user before planning"
    )


@pytest.mark.parametrize(("kind", "conflict", "expected"), [
    ("paper", True, "blocked"), ("grammar_only", False, "skipped"),
])
def test_conflict_and_trivial_priorities_precede_open_choices(kind, conflict, expected):
    request = _with_open_choices(route_request(kind))
    if conflict:
        request["intent_conflicts"] = [{
            "conflict_id": "conflict:structure", "fields": ["structure"],
            "reason": "Two incompatible fixed outlines were supplied.", "material": True,
        }]
    decision = select_route(request)
    assert decision["status"] == expected
    assert decision["final_owner"] is None
    assert decision["child_routes"] == []
