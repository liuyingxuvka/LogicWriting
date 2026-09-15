from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load_runner():
    path = SCRIPTS / "run_frozen_validation.py"
    spec = importlib.util.spec_from_file_location("logic_writing_run_frozen_validation_timeout", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _DrainTimeoutProcess:
    pid = 4172
    returncode = None

    def __init__(self) -> None:
        self.communicate_calls = 0

    def communicate(self, *, timeout: int):
        self.communicate_calls += 1
        if self.communicate_calls == 1:
            raise subprocess.TimeoutExpired("owner", timeout, output=b"partial-out", stderr=b"partial-err")
        raise subprocess.TimeoutExpired("owner", timeout, output=b"tail-out", stderr=b"tail-err")


def test_execute_timeout_with_pipe_drain_timeout_returns_terminal_result(monkeypatch, tmp_path):
    runner = _load_runner()
    process = _DrainTimeoutProcess()

    monkeypatch.setattr(runner, "_resolve_executable", lambda name: name)
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(runner, "_terminate_and_confirm", lambda _process: (False, [4172]))

    result = runner._execute(["python", "-c", "pass"], cwd=tmp_path, timeout=1)

    assert result["timed_out"] is True
    assert result["cleanup_confirmed"] is False
    assert result["remaining_process_ids"] == [4172]
    assert result["pipe_drain_timeout"] is True
    assert result["stdout"] == "partial-outtail-out"
    assert result["stderr"] == "partial-errtail-err"


def test_unexpected_timeout_still_writes_failed_owner_receipt(monkeypatch, tmp_path):
    runner = _load_runner()
    (tmp_path / "openspec").mkdir()
    (tmp_path / "source.txt").write_text("source\n", encoding="utf-8")
    contract = {
        "contract_version": "timeout-test-v1",
        "freshness": {"watch": ["source.txt"], "exclude": []},
        "checks": [
            {
                "id": "check.one",
                "kind": "command",
                "semantic_check_id": "test.one",
                "execution_id": "test-one-v1",
                "toolchain_identity": "python-test-runtime",
                "input_selectors": ["source.txt"],
                "depends_on_receipts": [],
                "command": "python",
                "args": ["-c", "pass", "--output-dir", "{owner_run_root}"],
                "timeout_seconds": 1,
                "expected": {"exit_code": 0},
            }
        ],
    }
    (tmp_path / "openspec" / "verification-contract.yaml").write_text(
        json.dumps(contract), encoding="utf-8"
    )
    receipts = tmp_path / "receipts"
    monkeypatch.setattr(
        runner,
        "_toolchain_observation",
        lambda check: {
            "declared_identity": check["toolchain_identity"],
            "observation_hash": "sha256:" + "b" * 64,
        },
    )

    def unexpected_timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("owner", 1, stderr=b"late-timeout")

    monkeypatch.setattr(runner, "_execute", unexpected_timeout)

    with pytest.raises(RuntimeError, match="cleanup_unconfirmed:check.one"):
        runner.run_validation(
            tmp_path,
            Path("openspec/verification-contract.yaml"),
            receipts,
            audit_only=False,
            require_clean_git=False,
        )

    attempts = list((receipts / "attempts" / "check.one").iterdir())
    assert len(attempts) == 1
    attempt = attempts[0]
    assert (attempt / "stdout.txt").is_file()
    assert (attempt / "stderr.txt").is_file()
    assert (attempt / "result.json").is_file()
    assert (attempt / "receipt.json").is_file()
    result = json.loads((attempt / "result.json").read_text(encoding="utf-8"))
    receipt = json.loads((attempt / "receipt.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "failed"
    assert receipt["terminal_status"] == "failed"
    assert result["status"] == "failed"
    assert receipt["timed_out"] is True
    assert receipt["cleanup_confirmed"] is False
    assert receipt["cleanup_error"] == "unhandled_timeout_from_owner_executor"


def test_testmesh_owner_result_records_passed_terminal_status_for_audit(monkeypatch, tmp_path):
    runner = _load_runner()
    (tmp_path / "openspec").mkdir()
    (tmp_path / "source.txt").write_text("source\n", encoding="utf-8")
    contract = {
        "contract_version": "status-test-v1",
        "freshness": {"watch": ["source.txt"], "exclude": []},
        "test_mesh": {},
        "checks": [{
            "id": "check.testmesh.plan", "kind": "command", "semantic_check_id": "test.one",
            "execution_id": "test-one-v1", "toolchain_identity": "python-test-runtime",
            "input_selectors": ["source.txt"], "depends_on_receipts": [],
            "command": "python", "args": ["-c", "pass", "--output-dir", "{owner_run_root}"],
            "timeout_seconds": 1, "expected": {"exit_code": 0},
        }],
    }
    (tmp_path / "openspec" / "verification-contract.yaml").write_text(
        json.dumps(contract), encoding="utf-8"
    )
    monkeypatch.setattr(
        runner,
        "_toolchain_observation",
        lambda check: {
            "declared_identity": check["toolchain_identity"],
            "observation_hash": "sha256:" + "c" * 64,
        },
    )
    monkeypatch.setattr(
        runner,
        "_execute",
        lambda *_args, **_kwargs: {
            "exit_code": 0,
            "stdout": "owner ok",
            "stderr": "",
            "timed_out": False,
            "cleanup_confirmed": True,
            "remaining_process_ids": [],
            "elapsed_seconds": 0.01,
        },
    )

    report = runner.run_validation(
        tmp_path,
        Path("openspec/verification-contract.yaml"),
        tmp_path / "receipts",
        audit_only=False,
        require_clean_git=False,
    )

    assert report["status"] == "passed"
    assert report["test_mesh"]["status"] == "passed"
    audit = runner.run_validation(
        tmp_path,
        Path("openspec/verification-contract.yaml"),
        tmp_path / "receipts",
        audit_only=True,
        require_clean_git=False,
    )
    assert audit["status"] == "passed", audit
    attempts = list((tmp_path / "receipts" / "attempts" / "check.testmesh.plan").iterdir())
    assert len(attempts) == 1
    result = json.loads((attempts[0] / "result.json").read_text(encoding="utf-8"))
    assert result["status"] == "passed"
