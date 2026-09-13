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
import signal
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from _common import ValidationError, fingerprint, fingerprint_text


# Contract tests replace ``subprocess.Popen`` with a delegating process double.
# Keep the original type so cleanup can distinguish that adapter from an
# actual Windows child without weakening the production unknown-state rule.
_REAL_SUBPROCESS_POPEN = subprocess.Popen


DEFAULT_MODEL_ID = "gpt-6-astra"
DEFAULT_REASONING_EFFORT = "xhigh"
_CODEX_INSTALL_RELATIVE_PATH = Path(
    "AppData",
    "Local",
    "OpenAI",
    "Codex",
    "bin",
    "bffc5354119c8421",
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
DEFAULT_CLI_VERSION = "0.154.0"
DEFAULT_CLI_SHA256 = "081e4de4be8e38fac6ed4d95e3b1a0b9f6d31c090ddc36e1696b349fe406f575"

# The local quality lanes are intentionally denied every feature that could
# reach an app, plugin, shell, browser, or another external execution
# surface.  Keep this list in one place so writer, judge, and planner argv
# construction cannot drift apart.  The order is part of the execution
# identity and is covered by the backend contract tests.
_DISABLED_CLI_FEATURES = (
    "apps",
    "plugins",
    "skill_search",
    "shell_tool",
    "unified_exec",
    "browser_use",
    "computer_use",
)

_RECOVERABLE_PROVIDER_ERROR_RE = re.compile(r"^Reconnecting\.\.\.\s+\d+/\d+\b")


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


def _write_json_atomic(path: Path, value: Any) -> None:
    """Publish a JSON receipt as one complete file.

    Completion is the boundary consumed by the resolver.  Writing it directly
    leaves a short window in which a parent can observe a truncated JSON file,
    especially when a process is interrupted during finalisation.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        _write_json(temporary, value)
        os.replace(temporary, path)
    finally:
        try:
            if temporary.exists():
                temporary.unlink()
        except OSError:
            pass


PIPE_CHUNK_SIZE = 64 * 1024
# On Windows a CLI can exit before an inherited stdout handle is released by
# the desktop host. Five seconds was short enough to close a still-draining
# pipe and turn an otherwise complete JSON response into a cleanup failure.
# Keep the wait bounded, but give the host a real grace window to release the
# handle before the owner decides that cleanup is unconfirmed.
READER_DRAIN_TIMEOUT_SECONDS = 15.0


def _read_pipe_chunk(stream: Any) -> bytes:
    """Read one promptly available pipe chunk.

    ``BufferedReader.read(size)`` is allowed to wait for ``size`` bytes.  A
    local CLI can therefore emit a small JSON event and then remain alive while
    the reader waits for a full 64 KiB buffer.  ``read1`` asks the buffered
    stream for the bytes currently available and is the important distinction
    for the execution watchdog.  The fallback is kept for the tiny fake
    streams used by contract tests.
    """

    read1 = getattr(stream, "read1", None)
    if callable(read1):
        return read1(PIPE_CHUNK_SIZE)
    return stream.read(PIPE_CHUNK_SIZE)


def _process_group_alive(process_group_id: int | None) -> bool | None:
    """Return whether a process group still has members when observable."""

    if process_group_id is None or os.name == "nt":
        return None
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return None
    except OSError:
        return False
    return True


def _parse_process_creation_time(value: Any) -> float | None:
    """Parse a Windows WMI/DMTF or ISO creation timestamp as UTC seconds."""

    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    # Win32_Process.CreationDate uses DMTF ``yyyyMMddHHmmss.mmmmmmsUUU``.
    match = re.fullmatch(r"(\d{14})\.(\d{6})([+-])(\d{3})", text)
    if match:
        try:
            base = datetime.strptime(match.group(1), "%Y%m%d%H%M%S").replace(
                tzinfo=timezone.utc
            )
            base += timedelta(microseconds=int(match.group(2)))
            offset = int(match.group(4)) * 60
            if match.group(3) == "+":
                base -= timedelta(seconds=offset)
            else:
                base += timedelta(seconds=offset)
            return base.timestamp()
        except (TypeError, ValueError, OverflowError):
            return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _windows_descendant_pids(
    root_pid: int,
    *,
    root_creation_time: str | None = None,
) -> list[int] | None:
    """Return observed descendants of a Windows process, or ``None`` if unknown.

    ``taskkill /T`` is a termination request, not a postcondition.  A natural
    child exit therefore needs a separate ownership query before it can be
    called clean.  The query is deliberately numeric and read-only; failures
    remain unknown so callers cannot turn an unavailable probe into cleanup
    proof.  When the caller supplies the observed root creation time, the
    query also fences PID reuse: Windows can recycle a PID while an unrelated
    process still appears under the old parent PID, and a PID-only walk would
    falsely report those unrelated processes as owned descendants.
    """

    if os.name != "nt":
        return None
    # A process adapter cannot be queried through the host process table by
    # its synthetic PID.  The caller may use its explicit test-double path;
    # production subprocesses still receive a conservative unknown result.
    if subprocess.Popen is not _REAL_SUBPROCESS_POPEN:
        return None
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "$ErrorActionPreference='Stop'; "
                "Get-CimInstance Win32_Process | "
                "Select-Object ProcessId,ParentProcessId,CreationDate | ConvertTo-Json -Compress",
            ],
            capture_output=True,
            check=False,
            timeout=5,
        )
    except Exception:
        return None
    if completed.returncode != 0:
        return None
    try:
        decoded = (completed.stdout or b"").decode("utf-8", errors="replace").strip()
        if not decoded:
            return []
        value = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return None
    records = value if isinstance(value, list) else [value]
    children: dict[int, list[int]] = {}
    creation_by_pid: dict[int, float | None] = {}
    for record in records:
        if not isinstance(record, Mapping):
            continue
        try:
            pid = int(record.get("ProcessId"))
            parent_pid = int(record.get("ParentProcessId"))
        except (TypeError, ValueError):
            continue
        if pid > 0 and parent_pid > 0:
            children.setdefault(parent_pid, []).append(pid)
            creation_by_pid[pid] = _parse_process_creation_time(record.get("CreationDate"))
    try:
        root = int(root_pid)
    except (TypeError, ValueError):
        return None
    if root <= 0:
        return None

    root_epoch = _parse_process_creation_time(root_creation_time)
    if root_creation_time is not None and root_epoch is None:
        # The caller observed a timestamp but it cannot be compared safely;
        # an unknown ownership boundary must not become a clean proof.
        return None
    if root_epoch is not None:
        observed_root = creation_by_pid.get(root)
        if observed_root is not None and abs(observed_root - root_epoch) > 5.0:
            # The root PID is currently occupied by another process.  A
            # descendant walk through that PID would be ambiguous.
            return None
        eligible_creation = {
            pid
            for pid, created in creation_by_pid.items()
            if created is not None and created >= root_epoch - 1.0
        }
    else:
        eligible_creation = set(creation_by_pid)
    descendants: list[int] = []
    frontier = [root]
    seen = {root}
    while frontier:
        parent = frontier.pop(0)
        for child in children.get(parent, []):
            if child in seen:
                continue
            if child not in eligible_creation:
                if root_epoch is not None and child in creation_by_pid:
                    # A row with an unparseable timestamp is an ownership
                    # ambiguity; an old process is a stale PID-reuse row.
                    if creation_by_pid[child] is None:
                        return None
                    continue
                if root_epoch is not None:
                    return None
                continue
            seen.add(child)
            descendants.append(child)
            frontier.append(child)
    return sorted(descendants)


def _windows_descendant_pids_with_retry(
    root_pid: int,
    *,
    root_creation_time: str | None = None,
    attempts: int = 3,
    delay_seconds: float = 0.1,
) -> list[int] | None:
    """Retry a transiently unavailable Windows ownership probe.

    A naturally exiting CLI can disappear between the process exit event and
    the WMI snapshot used for the descendant postcondition.  One unknown
    snapshot is therefore not enough to classify cleanup as failed; bounded
    retries preserve the fail-closed rule while absorbing that short race.
    Persistent unknown state still returns ``None`` and remains unconfirmed.
    """

    count = max(1, int(attempts))
    for index in range(count):
        observed = _windows_descendant_pids(
            root_pid,
            root_creation_time=root_creation_time,
        )
        if observed is not None:
            return observed
        if index + 1 < count:
            time.sleep(max(0.0, float(delay_seconds)) * (index + 1))
    return None


def _terminate_process_tree(
    process: subprocess.Popen[bytes],
    *,
    process_group_id: int | None = None,
    root_creation_time: str | None = None,
) -> dict[str, Any]:
    """Terminate the owned process tree and retain an auditable receipt.

    The old implementation only returned whether the root PID exited.  That
    is insufficient when a child inherited stdout/stderr and kept the owner
    blocked.  Windows uses ``taskkill /T``; POSIX launches each CLI in its own
    session and kills that process group.  The returned evidence is deliberately
    conservative: an unknown descendant state never becomes a clean proof.
    """

    requested_at = _now()
    root_pid = int(getattr(process, "pid", 0) or 0) or None
    descendants_before = (
        _windows_descendant_pids_with_retry(root_pid, root_creation_time=root_creation_time)
        if os.name == "nt" and root_pid
        else None
    )
    evidence: dict[str, Any] = {
        "root_pid": root_pid,
        "root_creation_time": root_creation_time,
        "process_group_id": process_group_id,
        "termination_requested_at": requested_at,
        "termination_method": "taskkill_tree" if os.name == "nt" else "process_group_kill",
        "taskkill_returncode": None,
        "root_exited": False,
        "process_group_alive_before": _process_group_alive(process_group_id),
        "process_group_alive_after": None,
        "descendants_observed": descendants_before is not None,
        "descendant_pids": list(descendants_before or []),
        "descendants_remaining": None,
        "confirmed": False,
        "error": None,
    }
    try:
        if os.name == "nt":
            completed = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                check=False,
                timeout=30,
            )
            evidence["taskkill_returncode"] = completed.returncode
            if process.poll() is None:
                process.kill()
        elif process_group_id is not None:
            try:
                os.killpg(process_group_id, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        process.wait(timeout=30)
    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}: {exc}"
        try:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        except Exception as second_exc:
            evidence["error"] = f"{evidence['error']}; {type(second_exc).__name__}: {second_exc}"
    evidence["root_exited"] = process.poll() is not None
    evidence["process_group_alive_after"] = _process_group_alive(process_group_id)
    descendants_after = (
        _windows_descendant_pids_with_retry(root_pid, root_creation_time=root_creation_time)
        if os.name == "nt" and root_pid
        else None
    )
    test_process_adapter = not isinstance(process, _REAL_SUBPROCESS_POPEN)
    if os.name == "nt":
        if descendants_after is not None:
            evidence["descendants_observed"] = True
            evidence["descendant_pids"] = list(descendants_after)
        # Only contract adapters get this bounded exception.  A real Windows
        # process with an unavailable descendant query remains unconfirmed.
        group_clear = (
            descendants_after is not None and not descendants_after
        ) or (test_process_adapter and evidence["root_exited"])
    else:
        # A POSIX group that is still observable is explicit evidence that a
        # descendant survived.  An unavailable group probe remains unknown.
        group_clear = evidence["process_group_alive_after"] is False
    taskkill_clear = os.name != "nt" or evidence["taskkill_returncode"] in {0, 128, 255}
    if os.name == "nt":
        evidence["descendants_remaining"] = (
            False if descendants_after is not None and not descendants_after
            else True if descendants_after is not None else None
        )
    else:
        evidence["descendants_remaining"] = (
            False if evidence["process_group_alive_after"] is False
            else True if evidence["process_group_alive_after"] is True else None
        )
    evidence["confirmed"] = bool(evidence["root_exited"] and group_clear and taskkill_clear and not evidence["error"])
    evidence["cleanup_finished_at"] = _now()
    return evidence


def _kill_tree(
    process: subprocess.Popen[bytes],
    *,
    process_group_id: int | None = None,
    root_creation_time: str | None = None,
) -> bool:
    """Backward-compatible boolean wrapper around the auditable terminator."""

    return bool(
        _terminate_process_tree(
            process,
            process_group_id=process_group_id,
            root_creation_time=root_creation_time,
        )["confirmed"]
    )


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
        # Top-level provider errors and turn terminal events are execution
        # diagnostics, not tool calls.  They are classified separately by
        # ``_provider_error_events`` and the terminal-state checks below.  In
        # particular, putting a reconnect diagnostic into this list would
        # inflate ``tool_event_count`` and make an otherwise successful turn
        # look like an input-isolation violation.
        if event_type in {"error", "turn.failed", "turn.error", "turn.aborted"}:
            continue
        if item_type and item_type not in safe_types:
            lowered = item_type.casefold()
            if any(token in lowered for token in ("command", "tool", "mcp", "shell", "web", "function")):
                found.append({"event_type": event_type, "item_type": item_type, "line": event.get("_line_index")})
        if event_type in {"item.started", "item.completed"} and not item_type:
            # An item event without a typed payload cannot prove isolation.
            found.append({"event_type": event_type, "item_type": "missing", "line": event.get("_line_index")})
    return found


def _event_position(event: Mapping[str, Any], fallback: int) -> int:
    """Return a stable event position for parsed and in-memory event lists."""

    value = event.get("_line_index")
    try:
        position = int(value)
    except (TypeError, ValueError):
        return fallback
    return position if position >= 0 else fallback


def _provider_error_events(events: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Extract top-level provider diagnostics without treating them as tools.

    The raw JSONL remains the authoritative event capture.  This small
    projection is only for completion/result metadata and intentionally keeps
    the message bounded so a provider diagnostic cannot create an oversized
    status receipt.
    """

    found: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        if _event_type(event) != "error":
            continue
        message = event.get("message")
        found.append(
            {
                "event_type": "error",
                "line": _event_position(event, index),
                "message": message[:2048] if isinstance(message, str) else None,
            }
        )
    return found


def _recoverable_provider_error_lines(
    events: list[Mapping[str, Any]],
    *,
    thread_ids: list[str],
    parse_errors: list[str],
    reader_errors: list[str],
    exit_code: int | None,
    output_bytes: bytes,
    agent_message_count: int,
    cleanup_confirmed: bool,
) -> set[int]:
    """Return reconnect diagnostic lines eligible for successful completion.

    A reconnect message is merely a recoverable provider diagnostic when the
    complete execution contract is already satisfied: one thread, a final
    successful turn, no terminal turn failure, exit code zero, valid reader
    capture, non-empty output, and confirmed cleanup.  Every provider error
    in the capture must meet the narrow message and ordering rule; a mixed
    capture is fail-closed and returns an empty set.
    """

    provider_errors = _provider_error_events(events)
    if not provider_errors:
        return set()
    if (
        len(thread_ids) != 1
        or exit_code != 0
        or parse_errors
        or reader_errors
        or not output_bytes.strip()
        or agent_message_count < 1
        or not cleanup_confirmed
    ):
        return set()

    turn_completed = [
        (index, event)
        for index, event in enumerate(events)
        if _event_type(event) == "turn.completed"
    ]
    turn_failed = [
        event
        for event in events
        if _event_type(event) in {"turn.failed", "turn.error", "turn.aborted"}
    ]
    if not turn_completed or turn_failed:
        return set()
    final_turn_position = max(
        _event_position(event, index) for index, event in turn_completed
    )
    recoverable: set[int] = set()
    for item in provider_errors:
        line = item["line"]
        message = item.get("message")
        if (
            not isinstance(message, str)
            or _RECOVERABLE_PROVIDER_ERROR_RE.match(message) is None
            or line >= final_turn_position
        ):
            # A single fatal/misordered provider error invalidates the whole
            # capture.  Never admit a partial success by dropping the bad
            # diagnostic from the metadata.
            return set()
        recoverable.add(line)
    return recoverable


class LocalCodexBackend:
    """The pinned local completion backend for writer, judge, and planner lanes.

    Planner completions share the process/capture safeguards but are consumed
    as planning artifacts; ``reader_execution`` only wraps writer and judge
    calls in the ``ReaderExecutionRecord`` schema.
    """

    def __init__(
        self,
        run_root: str | Path,
        *,
        executable: str | Path | None = None,
        model_id: str = DEFAULT_MODEL_ID,
        reasoning_effort: str = DEFAULT_REASONING_EFFORT,
        timeout_seconds: int = 900,
        no_progress_seconds: int = 0,
        expected_version: str = DEFAULT_CLI_VERSION,
        expected_sha256: str = DEFAULT_CLI_SHA256,
        expected_cli_version: str | None = None,
        expected_executable_sha256: str | None = None,
        startup_timeout_seconds: float | None = None,
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
        # A hard wall clock timeout is the portable liveness boundary.  The
        # optional idle watchdog is retained for diagnostics, but its default
        # is zero so a quiet model turn is never killed merely because the
        # provider has not emitted a pipe chunk recently.
        self.no_progress_seconds = max(0, int(no_progress_seconds))
        self.expected_version = expected_cli_version or expected_version
        self.expected_sha256 = expected_executable_sha256 or expected_sha256
        self.startup_timeout_seconds = (
            max(0.1, float(startup_timeout_seconds))
            if startup_timeout_seconds is not None
            else 30.0
        )
        self.executable_sha256 = hashlib.sha256(self.executable.read_bytes()).hexdigest()
        self.cli_version = self._probe_version(timeout_seconds=self.startup_timeout_seconds)
        if self.expected_version and self.cli_version != self.expected_version:
            raise ValidationError(
                f"local Codex version mismatch: expected {self.expected_version}, got {self.cli_version}"
            )
        if self.expected_sha256 and self.executable_sha256 != self.expected_sha256:
            raise ValidationError("local Codex executable fingerprint mismatch")
        self.backend_id = f"local-codex:{self.cli_version}:{self.model_id}:{self.reasoning_effort}"

    def _probe_version(self, *, timeout_seconds: float = 30.0) -> str:
        try:
            completed = subprocess.run(
                [str(self.executable), "--version"],
                capture_output=True,
                check=False,
                timeout=max(0.1, float(timeout_seconds)),
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
            "disabled_features": list(_DISABLED_CLI_FEATURES),
            "output_token_limit_supported": False,
            "max_output_tokens": None,
        }

    def run(self, role: str, request: Mapping[str, Any]) -> dict[str, Any]:
        if role not in {"writer", "judge", "planner"}:
            raise ValidationError("local Codex backend role must be writer, judge, or planner")
        prompt = request.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValidationError("local Codex backend requires a non-empty prompt")
        request_id = request.get("request_id") or request.get("run_id") or uuid.uuid4().hex
        run_id = str(request.get("run_id") or f"{role}:{_safe_name(request_id)}")
        attempt_root = self.run_root / role / _safe_name(run_id)
        # A repeated request must never replace an earlier immutable capture.
        # Keep the logical run id stable while allocating a fresh physical
        # attempt directory when the expected path already contains data.
        if attempt_root.is_symlink():
            raise ValidationError("execution attempt path cannot be a symlink")
        if attempt_root.exists() and any(attempt_root.iterdir()):
            attempt_root = self.run_root / role / f"{_safe_name(run_id)}-{uuid.uuid4().hex[:12]}"
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
        ]
        for feature in _DISABLED_CLI_FEATURES:
            argv.extend(["--disable", feature])
        argv.extend([
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
        ])
        # Cancellation/stop handles are process-local synchronization objects,
        # not logical input.  Exclude them from the immutable request identity
        # so an owner can pass an Event without making JSON fingerprinting
        # fail (or making otherwise identical requests appear different).
        request_identity = {
            key: value
            for key, value in request.items()
            if key not in {"cancel_event", "_cancel_event", "stop_event", "_stop_event"}
        }
        request_fingerprint = fingerprint(request_identity)
        settings_fingerprint = request.get("settings_fingerprint") or fingerprint(self.settings())
        started_at = _now()
        process: subprocess.Popen[bytes] | None = None
        stdout = b""
        stderr = b""
        stdout_parts: list[bytes] = []
        stderr_parts: list[bytes] = []
        exit_code: int | None = None
        timed_out = False
        cleanup_confirmed = False
        failure_reason: str | None = None
        failure_detail: str | None = None
        timeout_kind: str | None = None
        stop_requested = False
        stop_reason: str | None = None
        process_group_id: int | None = None
        # A creation timestamp belongs to an observed process.  Keep it null
        # for a start failure instead of manufacturing an identity for a PID
        # that never existed.
        process_creation_time: str | None = None
        termination_evidence: dict[str, Any] = {}
        lifecycle_events: list[dict[str, Any]] = []
        lifecycle_lock = threading.Lock()
        reader_errors: list[str] = []
        stdin_errors: list[str] = []
        readers: list[threading.Thread] = []
        stdin_writer: threading.Thread | None = None
        stdin_done = threading.Event()
        # Once this event is set, reader threads may finish their blocking
        # read, but they must not append bytes or lifecycle errors.  This is
        # the finalisation fence for a bounded drain.
        capture_finalized = threading.Event()
        capture_lock = threading.Lock()
        reader_started = False
        first_output_at: str | None = None
        last_output_at: dict[str, str | None] = {"stdout": None, "stderr": None}
        last_progress_monotonic = time.monotonic()
        process_exited_at: str | None = None
        cleanup_finished_at: str | None = None
        reader_drain_confirmed = False
        stream_close_confirmed = True
        process_exited_recorded = False

        def _lifecycle(event: str, **details: Any) -> None:
            if capture_finalized.is_set() and event not in {"capture_finalized", "cleanup_finished", "terminal_event"}:
                return
            item: dict[str, Any] = {"event": event, "at": _now()}
            item.update(details)
            with lifecycle_lock:
                lifecycle_events.append(item)

        def _close_stream(stream: Any) -> None:
            try:
                if stream is not None:
                    stream.close()
            except Exception:
                pass

        def _close_stream_bounded(stream: Any, *, timeout_seconds: float = 1.0) -> bool:
            """Close a possibly-hosted pipe without blocking finalisation."""

            if stream is None:
                return True
            finished = threading.Event()

            def _close() -> None:
                try:
                    _close_stream(stream)
                finally:
                    finished.set()

            closer = threading.Thread(target=_close, daemon=True)
            closer.start()
            closer.join(timeout=max(0.0, float(timeout_seconds)))
            return not closer.is_alive() and finished.is_set()

        def _reader(name: str, stream: Any, parts: list[bytes]) -> None:
            nonlocal reader_started, first_output_at, last_progress_monotonic
            # Keep a separate lifecycle event for the actual thread start;
            # ``reader_started`` is the aggregate compatibility flag.
            _lifecycle("thread_started", stream=name)
            _lifecycle("reader_started", stream=name)
            reader_started = True
            capture_path = events_path if name == "stdout" else stderr_path
            try:
                while True:
                    # ``read1`` avoids waiting for a full 64 KiB buffer after a
                    # small JSON event.  The two reader threads are the only
                    # consumers of the subprocess pipes for this run.
                    chunk = _read_pipe_chunk(stream)
                    if not chunk:
                        break
                    data = bytes(chunk)
                    with capture_lock:
                        if capture_finalized.is_set():
                            break
                        parts.append(data)
                        # Persist each chunk while the child is still alive.
                        # The final drain rewrites the same bytes from the
                        # in-memory aggregate, which gives the receipt a
                        # deterministic hash while this append keeps liveness
                        # observable to an owner.
                        with capture_path.open("ab") as capture:
                            capture.write(data)
                            capture.flush()
                    last_progress_monotonic = time.monotonic()
                    last_output_at[name] = _now()
                    if first_output_at is None:
                        first_output_at = _now()
                        _lifecycle("first_output", stream=name)
            except (AttributeError, OSError, TypeError, ValueError) as exc:
                if not capture_finalized.is_set():
                    reader_errors.append(f"{name}: {type(exc).__name__}: {exc}")
                    _lifecycle("reader_error", stream=name, error=str(exc))
            finally:
                if not capture_finalized.is_set():
                    _lifecycle("reader_drained", stream=name)

        def _write_stdin(stream: Any) -> None:
            try:
                if stream is not None:
                    stream.write(prompt_bytes)
                    flush = getattr(stream, "flush", None)
                    if callable(flush):
                        flush()
                    _lifecycle("stdin_sent", bytes=len(prompt_bytes))
            except (AttributeError, BrokenPipeError, OSError, TypeError, ValueError) as exc:
                stdin_errors.append(f"{type(exc).__name__}: {exc}")
                _lifecycle("stdin_error", error=str(exc))
            finally:
                _close_stream(stream)
                stdin_done.set()
                _lifecycle("stdin_finished", ok=not stdin_errors)

        def _record_process_exited() -> None:
            nonlocal process_exited_at, process_exited_recorded, exit_code
            if process is None or process_exited_recorded or process.poll() is None:
                return
            exit_code = process.returncode
            process_exited_at = _now()
            process_exited_recorded = True
            _lifecycle("process_exited", pid=process.pid, exit_code=exit_code)

        def _drain_and_finalize() -> tuple[bytes, bytes, bool, bool]:
            """Close stdin and drain both readers exactly once.

            No ``communicate`` call is permitted after reader threads start:
            doing so races the readers and can deadlock on an inherited pipe.
            This helper owns the one final drain/finalize phase for both normal
            exit and abort paths.
            """

            nonlocal cleanup_finished_at, reader_drain_confirmed, stream_close_confirmed
            stream_close_confirmed = _close_stream_bounded(process.stdin if process is not None else None)
            if stdin_writer is not None:
                stdin_writer.join(timeout=2.0)
            # Closing stdin can release a writer blocked on a full input pipe;
            # a still-live daemon writer is retained only as an explicit
            # cleanup failure and never as completion evidence.
            if stdin_writer is not None and stdin_writer.is_alive():
                stdin_errors.append("stdin writer did not finish before drain deadline")
                _lifecycle("stdin_unconfirmed")
            drain_deadline = time.monotonic() + READER_DRAIN_TIMEOUT_SECONDS
            for reader in readers:
                reader.join(timeout=max(0.0, drain_deadline - time.monotonic()))
            reader_drain_confirmed = all(not reader.is_alive() for reader in readers)
            if not reader_drain_confirmed:
                _lifecycle("reader_drain_unconfirmed")
                # Set the fence before asking the host to close its streams.
                # A reader that wakes after the deadline can no longer mutate
                # the captured byte lists or append a late error.
                with capture_lock:
                    capture_finalized.set()
                _lifecycle("capture_finalized", reason="reader_drain_timeout")
                stream_close_confirmed = bool(
                    _close_stream_bounded(process.stdout if process is not None else None)
                    and _close_stream_bounded(process.stderr if process is not None else None)
                    and stream_close_confirmed
                )
                for reader in readers:
                    reader.join(timeout=1.0)
                reader_drain_confirmed = all(not reader.is_alive() for reader in readers)
            if not capture_finalized.is_set():
                with capture_lock:
                    capture_finalized.set()
                _lifecycle("capture_finalized", reason="drain_complete")
            stream_close_confirmed = bool(
                _close_stream_bounded(process.stdout if process is not None else None)
                and _close_stream_bounded(process.stderr if process is not None else None)
                and stream_close_confirmed
            )
            cleanup_finished_at = _now()
            return b"".join(stdout_parts), b"".join(stderr_parts), reader_drain_confirmed, stream_close_confirmed

        def _cancel_reason() -> str | None:
            """Return the explicit bounded-stop signal, if one is present."""

            if bool(request.get("stop_requested")):
                return "stop_requested"
            if bool(request.get("cancelled")):
                return "cancelled"
            if bool(request.get("cancel_requested")):
                return "cancel_requested"
            event = (
                request.get("stop_event")
                or request.get("_stop_event")
                or request.get("cancel_event")
                or request.get("_cancel_event")
            )
            if event is not None and callable(getattr(event, "is_set", None)) and event.is_set():
                return "stop_event"
            return None

        def _cancel_requested() -> bool:
            return _cancel_reason() is not None

        try:
            popen_options: dict[str, Any] = {
                "cwd": str(self.run_root),
                "stdin": subprocess.PIPE,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "close_fds": True,
            }
            if os.name == "nt":
                popen_options["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            else:
                # Isolate the CLI and any descendants in a group that can be
                # terminated without touching the benchmark owner.
                popen_options["start_new_session"] = True
            initial_stop_reason = _cancel_reason()
            if initial_stop_reason is not None:
                # The owner may have been stopped between scheduling and this
                # backend call.  Do not create a child after that boundary;
                # the owner will materialise its pending row separately.
                stop_requested = True
                stop_reason = initial_stop_reason
                failure_reason = "cancelled"
                _lifecycle("abort_requested", reason="cancelled", phase="before_start", stop_reason=stop_reason)
            else:
                process = subprocess.Popen(argv, **popen_options)
                process_creation_time = _now()
                if os.name != "nt":
                    try:
                        process_group_id = os.getpgid(process.pid)
                    except OSError:
                        process_group_id = None
                _lifecycle("process_started", pid=process.pid, creation_time=process_creation_time, process_group_id=process_group_id)

            if process is not None:
                # Start readers before sending input.  This ordering prevents
                # a large prompt or a verbose startup diagnostic from
                # blocking the owner before its watchdog can observe the
                # child.
                readers = [
                    threading.Thread(target=_reader, args=("stdout", process.stdout, stdout_parts), daemon=True),
                    threading.Thread(target=_reader, args=("stderr", process.stderr, stderr_parts), daemon=True),
                ]
                for reader in readers:
                    reader.start()
                stdin_writer = threading.Thread(target=_write_stdin, args=(process.stdin,), daemon=True)
                stdin_writer.start()

            hard_deadline = time.monotonic() + max(1, int(self.timeout_seconds))
            # A separate bounded input deadline converts a child that never
            # reads stdin into an explicit stdin_failed receipt.
            stdin_deadline = min(hard_deadline, time.monotonic() + max(1, min(30, int(self.timeout_seconds))))
            while process is not None and process.poll() is None:
                now = time.monotonic()
                cancel_reason = _cancel_reason()
                if cancel_reason is not None:
                    stop_requested = True
                    stop_reason = cancel_reason
                    failure_reason = "cancelled"
                    _lifecycle("abort_requested", reason="cancelled", stop_reason=stop_reason)
                    break
                if stdin_errors:
                    failure_reason = "stdin_failed"
                    failure_detail = stdin_errors[-1]
                    _lifecycle("abort_requested", reason="stdin_failed")
                    break
                if not stdin_done.is_set() and now >= stdin_deadline:
                    failure_reason = "stdin_failed"
                    failure_detail = "stdin write exceeded its bounded deadline"
                    _lifecycle("abort_requested", reason="stdin_failed")
                    break
                if now >= hard_deadline:
                    timed_out = True
                    timeout_kind = "hard_deadline"
                    failure_reason = "hard_timeout"
                    _lifecycle("abort_requested", reason="hard_timeout")
                    break
                # ``last_progress_monotonic`` is refreshed from the reader
                # threads only when a chunk arrives.  The optional watchdog is
                # disabled by default (no_progress_seconds == 0).
                if self.no_progress_seconds and now - last_progress_monotonic >= self.no_progress_seconds:
                    timed_out = True
                    timeout_kind = "no_progress_watchdog"
                    failure_reason = "hard_timeout"
                    _lifecycle("abort_requested", reason="no_progress_watchdog")
                    break
                time.sleep(0.05)

            _record_process_exited()
            if process is not None and process.poll() is None and failure_reason in {"cancelled", "stdin_failed", "hard_timeout"}:
                if failure_reason == "hard_timeout":
                    timed_out = True
                termination_evidence = _terminate_process_tree(
                    process,
                    process_group_id=process_group_id,
                    root_creation_time=process_creation_time,
                )
                cleanup_confirmed = bool(termination_evidence.get("confirmed"))
            if process is not None and process.poll() is None:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    failure_reason = failure_reason or "cleanup_unconfirmed"
                    termination_evidence = _terminate_process_tree(
                        process,
                        process_group_id=process_group_id,
                        root_creation_time=process_creation_time,
                    )
                    cleanup_confirmed = bool(termination_evidence.get("confirmed"))
            _record_process_exited()
        except (OSError, ValueError) as exc:
            failure_reason = "start_failed" if process is None else (failure_reason or "process_failed")
            failure_detail = f"{type(exc).__name__}: {exc}"
            _lifecycle("process_error", error=failure_detail)
            if process is not None and process.poll() is None:
                termination_evidence = _terminate_process_tree(
                    process,
                    process_group_id=process_group_id,
                    root_creation_time=process_creation_time,
                )
                cleanup_confirmed = bool(termination_evidence.get("confirmed"))
            _record_process_exited()
        finally:
            if process is not None and process.poll() is None:
                # Any unexpected exception must still leave an explicit abort
                # and a bounded tree cleanup attempt before capture finalizes.
                failure_reason = failure_reason or "cleanup_unconfirmed"
                termination_evidence = _terminate_process_tree(
                    process,
                    process_group_id=process_group_id,
                    root_creation_time=process_creation_time,
                )
                cleanup_confirmed = bool(termination_evidence.get("confirmed"))
                _record_process_exited()
            stdout, stderr, reader_drain_confirmed, stream_close_confirmed = _drain_and_finalize()
            exit_code = process.returncode if process is not None else None
            if process is not None and process.poll() is not None:
                group_state = _process_group_alive(process_group_id)
                if os.name == "nt":
                    descendants = _windows_descendant_pids_with_retry(
                        process.pid, root_creation_time=process_creation_time
                    )
                    normal_tree_clear = (
                        descendants is not None and not descendants
                    ) or (
                        not isinstance(process, _REAL_SUBPROCESS_POPEN)
                        and process.poll() is not None
                    )
                else:
                    normal_tree_clear = group_state is False
                if not termination_evidence:
                    cleanup_confirmed = bool(process.poll() is not None and normal_tree_clear)
                cleanup_confirmed = bool(
                    cleanup_confirmed
                    and reader_drain_confirmed
                    and stream_close_confirmed
                    and not stdin_errors
                )
            else:
                cleanup_confirmed = False
            _lifecycle("cleanup_finished", readers_drained=reader_drain_confirmed, tree_confirmed=cleanup_confirmed)
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
        output_bytes = output_path.read_bytes() if output_path.is_file() else b""
        output_text = output_bytes.decode("utf-8", errors="replace") if output_bytes else ""
        agent_messages = [
            event for event in events
            if isinstance(event.get("item"), Mapping)
            and event["item"].get("type") == "agent_message"
        ]
        provider_errors = _provider_error_events(events)
        recoverable_provider_error_lines = _recoverable_provider_error_lines(
            events,
            thread_ids=thread_ids,
            parse_errors=parse_errors,
            reader_errors=reader_errors,
            exit_code=exit_code,
            output_bytes=output_bytes,
            agent_message_count=len(agent_messages),
            cleanup_confirmed=cleanup_confirmed,
        )
        provider_error_metadata = [
            {
                **item,
                "recoverable": item["line"] in recoverable_provider_error_lines,
            }
            for item in provider_errors
        ]
        provider_errors_recoverable = bool(provider_errors) and len(
            recoverable_provider_error_lines
        ) == len(provider_errors)
        if failure_reason is None:
            if timed_out:
                failure_reason = "hard_timeout"
            elif exit_code is None:
                failure_reason = "start_failed"
            elif exit_code != 0:
                failure_reason = "nonzero_exit"
            elif parse_errors or reader_errors:
                failure_reason = "parse_failed"
            elif len(thread_ids) != 1:
                failure_reason = "thread_identity_not_unique"
            elif provider_errors and not provider_errors_recoverable:
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
                failure_reason = "cleanup_unconfirmed"
        terminal_observed = (turn_completed[-1] if turn_completed else None) or (turn_failed[-1] if turn_failed else None)
        if terminal_observed is not None:
            _lifecycle(
                "terminal_event",
                event_type=_event_type(terminal_observed),
                line=terminal_observed.get("_line_index"),
            )
        if failure_reason == "stdin_failed" and failure_detail is None and stdin_errors:
            failure_detail = stdin_errors[-1]
        if failure_reason == "hard_timeout" and timeout_kind is None:
            timeout_kind = "hard_deadline"
        completed = failure_reason is None
        terminal_status = "completed" if completed else ("unavailable" if failure_reason and "unavailable" in failure_reason else "failed")
        thread_id = thread_ids[0] if len(thread_ids) == 1 else ""
        # The record context is the exact thread.started identity, so a
        # resolver can compare it without trusting a prefix or alias.
        context_id = thread_id if thread_id else f"context:unverified:{_safe_name(run_id)}"
        terminal_event = turn_completed[-1] if turn_completed else None
        process_identity = {
            "pid": process.pid if process is not None else None,
            "creation_time": process_creation_time,
            "owned_by_backend": process is not None,
        }
        if not termination_evidence:
            fallback_descendants = (
                _windows_descendant_pids_with_retry(
                    process.pid,
                    root_creation_time=process_creation_time,
                )
                if os.name == "nt" and process is not None
                else None
            )
            fallback_group_state = _process_group_alive(process_group_id)
            termination_evidence = {
                "root_pid": process.pid if process is not None else None,
                "root_creation_time": process_creation_time,
                "process_group_id": process_group_id,
                "termination_requested_at": None,
                "termination_method": "natural_exit" if process is not None else "not_started",
                "taskkill_returncode": None,
                "root_exited": bool(process is not None and process.poll() is not None),
                "process_group_alive_before": None,
                "process_group_alive_after": fallback_group_state,
                "descendants_observed": fallback_descendants is not None if os.name == "nt" else fallback_group_state is not None,
                "descendant_pids": list(fallback_descendants or []),
                "descendants_remaining": (
                    False if fallback_descendants is not None and not fallback_descendants
                    else True if fallback_descendants is not None else None
                ) if os.name == "nt" else (
                    False if fallback_group_state is False
                    else True if fallback_group_state is True else None
                ),
                "confirmed": cleanup_confirmed,
                "error": None,
                "cleanup_finished_at": cleanup_finished_at,
            }
        lifecycle = {
            "reader_started": bool(reader_started),
            "first_output": first_output_at is not None,
            "first_output_at": first_output_at,
            "terminal_event": terminal_event is not None or bool(turn_failed),
            "terminal_event_type": "turn.completed" if terminal_event else ("turn.failed" if turn_failed else None),
            "stop_requested": stop_requested,
            "stop_reason": stop_reason,
            "process_exited": bool(process_exited_recorded),
            "process_exited_at": process_exited_at,
            "cleanup_finished": cleanup_finished_at is not None,
            "cleanup_finished_at": cleanup_finished_at,
            "cleanup_confirmed": cleanup_confirmed,
            "terminal_published_after_cleanup": cleanup_finished_at is not None,
            "reader_drain_confirmed": reader_drain_confirmed,
            "stream_close_confirmed": stream_close_confirmed,
            "stdin_finished": stdin_done.is_set() and not (stdin_writer and stdin_writer.is_alive()),
            "stdin_sent": any(item.get("event") == "stdin_sent" for item in lifecycle_events),
            "last_output_at": dict(last_output_at),
        }
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
            "process_creation_time": process_creation_time,
            "process_identity": process_identity,
            "process_group_id": process_group_id,
            "thread_id": thread_id or None,
            "context_id": context_id,
            "started_at": started_at,
            "finished_at": finished_at,
            "last_output_at": dict(last_output_at),
            "exit_code": exit_code,
            "timed_out": timed_out,
            "stop_requested": stop_requested,
            "stop_reason": stop_reason,
            "descendant_cleanup_confirmed": cleanup_confirmed,
            "stream_close_confirmed": stream_close_confirmed,
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
            "provider_error_count": len(provider_errors),
            "recoverable_provider_error_count": len(recoverable_provider_error_lines),
            "provider_errors_recoverable": provider_errors_recoverable,
            "provider_error_events": provider_error_metadata,
            "agent_message_count": len(agent_messages),
            "parse_errors": parse_errors,
            "usage": next((event.get("usage") for event in reversed(events) if isinstance(event.get("usage"), Mapping)), None),
            "cost_actual": None,
            "terminal_status": terminal_status,
            "failure_reason": failure_reason,
            "failure_detail": failure_detail,
            "timeout_kind": timeout_kind,
            "lifecycle": lifecycle,
            "lifecycle_events": lifecycle_events,
            "cleanup_evidence": termination_evidence,
        }
        completion["completion_fingerprint"] = fingerprint(completion)
        _write_json_atomic(completion_path, completion)
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
            "process_id": process.pid if process is not None else None,
            "process_creation_time": process_creation_time,
            "process_identity": process_identity,
            "process_group_id": process_group_id,
            "thread_id": thread_id or context_id,
            "exit_code": exit_code if exit_code is not None else 1,
            "timed_out": timed_out,
            "stop_requested": stop_requested,
            "stop_reason": stop_reason,
            "descendant_cleanup_confirmed": cleanup_confirmed,
            "stream_close_confirmed": stream_close_confirmed,
            "terminal_event_type": "turn.completed" if terminal_event else "none",
            "terminal_event_index": terminal_event.get("_line_index") if terminal_event else 0,
            "tool_event_count": len(tools),
            "provider_error_count": len(provider_errors),
            "recoverable_provider_error_count": len(recoverable_provider_error_lines),
            "provider_errors_recoverable": provider_errors_recoverable,
            "provider_error_events": provider_error_metadata,
            "usage": completion["usage"],
            "cost_actual": None,
            "failure_reason": failure_reason,
            "failure_detail": failure_detail,
            "timeout_kind": timeout_kind,
            "lifecycle": lifecycle,
            "lifecycle_events": lifecycle_events,
            "cleanup_evidence": termination_evidence,
        }
        if completed:
            result["output_fingerprint"] = _sha256_bytes(output_bytes)
        return result


__all__ = ["LocalCodexBackend", "DEFAULT_CODEX_PATH", "DEFAULT_CLI_VERSION", "DEFAULT_CLI_SHA256"]
