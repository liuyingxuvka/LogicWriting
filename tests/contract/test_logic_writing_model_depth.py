"""Current map bindings and real source-dependent pointer invalidation."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import pytest
from flowguard.map.mapfile import load_map, model_registry, component_files, fingerprint, is_stale
from flowguard.map.inventory import build_inventory

ROOT = Path(__file__).resolve().parents[2]


def test_project_root_contract_declares_the_exact_logic_writing_mesh():
    data = load_map(ROOT)
    registry = model_registry(ROOT, data)
    assert data["project"] == "logic-writing"
    assert not registry.issues
    ids = {entry.id for entry in registry.entries}
    assert {"reader_artifact_model", "research_packet_model", "execution_binding", "operation_freshness_closure_model"} <= ids
    assert {"writer_projection", "editorial_disposition", "composition_graph", "artifact_audit", "researchguard_handoff", "logic_writing_models"}.isdisjoint(ids)
    owners = {row["id"]: row for row in data["components"]}
    bindings = json.loads((ROOT / ".flowguard/structure/owner-bindings.json").read_text())["bindings"]
    for leaf in bindings.values():
        owner = owners[leaf["owner"]]
        assert owner["models"]
        for path in leaf["runtime"] + leaf["tests"]:
            assert path in owner["files"]
            assert (ROOT / path).is_file()
        assert all(path in owner["tests"] for path in leaf["tests"])


@pytest.mark.parametrize("changed", [
    "skills/logic-writing/scripts/reader_pipeline.py",
    "skills/logic-writing/assets/schemas/artifact-map.schema.json",
    "tests/unit/test_writer_projection.py",
])
def test_native_protocol_rejects_old_execution_rebound_to_new_current_sources(tmp_path, changed):
    # The current FG pointer binds actual runtime/schema/tests. No native
    # terminal-success receipt is reused across runs or source versions.
    data = load_map(ROOT)
    selected = ["skills/logic-writing/scripts/reader_pipeline.py",
                "skills/logic-writing/assets/schemas/artifact-map.schema.json",
                "tests/unit/test_writer_projection.py",
                "skills/logic-writing/scripts/researchguard_handoff.py"]
    for relative in selected:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    inv = build_inventory(tmp_path, [])
    inv.set_explicit_sources(selected)
    comps = {row["id"]: dict(row) for row in data["components"]}
    for comp in comps.values():
        comp["status"] = "confirmed"
        comp["fingerprint"] = fingerprint(tmp_path, component_files(comp, inv))
    assert not is_stale(tmp_path, comps["reader-artifact"], inv)
    target = tmp_path / changed
    target.write_bytes(target.read_bytes() + b"\n ")
    inv = build_inventory(tmp_path, [])
    inv.set_explicit_sources(selected)
    assert is_stale(tmp_path, comps["reader-artifact"], inv)
    assert not is_stale(tmp_path, comps["research-packet"], inv)
