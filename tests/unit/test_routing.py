from __future__ import annotations

from select_route import select_route, validate_request


def request(kind: str, **overrides) -> dict:
    value = {
        "request_id": "request-1",
        "decision_id": "decision-1",
        "decided_at": "2026-07-14T10:00:00Z",
        "terminal_deliverable": {
            "kind": kind,
            "description": "A reader-ready final artifact",
            "acceptance_criteria": ["The final owner is explicit."],
        },
        "scope_class": "substantive",
        "material_assumptions": [],
    }
    value.update(overrides)
    return value


def test_investigation_product_has_one_investigation_owner():
    decision = select_route(request("research_report"))

    assert decision["status"] == "current"
    assert decision["final_owner"] == "investigation"
    assert decision["child_routes"] == []


def test_academic_product_keeps_academic_owner_when_research_happens_first():
    decision = select_route(request("paper", substantial_research_required=True))

    assert decision["status"] == "current"
    assert decision["final_owner"] == "academic-writing"
    assert decision["child_routes"] == ["investigation"]


def test_fiction_product_keeps_fiction_owner_when_historical_research_happens_first():
    decision = select_route(request("novel", substantial_research_required=True))

    assert decision["status"] == "current"
    assert decision["final_owner"] == "fiction-writing"
    assert decision["child_routes"] == ["investigation"]


def test_story_shaped_itinerary_keeps_travel_owner():
    decision = select_route(
        request("itinerary", constraints={"presentation": "story-shaped journey"})
    )

    assert decision["final_owner"] == "travel-guide"
    assert decision["child_routes"] == []


def test_travel_subject_paper_keeps_academic_owner():
    decision = select_route(request("paper", constraints={"subject": "travel"}))

    assert decision["final_owner"] == "academic-writing"


def test_novel_with_academic_notes_keeps_fiction_owner():
    decision = select_route(request("fiction_chapter", constraints={"notes": "academic"}))

    assert decision["final_owner"] == "fiction-writing"


def test_polished_investigation_report_does_not_transfer_owner():
    decision = select_route(
        request(
            "briefing",
            constraints={"style": "polished academic prose", "research_first": True},
        )
    )

    assert decision["final_owner"] == "investigation"
    assert "academic-writing" not in decision["child_routes"]


def test_ambiguous_deliverable_blocks_instead_of_assigning_two_owners():
    result = validate_request(request("research_piece"))

    assert result["status"] == "blocked"
    assert result["route_decision"]["status"] == "ambiguous"
    assert result["route_decision"]["final_owner"] is None
    assert result["route_decision"]["child_routes"] == []


def test_trivial_grammar_edit_skips_both_routes_with_reason():
    result = validate_request(request("paper", scope_class="grammar_only"))

    assert result["status"] == "current_pass"
    decision = result["route_decision"]
    assert decision["status"] == "skipped"
    assert decision["final_owner"] is None
    assert "does not activate" in decision["reason"]


def test_material_deliverable_change_invalidates_request_identity():
    report = select_route(request("research_report"))
    paper = select_route(request("paper"))

    assert report["request_fingerprint"] != paper["request_fingerprint"]
    assert report["terminal_deliverable"]["fingerprint"] != paper["terminal_deliverable"]["fingerprint"]
    assert report["final_owner"] == "investigation"
    assert paper["final_owner"] == "academic-writing"


def test_nonmaterial_decision_metadata_does_not_change_request_identity():
    first = select_route(request("paper"))
    second = select_route(
        request(
            "paper",
            decision_id="decision-2",
            decided_at="2026-07-14T10:01:00Z",
        )
    )

    assert first["request_fingerprint"] == second["request_fingerprint"]
    assert first["decision_fingerprint"] != second["decision_fingerprint"]
    assert first["final_owner"] == second["final_owner"] == "academic-writing"
