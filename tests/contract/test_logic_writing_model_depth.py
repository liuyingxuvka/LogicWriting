"""Fail-closed contract tests for the target-owned model-depth checker."""

from __future__ import annotations

import json
import importlib.util
from dataclasses import replace
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from flowguard.native_case_protocol import NativeModelCaseResult


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def checker():
    path = ROOT / "scripts" / "author" / "check_logic_writing_model_depth.py"
    spec = importlib.util.spec_from_file_location("model_depth_checker_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _write_native_envelope(case, result):
    """Bind synthetic protocol data; this does not execute a model owner."""
    _write_json(case.path, {
        "schema_version": "flowguard.native_model_case_result.v1",
        "results": [result.to_dict()],
    })
    case.result = result
    case.payload["native_case"] = {
        "path": str(case.path),
        "fingerprint": case.checker._sha(case.path),
        "result": result.to_dict(),
    }


@pytest.fixture
def native_protocol_case(tmp_path, checker):
    """A temporary typed fixture, never evidence of real model execution."""
    root = tmp_path / "project"
    root.mkdir()
    model_id = "protocol_fixture"
    model_path = "model.py"
    runner_path = "runner.py"
    test_path = "test_model.py"
    for relative in (model_path, runner_path, test_path):
        (root / relative).write_text(f"# synthetic protocol fixture: {relative}\n", encoding="utf-8")
    hashes = {relative: checker._sha(root / relative) for relative in (model_path, runner_path, test_path)}
    mesh = SimpleNamespace(
        MODEL_PATHS={model_id: model_path},
        RUNNER_PATHS={model_id: runner_path},
        TEST_PATHS={model_id: (test_path,)},
        _source_hashes=lambda _model, current_root: {
            relative: checker._sha(current_root / relative)
            for relative in (model_path, runner_path, test_path)
        },
    )
    output = tmp_path / "declared-native-output"
    output.mkdir()
    raw = output / "raw-result.json"
    summary = {"synthetic": True, "claim_scope": "protocol_only"}
    raw_payload = {
        "schema_version": "logic-writing.model-mesh-raw-result.v1",
        "model_id": model_id,
        "status": "pass",
        "summary": summary,
        "source_hashes": hashes,
    }
    _write_json(raw, raw_payload)
    result = NativeModelCaseResult(
        owner_id=f"model:{model_id}",
        source_case_id=f"mesh:{model_id}:current",
        outcome="pass",
        observed_status="pass",
        observed_finding_codes=(),
        executed_dimensions=checker.EXPECTED_DIMENSIONS,
        oracle_results=tuple({
            "dimension": dimension,
            "oracle_member_id": f"native:{model_id}:oracle",
            "status": "pass",
            "ok": True,
        } for dimension in checker.EXPECTED_DIMENSIONS),
        result_artifact_fingerprint=checker._sha(raw),
        # An orchestrated input need not alias the source-hash fingerprint.
        input_fingerprint=checker._fingerprint({"synthetic_runner_request": model_id}),
        model_fingerprint=hashes[model_path],
        code_fingerprint=checker._fingerprint({"model": hashes[model_path], "sources": hashes}),
        test_fingerprint=checker._fingerprint({"runner": hashes[runner_path], "tests": [hashes[test_path]]}),
        oracle_fingerprint=checker._fingerprint({"model_id": model_id, "status": "pass", "oracle": "native-model-mesh"}),
        toolchain_fingerprint=checker._fingerprint({"synthetic": "toolchain"}),
        environment_fingerprint=checker._fingerprint({"synthetic": "environment"}),
        raw_artifact_path="raw-result.json",
    )
    case = SimpleNamespace(
        checker=checker, root=root, mesh=mesh, model_id=model_id,
        path=output / "native-case-results.json", raw=raw, raw_payload=raw_payload,
        payload={"model_id": model_id, "status": "pass", "summary": summary,
                 "model_fingerprint": hashes[model_path], "source_hashes": hashes},
    )
    _write_native_envelope(case, result)
    return case


def _native_findings(case):
    findings = []
    case.checker._native(case.root, case.mesh, case.model_id, case.payload, findings)
    return findings


def test_native_protocol_accepts_the_declared_external_output_directory(native_protocol_case):
    case = native_protocol_case
    assert not case.path.is_relative_to(case.root)
    assert _native_findings(case) == []


@pytest.mark.parametrize("path_kind", ["relative", "wrong_filename", "symlink"])
def test_native_protocol_rejects_invalid_declared_paths(native_protocol_case, monkeypatch, path_kind):
    case = native_protocol_case
    if path_kind == "relative":
        case.payload["native_case"]["path"] = "native-case-results.json"
    elif path_kind == "wrong_filename":
        case.payload["native_case"]["path"] = str(case.path.with_name("other.json"))
    else:
        original = Path.is_symlink
        monkeypatch.setattr(Path, "is_symlink", lambda path: path == case.path or original(path))
    assert "native_terminal_receipt_path_mismatch" in {row["code"] for row in _native_findings(case)}


@pytest.mark.parametrize("field", ["model_id", "status", "summary", "source_hashes"])
def test_native_protocol_rejects_rehashed_raw_payload_disagreement(native_protocol_case, field):
    case = native_protocol_case
    replacement = {
        "model_id": "different_model",
        "status": "blocked",
        "summary": {"synthetic": True, "claim_scope": "different"},
        "source_hashes": {"old.py": case.checker._fingerprint({"old": "source"})},
    }
    raw = dict(case.raw_payload)
    raw[field] = replacement[field]
    _write_json(case.raw, raw)
    _write_native_envelope(case, replace(case.result, result_artifact_fingerprint=case.checker._sha(case.raw)))
    findings = _native_findings(case)
    assert any(row["code"] == "native_terminal_raw_payload_mismatch" and field in row.get("detail", "") for row in findings)
    assert not any(row["code"] == "native_terminal_raw_artifact_stale" for row in findings)


@pytest.mark.parametrize("field,code", [
    ("code_fingerprint", "native_terminal_receipt_code_mismatch"),
    ("test_fingerprint", "native_terminal_receipt_test_mismatch"),
    ("oracle_fingerprint", "native_terminal_receipt_oracle_mismatch"),
])
def test_native_protocol_rejects_validly_shaped_but_foreign_fingerprints(native_protocol_case, field, code):
    case = native_protocol_case
    wrong = case.checker._fingerprint({"foreign": field})
    _write_native_envelope(case, replace(case.result, **{field: wrong}))
    assert code in {row["code"] for row in _native_findings(case)}


def test_native_protocol_rejects_old_execution_rebound_to_new_current_sources(native_protocol_case):
    case = native_protocol_case
    (case.root / "test_model.py").write_text("# changed synthetic test source\n", encoding="utf-8")
    case.payload["source_hashes"] = case.mesh._source_hashes(case.model_id, case.root)
    findings = _native_findings(case)
    assert any(row["code"] == "native_terminal_raw_payload_mismatch" and "source_hashes" in row.get("detail", "") for row in findings)
    assert "native_terminal_receipt_code_mismatch" in {row["code"] for row in findings}
    assert "native_terminal_receipt_test_mismatch" in {row["code"] for row in findings}


def test_model_depth_parent_review_preserves_a_typed_missing_parent_finding(checker, tmp_path):
    findings = []
    mesh = SimpleNamespace(CHILDREN={"parent": ("child",)})
    checker._parent_review(tmp_path, mesh, "parent", {"child": {"model_id": "child"}}, "", findings)
    assert any(row["code"] == "missing_parent_receipt" for row in findings)


def test_model_depth_checker_emits_the_fixed_receipt_shape():
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/author/check_logic_writing_model_depth.py",
            "--root",
            ".",
            "--json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    result = json.loads(completed.stdout)
    assert result["schema_version"] == "logic-writing.model-depth-check.v1"
    assert result["source_fingerprint"].startswith("sha256:")
    assert len(result["checked_model_ids"]) == 22
    assert len(result["consumed_receipt_refs"]) > 0
    assert result["status"] in {"pass", "blocked"}
    assert all(isinstance(row.get("code"), str) for row in result["findings"])
    assert completed.returncode == (0 if result["status"] == "pass" else 1)


def test_model_depth_checker_rejects_a_non_logic_writing_root(tmp_path):
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "author" / "check_logic_writing_model_depth.py"),
            "--root",
            str(tmp_path),
            "--json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    result = json.loads(completed.stdout)
    assert completed.returncode == 1
    assert result["status"] == "blocked"
    assert any(row["code"] == "wrong_repository_or_source" for row in result["findings"])


def test_model_depth_source_bindings_use_canonical_text_identity(checker, tmp_path):
    crlf = tmp_path / "crlf.py"
    lf = tmp_path / "lf.py"
    crlf.write_bytes(b"value = 1\r\n")
    lf.write_bytes(b"value = 1\n")

    # Authority source bindings use FlowGuard's canonical text identity, while
    # native receipt envelopes continue to protect their exact artifact bytes.
    assert checker._source_sha(crlf) == checker._source_sha(lf)
    assert checker._sha(crlf) != checker._sha(lf)
