"""Run an explicitly authorised local Codex CLI execution and capture it.

This module is deliberately small and boring: the caller supplies a complete
prompt, the backend starts the pinned desktop ``codex.exe`` in read-only mode,
and every result is tied to files below one owner run root.  It never discovers
providers, reads credentials, resumes a thread, or accepts a caller-authored
terminal status as evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from _common import ValidationError, fingerprint, fingerprint_text


DEFAULT_MODEL_ID = "gpt-6-astra"
DEFAULT_REASONING_EFFORT = "xhigh"
_CODEX_INSTALL_RELATIVE_PATH = Path(
    "AppData",
    "Local",
    "OpenAI",
    "Codex",
    "bin",
    "8e5b6932251c2c1c",
    "codex.exe",
)


def _default_codex_path() -> Path:
    """Resolve the pinned executable below the current Windows user profile.

    The install identity is fixed by the relative path and SHA-256 below.  The
    user profile is resolved at runtime so the public source never embeds a
    machine-specific home path.
    """

    profile = os.environ.get("USERPROFILE", "").strip()
    return (Path(profile) if profile else Path.home()) / _CODEX_INSTALL_RELATIVE_PATH


DEFAULT_CODEX_PATH = _default_codex_path()
DEFAULT_CLI_VERSION = "0.153.4"
DEFAULT_CLI_SHA256 = "e5aa76d19c7c94e2e9ef9b707d590206a73ac0e97c8ddc8382181242494bef75"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _safe_name(value: Any) -> str:
    text = str(value or "").strip()
    # ``:`` is legal in our logical IDs but illegal in a Windows directory
    # component, so path components use a stricter portable alphabet.
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    text = text.strip("._") or "run-" + uuid.uuid4().hex[:12]
    return text[:160]


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValidationError("execution capture path escaped the owner run root") from exc


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _kill_tree(process: subprocess.Popen[bytes]) -> bool:
    """Terminate a timed-out process tree and prove the root has exited."""

    try:
        if os.name == "nt":
            completed = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                check=False,
                timeout=30,
            )
            if process.poll() is None:
                process.kill()
            process.wait(timeout=30)
            return process.poll() is not None and completed.returncode in {0, 128, 255}
        process.kill()
        process.wait(timeout=30)
        return process.poll() is not None
    except (OSError, subprocess.TimeoutExpired):
        return process.poll() is not None


def _event_type(item: Mapping[str, Any]) -> str:
    value = item.get("type")
    return value if isinstance(value, str) else ""


def _parse_events(stdout: bytes) -> tuple[list[dict[str, Any]], list[str]]:
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, line in enumerate(stdout.splitlines()):
        if not line.strip():
            continue
        try:
            value = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"line {index}: invalid JSONL ({exc})")
            continue
        if not isinstance(value, dict):
            errors.append(f"line {index}: event is not an object")
            continue
        value["_line_index"] = index
        events.append(value)
    return events, errors


def _tool_events(events: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    safe_types = {"agent_message", "reasoning", "turn.started", "turn.completed", "thread.started"}
    for event in events:
        event_type = _event_type(event)
        item = event.get("item")
        item_type = _event_type(item) if isinstance(item, Mapping) else ""
        # The current desktop CLI may emit an ``item.completed`` payload with
        # ``item.type == "error"`` for a diagnostic (for example, a shortened
        # skill description) and still complete the requested turn.  Treat
        # that payload as a diagnostic, not as a tool or failed execution.  A
        # top-level error/failed/aborted event remains terminal evidence of
        # failure and is retained here.
        if event_type in {"error", "turn.failed", "turn.error", "turn.aborted"}:
            found.append({"event_type": event_type, "item_type": item_type or "error", "line": event.get("_line_index")})
            continue
        if item_type and item_type not in safe_types:
            lowered = item_type.casefold()
            if any(token in lowered for token in ("command", "tool", "mcp", "shell", "web", "function")):
                found.append({"event_type": event_type, "item_type": item_type, "line": event.get("_line_index")})
        if event_type in {"item.started", "item.completed"} and not item_type:
            # An item event without a typed payload cannot prove isolation.
            found.append({"event_type": event_type, "item_type": "missing", "line": event.get("_line_index")})
    return found


class LocalCodexBackend:
    """The one production writer/judge backend permitted by this release."""

    def __init__(
        self,
        run_root: str | Path,
        *,
        executable: str | Path | None = None,
        model_id: str = DEFAULT_MODEL_ID,
        reasoning_effort: str = DEFAULT_REASONING_EFFORT,
        timeout_seconds: int = 900,
        expected_version: str = DEFAULT_CLI_VERSION,
        expected_sha256: str = DEFAULT_CLI_SHA256,
        expected_cli_version: str | None = None,
        expected_executable_sha256: str | None = None,
    ) -> None:
        self.run_root = Path(run_root).expanduser().resolve()
        self.run_root.mkdir(parents=True, exist_ok=True)
        candidate = executable or os.environ.get("LOGIC_WRITING_CODEX_EXECUTABLE")
        if candidate is None:
            # Never fall back to a PATH launcher: older desktop shims can
            # silently select an incompatible Codex runtime.
            candidate = DEFAULT_CODEX_PATH
        if not candidate:
            raise ValidationError("pinned local Codex executable is unavailable")
        self.executable = Path(candidate).expanduser().resolve()
        if not self.executable.is_file():
            raise ValidationError(f"pinned local Codex executable is missing: {self.executable}")
        self.model_id = model_id
        self.reasoning_effort = reasoning_effort
        self.timeout_seconds = int(timeout_seconds)
        self.expected_version = expected_cli_version or expected_version
        self.expected_sha256 = expected_executable_sha256 or expected_sha256
        self.executable_sha256 = hashlib.sha256(self.executable.read_bytes()).hexdigest()
        self.cli_version = self._probe_version()
        if self.expected_version and self.cli_version != self.expected_version:
            raise ValidationError(
                f"local Codex version mismatch: expected {self.expected_version}, got {self.cli_version}"
            )
        if self.expected_sha256 and self.executable_sha256 != self.expected_sha256:
            raise ValidationError("local Codex executable fingerprint mismatch")
        self.backend_id = f"local-codex:{self.cli_version}:{self.model_id}:{self.reasoning_effort}"

    def _probe_version(self) -> str:
        try:
            completed = subprocess.run(
                [str(self.executable), "--version"],
                capture_output=True,
                check=False,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValidationError(f"could not probe local Codex version: {exc}") from exc
        if completed.returncode != 0:
            raise ValidationError("local Codex --version failed")
        text = (completed.stdout or completed.stderr).decode("utf-8", errors="replace").strip()
        match = re.search(r"(\d+\.\d+\.\d+)", text)
        if not match:
            raise ValidationError("local Codex version output has no semantic version")
        return match.group(1)

    def settings(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "reasoning_effort": self.reasoning_effort,
            "sandbox": "read-only",
            "ignore_user_config": True,
            "ephemeral": True,
            "json_events": True,
            "color": "never",
            "output_token_limit_supported": False,
            "max_output_tokens": None,
        }

    def run(self, role: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if role not in {"writer", "judge"}:
            raise ValidationError("local Codex backend role must be writer or judge")
        prompt = request.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValidationError("local Codex backend requires a non-empty prompt")
        request_id = request.get("request_id") or request.get("run_id") or uuid.uuid4().hex
        run_id = str(request.get("run_id") or f"{role}:{_safe_name(request_id)}")
        attempt_root = self.run_root / role / _safe_name(run_id)
        attempt_root.mkdir(parents=True, exist_ok=True)
        prompt_path = attempt_root / "input.txt"
        events_path = attempt_root / "events.jsonl"
        stderr_path = attempt_root / "stderr.txt"
        output_path = attempt_root / "output.txt"
        completion_path = attempt_root / "completion.json"
        prompt_bytes = prompt.encode("utf-8")
        _write_bytes(prompt_path, prompt_bytes)
        argv = [
            str(self.executable),
            "exec",
            "--ignore-user-config",
            "--model",
            self.model_id,
            "-c",
            f'model_reasoning_effort="{self.reasoning_effort}"',
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--ephemeral",
            "--json",
            "--color",
            "never",
            "--output-last-message",
            str(output_path),
            "-",
        ]
        request_fingerprint = fingerprint(dict(request))
        settings_fingerprint = request.get("settings_fingerprint") or fingerprint(self.settings())
        started_at = _now()
        process: subprocess.Popen[bytes] | None = None
        stdout = b""
        stderr = b""
        exit_code: int | None = None
        timed_out = False
        cleanup_confirmed = False
        failure_reason: str | None = None
        try:
            process = subprocess.Popen(
                argv,
                cwd=str(self.run_root),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
            try:
                stdout, stderr = process.communicate(prompt_bytes, timeout=self.timeout_seconds)
                exit_code = process.returncode
                cleanup_confirmed = process.poll() is not None
            except subprocess.TimeoutExpired as exc:
                timed_out = True
                stdout = exc.output or b""
                stderr = exc.stderr or b""
                cleanup_confirmed = _kill_tree(process)
                if process.poll() is not None:
                    try:
                        tail_out, tail_err = process.communicate(timeout=30)
                        stdout += tail_out or b""
                        stderr += tail_err or b""
                    except (OSError, subprocess.TimeoutExpired):
                        pass
                exit_code = process.returncode
                failure_reason = "timeout"
        except (OSError, ValueError) as exc:
            failure_reason = f"process_start_failed: {exc}"
            cleanup_confirmed = process is None or process.poll() is not None
        finally:
            finished_at = _now()
            _write_bytes(events_path, stdout)
            _write_bytes(stderr_path, stderr)
            # Codex normally writes output-last-message itself.  An absent file
            # is preserved as an empty capture and therefore cannot pass.
            if not output_path.is_file():
                _write_bytes(output_path, b"")

        events, parse_errors = _parse_events(stdout)
        _write_json(attempt_root / "parsed-events.json", events)
        thread_ids = [
            str(event.get("thread_id"))
            for event in events
            if event.get("type") == "thread.started" and isinstance(event.get("thread_id"), str)
        ]
        turn_completed = [event for event in events if event.get("type") == "turn.completed"]
        turn_failed = [event for event in events if event.get("type") in {"turn.failed", "turn.error", "turn.aborted"}]
        tools = _tool_events(events)
        agent_messages = [
            event for event in events
            if isinstance(event.get("item"), Mapping)
            and event["item"].get("type") == "agent_message"
        ]
        output_bytes = output_path.read_bytes() if output_path.is_file() else b""
        output_text = output_bytes.decode("utf-8", errors="replace") if output_bytes else ""
        if failure_reason is None:
            if timed_out:
                failure_reason = "timeout"
            elif exit_code != 0:
                failure_reason = f"codex_exit_{exit_code}"
            elif parse_errors:
                failure_reason = "invalid_jsonl_events"
            elif len(thread_ids) != 1:
                failure_reason = "thread_identity_not_unique"
            elif any(event.get("type") == "error" for event in events):
                failure_reason = "error_event"
            elif not turn_completed or turn_failed:
                failure_reason = "terminal_turn_event_missing_or_failed"
            elif not agent_messages:
                failure_reason = "agent_message_missing"
            elif tools:
                failure_reason = "input_isolation_failed_tool_event"
            elif not output_bytes.strip():
                failure_reason = "output_missing_or_empty"
            elif not cleanup_confirmed:
                failure_reason = "process_cleanup_unconfirmed"
        completed = failure_reason is None
        terminal_status = "completed" if completed else ("unavailable" if failure_reason and "unavailable" in failure_reason else "failed")
        thread_id = thread_ids[0] if len(thread_ids) == 1 else ""
        # The record context is the exact thread.started identity, so a
        # resolver can compare it without trusting a prefix or alias.
        context_id = thread_id if thread_id else f"context:unverified:{_safe_name(run_id)}"
        terminal_event = turn_completed[-1] if turn_completed else None
        completion = {
            "schema_version": "logic-writing.local-execution-completion.v1",
            "role": role,
            "run_id": run_id,
            "request_fingerprint": request_fingerprint,
            "input_prompt_locator": _relative(self.run_root, prompt_path),
            "input_prompt_path": _relative(self.run_root, prompt_path),
            "input_prompt_fingerprint": _sha256_bytes(prompt_bytes),
            "executable_path": str(self.executable),
            "executable_sha256": _sha256_bytes(self.executable.read_bytes()),
            "cli_version": self.cli_version,
            "argv_fingerprint": fingerprint(argv),
            "model_id": self.model_id,
            "settings_fingerprint": settings_fingerprint,
            "process_id": process.pid if process is not None else None,
            "thread_id": thread_id or None,
            "context_id": context_id,
            "started_at": started_at,
            "finished_at": finished_at,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "descendant_cleanup_confirmed": cleanup_confirmed,
            "terminal_event_type": "turn.completed" if terminal_event else None,
            "terminal_event_index": terminal_event.get("_line_index") if terminal_event else None,
            "events_locator": _relative(self.run_root, events_path),
            "events_path": _relative(self.run_root, events_path),
            "events_fingerprint": _sha256_bytes(stdout),
            "stderr_locator": _relative(self.run_root, stderr_path),
            "stderr_path": _relative(self.run_root, stderr_path),
            "stderr_fingerprint": _sha256_bytes(stderr),
            "raw_output_locator": _relative(self.run_root, output_path),
            "raw_output_path": _relative(self.run_root, output_path),
            "raw_output_fingerprint": _sha256_bytes(output_bytes),
            "output_bytes": len(output_bytes),
            "tool_event_count": len(tools),
            "agent_message_count": len(agent_messages),
            "parse_errors": parse_errors,
            "usage": next((event.get("usage") for event in reversed(events) if isinstance(event.get("usage"), Mapping)), None),
            "cost_actual": None,
            "terminal_status": terminal_status,
            "failure_reason": failure_reason,
        }
        completion["completion_fingerprint"] = fingerprint(completion)
        _write_json(completion_path, completion)
        result: dict[str, Any] = {
            "backend_id": self.backend_id,
            "run_id": run_id,
            "context_id": context_id,
            "parent_orchestrator_run_id": str(request.get("parent_orchestrator_run_id") or "orchestrator:local-quality"),
            "model_id": self.model_id,
            "started_at": started_at,
            "finished_at": finished_at,
            "terminal_status": terminal_status,
            "output": output_text if completed else (output_text or None),
            "provider_completion_ref": f"local-codex:{thread_id or run_id}",
            # Judges are never ``not_applicable``: even a failed/unavailable
            # judge attempt must remain distinguishable from a writer record.
            # ``independence_unverified`` preserves the failure receipt while
            # keeping it in the reader-execution-record schema.
            "independence_status": (
                "verified" if role == "judge" and completed
                else "independence_unverified" if role == "judge"
                else "not_applicable"
            ),
            "writer_context_ids": list(request.get("writer_context_ids", [])) if role == "judge" else [],
            "settings_fingerprint": settings_fingerprint,
            "execution_capture_ref": _relative(self.run_root, completion_path),
            "completion_locator": _relative(self.run_root, completion_path),
            "raw_output_locator": _relative(self.run_root, output_path),
            "events_locator": _relative(self.run_root, events_path),
            "stderr_locator": _relative(self.run_root, stderr_path),
            "request_fingerprint": request_fingerprint,
            "input_prompt_fingerprint": _sha256_bytes(prompt_bytes),
            "input_prompt_locator": _relative(self.run_root, prompt_path),
            "raw_output_fingerprint": _sha256_bytes(output_bytes),
            "events_fingerprint": _sha256_bytes(stdout),
            "stderr_fingerprint": _sha256_bytes(stderr),
            "argv_fingerprint": fingerprint(argv),
            "cli_executable": str(self.executable),
            "cli_executable_fingerprint": _sha256_bytes(self.executable.read_bytes()),
            "cli_version": self.cli_version,
            "process_id": process.pid if process is not None else 1,
            "thread_id": thread_id or context_id,
            "exit_code": exit_code if exit_code is not None else 1,
            "timed_out": timed_out,
            "descendant_cleanup_confirmed": cleanup_confirmed,
            "terminal_event_type": "turn.completed" if terminal_event else "none",
            "terminal_event_index": terminal_event.get("_line_index") if terminal_event else 0,
            "tool_event_count": len(tools),
            "usage": completion["usage"],
            "cost_actual": None,
        }
        if completed:
            result["output_fingerprint"] = _sha256_bytes(output_bytes)
        return result


__all__ = ["LocalCodexBackend", "DEFAULT_CODEX_PATH", "DEFAULT_CLI_VERSION", "DEFAULT_CLI_SHA256"]
