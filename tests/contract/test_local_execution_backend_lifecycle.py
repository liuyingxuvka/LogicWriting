from __future__ import annotations

import inspect
import hashlib
import json
import subprocess
import sys
import threading
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


def _install_fake_child(monkeypatch, *, mode: str = "complete", argv_capture=None):
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
    elif mode == "reconnecting":
        code = (
            "import json,pathlib,sys; "
            "sys.stdin.buffer.read(); "
            "events=[{'type':'thread.started','thread_id':'fake-thread'},"
            "{'type':'turn.started'},"
            "{'type':'error','message':'Reconnecting... 2/5 (stream disconnected)'},"
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
            if argv_capture is not None:
                argv_capture.append(list(argv))
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


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        (
            [
                {
                    "ProcessId": 100,
                    "ParentProcessId": 1,
                    "CreationDate": "20260911044411.350429+000",
                },
                {
                    "ProcessId": 200,
                    "ParentProcessId": 100,
                    "CreationDate": "20260911044412.000000+000",
                },
                {
                    "ProcessId": 300,
                    "ParentProcessId": 100,
                    "CreationDate": "20260911040000.000000+000",
                },
            ],
            [200],
        ),
        (
            [
                {
                    "ProcessId": 100,
                    "ParentProcessId": 1,
                    "CreationDate": "20260911045000.000000+000",
                },
                {
                    "ProcessId": 200,
                    "ParentProcessId": 100,
                    "CreationDate": "20260911045001.000000+000",
                },
            ],
            None,
        ),
    ],
)
def test_windows_descendant_walk_fences_pid_reuse(monkeypatch, rows, expected):
    monkeypatch.setattr(backend_module.os, "name", "nt")
    monkeypatch.setattr(
        backend_module.subprocess,
        "Popen",
        backend_module._REAL_SUBPROCESS_POPEN,
    )

    def fake_run(*args, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(rows).encode("utf-8"),
            stderr=b"",
        )

    monkeypatch.setattr(backend_module.subprocess, "run", fake_run)
    assert backend_module._windows_descendant_pids(
        100,
        root_creation_time="2026-09-11T04:44:11.350429Z",
    ) == expected


def test_windows_descendant_probe_retries_transient_unknown(monkeypatch):
    """A single WMI miss after natural exit must not create a false failure."""

    monkeypatch.setattr(backend_module.os, "name", "nt")
    monkeypatch.setattr(
        backend_module.subprocess,
        "Popen",
        backend_module._REAL_SUBPROCESS_POPEN,
    )
    observed: list[tuple[int, str | None]] = []
    responses = iter((None, None, []))
    monkeypatch.setattr(
        backend_module,
        "_windows_descendant_pids",
        lambda root_pid, *, root_creation_time=None: (
            observed.append((root_pid, root_creation_time)) or next(responses)
        ),
    )
    monkeypatch.setattr(backend_module.time, "sleep", lambda _seconds: None)

    assert backend_module._windows_descendant_pids_with_retry(
        100,
        root_creation_time="2026-09-11T05:55:00.123456Z",
    ) == []
    assert observed == [
        (100, "2026-09-11T05:55:00.123456Z"),
        (100, "2026-09-11T05:55:00.123456Z"),
        (100, "2026-09-11T05:55:00.123456Z"),
    ]


@pytest.mark.parametrize(
    ("early_descendants", "expected_status", "expected_reason", "expected_phases"),
    [
        ([], "completed", None, ["at_exit"]),
        ([9999], "failed", "cleanup_unconfirmed", ["at_exit", "after_drain"]),
    ],
)
def test_local_run_uses_exit_boundary_snapshot_without_weakening_unknown_rule(
    monkeypatch,
    tmp_path,
    early_descendants,
    expected_status,
    expected_reason,
    expected_phases,
):
    """An early empty snapshot survives a late WMI miss; nonempty stays unknown."""

    real_popen = backend_module._REAL_SUBPROCESS_POPEN
    code = (
        "import json,pathlib,sys; "
        "sys.stdin.buffer.read(); "
        "events=[{'type':'thread.started','thread_id':'boundary-thread'},"
        "{'type':'turn.started'},"
        "{'type':'item.completed','item':{'type':'agent_message','text':'done'}},"
        "{'type':'turn.completed'}]; "
        "[ (sys.stdout.write(json.dumps(item)+'\\n'),sys.stdout.flush()) for item in events ]; "
        "pathlib.Path(sys.argv[-1]).write_text('done\\n',encoding='utf-8')"
    )

    def real_child(_argv, **kwargs):
        output_path = _argv[_argv.index("--output-last-message") + 1]
        return real_popen([sys.executable, "-c", code, output_path], **kwargs)

    monkeypatch.setattr(backend_module.subprocess, "Popen", real_child)
    drain_started = False
    phases = []
    real_join = threading.Thread.join

    def mark_drain_started(thread, *args, **kwargs):
        nonlocal drain_started
        drain_started = True
        return real_join(thread, *args, **kwargs)

    monkeypatch.setattr(threading.Thread, "join", mark_drain_started)

    def observe(_root_pid, *, root_creation_time=None):
        del root_creation_time
        if drain_started:
            phases.append("after_drain")
            return None
        phases.append("at_exit")
        return list(early_descendants)

    monkeypatch.setattr(backend_module, "_windows_descendant_pids_with_retry", observe)
    result = _backend(tmp_path).run("writer", _request("writer:boundary-snapshot"))

    assert result["terminal_status"] == expected_status
    assert result["failure_reason"] == expected_reason
    assert result["cleanup_evidence"]["confirmed"] is (expected_status == "completed")
    assert phases == expected_phases


