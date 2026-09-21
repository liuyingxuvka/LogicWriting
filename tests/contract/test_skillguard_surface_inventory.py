"""Contract tests for LogicWriting's compact SkillGuard v3 source."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = ROOT / "skills" / "logic-writing"
CONTROL = SKILL_ROOT / ".skillguard"


def _source() -> dict:
    return json.loads((CONTROL / "contract-source.json").read_text(encoding="utf-8"))


def _compiled() -> dict:
    return json.loads((CONTROL / "compiled-contract.json").read_text(encoding="utf-8"))


def _manifest() -> dict:
    return json.loads((CONTROL / "check-manifest.json").read_text(encoding="utf-8"))


def test_v3_contract_is_closed_and_projects_the_same_check_set() -> None:
    source = _source()
    compiled = _compiled()
    manifest = _manifest()
    assert source["schema_version"] == "skillguard.skill_contract.v3"
    assert compiled["schema_version"] == "skillguard.compiled_contract.v3"
    assert manifest["schema_version"] == "skillguard.check_manifest.v3"
    source_checks = {row["check_id"] for row in source["checks"]}
    assert source_checks == {row["check_id"] for row in compiled["checks"]}
    assert source_checks == {row["check_id"] for row in manifest["checks"]}
    assert len(source_checks) == 12
    input_ids = {row["id"] for row in source["inputs"]}
    obligation_ids = {row["obligation_id"] for row in source["obligations"]}
    for check in source["checks"]:
        assert set(check["input_ids"]) <= input_ids
        assert set(check.get("depends_on_check_ids", ())) <= source_checks
        assert set(check.get("covers_obligation_ids", ())) <= obligation_ids
    step_ids = {row["step_id"] for row in source["steps"]}
    assert len(step_ids) == len(source["steps"])
    assert all(set(row["check_ids"]) <= source_checks for row in source["steps"])
    assert all(set(row["requires"]) <= step_ids for row in source["steps"])


def test_v3_inputs_and_consumer_projection_are_portable_and_current() -> None:
    source = _source()
    compiled = _compiled()
    manifest = _manifest()
    input_paths = {row["path"] for row in source["inputs"]}
    inventory_paths = {
        row["path"] for row in compiled["content_impact_plan"]["inventory"]
    }
    assert inventory_paths <= input_paths
    assert input_paths - inventory_paths == {
        ".skillguard/checks/run_logic_writing_check.py"
    }
    assert all("\\" not in path and not Path(path).is_absolute() for path in input_paths)
    assert all((SKILL_ROOT / path).is_file() for path in input_paths)
    assert ".skillguard/checks/run_logic_writing_check.py" in input_paths
    consumer_paths = set(source["consumer_projection"]["file_paths"])
    assert consumer_paths <= input_paths
    assert ".skillguard" not in " ".join(consumer_paths)
    assert manifest["contract_hash"] == compiled["contract_hash"]
    assert manifest["manifest_hash"].startswith("sha256:")


def test_v3_route_is_a_single_sequential_current_validation_chain() -> None:
    source = _source()
    route = source["routes"][0]
    assert len(source["routes"]) == 1
    assert route["route_id"] == "route:logic-writing:current-validation"
    assert route["when"] == [{"fact": "operation", "equals": "validate"}]
    ordered_steps = route["step_ids"]
    assert len(ordered_steps) == len(set(ordered_steps)) == 12
    by_id = {row["step_id"]: row for row in source["steps"]}
    for index, step_id in enumerate(ordered_steps):
        requires = by_id[step_id]["requires"]
        assert requires == ([] if index == 0 else [ordered_steps[index - 1]])
    assert set(route["obligation_ids"]) == {
        row["obligation_id"] for row in source["obligations"]
    }


def test_v3_contract_has_no_v2_surface_authority() -> None:
    source_text = (CONTROL / "contract-source.json").read_text(encoding="utf-8")
    assert "depth_profile" not in source_text
    assert "surface_inventory" not in source_text
    assert "surface-semantic-map" not in source_text
