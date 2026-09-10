from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

from _common import ValidationError, fingerprint, fingerprint_text
from execution_record_resolver import LocalExecutionRecordResolver
from local_execution_backend import _parse_events, _tool_events
from reader_execution import _record_from_result, dispatch_judge, dispatch_writer


FP_A = "sha256:" + "a" * 64
FP_B = "sha256:" + "b" * 64


class FailedBackend:
    def run(self, role, request):
        return {
            "run_id": "writer:failed",
            "context_id": "context:failed",
            "parent_orchestrator_run_id": "orchestrator:test",
            "model_id": "test-model",
            "started_at": "2026-09-08T00:00:00Z",
            "finished_at": "2026-09-08T00:00:01Z",
            "terminal_status": "failed",
            "provider_completion_ref": "local-test:failed",
        }


def test_dispatch_propagates_failed_terminal_status():
    request = {
        "reader_intent_fingerprint": FP_A,
        "writer_input_fingerprint": FP_B,
    }
    dispatched = dispatch_writer(request, FailedBackend())
    assert dispatched["status"] == "failed"
    assert dispatched["record"]["terminal_status"] == "failed"


@pytest.mark.parametrize("terminal_status", [None, "finished"])
def test_record_from_result_requires_an_explicit_known_terminal_status(terminal_status):
    request = {
        "reader_intent_fingerprint": FP_A,
        "writer_input_fingerprint": FP_B,
    }
    result = {
        "run_id": "writer:missing-terminal",
        "context_id": "context:missing-terminal",
        "parent_orchestrator_run_id": "orchestrator:test",
        "model_id": "test-model",
        "started_at": "2026-09-08T00:00:00Z",
        "finished_at": "2026-09-08T00:00:01Z",
        "provider_completion_ref": "local-test:missing-terminal",
        "output": "done",
    }
    if terminal_status is not None:
        result["terminal_status"] = terminal_status
    with pytest.raises(ValidationError, match="terminal_status"):
        _record_from_result(request, result, role="writer", backend_id="local-test")


def test_failed_judge_preserves_unverified_independence_status():
    request = {
        "reader_intent_fingerprint": FP_A,
        "writer_input_fingerprint": FP_B,
        "rubric_fingerprint": FP_A,
        "evaluation_mode": "pair",
        "pair_inputs": [
            {
                "anonymous_label": "X",
                "artifact_fingerprint": FP_A,
                "writer_run_id": "writer:x",
                "writer_context_id": "context:x",
                "writer_input_fingerprint": FP_A,
            },
            {
                "anonymous_label": "Y",
                "artifact_fingerprint": FP_B,
                "writer_run_id": "writer:y",
                "writer_context_id": "context:y",
                "writer_input_fingerprint": FP_B,
            },
        ],
    }
    dispatched = dispatch_judge(request, FailedBackend())
    assert dispatched["status"] == "failed"
    assert dispatched["record"]["terminal_status"] == "failed"
    assert dispatched["record"]["independence_status"] == "independence_unverified"


