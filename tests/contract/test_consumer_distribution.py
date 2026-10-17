from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = ROOT / "skills" / "logic-writing"


def test_declared_route_resources_are_copied_into_consumer_projection(tmp_path):
    manifest = json.loads(
        (SKILL_ROOT / "references" / "routes" / "required-resources.json").read_text(
            encoding="utf-8"
        )
    )
    stage = tmp_path / "skills" / "logic-writing"
    shutil.copytree(SKILL_ROOT, stage, ignore=shutil.ignore_patterns("__pycache__"))

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
    assert all((stage / path).is_file() for path in required_paths)
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from check_installation_parity import check
    assert check(SKILL_ROOT, tmp_path)["status"] == "passed"
    target = stage / next(iter(sorted(required_paths)))
    target.write_bytes(target.read_bytes() + b"\nchanged")
    assert check(SKILL_ROOT, tmp_path)["status"] == "failed"
