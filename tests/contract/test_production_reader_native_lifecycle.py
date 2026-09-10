from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import production_reader_pipeline as pipeline
from build_source_unit_manifest import fingerprint_bytes


class _FakeNativeProcess:
    def __init__(self, command: list[str], mode: str):
        self.command = command
        self.mode = mode
        self.pid = 48152
        self.returncode: int | None = 0 if mode == "normal" else 9 if mode == "nonzero" else None
        self.communicate_calls: list[float] = []
        self.killed = False
        output = Path(command[command.index("--output") + 1])
        if mode in {"normal", "nonzero"}:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps({"status": "pass" if mode == "normal" else "blocked"}) + "\n", encoding="utf-8")

    def poll(self) -> int | None:
        return self.returncode

    def communicate(self, *, timeout: float):
        self.communicate_calls.append(timeout)
        if self.mode == "normal":
            return "native stdout", "native stderr"
        if self.mode == "nonzero":
            return "blocked stdout", "blocked stderr"
        if self.mode == "communicate-error":
            raise OSError("synthetic pipe capture failure")
        if len(self.communicate_calls) == 1:
            raise subprocess.TimeoutExpired(self.command, timeout, output="partial stdout", stderr="partial stderr")
        if self.mode == "timeout-drain":
            raise subprocess.TimeoutExpired(self.command, timeout, output="late stdout", stderr="late stderr")
        self.returncode = -9
        return "after kill", "killed stderr"


def _run(provider: pipeline.InstalledResearchGuardProvider, root: Path) -> dict:
    output = root / "native-result.json"
    return provider._run("synthetic-console", ["depth", "model.json"], output, cwd=root)


def _receipt(root: Path) -> dict:
    path = root / "native-result.execution.json"
    assert path.is_file()
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("mode", ["normal", "nonzero"])
def test_native_execution_receipt_is_written_for_exit_paths(monkeypatch, tmp_path: Path, mode: str):
    process_box: list[_FakeNativeProcess] = []

    def popen(command, **kwargs):
        process = _FakeNativeProcess(command, mode)
        process_box.append(process)
        return process

    monkeypatch.setattr(pipeline.subprocess, "Popen", popen)
    provider = pipeline.InstalledResearchGuardProvider(timeout_seconds=3, cleanup_timeout_seconds=1)

    if mode == "normal":
        assert _run(provider, tmp_path) == {"status": "pass"}
    else:
        with pytest.raises(pipeline.ProductionPipelineBlocked, match="native_check_blocked"):
            _run(provider, tmp_path)

    receipt = _receipt(tmp_path)
    process = process_box[0]
    output_bytes = (tmp_path / "native-result.json").read_bytes()
    assert receipt["pid"] == process.pid
    assert receipt["terminal_status"] == ("completed" if mode == "normal" else "failed")
    assert receipt["timeout"] is False
    assert receipt["cleanup_method"] == "natural_exit"
    assert receipt["cleanup_confirmed"] is True
    assert receipt["stdout_fingerprint"] == fingerprint_bytes(
        ("native stdout" if mode == "normal" else "blocked stdout").encode("utf-8")
    )
    assert receipt["stderr_fingerprint"] == fingerprint_bytes(
        ("native stderr" if mode == "normal" else "blocked stderr").encode("utf-8")
    )
    assert receipt["output_fingerprint"] == fingerprint_bytes(output_bytes)
    assert process.communicate_calls == [3]


def test_native_timeout_receipt_records_bounded_cleanup(monkeypatch, tmp_path: Path):
    process_box: list[_FakeNativeProcess] = []

    def popen(command, **kwargs):
        process = _FakeNativeProcess(command, "timeout")
        process_box.append(process)
        return process

    def taskkill(command, **kwargs):
        assert kwargs["timeout"] == 1
        process_box[0].killed = True
        process_box[0].returncode = -9
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(pipeline.subprocess, "Popen", popen)
    monkeypatch.setattr(pipeline.subprocess, "run", taskkill)
    provider = pipeline.InstalledResearchGuardProvider(timeout_seconds=3, cleanup_timeout_seconds=1)

    with pytest.raises(pipeline.ProductionPipelineBlocked, match="native_provider_timeout"):
        _run(provider, tmp_path)

    receipt = _receipt(tmp_path)
    process = process_box[0]
    assert process.killed is True
    assert process.communicate_calls == [3, 1]
    assert receipt["pid"] == process.pid
    assert receipt["terminal_status"] == "timed_out"
    assert receipt["timeout"] is True
    assert receipt["timeout_stage"] == "execution"
    assert receipt["cleanup_method"] == "taskkill_tree"
    assert receipt["cleanup_confirmed"] is True
    assert receipt["stdout_fingerprint"] == fingerprint_bytes(b"after kill")
    assert receipt["stderr_fingerprint"] == fingerprint_bytes(b"killed stderr")
    assert receipt["output_fingerprint"] is None


