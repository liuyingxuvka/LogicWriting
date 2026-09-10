from __future__ import annotations

import inspect
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import local_execution_backend as backend_module
from local_execution_backend import LocalCodexBackend, _read_pipe_chunk


def _backend(tmp_path: Path, *, timeout_seconds: int = 5, no_progress_seconds: int = 0) -> LocalCodexBackend:
    # The pinned executable is only used for identity/version probing in these
    # tests.  Popen is replaced with a short fake child below, so no desktop
    # Codex or credentials are touched.
    executable = tmp_path / "codex.exe"
    executable.write_bytes(b"fake pinned executable")
    backend = object.__new__(LocalCodexBackend)
    backend.run_root = (tmp_path / "captures").resolve()
    backend.run_root.mkdir(parents=True, exist_ok=True)
    backend.executable = executable.resolve()
    backend.model_id = "gpt-6-astra"
    backend.reasoning_effort = "xhigh"
    backend.timeout_seconds = timeout_seconds
    backend.no_progress_seconds = no_progress_seconds
    backend.expected_version = ""
    backend.expected_sha256 = ""
    backend.executable_sha256 = hashlib.sha256(executable.read_bytes()).hexdigest()
    backend.cli_version = "0.0.0"
    backend.backend_id = "local-codex:0.0.0:gpt-6-astra:xhigh"
    return backend


def _install_fake_child(monkeypatch, *, mode: str = "complete"):
    real_popen = subprocess.Popen
    real_run = subprocess.run

    if mode == "complete":
        code = (
            "import json,pathlib,sys,time; "
            "sys.stdin.buffer.read(); "
            "events=[{'type':'thread.started','thread_id':'fake-thread'},"
            "{'type':'turn.started'},"
            "{'type':'item.completed','item':{'type':'agent_message','text':'done'}},"
            "{'type':'turn.completed'}]; "
            "[ (sys.stdout.write(json.dumps(item)+'\\n'),sys.stdout.flush()) for item in events ]; "
            "pathlib.Path(sys.argv[-1]).write_text('done\\n',encoding='utf-8')"
        )
    elif mode == "timeout":
        code = "import time; time.sleep(30)"
    else:
        raise AssertionError(mode)

    class DelegatingPopen:
        def __init__(self, argv, **kwargs):
            output_path = argv[argv.index("--output-last-message") + 1]
            self._process = real_popen([sys.executable, "-c", code, str(output_path)], **kwargs)
            self.pid = self._process.pid
            self.stdin = self._process.stdin
            self.stdout = self._process.stdout
            self.stderr = self._process.stderr

        @property
        def returncode(self):
            return self._process.returncode

        def poll(self):
            return self._process.poll()

        def wait(self, *args, **kwargs):
            return self._process.wait(*args, **kwargs)

        def kill(self):
            return self._process.kill()

    monkeypatch.setattr(backend_module.subprocess, "Popen", DelegatingPopen)

    def fake_run(argv, *args, **kwargs):
        if argv and argv[0] == "taskkill":
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(backend_module.subprocess, "run", fake_run)


def _request(run_id: str = "writer:fake") -> dict[str, object]:
    return {
        "request_id": run_id,
        "run_id": run_id,
        "parent_orchestrator_run_id": "orchestrator:test",
        "prompt": "Return one sentence.",
        "settings": {"sandbox": "read-only"},
    }


def test_pipe_reader_prefers_read1_for_prompt_progress():
    class BufferedFake:
        def __init__(self):
            self.calls = []

        def read1(self, size):
            self.calls.append(("read1", size))
            return b"event"

        def read(self, size):
            raise AssertionError("the potentially blocking read fallback was used")

    stream = BufferedFake()
    assert _read_pipe_chunk(stream) == b"event"
    assert stream.calls and stream.calls[0][0] == "read1"