def test_terminate_process_tree_passes_root_identity_to_each_windows_probe(monkeypatch):
    """Both cleanup probes must fence the root PID with its observed identity."""

    class FakeProcess:
        pid = 9010

        def __init__(self):
            self.returncode = None

        def poll(self):
            return self.returncode

        def kill(self):
            self.returncode = -9

        def wait(self, timeout=None):
            self.returncode = -9
            return self.returncode

    root_creation_time = "2026-09-11T05:55:00.123456Z"
    probe_calls: list[tuple[int, str | None]] = []
    monkeypatch.setattr(backend_module.os, "name", "nt")
    monkeypatch.setattr(
        backend_module,
        "_windows_descendant_pids",
        lambda root_pid, *, root_creation_time=None: (
            probe_calls.append((root_pid, root_creation_time)) or []
        ),
    )
    monkeypatch.setattr(
        backend_module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=b"", stderr=b""),
    )

    evidence = backend_module._terminate_process_tree(
        FakeProcess(),
        root_creation_time=root_creation_time,
    )

    assert probe_calls == [(9010, root_creation_time), (9010, root_creation_time)]
    assert evidence["root_creation_time"] == root_creation_time
    assert evidence["descendants_observed"] is True
    assert evidence["descendants_remaining"] is False
    assert evidence["confirmed"] is True


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


def test_local_run_disables_all_external_cli_features_in_fixed_order(monkeypatch, tmp_path):
    argv_capture = []
    _install_fake_child(monkeypatch, argv_capture=argv_capture)
    backend = _backend(tmp_path)

    result = backend.run("writer", _request("writer:argv-policy"))

    assert result["terminal_status"] == "completed"
    assert len(argv_capture) == 1
    argv = argv_capture[0]
    start = argv.index("--ignore-user-config") + 1
    expected = [
        "--disable", "apps",
        "--disable", "plugins",
        "--disable", "skill_search",
        "--disable", "shell_tool",
        "--disable", "unified_exec",
        "--disable", "browser_use",
        "--disable", "computer_use",
    ]
    assert argv[start : start + len(expected)] == expected
    assert argv.count("--disable") == 7
    assert [argv[index + 1] for index, value in enumerate(argv) if value == "--disable"] == [
        "apps", "plugins", "skill_search", "shell_tool", "unified_exec", "browser_use", "computer_use"
    ]
    assert backend.settings()["disabled_features"] == [
        "apps", "plugins", "skill_search", "shell_tool", "unified_exec", "browser_use", "computer_use"
    ]


def test_local_run_admits_only_narrow_reconnect_diagnostic_before_completed_turn(monkeypatch, tmp_path):
    _install_fake_child(monkeypatch, mode="reconnecting")
    backend = _backend(tmp_path)

    result = backend.run("judge", _request("judge:reconnecting"))

    assert result["terminal_status"] == "completed"
    assert result["failure_reason"] is None
    assert result["tool_event_count"] == 0
    assert result["provider_error_count"] == 1
    assert result["recoverable_provider_error_count"] == 1
    assert result["provider_errors_recoverable"] is True
    assert result["provider_error_events"] == [
        {
            "event_type": "error",
            "line": 2,
            "message": "Reconnecting... 2/5 (stream disconnected)",
            "recoverable": True,
        }
    ]
    completion = json.loads(
        (backend.run_root / result["execution_capture_ref"]).read_text(encoding="utf-8")
    )
    assert completion["provider_error_events"][0]["recoverable"] is True
    assert b"Reconnecting... 2/5" in (backend.run_root / completion["events_locator"]).read_bytes()


def test_local_run_stop_request_records_bounded_cleanup_evidence(monkeypatch, tmp_path):
    _install_fake_child(monkeypatch, mode="timeout")
    monkeypatch.setattr(
        backend_module,
        "_windows_descendant_pids",
        lambda root_pid, *, root_creation_time=None: [],
    )
    backend = _backend(tmp_path, timeout_seconds=5)
    stop_event = threading.Event()
    timer = threading.Timer(0.2, stop_event.set)
    timer.start()
    try:
        result = backend.run("writer", {**_request("writer:stop"), "stop_event": stop_event})
    finally:
        timer.cancel()
        timer.join(timeout=1.0)

    assert result["terminal_status"] == "failed"
    assert result["failure_reason"] == "cancelled"
    assert result["stop_requested"] is True
    assert result["stop_reason"] == "stop_event"
    assert result["cleanup_evidence"]["confirmed"] is True
    assert result["cleanup_evidence"]["descendants_remaining"] is False
    assert result["lifecycle"]["cleanup_finished"] is True
    assert result["lifecycle"]["cleanup_confirmed"] is True
    assert result["lifecycle"]["terminal_published_after_cleanup"] is True
    assert any(
        item["event"] == "abort_requested" and item.get("stop_reason") == "stop_event"
        for item in result["lifecycle_events"]
    )


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
