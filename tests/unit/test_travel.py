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


def test_travel_guide_structure_lives_only_in_the_composition():
    plan = json.loads((ROUTE / "examples" / "good_city_couple_trip" / "plan.json").read_text(encoding="utf-8"))
    assert "reader_projection" not in plan
    assert "traveler_native_guide" not in plan
    assert "story_output" not in plan
    brief = json.loads((ROOT / "skills/logic-writing/assets/examples/travel/brief-request.json").read_text())
    assert brief["route_composition"]["trip_plan"] == "trip-plan.json"
    assert brief["route_composition"]["body_sections"]


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


def test_handwritten_world_status_is_rejected(monkeypatch):
    monkeypatch.syspath_prepend(str(ROUTE / "scripts"))
    from travel_contract import validate_plan
    base_path = ROUTE / "examples/good_city_couple_trip/plan.json"
    plan = json.loads(base_path.read_text(encoding="utf-8"))
    plan["world_feasibility"]["checks"][0]["status"] = "pass"
    codes = {row["code"] for row in validate_plan(plan, plan_path=base_path, repository_root=ROOT)}
    assert "world_feasibility.status.retired" in codes


def test_requested_claim_level_cannot_exceed_saved_evidence(monkeypatch):
    monkeypatch.syspath_prepend(str(ROUTE / "scripts"))
    from travel_contract import review_plan
    base_path = ROUTE / "examples/good_city_couple_trip/plan.json"
    plan = json.loads(base_path.read_text(encoding="utf-8"))
    assert review_plan(plan, plan_path=base_path)["allowed_claim_level"] == "initial_plan"
    plan["trip_context"]["requested_claim_level"] = "bookable"
    codes = {row["code"] for row in review_plan(plan, plan_path=base_path)["issues"]}
    assert codes == {"trip_context.requested_claim_level.overreach"}


def test_composition_refs_resolve_in_the_trip_plan(monkeypatch):
    monkeypatch.syspath_prepend(str(ROUTE / "scripts"))
    from travel_contract import validate_composition_refs
    assets = ROOT / "skills/logic-writing/assets/examples/travel"
    plan = json.loads((assets / "trip-plan.json").read_text(encoding="utf-8"))
    composition = json.loads((assets / "brief-request.json").read_text(encoding="utf-8"))["route_composition"]
    assert validate_composition_refs(plan, composition) == []
    composition["body_sections"][0]["route_refs"] = ["unknown-route"]
    assert {row["code"] for row in validate_composition_refs(plan, composition)} == {"travel_composition.route_ref.unknown"}


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


def test_failing_world_report_limits_the_claim_level(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(ROUTE / "scripts"))
    from travel_contract import review_plan
    base_path = ROUTE / "examples/good_city_couple_trip/plan.json"
    plan = json.loads(base_path.read_text(encoding="utf-8"))
    from fixture_mutation import apply_mutations
    current = json.loads((ROUTE / "examples/positive_cases/near_future_bookable.json").read_text(encoding="utf-8"))
    plan = apply_mutations(plan, current["mutations"])
    assert review_plan(plan, plan_path=base_path)["allowed_claim_level"] == "bookable"
    failed = tmp_path / "world-fail.json"
    failed.write_text(json.dumps({"status": "FAIL"}), encoding="utf-8")
    plan["world_feasibility"]["checks"][0]["worldguard_report"] = str(failed)
    review = review_plan(plan, plan_path=base_path)
    assert review["allowed_claim_level"] == "initial_plan"
    assert review["allowed_claim_reason"] == "upstream_nonpass"


def test_travel_extension_tracks_trip_and_report_file_bytes(tmp_path):
    import shutil
    from route_inputs import route_extension_fingerprint
    from _common import fingerprint_without

    assets = ROOT / "skills/logic-writing/assets/examples/travel"
    trip = tmp_path / "trip-plan.json"
    report = tmp_path / "worldguard-check.json"
    shutil.copyfile(assets / trip.name, trip)
    shutil.copyfile(assets / report.name, report)
    composition = json.loads((assets / "brief-request.json").read_text(encoding="utf-8"))["route_composition"]
    original = route_extension_fingerprint(composition, tmp_path)
    report_bytes = report.read_bytes()
    report.write_bytes(report_bytes + b"\n")
    assert route_extension_fingerprint(composition, tmp_path) != original
    report.write_bytes(report_bytes)
    assert route_extension_fingerprint(composition, tmp_path) == original
    trip.write_bytes(trip.read_bytes() + b"\n")
    assert route_extension_fingerprint(composition, tmp_path) != original
    other_route = {"final_owner": "fiction-writing", "extension_fingerprint": "old", "plan": "unchanged"}
    assert route_extension_fingerprint(other_route) == fingerprint_without(other_route, "extension_fingerprint")