def test_second_cleanup_drain_timeout_is_fail_closed_and_receipted(monkeypatch, tmp_path: Path):
    process_box: list[_FakeNativeProcess] = []

    def popen(command, **kwargs):
        process = _FakeNativeProcess(command, "timeout-drain")
        process_box.append(process)
        return process

    def taskkill(command, **kwargs):
        assert kwargs["timeout"] == 1
        # Pretend taskkill acknowledged the tree while the pipe remains
        # un-drainable.  The second communicate timeout must still block.
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(pipeline.subprocess, "Popen", popen)
    monkeypatch.setattr(pipeline.subprocess, "run", taskkill)
    provider = pipeline.InstalledResearchGuardProvider(timeout_seconds=3, cleanup_timeout_seconds=1)

    with pytest.raises(pipeline.ProductionPipelineBlocked, match="native_cleanup_unconfirmed"):
        _run(provider, tmp_path)

    receipt = _receipt(tmp_path)
    process = process_box[0]
    assert process.communicate_calls == [3, 1]
    assert receipt["pid"] == process.pid
    assert receipt["terminal_status"] == "timed_out"
    assert receipt["timeout"] is True
    assert receipt["timeout_stage"] == "cleanup_drain"
    assert receipt["cleanup_method"] == "taskkill_tree+communicate_timeout"
    assert receipt["cleanup_confirmed"] is False
    assert receipt["stdout_fingerprint"] == fingerprint_bytes(b"late stdout")
    assert receipt["stderr_fingerprint"] == fingerprint_bytes(b"late stderr")


def test_communicate_error_cannot_be_reported_as_a_native_pass(monkeypatch, tmp_path: Path):
    process_box: list[_FakeNativeProcess] = []

    def popen(command, **kwargs):
        process = _FakeNativeProcess(command, "communicate-error")
        process_box.append(process)
        return process

    def taskkill(command, **kwargs):
        assert kwargs["timeout"] == 1
        return type("Result", (), {"returncode": 1})()

    monkeypatch.setattr(pipeline.subprocess, "Popen", popen)
    monkeypatch.setattr(pipeline.subprocess, "run", taskkill)
    provider = pipeline.InstalledResearchGuardProvider(timeout_seconds=3, cleanup_timeout_seconds=1)

    with pytest.raises(pipeline.ProductionPipelineBlocked, match="native_execution_capture_failed"):
        _run(provider, tmp_path)

    receipt = _receipt(tmp_path)
    assert receipt["terminal_status"] == "failed"
    assert receipt["communicate_completed"] is False
    assert "synthetic pipe capture failure" in receipt["failure_detail"]


def test_taskkill_timeout_is_bounded_and_fail_closed(monkeypatch, tmp_path: Path):
    process_box: list[_FakeNativeProcess] = []

    def popen(command, **kwargs):
        process = _FakeNativeProcess(command, "timeout")
        process_box.append(process)
        return process

    def taskkill(command, **kwargs):
        assert kwargs["timeout"] == 1
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(pipeline.subprocess, "Popen", popen)
    monkeypatch.setattr(pipeline.subprocess, "run", taskkill)
    provider = pipeline.InstalledResearchGuardProvider(timeout_seconds=3, cleanup_timeout_seconds=1)

    with pytest.raises(pipeline.ProductionPipelineBlocked, match="native_cleanup_unconfirmed"):
        _run(provider, tmp_path)

    receipt = _receipt(tmp_path)
    assert process_box[0].communicate_calls == [3, 1]
    assert receipt["terminal_status"] == "timed_out"
    assert receipt["timeout"] is True
    assert receipt["cleanup_method"] == "taskkill_timeout"
    assert receipt["cleanup_confirmed"] is False
