from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from check_consumer_resource_closure import check_consumer_resource_closure


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "skills/logic-writing/references/routes/required-resources.json"


def _stage(tmp_path: Path) -> Path:
    stage = tmp_path / "stage"
    shutil.copytree(ROOT / "skills", stage / "skills")
    return stage


def test_consumer_resource_closure_passes_both_route_stages(tmp_path):
    result = check_consumer_resource_closure(_stage(tmp_path))
    assert result["status"] == "passed"
    assert {row["route"] for row in result["routes"]} == {"fiction-writing", "travel-guide"}
    assert all(row["passed"] for row in result["routes"])


def test_missing_fiction_prose_reference_blocks_route(tmp_path):
    stage = _stage(tmp_path)
    path = stage / "skills/logic-writing/routes/fiction/references/prose-native-contract.md"
    path.unlink()
    result = check_consumer_resource_closure(stage, route="fiction-writing")
    codes = {finding["code"] for finding in result["findings"]}
    assert result["status"] == "failed"
    assert {"required_resource_missing", "missing_markdown_reference"} <= codes


def test_missing_travel_guide_text_blocks_json_association(tmp_path):
    stage = _stage(tmp_path)
    path = stage / "skills/logic-writing/routes/travel/examples/good_text_outputs/city_couple_native_guide.txt"
    path.unlink()
    result = check_consumer_resource_closure(stage, route="travel-guide")
    assert result["status"] == "failed"
    assert any(finding["code"] == "linked_prose_missing" for finding in result["findings"])


def test_test_only_missing_association_is_reported_without_runtime_dependency(tmp_path):
    stage = _stage(tmp_path)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["routes"]["travel-guide"]["json_associations"].append(
        {
            "json_path": "skills/logic-writing/routes/travel/examples/negative.json",
            "text_path": "skills/logic-writing/routes/travel/examples/negative.md",
            "required": False,
            "test_only": True,
        }
    )
    custom_manifest = stage / "manifest.json"
    custom_manifest.write_text(json.dumps(manifest), encoding="utf-8")
    result = check_consumer_resource_closure(stage, manifest_path=custom_manifest, route="travel-guide")
    assert result["status"] == "failed"
    assert {finding["code"] for finding in result["findings"]} >= {
        "test_only_json_missing",
        "test_only_text_missing",
    }
    assert all(association["test_only"] is False for association in result["routes"][0]["json_associations"][:1])