def test_local_run_uses_one_finalize_path_and_records_lifecycle(monkeypatch, tmp_path):
    _install_fake_child(monkeypatch)
    backend = _backend(tmp_path)

    source = inspect.getsource(LocalCodexBackend.run)
    assert "communicate(" not in source
    result = backend.run("writer", _request())

    assert result["terminal_status"] == "completed"
    assert result["failure_reason"] is None
    lifecycle = result["lifecycle"]
    assert lifecycle["reader_started"] is True
    assert lifecycle["first_output"] is True
    assert lifecycle["terminal_event"] is True
    assert lifecycle["process_exited"] is True
    assert lifecycle["cleanup_finished"] is True
    event_names = [item["event"] for item in result["lifecycle_events"]]
    assert {"process_started", "stdin_sent", "first_output", "thread_started", "terminal_event", "process_exited", "cleanup_finished"} <= set(event_names)
    assert lifecycle["stdin_sent"] is True
    assert lifecycle["last_output_at"]["stdout"]
    assert lifecycle["last_output_at"]["stderr"] is None
    assert result["cleanup_evidence"]["confirmed"] is True
    assert result["process_creation_time"]
    completion = json.loads((backend.run_root / result["execution_capture_ref"]).read_text(encoding="utf-8"))
    assert completion["lifecycle"]["reader_drain_confirmed"] is True
    assert completion["lifecycle_events"]


def test_planner_run_has_independent_local_completion_capture(monkeypatch, tmp_path):
    """Planner work is captured by the backend but never promoted to a reader record."""

    _install_fake_child(monkeypatch)
    backend = _backend(tmp_path)

    result = backend.run("planner", _request("planner:logic-card"))

    assert result["terminal_status"] == "completed"
    assert result["independence_status"] == "not_applicable"
    assert result["process_id"] is not None
    assert result["cleanup_evidence"]["confirmed"] is True
    completion_path = backend.run_root / result["execution_capture_ref"]
    completion = json.loads(completion_path.read_text(encoding="utf-8"))
    assert completion["role"] == "planner"
    assert completion["terminal_status"] == "completed"
    assert completion["lifecycle"]["process_exited"] is True
    assert completion["lifecycle"]["cleanup_finished"] is True
    # The planner lane is consumed as a local completion artifact.  It is not
    # passed through dispatch_writer/dispatch_judge and therefore has no
    # ReaderExecutionRecord-shaped wrapper here.
    assert "record" not in result


def test_local_run_hard_timeout_has_process_identity_and_cleanup_receipt(monkeypatch, tmp_path):
    _install_fake_child(monkeypatch, mode="timeout")
    backend = _backend(tmp_path, timeout_seconds=1, no_progress_seconds=0)

    started = time.monotonic()
    result = backend.run("writer", _request("writer:timeout"))
    assert time.monotonic() - started < 8
    assert result["terminal_status"] == "failed"
    assert result["failure_reason"] == "hard_timeout"
    assert result["timed_out"] is True
    assert result["process_id"] > 1
    assert result["process_creation_time"]
    assert result["cleanup_evidence"]["root_pid"] == result["process_id"]
    assert result["cleanup_evidence"]["root_creation_time"] == result["process_creation_time"]
    assert result["cleanup_evidence"]["confirmed"] is True
    assert result["lifecycle"]["process_exited"] is True
    assert result["lifecycle"]["cleanup_finished"] is True


def test_local_run_does_not_overwrite_existing_attempt_capture(monkeypatch, tmp_path):
    _install_fake_child(monkeypatch)
    backend = _backend(tmp_path)
    first = backend.run("writer", _request("writer:repeat"))
    second = backend.run("writer", _request("writer:repeat"))
    assert first["terminal_status"] == second["terminal_status"] == "completed"
    assert first["execution_capture_ref"] != second["execution_capture_ref"]
    assert (backend.run_root / first["execution_capture_ref"]).is_file()
    assert (backend.run_root / second["execution_capture_ref"]).is_file()


def test_local_run_start_failure_is_explicit_and_never_claims_completion(monkeypatch, tmp_path):
    backend = _backend(tmp_path)

    def fail(*args, **kwargs):
        raise OSError("fake process start failure")

    monkeypatch.setattr(backend_module.subprocess, "Popen", fail)
    result = backend.run("writer", _request("writer:start-failure"))
    assert result["terminal_status"] == "failed"
    assert result["failure_reason"] == "start_failed"
    assert result["process_identity"]["pid"] is None
    assert result["process_creation_time"] is None
    assert result["cleanup_evidence"]["confirmed"] is False