def _make_capture(tmp_path: Path):
    run_root = tmp_path / "run"
    attempt = run_root / "writer" / "one"
    attempt.mkdir(parents=True)
    prompt = "Return one sentence."
    prompt_path = attempt / "input.txt"
    events_path = attempt / "events.jsonl"
    stderr_path = attempt / "stderr.txt"
    output_path = attempt / "output.txt"
    executable = tmp_path / "codex.exe"
    prompt_path.write_text(prompt, encoding="utf-8")
    events_path.write_text(
        '{"type":"thread.started","thread_id":"thread-one"}\r\n'
        '{"type":"turn.started"}\r\n'
        '{"type":"item.completed","item":{"type":"agent_message","text":"done"}}\r\n'
        '{"type":"turn.completed","usage":{"output_tokens":1}}\r\n',
        encoding="utf-8",
        newline="",
    )
    stderr_path.write_bytes(b"")
    output_path.write_text("done\n", encoding="utf-8")
    executable.write_bytes(b"fake pinned executable")
    def sha(path: Path) -> str:
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    request = {
        "request_id": "writer:one",
        "reader_intent_fingerprint": FP_A,
        "writer_input_fingerprint": FP_B,
        "settings": {"sandbox": "read-only"},
        "prompt": prompt,
    }
    req_fp = fingerprint(request)
    result = {
        "run_id": "writer:one",
        "context_id": "thread-one",
        "parent_orchestrator_run_id": "orchestrator:test",
        "model_id": "gpt-6-astra",
        "started_at": "2026-09-08T00:00:00Z",
        "finished_at": "2026-09-08T00:00:01Z",
        "terminal_status": "completed",
        "output": "done\n",
        "output_fingerprint": sha(output_path),
        "provider_completion_ref": "local-codex:thread-one",
        "settings_fingerprint": fingerprint(request["settings"]),
        "request_fingerprint": req_fp,
        "input_prompt_fingerprint": fingerprint_text(prompt),
        "execution_capture_ref": "writer/one/completion.json",
        "completion_locator": "writer/one/completion.json",
        "raw_output_locator": "writer/one/output.txt",
        "events_locator": "writer/one/events.jsonl",
        "stderr_locator": "writer/one/stderr.txt",
        "request_fingerprint": req_fp,
        "input_prompt_locator": "writer/one/input.txt",
        "raw_output_fingerprint": sha(output_path),
        "events_fingerprint": sha(events_path),
        "stderr_fingerprint": sha(stderr_path),
        "argv_fingerprint": fingerprint([str(executable), "exec"]),
        "cli_executable": str(executable),
        "cli_executable_fingerprint": sha(executable),
        "cli_version": "0.153.4",
        "process_id": 123,
        "thread_id": "thread-one",
        "exit_code": 0,
        "timed_out": False,
        "descendant_cleanup_confirmed": True,
        "terminal_event_type": "turn.completed",
        "terminal_event_index": 3,
        "tool_event_count": 0,
        "writer_context_ids": [],
        "usage": {"output_tokens": 1},
        "cost_actual": None,
    }
    completion = {
        "schema_version": "logic-writing.local-execution-completion.v1",
        "role": "writer",
        "run_id": "writer:one",
        "request_fingerprint": req_fp,
        "input_prompt_locator": "writer/one/input.txt",
        "input_prompt_fingerprint": fingerprint_text(prompt),
        "executable_path": str(executable),
        "executable_sha256": sha(executable),
        "cli_version": "0.153.4",
        "argv_fingerprint": result["argv_fingerprint"],
        "model_id": "gpt-6-astra",
        "settings_fingerprint": result["settings_fingerprint"],
        "process_id": 123,
        "thread_id": "thread-one",
        "context_id": "thread-one",
        "started_at": result["started_at"],
        "finished_at": result["finished_at"],
        "exit_code": 0,
        "timed_out": False,
        "descendant_cleanup_confirmed": True,
        "terminal_event_type": "turn.completed",
        "terminal_event_index": 3,
        "events_locator": result["events_locator"],
        "events_fingerprint": result["events_fingerprint"],
        "stderr_locator": result["stderr_locator"],
        "stderr_fingerprint": result["stderr_fingerprint"],
        "raw_output_locator": result["raw_output_locator"],
        "raw_output_fingerprint": result["raw_output_fingerprint"],
        "output_bytes": len(output_path.read_bytes()),
        "tool_event_count": 0,
        "parse_errors": [],
        "usage": {"output_tokens": 1},
        "cost_actual": None,
        "terminal_status": "completed",
        "failure_reason": None,
    }
    completion["completion_fingerprint"] = fingerprint(completion)
    (attempt / "completion.json").write_text(json.dumps(completion, indent=2), encoding="utf-8")
    record = _record_from_result(request, result, role="writer", backend_id="local-codex:test")
    return run_root, record


def test_local_resolver_verifies_capture_and_bytes(tmp_path):
    run_root, record = _make_capture(tmp_path)
    resolver = LocalExecutionRecordResolver(run_root, expected_cli_version="0.153.4")
    verified = resolver.resolve(record)
    assert verified["verified"] is True
    assert verified["context_id"] == "thread-one"


def test_local_resolver_rejects_changed_output(tmp_path):
    run_root, record = _make_capture(tmp_path)
    (run_root / "writer" / "one" / "output.txt").write_text("changed\n", encoding="utf-8")
    resolver = LocalExecutionRecordResolver(run_root, expected_cli_version="0.153.4")
    with pytest.raises(ValidationError, match="raw_output_fingerprint"):
        resolver.resolve(record)


def test_event_parser_requires_objects_and_detects_tools():
    events, errors = _parse_events(b'{"type":"thread.started","thread_id":"t"}\nnot-json\n')
    assert len(events) == 1
    assert errors
    assert _tool_events([{"type": "item.completed", "item": {"type": "command_execution"}}])


def test_informational_item_error_does_not_count_as_tool_event():
    events = [
        {"type": "thread.started", "thread_id": "t"},
        {"type": "item.completed", "item": {"type": "error", "message": "diagnostic only"}},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "done"}},
        {"type": "turn.completed"},
    ]
    assert _tool_events(events) == []
