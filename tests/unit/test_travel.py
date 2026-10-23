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
    assert codes == {"fallback_options.reachability.unproven"}
    assert codes == set(case["expected_issue_codes"])


def test_world_check_may_record_not_run(monkeypatch):
    monkeypatch.syspath_prepend(str(ROUTE / "scripts"))
    from travel_contract import validate_plan
    base_path = ROUTE / "examples/good_city_couple_trip/plan.json"
    plan = json.loads(base_path.read_text(encoding="utf-8"))
    plan["world_feasibility"]["checks"][0]["status"] = "not_run"
    codes = {row["code"] for row in validate_plan(plan, plan_path=base_path, repository_root=ROOT)}
    assert "world_feasibility.status.invalid" not in codes


def test_allowed_claim_level_must_match_the_current_evidence(monkeypatch):
    monkeypatch.syspath_prepend(str(ROUTE / "scripts"))
    from travel_contract import validate_plan

    base_path = ROUTE / "examples" / "good_city_couple_trip" / "plan.json"
    plan = json.loads(base_path.read_text(encoding="utf-8"))
    assert plan["trip_context"]["allowed_claim_level"] == "initial_plan"
    plan["trip_context"]["allowed_claim_level"] = "bookable"
    codes = {row["code"] for row in validate_plan(plan, plan_path=base_path, repository_root=ROOT)}
    assert codes == {"trip_context.allowed_claim_level.derived_mismatch"}


def test_travel_composition_must_name_trip_plan_ids(monkeypatch):
    monkeypatch.syspath_prepend(str(ROUTE / "scripts"))
    from travel_contract import validate_composition_refs
    from tests.v2_support import make_intent, make_plan, make_route_composition

    plan = json.loads((ROUTE / "examples" / "good_city_couple_trip" / "plan.json").read_text(encoding="utf-8"))
    intent = make_intent()
    composition = make_route_composition("travel-guide", intent, make_plan(intent, "travel-guide"))
    codes = {row["code"] for row in validate_composition_refs(plan, composition)}
    assert codes == {
        "travel_composition.route_ref.unknown",
        "travel_composition.fallback.unknown",
        "travel_composition.risk.unknown",
        "travel_composition.route_node.unknown",
    }
    composition["body_sections"][0]["route_refs"] = ["trace-primary"]
    binding = composition["risk_fallback_bindings"][0]
    binding.update({"risk_id": "pit-weather", "fallback_id": "fb-gallery", "reachable_from_route_node_ids": ["rn-p-station"]})
    assert validate_composition_refs(plan, composition) == []


def test_text_check_runs_on_one_actual_guide(tmp_path):
    import subprocess
    import sys

    script = ROUTE / "scripts" / "validate_travel_text_outputs.py"
    good = ROUTE / "examples" / "good_text_outputs"
    run = subprocess.run(
        [sys.executable, str(script), "--guide", str(good / "city_couple_native_guide.txt"),
         "--review", str(good / "city_couple_native_guide.review.json"), "--json"],
        capture_output=True, text=True,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    bullets = tmp_path / "guide.md"
    bullets.write_text("- Day 1: museum\n- Day 2: market\n- Day 3: train\n", encoding="utf-8")
    run = subprocess.run([sys.executable, str(script), "--guide", str(bullets), "--json"], capture_output=True, text=True)
    assert run.returncode == 1
    assert "text.bullet_list_only" in {row["code"] for row in json.loads(run.stdout)["issues"]}


def test_chinese_prose_guide_and_advisory_hints(monkeypatch):
    monkeypatch.syspath_prepend(str(ROUTE / "scripts"))
    from validate_travel_text_outputs import validate_text

    weather_codes = {"text.weather_evidence_missing", "text.weather_source_mode_missing",
                     "text.weather_hazards_missing", "text.weather_hazard_boundary_missing"}
    for name in ("guide.md", "guide-zh.md"):
        warnings = []
        text = (ROOT / "tests/fixtures/trials/trialC" / name).read_text(encoding="utf-8")
        issues = validate_text(text, warnings=warnings)
        assert {row["code"] for row in issues} == weather_codes
        assert "text.local_texture.too_thin" in {row["code"] for row in warnings}
    warnings = []
    assert validate_text("第一段说明。\n\n第二段说明。", warnings=warnings) == []
    assert {row["code"] for row in warnings} == {"text.local_texture.too_thin", "text.generic_risk"}
    assert "text.generic_risk" in {row["code"] for row in validate_text(
        "第一段说明。\n\n第二段说明。", {"observed_risks": ["absent"], "observed_fallbacks": ["missing"]})}
