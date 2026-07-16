from __future__ import annotations

import json
from pathlib import Path

from select_route import select_route


ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / "skills" / "logic-writing" / "routes" / "travel"


def test_travel_route_pack_is_internal_not_installable():
    assert ROUTE.is_dir()
    assert not (ROUTE / "SKILL.md").exists()
    assert not (ROUTE / "agents").exists()
    assert not (ROUTE / ".skillguard").exists()


def test_story_shaped_itinerary_does_not_invoke_fiction_owner():
    decision = select_route({
        "request_id": "request:travel-unit",
        "decision_id": "decision:travel-unit",
        "decided_at": "2026-07-16T10:00:00Z",
        "terminal_deliverable": {
            "kind": "itinerary",
            "description": "A story-shaped but operational itinerary",
            "acceptance_criteria": ["The final guide remains executable."],
        },
        "scope_class": "substantive",
        "substantial_research_required": True,
        "constraints": {"presentation": "journey storyline"},
        "material_assumptions": [],
    })
    assert decision["final_owner"] == "travel-guide"
    assert decision["child_routes"] == ["investigation"]


def test_travel_plan_uses_neutral_reader_projection():
    plan = json.loads((ROUTE / "examples" / "good_city_couple_trip" / "plan.json").read_text(encoding="utf-8"))
    assert "reader_projection" in plan
    assert "story_output" not in plan
    assert plan["closure_report"]["surface_rows"][-2]["owner"] == "logic-writing.shared-reader-projection"


def test_travel_case_families_remain_complete():
    assert len(list((ROUTE / "examples" / "positive_cases").glob("*.json"))) >= 6
    assert len(list((ROUTE / "examples" / "failure_cases").glob("*.json"))) >= 20
    assert len(list((ROUTE / "examples" / "text_failure_cases").glob("*.json"))) >= 8
