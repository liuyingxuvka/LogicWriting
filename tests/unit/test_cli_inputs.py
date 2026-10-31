from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

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
        "request": chain["reader_brief"]["request"],
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


def test_relative_artifact_path_is_read_from_the_request_folder(tmp_path):
    artifact = tmp_path / "piece.md"
    artifact.write_text("A current paragraph.\n", encoding="utf-8")
    request = tmp_path / "map-req.json"
    request.write_text(json.dumps({"artifact_path": "piece.md", "map_id": "map:relative", "language": "en"}), encoding="utf-8")
    argv = [sys.executable, str(SCRIPTS / "build_artifact_map.py"), "--input", str(request)]

    built = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
    assert built.returncode == 0, built.stdout + built.stderr
    assert json.loads(built.stdout)["artifact_map"]["artifact_path"] == str(artifact)

    artifact.rename(tmp_path / "renamed.md")
    missing = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
    assert missing.returncode == 1
    assert f"artifact_path does not identify a current file: {artifact}" in missing.stdout


def test_artifact_path_in_referenced_objects_uses_the_containing_file(tmp_path):
    from _common import load_request

    request_folder = tmp_path / "request"
    reference_folder = tmp_path / "records"
    request_folder.mkdir()
    reference_folder.mkdir()
    contract = {"artifact_path": "contract.md"}
    shared = {"artifact_path": "shared.md"}
    (reference_folder / "contract.json").write_text(json.dumps(contract), encoding="utf-8")
    (reference_folder / "shared.json").write_text(json.dumps({
        "status": "current_pass", "errors": [], "warnings": [], "shared_writing": shared,
    }), encoding="utf-8")
    request = request_folder / "input.json"
    request.write_text(json.dumps({
        "contract": "../records/contract.json", "shared_writing": "../records/shared.json",
        "artifact_map": {"artifact_path": "do-not-rebase.md"},
        "native_result_locator": "opaque-result.json", "map_id": "scalar.json",
    }), encoding="utf-8")

    loaded = load_request(request)

    assert loaded["contract"]["artifact_path"] == str(reference_folder / "contract.md")
    assert loaded["shared_writing"]["artifact_path"] == str(reference_folder / "shared.md")
    assert loaded["artifact_map"]["artifact_path"] == "do-not-rebase.md"
    assert loaded["native_result_locator"] == "opaque-result.json"
    assert loaded["map_id"] == "scalar.json"


def test_inline_artifact_paths_use_request_folder_and_stdin_stays_relative(tmp_path, monkeypatch):
    import io
    from _common import load_request

    payload = {"artifact_path": "piece.md", "contract": {"artifact_path": "contract.md"},
               "shared_writing": {"artifact_path": "shared.md"}}
    request = tmp_path / "input.json"
    request.write_text(json.dumps(payload), encoding="utf-8")
    loaded = load_request(request)
    assert loaded["artifact_path"] == str(tmp_path / "piece.md")
    assert loaded["contract"]["artifact_path"] == str(tmp_path / "contract.md")
    assert loaded["shared_writing"]["artifact_path"] == str(tmp_path / "shared.md")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert load_request("-") == payload


@pytest.mark.parametrize("case", ["blocked", "partial_errors", "blocked_empty", "matching_partial", "success_sole", "raw_status"])
def test_a_failed_result_is_not_used_as_the_next_input(tmp_path, case):
    from _common import ValidationError, load_request

    records = tmp_path / "records"
    records.mkdir()
    payload = {"status": "blocked", "errors": ["first reason\ncontinued", "later error"],
               "warnings": [], "unrelated": {"other": True}}
    if case == "partial_errors":
        payload["status"] = "partial"
    elif case == "blocked_empty":
        payload["errors"] = []
    elif case == "matching_partial":
        payload.update(status="partial", shared_writing={"artifact_path": "piece.md"})
    elif case == "success_sole":
        payload.update(status="current_pass", errors=[])
    elif case == "raw_status":
        payload = {"status": "draft", "content": "raw object"}
    (records / "earlier.json").write_text(json.dumps(payload), encoding="utf-8")
    request = tmp_path / "request.json"
    request.write_text(json.dumps({"shared_writing": "records/earlier.json"}), encoding="utf-8")
    if case in {"blocked", "partial_errors", "blocked_empty"}:
        with pytest.raises(ValidationError) as raised:
            load_request(request)
        message = str(raised.value)
        assert message.startswith(f"input earlier.json is a failed result (status {payload['status']}): ")
        assert "\n" not in message
        if case != "blocked_empty":
            assert message.endswith("first reason continued")
            assert "later error" not in message
    else:
        loaded = load_request(request)["shared_writing"]
        if case == "matching_partial":
            assert loaded == {"artifact_path": str(records / "piece.md")}
        elif case == "success_sole":
            assert loaded == {"other": True}
        else:
            assert loaded == payload
