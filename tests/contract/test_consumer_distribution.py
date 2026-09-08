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
    assert all(path in inventory for path in required_paths)
    assert all(
        inventory[path]["install_disposition"] == "copy"
        for path in required_paths
    )

    # Keep the reviewed subtree overrides broad enough to cover newly added
    # route references and example payloads without another hand-maintained
    # per-file list.
    overrides = {
        str(row["path"]): row
        for row in json.loads(
            (SKILL_ROOT / ".skillguard" / "contract-source.json").read_text(
                encoding="utf-8"
            )
        )["content_role_overrides"]
    }
    assert {
        "skills/logic-writing/routes/fiction/references",
        "skills/logic-writing/routes/travel/references",
        "skills/logic-writing/routes/fiction/examples",
        "skills/logic-writing/routes/travel/examples",
    } == set(overrides)
    assert all(row["install_disposition"] == "copy" for row in overrides.values())
