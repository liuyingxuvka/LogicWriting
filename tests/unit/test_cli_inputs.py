from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests.v2_support import closure_input, complete_chain, make_reader_chain, route_request

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "logic-writing" / "scripts"


def run(script: str, request: Path, output: Path | None = None) -> subprocess.CompletedProcess:
    argv = [sys.executable, str(SCRIPTS / script), "--input", str(request)]
    if output is not None:
        argv += ["--output", str(output)]
    return subprocess.run(argv, capture_output=True, text=True, cwd=request.parent)


def test_request_fields_may_name_json_files(tmp_path):
    inline = closure_input(complete_chain(tmp_path / "chain"))
    by_file = {}
    for key, value in inline.items():
        if isinstance(value, dict):
            (tmp_path / f"{key}.json").write_text(json.dumps(value), encoding="utf-8")
            by_file[key] = f"{key}.json"
        else:
            by_file[key] = value
    request = tmp_path / "closure-input.json"
    request.write_text(json.dumps(by_file), encoding="utf-8")
    closed = run("derive_closure.py", request)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert json.loads(closed.stdout)["closure"]["status"] == "passed"

    by_file["artifact_map"] = "missing.json"
    request.write_text(json.dumps(by_file), encoding="utf-8")
    assert run("derive_closure.py", request).returncode != 0


def test_a_field_may_name_an_earlier_scripts_output(tmp_path):
    chain = make_reader_chain(tmp_path / "chain", owner="investigation")
    route_input = tmp_path / "route-request.json"
    route_input.write_text(json.dumps(route_request("research_report")), encoding="utf-8")
    assert run("select_route.py", route_input, tmp_path / "route.json").returncode == 0
    brief_input = tmp_path / "brief-request.json"
    brief_input.write_text(json.dumps({
        "route_decision": "route.json",
        "content_boundaries": chain["reader_brief"]["content_boundaries"],
        "composition_plan": chain["plan"],
        "route_composition": chain["route_composition"],
        "brief_id": "brief:file-input",
    }), encoding="utf-8")
    built = run("build_reader_brief.py", brief_input)
    assert built.returncode == 0, built.stdout + built.stderr
    assert json.loads(built.stdout)["reader_brief"]["final_owner"] == "investigation"


def test_json_named_artifact_path_and_scalar_id_are_not_expanded(tmp_path):
    import hashlib

    artifact = tmp_path / "reader.json"
    artifact.write_text('{"measurement": 12}\n', encoding="utf-8")
    request = tmp_path / "map-request.json"
    request.write_text(json.dumps({
        "artifact_path": str(artifact),
        "map_id": "not-a-file.json",
        "language": "en",
    }), encoding="utf-8")
    built = run("build_artifact_map.py", request)
    assert built.returncode == 0, built.stdout + built.stderr
    amap = json.loads(built.stdout)["artifact_map"]
    assert amap["map_id"] == "not-a-file.json"
    assert amap["artifact_fingerprint"] == "sha256:" + hashlib.sha256(artifact.read_bytes()).hexdigest()
