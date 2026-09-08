"""Resolve a ``ReaderExecutionRecord`` against its local immutable capture.

The record fingerprint protects the JSON envelope from accidental edits.  It
does not prove that Codex actually ran.  ``LocalExecutionRecordResolver`` is
the second half of that proof: it follows only relative locators inside the
owner run root and rechecks the captured prompt, events, output, executable,
terminal state, and judge context separation.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from _common import ValidationError, fingerprint, fingerprint_text


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"execution capture is unreadable: {path}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"execution capture is not an object: {path}")
    return value


def _parse_time(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise ValidationError(f"{label} is missing")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValidationError(f"{label} is not RFC3339") from exc


class LocalExecutionRecordResolver:
    """Verify records created by :class:`LocalCodexBackend`."""

    def __init__(
        self,
        run_root: str | Path,
        *,
        expected_cli_version: str | None = None,
        expected_cli_sha256: str | None = None,
        expected_backend_id: str | None = None,
    ) -> None:
        self.run_root = Path(run_root).expanduser().resolve()
        self.expected_cli_version = expected_cli_version
        self.expected_cli_sha256 = expected_cli_sha256
        self.expected_backend_id = expected_backend_id

    def _path(self, locator: Any, label: str) -> Path:
        if not isinstance(locator, str) or not locator.strip():
            raise ValidationError(f"{label} is missing")
        candidate = Path(locator)
        if candidate.is_absolute() or any(part == ".." for part in candidate.parts):
            raise ValidationError(f"{label} must be a relative path")
        resolved = (self.run_root / candidate).resolve()
        try:
            resolved.relative_to(self.run_root)
        except ValueError as exc:
            raise ValidationError(f"{label} escaped the execution run root") from exc
        if resolved.is_symlink():
            raise ValidationError(f"{label} cannot resolve through a symlink")
        return resolved

    @staticmethod
    def _completion_fingerprint(value: Mapping[str, Any]) -> str:
        return fingerprint({key: item for key, item in value.items() if key != "completion_fingerprint"})

    @staticmethod
    def _events(path: Path) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        try:
            lines = path.read_bytes().splitlines()
        except OSError as exc:
            raise ValidationError(f"events capture is unreadable: {path}") from exc
        for index, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                event = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValidationError(f"events capture contains invalid JSON at line {index}") from exc
            if not isinstance(event, dict):
                raise ValidationError(f"events capture contains a non-object at line {index}")
            event["_line_index"] = index
            events.append(event)
        return events

    @staticmethod
    def _has_tool_event(events: list[Mapping[str, Any]]) -> bool:
        for event in events:
            if event.get("type") in {"error", "turn.failed", "turn.error", "turn.aborted"}:
                return True
            item = event.get("item")
            item_type = item.get("type") if isinstance(item, Mapping) else None
            # ``item.type == error`` can be a non-terminal desktop CLI
            # diagnostic.  Only command/tool-like item types violate the
            # reader's no-tools execution boundary.
            if isinstance(item_type, str) and any(
                token in item_type.casefold() for token in ("command", "tool", "mcp", "shell", "web", "function")
            ):
                return True
        return False

    def resolve(self, record: Mapping[str, Any]) -> dict[str, Any]:
        value = dict(record)
        if value.get("terminal_status") != "completed":
            raise ValidationError("only completed execution records can be locally verified")
        if self.expected_backend_id and value.get("backend_id") != self.expected_backend_id:
            raise ValidationError("execution record backend identity is not the expected local backend")
        capture_path = self._path(value.get("execution_capture_ref"), "execution_capture_ref")
        completion = _read_json(capture_path)
        if completion.get("schema_version") != "logic-writing.local-execution-completion.v1":
            raise ValidationError("local execution completion schema is not current")
        if completion.get("completion_fingerprint") != self._completion_fingerprint(completion):
            raise ValidationError("local execution completion fingerprint is stale")
        for key in ("role", "run_id", "settings_fingerprint", "started_at", "finished_at", "terminal_status"):
            if completion.get(key) != (value.get("role") if key == "role" else value.get(key)):
                raise ValidationError(f"execution capture and record disagree on {key}")
        if completion.get("context_id") and value.get("context_id") != completion["context_id"]:
            raise ValidationError("execution capture context_id does not match record")
        if completion.get("model_id") != value.get("model_id"):
            raise ValidationError("execution capture model_id does not match record")
        if completion.get("request_fingerprint") != value.get("request_fingerprint"):
            raise ValidationError("execution capture request fingerprint does not match record")
        if completion.get("input_prompt_fingerprint") != value.get("input_prompt_fingerprint"):
            raise ValidationError("execution capture prompt fingerprint does not match record")
        started = _parse_time(value.get("started_at"), "record.started_at")
        finished = _parse_time(value.get("finished_at"), "record.finished_at")
        if finished < started:
            raise ValidationError("execution finished before it started")
        if completion.get("timed_out") is not False or completion.get("descendant_cleanup_confirmed") is not True:
            raise ValidationError("execution capture does not prove clean completion")
        if completion.get("exit_code") != 0 or completion.get("terminal_event_type") != "turn.completed":
            raise ValidationError("execution capture has no successful terminal event")
        if completion.get("tool_event_count") != 0 or completion.get("parse_errors"):
            raise ValidationError("execution capture is not input-isolated")
        thread_id = completion.get("thread_id")
        if not isinstance(thread_id, str) or not thread_id:
            raise ValidationError("execution capture has no unique thread identity")
        events_path = self._path(completion.get("events_locator"), "events_locator")
        stderr_path = self._path(completion.get("stderr_locator"), "stderr_locator")
        output_path = self._path(completion.get("raw_output_locator"), "raw_output_locator")
        prompt_path = self._path(completion.get("input_prompt_locator"), "input_prompt_locator")
        for path, field in (
            (events_path, "events_fingerprint"),
            (stderr_path, "stderr_fingerprint"),
            (output_path, "raw_output_fingerprint"),
        ):
            if _sha256_bytes(path.read_bytes()) != completion.get(field):
                raise ValidationError(f"{field} does not match the captured bytes")
        prompt_bytes = prompt_path.read_bytes()
        if _sha256_bytes(prompt_bytes) != completion.get("input_prompt_fingerprint"):
            raise ValidationError("input prompt bytes do not match the capture")
        output_bytes = output_path.read_bytes()
        if not output_bytes.strip():
            raise ValidationError("completed execution has an empty output")
        events = self._events(events_path)
        thread_events = [row for row in events if row.get("type") == "thread.started"]
        if len(thread_events) != 1 or thread_events[0].get("thread_id") != thread_id:
            raise ValidationError("execution capture does not contain one matching thread.started event")
        turns = [row for row in events if row.get("type") == "turn.completed"]
        if not turns:
            raise ValidationError("execution capture has no turn.completed event")
        agent_messages = [
            row for row in events
            if isinstance(row.get("item"), Mapping)
            and row["item"].get("type") == "agent_message"
        ]
        if not agent_messages:
            raise ValidationError("execution capture has no agent_message event")
        if self._has_tool_event(events):
            raise ValidationError("execution capture contains a tool event")
        cli_sha = completion.get("executable_sha256")
        if not isinstance(cli_sha, str) or not cli_sha.startswith("sha256:"):
            raise ValidationError("execution capture has no executable fingerprint")
        if self.expected_cli_sha256 and cli_sha.removeprefix("sha256:") != self.expected_cli_sha256.removeprefix("sha256:"):
            raise ValidationError("execution capture executable fingerprint is not current")
        if self.expected_cli_version and completion.get("cli_version") != self.expected_cli_version:
            raise ValidationError("execution capture CLI version is not current")
        executable_path = Path(completion.get("executable_path", ""))
        try:
            executable_bytes = executable_path.read_bytes()
        except (OSError, ValueError) as exc:
            raise ValidationError("captured executable path is unreadable") from exc
        if _sha256_bytes(executable_bytes) != cli_sha:
            raise ValidationError("captured executable bytes do not match executable fingerprint")
        if value.get("raw_output_fingerprint") != completion.get("raw_output_fingerprint"):
            raise ValidationError("record output fingerprint does not match raw output capture")
        writer_context_ids = list(value.get("writer_context_ids", []))
        if value.get("role") == "judge":
            if value.get("independence_status") != "verified":
                raise ValidationError("judge record is not marked verified")
            pair_contexts = [row.get("writer_context_id") for row in value.get("pair_inputs", [])]
            if len(pair_contexts) != 2 or any(not isinstance(item, str) for item in pair_contexts):
                raise ValidationError("judge record does not bind two writer contexts")
            if set(writer_context_ids) != set(pair_contexts):
                raise ValidationError("judge capture writer contexts do not match the ordered pair")
            if value.get("context_id") in set(pair_contexts):
                raise ValidationError("judge context must differ from both writer contexts")
        return {
            "verified": True,
            "role": value["role"],
            "run_id": value["run_id"],
            "context_id": value["context_id"],
            "writer_context_ids": writer_context_ids,
            "capture_path": str(capture_path),
            "output_path": str(output_path),
            "thread_id": thread_id,
            "terminal_status": value["terminal_status"],
            "model_id": value["model_id"],
            "settings_fingerprint": value["settings_fingerprint"],
        }


__all__ = ["LocalExecutionRecordResolver"]
