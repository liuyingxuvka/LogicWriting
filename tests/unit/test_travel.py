from __future__ import annotations

import json
from pathlib import Path

from select_route import select_route
from tests.v2_support import route_request


ROOT = Path(__file__).resolve().parents[2]
ROUTE = ROOT / "skills" / "logic-writing" / "routes" / "travel"


def test_travel_route_pack_is_internal_not_installable():
    assert ROUTE.is_dir()
    assert not (ROUTE / "SKILL.md").exists()
    assert not (ROUTE / "agents").exists()


def test_story_shaped_itinerary_does_not_invoke_fiction_owner():
    decision = select_route(route_request("itinerary", research=True))
    assert decision["final_owner"] == "travel-guide"
    assert decision["child_routes"] == ["investigation"]


def test_travel_plan_uses_neutral_reader_projection():
    plan = json.loads((ROUTE / "examples" / "good_city_couple_trip" / "plan.json").read_text(encoding="utf-8"))
    assert "reader_projection" in plan
    assert "story_output" not in plan
    assert plan["closure_report"]["surface_rows"][-2]["owner"] == "logic-writing.shared-reader-projection"


def test_native_travel_plan_preserves_fallback_reachability(monkeypatch):
    monkeypatch.syspath_prepend(str(ROUTE / "scripts"))
    from fixture_mutation import apply_mutations
    from travel_contract import validate_plan

    base_path = ROUTE / "examples" / "good_city_couple_trip" / "plan.json"
    base = json.loads(base_path.read_text(encoding="utf-8"))
    assert validate_plan(base, plan_path=base_path, repository_root=ROOT) == []

    case = json.loads((ROUTE / "examples" / "failure_cases" / "fallback_unreachable.json").read_text(encoding="utf-8"))
    issues = validate_plan(apply_mutations(base, case["mutations"]), plan_path=base_path, repository_root=ROOT)
    codes = {row["code"] for row in issues}
    assert codes == {
        "fallback_options.reachability.unproven",
        "closure_report.status.mismatch",
    }
    assert codes == set(case["expected_issue_codes"])


def test_world_check_may_record_not_run(monkeypatch):
    monkeypatch.syspath_prepend(str(ROUTE / "scripts"))
    from travel_contract import validate_plan
    base_path = ROUTE / "examples/good_city_couple_trip/plan.json"
    plan = json.loads(base_path.read_text(encoding="utf-8"))
    plan["world_feasibility"]["checks"][0]["status"] = "not_run"
    codes = {row["code"] for row in validate_plan(plan, plan_path=base_path, repository_root=ROOT)}
    assert "world_feasibility.status.invalid" not in codes
