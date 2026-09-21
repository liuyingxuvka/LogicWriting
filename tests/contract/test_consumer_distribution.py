from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = ROOT / "skills" / "logic-writing"


def test_declared_route_resources_are_copied_into_consumer_projection():
    manifest = json.loads(
        (SKILL_ROOT / "references" / "routes" / "required-resources.json").read_text(
            encoding="utf-8"
        )
    )
    contract = json.loads(
        (SKILL_ROOT / ".skillguard" / "compiled-contract.json").read_text(
            encoding="utf-8"
        )
    )
    inventory = {
        str(row["path"]): row
        for row in contract["content_impact_plan"]["inventory"]
    }

    def portable(path: str) -> str:
        prefix = "skills/logic-writing/"
        return path[len(prefix) :] if path.startswith(prefix) else path

    required_paths: set[str] = set()
    for route in manifest["routes"].values():
        required_paths.update(route.get("required_resources", []))
        required_paths.update(route.get("longform_resources", []))
        required_paths.update(
            association["json_path"]
            for association in route.get("json_associations", [])
        )
        required_paths.update(
            association["text_path"]
            for association in route.get("json_associations", [])
        )

    assert required_paths
    required_paths = {portable(path) for path in required_paths}
    assert all(path in inventory for path in required_paths)
    assert all(
        inventory[path]["install_disposition"] == "copy"
        for path in required_paths
    )

    projection_paths = set(contract["consumer_projection"]["file_paths"])
    assert required_paths <= projection_paths
    assert all(inventory[path]["install_disposition"] == "copy" for path in required_paths)
