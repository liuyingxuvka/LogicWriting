"""Contract tests for LogicWriting's author-owned surface inventory."""

from __future__ import annotations

import json
import copy
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[2]
CONTROL = ROOT / "skills" / "logic-writing" / ".skillguard"


def test_surface_inventory_generator_is_current_and_binds_model_depth():
    command = [
        sys.executable,
        "scripts/author/build_skillguard_surface_inventory.py",
        "--root",
        ".",
        "--member",
        "logic-writing",
        "--check",
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    result = json.loads(completed.stdout)
    assert result["status"] == "current"
    assert result["surface_count"] > 0
    assert result["source_path_count"] > 0

    source = json.loads(
        (CONTROL / "contract-source.json").read_text(encoding="utf-8")
    )
    inventory = json.loads(
        (CONTROL / "surface-inventory.json").read_text(encoding="utf-8")
    )
    deepening = "check:logic-writing:model-depth"
    assert source["depth_profile"]["model_deepening_check_id"] == deepening
    assert source["depth_profile"]["surface_inventory"]["model_deepening_check_id"] == deepening
    assert inventory["model_deepening_check_id"] == deepening
    assert inventory["inventory_hash"] == result["inventory_hash"]


def test_surface_inventory_has_a_governed_row_for_each_current_obligation():
    inventory = json.loads(
        (CONTROL / "surface-inventory.json").read_text(encoding="utf-8")
    )
    current = set(inventory["current_obligation_ids"])
    covered = {
        obligation_id
        for row in inventory["model_obligations"]
        for obligation_id in [row["obligation_id"]]
        if row["disposition"] == "governed" and row["surface_ids"]
    }
    assert covered == current


@pytest.fixture(scope="module")
def surface_context():
    path = ROOT / "scripts/author/build_skillguard_surface_inventory.py"
    spec = importlib.util.spec_from_file_location("lw_surface_contract_tests", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    scanner = module.load_skillguard()
    mapping = json.loads((CONTROL / "surface-semantic-map.json").read_text(encoding="utf-8"))
    inventory = json.loads((CONTROL / "surface-inventory.json").read_text(encoding="utf-8"))
    return module, scanner, mapping, inventory


def native_findings(context, inventory, root=ROOT):
    _, scanner, _, _ = context
    source = json.loads((CONTROL / "contract-source.json").read_text(encoding="utf-8"))
    profile = source["depth_profile"]
    return scanner.validate_full_surface_inventory(
        inventory, target_root=root / "skills/logic-writing", command_surface=(),
        route_entries=(), command_handlers=None,
        native_check_ids=profile["native_check_ids"],
        model_deepening_check_id=profile["model_deepening_check_id"],
    )


def test_compact_routes_preserve_real_native_owners_and_functions(surface_context):
    _, _, _, inventory = surface_context
    compiled = json.loads((CONTROL / "compiled-contract.json").read_text(encoding="utf-8"))
    expected = {row["route_id"]: (row["owner_id"], row["function_id"]) for row in compiled["routes"]}
    actual = {row["route_id"]: (row["owner_id"], row["function_id"]) for row in inventory["rows"]}
    assert len(expected) == 5
    assert actual == expected
    assert "owner:logic-writing:source-surface" not in inventory["owner_ids"]
    assert all(row["source_path"] for row in inventory["rows"])


def test_explicit_rules_preserve_reviewed_semantic_ownership(surface_context):
    module, _, _, inventory = surface_context
    rules = module._rules()
    assert set(rules[".skillguard/contract-source.json"]) == set(module.OBLIGATIONS)
    assert rules[".skillguard/evidence-specs/academic.json"] == ("academic-provenance",)
    assert set(rules["scripts/reader_pipeline.py"]) == {
        "routing", "academic-provenance", "fiction-native", "investigation-evidence",
        "reader-actual-artifact", "shared-writing", "travel-native",
    }
    for row in inventory["full_surfaces"]:
        assert {"check:logic-writing:model-depth", "check:logic-writing:contract-calibration"} <= set(row["adequacy_check_ids"])


def test_current_full_inventory_passes_native_discovery(surface_context):
    assert native_findings(surface_context, surface_context[3]) == ()


@pytest.mark.parametrize("mutation", ["missing_row", "unknown_owner", "missing_depth", "single_adequacy", "component_members", "live_as_not_applicable"])
def test_malformed_or_uncovered_live_surface_is_rejected(surface_context, mutation):
    _, scanner, _, original = surface_context
    inventory = copy.deepcopy(original)
    row = next(row for row in inventory["full_surfaces"] if row.get("review_granularity") == "component")
    if mutation == "missing_row":
        inventory["full_surfaces"].remove(row)
        inventory["full_surface_ids"].remove(row["surface_id"])
    elif mutation == "unknown_owner":
        row["owner_id"] = "owner:unknown"
    elif mutation == "missing_depth":
        row["adequacy_check_ids"].remove("check:logic-writing:model-depth")
    elif mutation == "single_adequacy":
        row["adequacy_check_ids"] = ["check:logic-writing:model-depth"]
    elif mutation == "component_members":
        row["component_members"] = []
    else:
        row["disposition"] = "not_applicable_proven"
        row["disposition_reason"] = "Caller declares this live implementation inapplicable."
    inventory["inventory_hash"] = scanner.surface_inventory_hash(inventory)
    assert native_findings(surface_context, inventory), mutation


def test_actual_source_byte_change_stales_inventory(surface_context):
    # A caller's deep --basetemp path can exceed the Windows path limit once
    # the real route fixture tree is appended. Keep this owned copy shallow.
    with tempfile.TemporaryDirectory(prefix="lwsg-") as directory:
        root = Path(directory)
        shutil.copytree(ROOT / "skills/logic-writing", root / "skills/logic-writing", ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        path = root / "skills/logic-writing/SKILL.md"
        path.write_bytes(path.read_bytes() + b"\nChanged author intent.\n")
        findings = native_findings(surface_context, surface_context[3], root=root)
        assert findings
        assert any("fingerprint" in row.code or "stale" in row.code for row in findings)


@pytest.mark.parametrize("mutation", ["known_model_rebind", "foreign_self_obligation"])
def test_resigned_semantic_map_cannot_redefine_author_rules(surface_context, mutation):
    module, scanner, original_mapping, inventory = surface_context
    mapping = copy.deepcopy(original_mapping)
    if mutation == "known_model_rebind":
        mapping["surface_bindings"][0]["model_obligation_ids"] = ["obligation:logic-writing:fiction-native"]
    else:
        mapping["decision_rules"][0]["model_obligation_ids"] = ["obligation:skillguard:self-depth"]
    mapping["map_hash"] = module._hash({key: value for key, value in mapping.items() if key != "map_hash"})
    with pytest.raises(ValueError, match="surface_semantic_map_stale_or_mismatched"):
        module.validate_outputs(ROOT, scanner, mapping, inventory)


def test_official_schema_rejects_invalid_function_id(surface_context):
    module, scanner, _, original = surface_context
    inventory = copy.deepcopy(original)
    inventory["rows"][0]["function_id"] = ".invalid-hidden-module"
    with pytest.raises(ValueError, match="schema invalid"):
        module._schema_check(inventory, "skillguard_surface_inventory_v1.schema.json", scanner)
