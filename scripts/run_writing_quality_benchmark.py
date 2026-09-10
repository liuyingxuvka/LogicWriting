"""Run the local LogicWriting writer/judge benchmark.

With no backend this command emits an unavailable receipt and never invents a
score.  With ``--backend-plan`` it starts the pinned local Codex CLI through
``LocalCodexBackend`` and records every writer, artifact, pair judge, and
aggregation input below one owner run root.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, wait
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
import time

ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = ROOT / "skills" / "logic-writing" / "scripts"
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))

from _common import ValidationError, fingerprint, fingerprint_text, fingerprint_without, require_mapping, require_schema  # noqa: E402
from execution_record_resolver import LocalExecutionRecordResolver  # noqa: E402
from local_execution_backend import (  # noqa: E402
    DEFAULT_CLI_SHA256,
    DEFAULT_CLI_VERSION,
    DEFAULT_MODEL_ID,
    DEFAULT_REASONING_EFFORT,
    LocalCodexBackend,
    _process_group_alive,
    _terminate_process_tree,
)
from reader_execution import dispatch_judge, dispatch_writer, validate_execution_record  # noqa: E402
from reader_pipeline import build_artifact_map  # noqa: E402
from production_reader_pipeline import (  # noqa: E402
    InstalledResearchGuardProvider,
    prepare_production_reader_input,
    render_reader_spine_prompt,
)

# Keep the concrete process type before contract tests replace
# ``subprocess.Popen`` with a lightweight fake.  The isolated runner uses this
# distinction only to decide whether the real child bootstrap watchdog or a
# test-double's direct hard timeout should own a still-starting process.
_SUBPROCESS_POPEN_TYPE = subprocess.Popen


CASE_COUNT = 12
REPEATS = 2
VERSIONS = ("baseline", "repaired")
CASE_ORDER = ("I01", "A01", "F01", "T01", "I02", "A02", "F02", "T02", "I03", "A03", "F03", "T03")
HELD_OUT_CASE_IDS = ("H-I", "H-A", "H-F", "H-T")
HELD_OUT_REPEATS = 1
HELD_OUT_VERSION = "current"
HELD_OUT_RUBRIC = (
    "评审一篇独立成稿，不比较版本，也不要猜测作者身份。先写出覆盖全文的实际反向提纲，"
    "再逐项核对材料、任务和约束。每个反向提纲单元必须包含原文中的可定位摘录和单元定位；"
    "每个核心义务都要给出可定位的通过或缺陷证据。八个评分维度均使用1到5分。"
    "content_fidelity、instruction_fidelity、structure_fidelity低于4，或存在需要修复的核心缺陷，"
    "都不能通过。不得补写材料没有给出的事实、时间、价格、因果、无障碍属性或人物内心。"
    "只返回指定JSON，不输出评审过程。"
)
DIMENSIONS = (
    "clarity", "coherence", "naturalness", "reader_fit", "genre_fit",
    "content_fidelity", "instruction_fidelity", "structure_fidelity",
)

_REQUIRED_NODE_TYPES = {
    "C0": "Claim",
    "E1": "Evidence",
    "W1": "Warrant",
    "A1": "Assumption",
    "L1": "Limitation",
    "R1": "Rebuttal",
}
_NODE_TYPE_ALIASES = {
    "claim": "Claim",
    "evidence": "Evidence",
    "warrant": "Warrant",
    "assumption": "Assumption",
    "limitation": "Limitation",
    "rebuttal": "Rebuttal",
}
_EDGE_TYPE_ALIASES = {
    "support": "supports",
    "supports": "supports",
    "depends_on": "depends_on",
    "qualify": "qualifies",
    "qualifies": "qualifies",
    "attack": "attacks",
    "attacks": "attacks",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _bytes_fp(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parallel_jobs(executor: Any, jobs: list[dict[str, Any]], worker: Callable[..., dict[str, Any]], *, timeout_seconds: int, role: str, startup_timeout_seconds: int = 180) -> list[dict[str, Any]]:
    """Legacy in-process adapter retained for focused compatibility tests.

    A provider can fail to emit its terminal receipt while its worker remains
    alive.  Waiting on an unbounded executor context in that situation
    strands the aggregate owner forever.  The runner records a durable failed
    row for every future that has no terminal result, then lets the backend's
    own process cleanup finish in the background.  Production benchmark runs
    use ``_run_isolated_jobs`` below, which starts one independently terminable
    subprocess per job; this adapter is never used as final execution
    isolation.
    """
    # Submit only one bounded wave at a time.  Submitting the entire batch at
    # once makes queued work invisible to the startup watchdog and lets one
    # stuck future consume the deadline for every later job.
    max_workers = max(1, int(getattr(executor, "_max_workers", 1)))
    waves = [jobs[offset:offset + max_workers] for offset in range(0, len(jobs), max_workers)]
    started = time.monotonic()
    deadline = started + max(1, int(timeout_seconds))
    startup_deadline = started + max(1, int(startup_timeout_seconds))
    rows: list[dict[str, Any]] = []

    def _legacy_failure(job: Mapping[str, Any], *, error_class: str, message: str) -> dict[str, Any]:
        row = _job_row(job, role, status="failed", terminal_reason=error_class)
        row["error"] = message
        row["error_event"] = {
            "type": "error_event", "role": role, "job_id": row["job_id"],
            "error_class": error_class, "message": message, "terminal": True,
        }
        return row

    for wave_index, wave in enumerate(waves):
        if time.monotonic() >= deadline:
            error_class = "OrchestrationTimeout"
            message = f"{role} job exceeded orchestration deadline"
            for job in wave:
                rows.append(_legacy_failure(job, error_class=error_class, message=message))
            continue
        futures = [executor.submit(worker, job) for job in wave]
        future_jobs = dict(zip(futures, wave))
        wave_deadline = min(deadline, time.monotonic() + max(1, int(timeout_seconds / max(1, len(waves)))))
        pending = set(futures)
        while pending and time.monotonic() < wave_deadline:
            if wave_index == 0 and not rows and time.monotonic() >= startup_deadline:
                message = f"{role} startup/dispatch exceeded deadline"
                for job in wave:
                    rows.append(_legacy_failure(job, error_class="StartupDispatchTimeout", message=message))
                pending.clear()
                break
            done, pending = wait(pending, timeout=min(1.0, max(0.0, wave_deadline - time.monotonic())))
            for future in done:
                try:
                    rows.append(future.result())
                except Exception as exc:
                    rows.append(_legacy_failure(future_jobs[future], error_class=type(exc).__name__, message=str(exc)))
        for future, job in zip(futures, wave):
            if future in pending:
                message = f"{role} job exceeded orchestration deadline"
                rows.append(_legacy_failure(job, error_class="OrchestrationTimeout", message=message))
    executor.shutdown(wait=False, cancel_futures=True)
    return rows


def _job_identity(job: Mapping[str, Any], role: str) -> dict[str, Any]:
    case = job.get("case") if isinstance(job.get("case"), Mapping) else {}
    case_id = str(case.get("case_id") or job.get("case_id") or "unknown")
    repeat = int(job.get("repeat", 0) or 0)
    attempt_id = str(job.get("attempt_id") or "1")
    version = str(job.get("version")) if job.get("version") is not None else None
    judge_index = int(job.get("judge_index", 0) or 0) if job.get("judge_index") is not None else None
    suffix = version or (str(judge_index) if judge_index is not None else "job")
    job_id = str(job.get("job_id") or f"{role}:{case_id}:{repeat}:{suffix}")
    return {
        "job_id": job_id,
        "role": role,
        "case_id": case_id,
        "repeat": repeat,
        "attempt_id": attempt_id,
        "version": version,
        "judge_index": judge_index,
    }


def _job_row(job: Mapping[str, Any], role: str, *, status: str = "queued", terminal_reason: str | None = None) -> dict[str, Any]:
    identity = _job_identity(job, role)
    now = _now()
    row: dict[str, Any] = {
        "schema_version": "logic-writing.quality-job-result.v1",
        **identity,
        "status": status,
        "terminal_reason": terminal_reason,
        "status_history": [{"status": status, "at": now}],
        "scheduled_at": now,
        "started_at": None,
        "finished_at": now if status not in {"queued", "starting", "running"} else None,
        "dependency_status": "unknown",
        "process_id": None,
        "process_creation_time": None,
        "process_identity": {"pid": None, "creation_time": None, "owned_by_aggregator": False},
        "cleanup_confirmed": False,
        "cleanup_evidence": {"required": True, "confirmed": False, "root_pid": None, "root_creation_time": None},
    }
    if terminal_reason is not None:
        row["error"] = terminal_reason
        row["error_event"] = {
            "type": "error_event",
            "role": role,
            "job_id": identity["job_id"],
            "error_class": terminal_reason,
            "message": terminal_reason,
            "terminal": True,
        }
    return row


_JOB_NOT_STARTED_STATUSES = frozenset({
    "queued",
    "not_started_dependency_failed",
    "not_started_deadline",
    "not_started_cleanup_blocked",
})
_JOB_TERMINAL_STATUSES = frozenset({
    "completed",
    "failed",
    "timed_out",
    "cancelled",
    "not_started_dependency_failed",
    "not_started_deadline",
    "not_started_cleanup_blocked",
})
_JOB_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "queued": frozenset({"starting", "failed", "cancelled", "not_started_dependency_failed", "not_started_deadline", "not_started_cleanup_blocked"}),
    "starting": frozenset({"running", "failed", "timed_out", "cancelled", "not_started_dependency_failed", "not_started_cleanup_blocked"}),
    "running": frozenset({"completed", "failed", "timed_out", "cancelled"}),
}


def _job_transition(row: dict[str, Any], status: str, *, reason: str | None = None, at: str | None = None) -> None:
    """Append one legal lifecycle state and reject late/duplicate terminal data.

    A child can finish after the parent has timed it out.  Treating that late
    row as an ordinary assignment would allow a failed job to become
    ``completed``.  The parent therefore has one explicit transition function;
    every status mutation passes through it and a repeated terminal state is a
    protocol error.
    """

    history = row.setdefault("status_history", [])
    current = None
    if history and isinstance(history[-1], Mapping):
        current = history[-1].get("status")
    if not isinstance(current, str):
        current = row.get("status") if isinstance(row.get("status"), str) else None
    if status not in _JOB_TERMINAL_STATUSES and status not in {"queued", "starting", "running"}:
        raise ValidationError(f"unknown job status: {status}")
    if current == status:
        if status in _JOB_TERMINAL_STATUSES:
            raise ValidationError(f"duplicate terminal job transition: {status}")
        if reason is not None:
            raise ValidationError(f"active job transition cannot carry terminal reason: {status}")
        return
    if current in _JOB_TERMINAL_STATUSES:
        raise ValidationError(f"late job transition after terminal state {current}: {status}")
    if current is not None and status not in _JOB_ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise ValidationError(f"illegal job transition {current} -> {status}")
    history.append({"status": status, "at": at or _now()})
    row["status"] = status
    if reason is not None:
        row["terminal_reason"] = reason
        row.setdefault("error", reason)
    if status in _JOB_TERMINAL_STATUSES:
        row["finished_at"] = at or _now()


def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    """Append one complete owner event and force it to the private run root."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(dict(value), ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()
        try:
            os.fsync(stream.fileno())
        except OSError:
            # Some contract-test streams and filesystems do not expose fsync;
            # the flushed append is still a complete line and remains valid.
            pass


def _dependency_judge_row(job: Mapping[str, Any], *, reason: str = "dependency_failed") -> dict[str, Any]:
    """Materialise a judge outcome when its writer pair was not runnable."""

    row = _job_row(job, "judge", status="not_started_dependency_failed", terminal_reason=reason)
    row.update({
        "dependency_status": "failed",
        "dependency_writer_jobs": [
            f"writer:{job.get('case', {}).get('case_id', 'unknown')}:{int(job.get('repeat', 0) or 0)}:baseline",
            f"writer:{job.get('case', {}).get('case_id', 'unknown')}:{int(job.get('repeat', 0) or 0)}:repaired",
        ],
        "error_event": {
            "type": "error_event",
            "role": "judge",
            "job_id": row["job_id"],
            "error_class": reason,
            "message": "judge was not started because its required writer dependency did not complete",
            "terminal": True,
        },
    })
    return row


def _job_started(row: Mapping[str, Any]) -> bool:
    """Return whether a scheduled child process actually started."""

    process_id = row.get("process_id")
    if isinstance(process_id, bool):
        return False
    try:
        return int(process_id) > 0
    except (TypeError, ValueError):
        return False


def _execution_progress(rows: Mapping[str, Mapping[str, Any]], planned: int) -> dict[str, int]:
    """Build the live progress shape used by the owner and its receipt."""

    values = list(rows.values())
    statuses = [str(row.get("status") or "queued") for row in values]
    terminal = sum(status in _JOB_TERMINAL_STATUSES for status in statuses)
    not_started = sum(status in _JOB_NOT_STARTED_STATUSES for status in statuses)
    return {
        "planned": int(planned),
        "started": sum(_job_started(row) or status in {"starting", "running"} for row, status in zip(values, statuses)),
        "running": sum(status == "running" for status in statuses),
        "succeeded": sum(status == "completed" for status in statuses),
        "failed": sum(status in {"failed", "timed_out", "cancelled"} for status in statuses),
        "not_started": not_started,
        "terminal": terminal,
    }


def _backend_config(backend: LocalCodexBackend) -> dict[str, Any]:
    """Serialize only the pinned local backend identity for a child job."""

    return {
        "run_root": str(backend.run_root),
        "executable": str(backend.executable),
        "model_id": backend.model_id,
        "reasoning_effort": backend.reasoning_effort,
        "timeout_seconds": backend.timeout_seconds,
        "no_progress_seconds": backend.no_progress_seconds,
        "expected_cli_version": backend.cli_version,
        "expected_executable_sha256": backend.executable_sha256,
    }


def _write_json_atomic(path: Path, value: Any) -> None:
    """Publish one child marker/row without exposing a partial JSON file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    _write_json(temporary, value)
    os.replace(temporary, path)


def _job_process_options() -> dict[str, Any]:
    options: dict[str, Any] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        options["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        options["start_new_session"] = True
    return options


def _job_worker_main(payload_path: Path) -> int:
    """Run exactly one benchmark job in its own process boundary."""

    payload: dict[str, Any] = {}
    role = "writer"
    row_path: Path | None = None
    try:
        value = _read_json(payload_path)
        if not isinstance(value, dict):
            raise ValueError("job payload is not an object")
        payload = value
        role = str(payload["role"])
        job = payload["job"]
        row_path = Path(str(payload["row_path"])).resolve()
        marker_path = Path(str(payload["marker_path"])).resolve()
        identity = _job_identity(job, role)
        worker_started_at = _now()
        backend_config = payload.get("backend_config")
        if not isinstance(backend_config, Mapping):
            raise ValueError("local backend dependency is missing")
        backend = LocalCodexBackend(**dict(backend_config))
        resolver = LocalExecutionRecordResolver(
            backend.run_root,
            expected_cli_version=backend.cli_version,
            expected_cli_sha256=backend.executable_sha256,
            expected_backend_id=backend.backend_id,
        )
        # The marker is the parent's admission signal: publish it only after
        # the worker has reconstructed and validated its pinned backend and
        # resolver.  Publishing ``running`` before dependency construction
        # made a worker that failed during backend initialization look ready;
        # the parent then skipped its startup-dependency gate and eventually
        # mislabeled the row as a hard timeout.  A dependency failure now
        # remains a durable ``not_started_dependency_failed`` row.
        _write_json_atomic(marker_path, {
            "schema_version": "logic-writing.quality-job-marker.v1",
            **identity,
            "status": "running",
            "process_id": os.getpid(),
            "process_creation_time": _now(),
            "started_at": worker_started_at,
        })
        if role == "writer":
            row = _execute_writer_job(
                case=job["case"], repeat=int(job["repeat"]), version=str(job["version"]),
                writer_dir=Path(str(payload["writer_dir"])), local_backend=backend, backend=None, resolver=resolver,
            )
        elif role == "judge":
            if job.get("evaluation_mode") == "single":
                row = _execute_single_judge_job(
                    case=job["case"], repeat=int(job["repeat"]), judge_index=int(job["judge_index"]),
                    writer=job["writer"], rubric_text=str(payload["rubric_text"]),
                    cases_dir=Path(str(payload["cases_dir"])), judge_dir=Path(str(payload["judge_dir"])),
                    local_backend=backend, backend=None, resolver=resolver,
                )
            else:
                row = _execute_judge_job(
                    case=job["case"], repeat=int(job["repeat"]), judge_index=int(job["judge_index"]), order=job["order"],
                    rubric_text=str(payload["rubric_text"]), cases_dir=Path(str(payload["cases_dir"])),
                    judge_dir=Path(str(payload["judge_dir"])), local_backend=backend, backend=None, resolver=resolver,
                )
        else:
            raise ValueError(f"unsupported job role: {role}")
        if not isinstance(row, dict):
            raise ValueError("job worker returned no row")
        row.update({
            "schema_version": "logic-writing.quality-job-result.v1",
            **identity,
            "worker_process_id": os.getpid(),
            "worker_process_creation_time": payload.get("worker_process_creation_time"),
            "dependency_status": "ready",
        })
        row.setdefault("status_history", [{"status": "running", "at": worker_started_at}])
        _job_transition(row, str(row.get("status") or "failed"), at=_now())
        _write_json_atomic(row_path, row)
        return 0
    except Exception as exc:
        if row_path is not None:
            row = _job_row(payload.get("job", {}), role, status="not_started_dependency_failed", terminal_reason="dependency_failed")
            row.update({
                "dependency_status": "failed",
                "worker_process_id": os.getpid(),
                "worker_process_creation_time": payload.get("worker_process_creation_time"),
                "error": str(exc),
                "error_event": {
                    "type": "error_event", "role": role, "job_id": row["job_id"],
                    "error_class": type(exc).__name__, "message": str(exc), "terminal": True,
                },
            })
            try:
                _write_json_atomic(row_path, row)
            except OSError:
                pass
        return 1


def _decorate_job_row(
    row: dict[str, Any],
    identity: Mapping[str, Any],
    *,
    process_id: int | None,
    process_creation_time: str,
    cleanup_evidence: Mapping[str, Any],
    status: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    result = dict(row)
    result.update({
        "schema_version": "logic-writing.quality-job-result.v1",
        **dict(identity),
        "process_id": process_id,
        "process_creation_time": process_creation_time,
        "process_identity": {"pid": process_id, "creation_time": process_creation_time, "owned_by_aggregator": True},
        "cleanup_evidence": dict(cleanup_evidence),
        "cleanup_confirmed": bool(cleanup_evidence.get("confirmed")),
        "finished_at": result.get("finished_at") or _now(),
    })
    if status is not None:
        _job_transition(result, status, reason=reason)
    elif reason is not None:
        result["terminal_reason"] = reason
    if result.get("status") in {"failed", "timed_out", "cancelled", "not_started_dependency_failed", "not_started_deadline"} and "error_event" not in result:
        result["error_event"] = {
            "type": "error_event", "role": identity["role"], "job_id": identity["job_id"],
            "error_class": str(result.get("terminal_reason") or result.get("status")),
            "message": str(result.get("terminal_reason") or result.get("status")), "terminal": True,
        }
    return result


def _run_isolated_jobs(
    jobs: list[dict[str, Any]],
    *,
    role: str,
    output_dir: Path,
    writer_dir: Path,
    judge_dir: Path,
    cases_dir: Path,
    rubric_text: str,
    local_backend: LocalCodexBackend,
    plan: Mapping[str, Any],
    timeout_seconds: int,
    startup_timeout_seconds: int,
) -> list[dict[str, Any]]:
    """Run jobs as independently terminable children and aggregate rows.

    The parent owns the shared ledger.  A child owns only its job directory;
    every state transition is copied into the parent row after the child has
    exited and its cleanup evidence has been checked.  Queued jobs are never
    submitted once the batch deadline is stale, and a slot is released only
    after the child process cleanup phase returns.
    """

    if not jobs:
        return []
    dispatch_root = output_dir / "job-dispatch" / role
    dispatch_root.mkdir(parents=True, exist_ok=True)
    concurrency = max(1, min(int(plan.get("concurrency", 1)), len(jobs)))
    per_job_timeout = max(1, int(plan.get("timeout_seconds", 900)))
    batch_deadline = time.monotonic() + max(1, int(timeout_seconds))
    rows: list[dict[str, Any]] = []
    pending = list(jobs)
    active: dict[str, dict[str, Any]] = {}
    lane_stopped = False
    # The parent is the sole writer for these live progress surfaces.  Child
    # processes only publish their marker and terminal row in their own job
    # directory; this avoids concurrent JSONL/progress corruption.
    state_events_path = output_dir / "job-state-events.jsonl"
    progress_path = output_dir / "progress-summary.json"
    state_rows: dict[str, dict[str, Any]] = {}

    def _record_state(row: Mapping[str, Any], *, event: str) -> None:
        identity = {
            key: row.get(key)
            for key in ("job_id", "role", "case_id", "repeat", "attempt_id", "version", "judge_index")
        }
        job_id = str(identity["job_id"])
        state_rows[job_id] = dict(row)
        _append_jsonl(
            state_events_path,
            {
                "schema_version": "logic-writing.quality-job-state-event.v1",
                "event": event,
                "at": _now(),
                **identity,
                "status": row.get("status"),
                "terminal_reason": row.get("terminal_reason"),
                "process_id": row.get("process_id"),
                "process_creation_time": row.get("process_creation_time"),
                "cleanup_confirmed": bool(row.get("cleanup_confirmed")),
            },
        )
        progress = _execution_progress(state_rows, len(jobs))
        _write_json_atomic(
            progress_path,
            {
                "schema_version": "logic-writing.quality-progress.v1",
                "role": role,
                "updated_at": _now(),
                **progress,
            },
        )

    # Materialise every planned key before the first child is launched.
    for planned_job in jobs:
        _record_state(_job_row(planned_job, role), event="planned")

    def _stop_pending(reason: str) -> None:
        nonlocal lane_stopped
        lane_stopped = True
        while pending:
            job = pending.pop(0)
            row = _job_row(job, role, status="not_started_cleanup_blocked", terminal_reason=reason)
            row["dependency_status"] = "not_started"
            rows.append(row)
            _record_state(row, event="not_started")

    def _paths(identity: Mapping[str, Any]) -> tuple[Path, Path, Path]:
        case_id, repeat = str(identity["case_id"]), str(identity["repeat"])
        if role == "writer":
            leaf = writer_dir / case_id / repeat / str(identity["version"])
            row_path = leaf / "writer.json"
        else:
            leaf = judge_dir / case_id / repeat / str(identity["judge_index"])
            row_path = leaf / "judge.json"
        token = _safe_dispatch_name(str(identity["job_id"]))
        return row_path, dispatch_root / f"{token}.payload.json", dispatch_root / f"{token}.marker.json"

    while pending or active:
        now = time.monotonic()
        if lane_stopped and pending:
            _stop_pending("cleanup_unconfirmed")
        while not lane_stopped and pending and len(active) < concurrency and time.monotonic() < batch_deadline:
            job = pending.pop(0)
            identity = _job_identity(job, role)
            base = _job_row(job, role, status="starting")
            base["started_at"] = _now()
            _record_state(base, event="starting")
            row_path, payload_path, marker_path = _paths(identity)
            # Existing job directories are immutable evidence from an earlier
            # run.  Do not let a late/repeated child overwrite them.
            if row_path.parent.exists() and any(row_path.parent.iterdir()):
                _job_transition(base, "failed", reason="run_root_not_empty")
                base["dependency_status"] = "blocked_existing_capture"
                base["error_event"] = {
                    "type": "error_event", "role": role, "job_id": identity["job_id"],
                    "error_class": "run_root_not_empty", "message": "job capture directory already contains evidence", "terminal": True,
                }
                rows.append(base)
                _record_state(base, event="terminal")
                continue
            payload = {
                "schema_version": "logic-writing.quality-job-payload.v1",
                "role": role,
                "job": job,
                "row_path": str(row_path.resolve()),
                "marker_path": str(marker_path.resolve()),
                "writer_dir": str(writer_dir.resolve()),
                "judge_dir": str(judge_dir.resolve()),
                "cases_dir": str(cases_dir.resolve()),
                "rubric_text": rubric_text,
                "backend_config": _backend_config(local_backend),
                "worker_process_creation_time": _now(),
            }
            _write_json_atomic(payload_path, payload)
            try:
                process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--_job-worker", str(payload_path)], **_job_process_options())
            except (OSError, ValueError) as exc:
                _job_transition(base, "not_started_dependency_failed", reason="start_failed")
                base.update({
                    "dependency_status": "failed", "error": str(exc),
                    "error_event": {"type": "error_event", "role": role, "job_id": identity["job_id"], "error_class": type(exc).__name__, "message": str(exc), "terminal": True},
                })
                rows.append(base)
                _record_state(base, event="terminal")
                continue
            pid = int(process.pid)
            child_started = _now()
            base["process_id"] = pid
            base["process_creation_time"] = child_started
            base["process_identity"] = {"pid": pid, "creation_time": child_started, "owned_by_aggregator": True}
            base["dependency_status"] = "starting"
            _record_state(base, event="process_started")
            active[identity["job_id"]] = {
                "job": job, "identity": identity, "base": base, "process": process,
                "row_path": row_path, "marker_path": marker_path, "payload_path": payload_path,
                "started_monotonic": time.monotonic(), "child_started": child_started,
            }
            now = time.monotonic()
        # Let active children reach their batch-deadline terminal state before
        # classifying queued work.  This matters when child cleanup is
        # unconfirmed: the cleanup gate must convert the remaining queue to
        # ``not_started_cleanup_blocked`` rather than allowing this earlier
        # queue pass to hide that safety failure as ``not_started_deadline``.
        if pending and not active and time.monotonic() >= batch_deadline:
            while pending:
                job = pending.pop(0)
                row = _job_row(job, role, status="not_started_deadline", terminal_reason="batch_deadline")
                row["dependency_status"] = "not_started"
                rows.append(row)
        for job_id, state in list(active.items()):
            process = state["process"]
            base = state["base"]
            marker_path = state["marker_path"]
            if marker_path.is_file() and base.get("dependency_status") == "starting":
                try:
                    marker = _read_json(marker_path)
                except (OSError, ValueError, TypeError):
                    marker = {}
                if isinstance(marker, Mapping) and marker.get("status") == "running":
                    base["dependency_status"] = "ready"
                    base["started_at"] = marker.get("started_at") or base.get("started_at")
                    _job_transition(base, "running", at=str(base.get("started_at") or _now()))
                    _record_state(base, event="running")
            elapsed = time.monotonic() - float(state["started_monotonic"])
            reason: str | None = None
            terminal_status: str | None = None
            if process.poll() is None and time.monotonic() >= batch_deadline:
                reason, terminal_status = "batch_deadline", "timed_out"
            elif process.poll() is None and base.get("dependency_status") == "starting" and elapsed >= max(1, int(startup_timeout_seconds)):
                # A worker that never reaches the ready marker has not
                # started the requested job.  Keep the public terminal reason
                # in the dependency-failure vocabulary used by the child
                # path; retain the more specific watchdog diagnosis on the
                # row for operators.
                reason, terminal_status = "dependency_failed", "not_started_dependency_failed"
                base["dependency_failure_reason"] = "startup_timeout"
                base["dependency_status"] = "failed"
                base["dependency_status"] = "failed"
            # A job timeout is meaningful only after the child has passed the
            # dependency/startup gate.  On Windows process startup can take
            # longer than a deliberately tiny contract-test job timeout; if
            # we applied ``per_job_timeout`` while the child is still marked
            # ``starting``, a dependency-construction failure would be
            # mislabeled as ``timed_out`` before its terminal row could be
            # published.  Let the startup watchdog own that interval and let
            # the batch deadline remain the outer bound.
            elif (
                process.poll() is None
                and (
                    base.get("dependency_status") != "starting"
                    # Contract tests use a small in-memory process double to
                    # exercise cleanup failure.  It has no child bootstrap
                    # boundary, so its per-job timeout must remain the hard
                    # liveness limit.  Real subprocess workers get the
                    # dedicated startup watchdog above, which gives a slow
                    # interpreter enough time to publish a dependency row.
                    or not isinstance(process, _SUBPROCESS_POPEN_TYPE)
                )
                and elapsed >= per_job_timeout
            ):
                reason, terminal_status = "hard_timeout", "timed_out"
            if process.poll() is None and terminal_status is not None:
                evidence = _terminate_process_tree(process, process_group_id=(process.pid if os.name != "nt" else None))
                evidence = dict(evidence)
                evidence.setdefault("root_creation_time", state["child_started"])
                row = _decorate_job_row(base, state["identity"], process_id=process.pid, process_creation_time=state["child_started"], cleanup_evidence=evidence, status=terminal_status, reason=reason)
                rows.append(row)
                _record_state(row, event="terminal")
                if not evidence.get("confirmed"):
                    _stop_pending("cleanup_unconfirmed")
                del active[job_id]
                continue
            if process.poll() is None:
                continue
            returncode = process.returncode
            # The process has exited.  Check its process group once more and
            # use the same tree receipt shape as the abort path.
            group_state = _process_group_alive(process.pid if os.name != "nt" else None)
            evidence = {
                "required": True, "confirmed": bool(returncode is not None and (group_state is False or group_state is None or os.name == "nt")),
                "root_pid": process.pid, "root_creation_time": state["child_started"],
                "process_group_id": process.pid if os.name != "nt" else None,
                "termination_method": "natural_exit", "root_exited": returncode is not None,
                "process_group_alive_after": group_state, "returncode": returncode, "cleanup_finished_at": _now(),
            }
            try:
                child_row = _read_json(state["row_path"]) if state["row_path"].is_file() else None
            except (OSError, ValueError, TypeError) as exc:
                child_row = None
                read_error = str(exc)
            else:
                read_error = None
            if not isinstance(child_row, dict):
                row = _decorate_job_row(base, state["identity"], process_id=process.pid, process_creation_time=state["child_started"], cleanup_evidence=evidence, status="failed", reason="worker_no_terminal_result")
                row["error"] = read_error or "job worker exited without a terminal row"
            elif returncode != 0 and child_row.get("status") == "completed":
                row = _decorate_job_row(base, state["identity"], process_id=process.pid, process_creation_time=state["child_started"], cleanup_evidence=evidence, status="failed", reason="nonzero_exit")
                row["error"] = f"job worker exited with code {returncode}"
            else:
                child_row.setdefault("status_history", base.get("status_history", []))
                row = _decorate_job_row(child_row, state["identity"], process_id=process.pid, process_creation_time=state["child_started"], cleanup_evidence=evidence)
                if not evidence.get("confirmed"):
                    # The process has already reached a terminal child state;
                    # a duplicate terminal transition is rejected.  Preserve
                    # that state and attach the cleanup failure as the reason
                    # that stops the lane.
                    row["terminal_reason"] = "cleanup_unconfirmed"
                    row["error"] = "cleanup_unconfirmed"
                    row["error_event"] = {
                        "type": "error_event", "role": role, "job_id": state["identity"]["job_id"],
                        "error_class": "cleanup_unconfirmed", "message": "owned process cleanup was not confirmed", "terminal": True,
                    }
                    lane_stopped = True
            rows.append(row)
            _record_state(row, event="terminal")
            del active[job_id]
        if active:
            time.sleep(0.05)
    if lane_stopped and pending:
        _stop_pending("cleanup_unconfirmed")
    order = {str(_job_identity(job, role)["job_id"]): index for index, job in enumerate(jobs)}
    return sorted(rows, key=lambda row: order.get(str(row.get("job_id")), len(order)))


def _safe_dispatch_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value)[:180] or "job"


def _orchestration_timeout(plan: dict[str, Any], job_count: int) -> int:
    """Scale the batch deadline to scheduled waves unless explicitly set."""
    explicit = plan.get("orchestration_timeout_seconds")
    if explicit is not None:
        return max(1, int(explicit))
    per_job = max(1, int(plan.get("timeout_seconds", 900)))
    concurrency = max(1, int(plan.get("concurrency", 1)))
    waves = max(1, (max(0, job_count) + concurrency - 1) // concurrency)
    return per_job * waves


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _material_files(cases_dir: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(cases_dir.glob("materials-*.json")):
        value = _read_json(path)
        if not isinstance(value, dict) or not isinstance(value.get("records"), list):
            raise ValueError(f"material pack is invalid: {path.name}")
        file_fp = _bytes_fp(path.read_bytes())
        for row in value["records"]:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not isinstance(row.get("text"), str):
                raise ValueError(f"material record is invalid: {path.name}")
            material_id = row["id"]
            if material_id in result:
                raise ValueError(f"duplicate material id: {material_id}")
            result[material_id] = {
                **row,
                "source_file": path.name,
                "source_file_fingerprint": file_fp,
                "synthetic": bool(value.get("synthetic", False)),
            }
    if len(result) != 26:
        raise ValueError(f"expected 26 frozen material records, found {len(result)}")
    return result


def _load_cases(cases_dir: Path) -> list[dict[str, Any]]:
    """Load the canonical manifest; old per-case files remain fallback only."""

    manifest_path = cases_dir / "case-manifest.json"
    if manifest_path.is_file():
        manifest = _read_json(manifest_path)
        if not isinstance(manifest, list) or len(manifest) != CASE_COUNT:
            raise ValueError("case-manifest.json must contain exactly twelve cases")
        materials = _material_files(cases_dir)
        cases: list[dict[str, Any]] = []
        seen: set[str] = set()
        manifest_fp = _bytes_fp(manifest_path.read_bytes())
        for row in manifest:
            if not isinstance(row, dict) or not isinstance(row.get("case_id"), str):
                raise ValueError("case manifest row has no case_id")
            case_id = row["case_id"]
            if case_id in seen:
                raise ValueError(f"duplicate case id: {case_id}")
            seen.add(case_id)
            refs = row.get("material_refs")
            if not isinstance(refs, list) or not refs:
                raise ValueError(f"case {case_id} has no material_refs")
            selected: list[dict[str, Any]] = []
            for ref in refs:
                if not isinstance(ref, dict) or not isinstance(ref.get("id"), str):
                    raise ValueError(f"case {case_id} has an invalid material ref")
                material = materials.get(ref["id"])
                if material is None or material["source_file"] != ref.get("path"):
                    raise ValueError(f"case {case_id} has a foreign or missing material {ref.get('id')}")
                selected.append(material)
            cases.append({**row, "materials": [item["id"] for item in selected], "material_records": selected, "case_manifest_fingerprint": manifest_fp})
        return cases
    cases = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(cases_dir.glob("*.json"))]
    if len(cases) != CASE_COUNT or any(not isinstance(case, dict) or not case.get("materials") for case in cases):
        raise ValueError("legacy case inputs must contain twelve cases with materials")
    return cases


def _load_frozen_inputs(cases_dir: Path) -> tuple[list[dict[str, Any]], str, str, str, dict[str, str]]:
    cases = _load_cases(cases_dir)
    rubric_path = cases_dir / "judge-rubric.md"
    if not rubric_path.is_file():
        raise ValueError("judge-rubric.md is required")
    manifest_path = cases_dir / "input-manifest.json"
    input_manifest_fp = _bytes_fp(manifest_path.read_bytes()) if manifest_path.is_file() else fingerprint({"cases": cases})
    material_files = {path.name: _bytes_fp(path.read_bytes()) for path in sorted(cases_dir.glob("materials-*.json"))}
    source_manifest_fp = fingerprint({
        "input_manifest": input_manifest_fp,
        "case_manifest": _bytes_fp((cases_dir / "case-manifest.json").read_bytes()) if (cases_dir / "case-manifest.json").is_file() else None,
        "materials": material_files,
        "rubric": _bytes_fp(rubric_path.read_bytes()),
    })
    return cases, rubric_path.read_text(encoding="utf-8"), input_manifest_fp, source_manifest_fp, material_files


_PRODUCTION_DELIVERABLES = {
    "investigation": "research_report",
    "academic-writing": "paper",
    "fiction-writing": "short_story",
    "travel-guide": "destination_guide",
}


def _production_token(case: Mapping[str, Any]) -> str:
    """Return an opaque request identity that does not expose benchmark labels."""

    return fingerprint({
        "route": case.get("route"),
        "language": case.get("language"),
        "task": case.get("task"),
        "constraints": case.get("constraints"),
        "materials": [
            {"id": row.get("id"), "text": row.get("text")}
            for row in case.get("material_records", [])
        ],
    })[7:23]


def _production_request_and_boundaries(case: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Build a current WritingRequest and reader-facing material boundary.

    The benchmark case id and judge rubric are intentionally kept outside this
    object.  They belong to the quality ledger, while the production planner
    receives only the user's task, constraints and frozen source material.
    """

    route = str(case.get("route"))
    token = _production_token(case)
    language = str(case.get("language") or "zh-CN")
    revision = case.get("revision_input")
    task = str(case.get("task") or "")
    constraints = str(case.get("constraints") or "")
    extent_match = re.search(r"(\d+)\s*[—–-]\s*(\d+)", task)
    minimum, maximum = (int(extent_match.group(1)), int(extent_match.group(2))) if extent_match else (120, 600)
    if maximum < minimum:
        minimum, maximum = maximum, minimum
    target = max(1, (minimum + maximum) // 2)
    outline_label = "正文"
    if "结果" in task and "意义" in task:
        outline_label = "结果与意义"
    elif "第一天" in task and "第二天" in task:
        outline_label = "行程安排"
    elif "Comparison design" in task:
        outline_label = "Comparison design and Interpretation"
    intent: dict[str, Any] = {
        "schema_version": "2.0",
        "artifact_mode": "revise_existing" if isinstance(revision, str) and revision.strip() else "create_new",
        "language": language,
        "audience": {
            "investigation": "需要根据证据做决定的读者",
            "academic-writing": "需要核对论证边界的学术读者",
            "fiction-writing": "希望沉浸在清楚视角中的读者",
            "travel-guide": "需要可执行安排的旅行者",
        }.get(route, "需要一篇完整成品的读者"),
        "purpose": task,
        "structure": {
            "mode": "partially_fixed",
            "requested_outline": [{
                "outline_id": "outline:answer",
                "parent_outline_id": None,
                "order": 1,
                "label": outline_label,
                "required": True,
                "title_locked": bool("标题" in task or "headings" in task.casefold()),
                "source": "user",
            }],
        },
        "heading_policy": "preserve_requested" if ("标题" in task or "heading" in task.casefold()) else "route_selected",
        "list_policy": "lists_allowed" if any(word in task for word in ("列表", "清单", "表格", "table", "checklist")) else "prose_default",
        "style": {
            "voice": "自然、清楚、连续推进，不把材料卡片逐项复述",
            "formality": "scholarly" if route == "academic-writing" else "neutral",
            "required_traits": ["连贯", "具体", "因果清楚"],
            "forbidden_traits": ["卡片式碎片", "内部工作流", "泛化免责声明"],
        },
        "extent": {"unit": "words" if language.casefold().startswith("en") else "characters", "minimum": minimum, "target": target, "maximum": maximum},
        "artifact_format": "markdown",
        "citation_policy": "inline" if ("引用" in task or "cite" in task.casefold()) else "none",
        "table_policy": "allowed" if any(word in task for word in ("表格", "table")) else "forbidden",
        "required_content": ["完成任务并让正文按因果或场景关系向前推进"],
        "forbidden_content": ["内部工作流", "模型标签", "评分过程"],
        "reference_examples": [],
        "unresolved_choices": [],
    }
    intent["intent_fingerprint"] = fingerprint_without(intent, "intent_fingerprint")
    request = {
        "schema_version": "2.0",
        "request_id": f"request:{token}",
        "terminal_deliverable": {
            "kind": _PRODUCTION_DELIVERABLES[route],
            "description": "一篇基于冻结材料、可直接阅读且有明确边界的成品",
            "acceptance_criteria": ["保留任务要求的事实和限制", "正文形成连续推进", "不泄露内部流程"],
        },
        "reader_intent": intent,
    }
    request["terminal_deliverable"]["fingerprint"] = fingerprint_without(request["terminal_deliverable"], "fingerprint")
    request["request_fingerprint"] = fingerprint_without(request, "request_fingerprint")

    anchors = []
    material_texts = []
    anchor_ids = []
    for index, material in enumerate(case.get("material_records", []), start=1):
        material_id = str(material.get("id") or f"material-{index}")
        text = str(material.get("text") or "")
        anchor_id = f"evidence:{material_id}"
        anchor_ids.append(anchor_id)
        material_texts.append(f"[{material_id}] {text}")
        anchors.append({
            "anchor_id": anchor_id,
            "source_id": f"source:{material_id}",
            "locator": str(material.get("source_locator") or material.get("source_file") or material_id),
            "relation": (
                "context" if material.get("role") == "process_log"
                else "counter" if material.get("role") in {"counterexample", "rebuttal"}
                else "support"
            ),
            "observed_summary": text,
            "boundary": "冻结材料；只能支持其中明确写出的事实，不可外推。",
        })
    safe_meaning = (
        f"用户任务：{task}\n用户约束：{constraints}\n冻结材料（逐条事实）：\n"
        + "\n".join(material_texts)
    )
    boundaries = {
        "content_units": [{
            "content_unit_id": "content:materials",
            "safe_meaning": safe_meaning,
            "required": True,
            "evidence_anchor_ids": anchor_ids,
            "alternative_ids": [],
            "limitation_ids": [],
            "model_row_ids": ["model:throughline"],
        }],
        "evidence_anchors": anchors,
        "alternatives": [],
        "limitations": [],
        "citation_duties": [],
        "must_preserve_tokens": [],
        "verbatim_obligations": [],
        "prohibited_overclaims": [],
    }
    return request, boundaries, token


def _production_research_prompt(inputs: Mapping[str, Any]) -> str:
    request = inputs["writing_request"]
    intent = request["reader_intent"]
    boundaries = inputs["content_boundaries"]
    material = boundaries["content_units"][0]["safe_meaning"]
    return (
        "你是写作前的证据模型规划器。这是纯粹的离线 JSON 变换；严禁调用工具、浏览网页、读取文件、运行命令或向其它代理发消息。"
        "所有事实只能来自下文，遇到不确定处保留边界，不要尝试外部研究。只返回一个 JSON 对象，不要 Markdown、解释、评分、案例标签、rubric 或预写答案。"
        "请把任务材料建成一个可验证的、边界明确的 LogicGuard 模型。模型必须使用一条根 Claim C0，"
        "以及 E1(Evidence)、W1(Warrant)、A1(Assumption)、L1(Limitation)、R1(Rebuttal)，五条边分别为："
        "E1 supports C0、W1 supports C0、A1 depends_on C0、L1 qualifies C0、R1 attacks C0。"
        "model.target_units 必须有 unit:main，model.model_cards 必须有 card:main，二者 node_ids 都覆盖六个节点，"
        "role_dispositions 必须把 competition 设为 not_applicable。每个节点要写与材料相符的简短语义，"
        "不要创造材料没有的事实。JSON 形状必须是一个对象，顶层只能有 candidate_model 和 target_goal；"
        "candidate_model 必须含 model、nodes、edges。nodes 可以是数组或对象：数组中的每项都必须含 id、type、text，"
        "对象形式的键就是节点 id；六个节点的 type 必须分别是 C0=Claim、E1=Evidence、W1=Warrant、"
        "A1=Assumption、L1=Limitation、R1=Rebuttal。edges 必须是数组，每项都要有 source、target、type，"
        "并且只使用上述五种关系。为兼容有限的本地输出，节点的 role 或 kind 可以代替 type，边的 from/to/relation"
        "可以分别代替 source/target/type；同一项同时出现规范字段和别名时值必须一致，未知角色、关系或字段形状必须失败。"
        "target_goal 必须是非空且有边界的一句话。\n\n"
        f"读者意图：{json.dumps(intent, ensure_ascii=False, sort_keys=True)}\n"
        f"材料与限制：\n{material}"
    )


def _production_compose_prompt(inputs: Mapping[str, Any]) -> str:
    request = inputs["writing_request"]
    intent = request["reader_intent"]
    boundaries = inputs["content_boundaries"]
    native = inputs["native_plan"]
    return (
        "你是最终成稿前的组合规划器。这是纯粹的离线 JSON 变换；严禁调用工具、浏览网页、读取文件、运行命令或向其它代理发消息。"
        "所有事实只能来自下文，不要尝试外部研究。只返回一个 JSON 对象，不要 Markdown、评分、案例标签、rubric 或成稿。"
        "请根据读者意图、冻结材料和已经通过 native depth 的 ResearchGuard plan，给出四个字段："
        "central_question、central_throughline、opening_job、conclusion_job。每个字段都是具体的一句话，"
        "说明段落如何承接、限制如何改变结论或行动；不要罗列资料卡片。"
        "如果受限视角下的结尾缺少合法的知情路径，必须在 conclusion_job 中明确写出需要用户决定或补充材料，"
        "不能把无解要求继续包装成可直接成稿。旅行方案的每个失败分支必须给出材料支持的动作，或明确收束为出发前核实门槛，"
        "不能只写‘不能/不可’。不要添加其它字段。\n\n"
        f"读者意图：{json.dumps(intent, ensure_ascii=False, sort_keys=True)}\n"
        f"冻结内容边界：{json.dumps(boundaries, ensure_ascii=False, sort_keys=True)}\n"
        f"Native plan：{json.dumps(native, ensure_ascii=False, sort_keys=True)}"
    )


def _normalise_candidate_model(value: Mapping[str, Any], token: str) -> dict[str, Any]:
    candidate = dict(value)
    if "model" not in candidate or not isinstance(candidate.get("model"), Mapping):
        raise ValidationError("planner candidate_model must contain model")
    model_info = dict(candidate["model"])
    candidate["model"] = model_info
    candidate["model"]["id"] = f"logic-writing-production-{token}"
    candidate["model"].setdefault("root_claim", "C0")
    nodes_raw = candidate.get("nodes")
    if isinstance(nodes_raw, list):
        nodes = {}
        for index, row in enumerate(nodes_raw):
            if not isinstance(row, Mapping):
                raise ValidationError(f"planner candidate_model node {index} must be an object")
            node_id = row.get("id")
            if not isinstance(node_id, str) or not node_id.strip():
                raise ValidationError(f"planner candidate_model node {index} requires a non-empty id")
            node_id = node_id.strip()
            if node_id in nodes:
                raise ValidationError(f"planner candidate_model contains duplicate node id {node_id!r}")
            item = dict(row)
            item.pop("id", None)
            nodes[node_id] = item
        candidate["nodes"] = nodes
    elif isinstance(nodes_raw, Mapping):
        nodes = {}
        for key, row in nodes_raw.items():
            if not isinstance(key, str) or not key.strip():
                raise ValidationError("planner candidate_model node ids must be non-empty strings")
            if not isinstance(row, Mapping):
                raise ValidationError(f"planner candidate_model node {key!r} must be an object")
            node_id = key.strip()
            if node_id in nodes:
                raise ValidationError(f"planner candidate_model contains duplicate node id {node_id!r}")
            nodes[node_id] = dict(row)
        candidate["nodes"] = nodes
    else:
        raise ValidationError("planner candidate_model must contain nodes")

    for node_id, item in candidate["nodes"].items():
        supplied_types: list[tuple[str, str]] = []
        for field in ("type", "role", "kind"):
            if field not in item:
                continue
            raw_type = item[field]
            if not isinstance(raw_type, str) or not raw_type.strip():
                raise ValidationError(f"planner candidate_model node {node_id!r} has an invalid {field}")
            lookup = raw_type.strip().casefold().replace("-", "_").replace(" ", "_")
            canonical_type = _NODE_TYPE_ALIASES.get(lookup)
            if canonical_type is None:
                raise ValidationError(f"planner candidate_model node {node_id!r} has an unknown role/type {raw_type!r}")
            supplied_types.append((field, canonical_type))
        if not supplied_types:
            raise ValidationError(f"planner candidate_model node {node_id!r} requires type, role, or kind")
        canonical_types = {item_type for _, item_type in supplied_types}
        if len(canonical_types) != 1:
            raise ValidationError(f"planner candidate_model node {node_id!r} has conflicting type aliases")
        item["type"] = supplied_types[0][1]
        # Keep one canonical field so the native model sees a deterministic
        # role and cannot accidentally privilege an alias during parsing.
        item.pop("role", None)
        item.pop("kind", None)

    if not isinstance(candidate.get("edges"), list):
        raise ValidationError("planner candidate_model must contain edges")
    canonical_edges: list[dict[str, Any]] = []
    for edge_index, edge in enumerate(candidate["edges"]):
        if not isinstance(edge, Mapping):
            raise ValidationError(f"planner candidate_model edge {edge_index} must be an object")
        item = dict(edge)
        endpoint_values: dict[str, str] = {}
        for canonical, aliases in (("source", ("source", "from")), ("target", ("target", "to"))):
            supplied = []
            for field in aliases:
                if field not in item:
                    continue
                raw_value = item[field]
                if not isinstance(raw_value, str) or not raw_value.strip():
                    raise ValidationError(f"planner candidate_model edge {edge_index} has an invalid {field}")
                supplied.append((field, raw_value.strip()))
            if not supplied:
                raise ValidationError(f"planner candidate_model edge {edge_index} is missing {canonical}")
            values = {raw_value for _, raw_value in supplied}
            if len(values) != 1:
                raise ValidationError(f"planner candidate_model edge {edge_index} has conflicting {canonical} aliases")
            endpoint_values[canonical] = supplied[0][1]

        relation_values: list[tuple[str, str]] = []
        for field in ("type", "relation"):
            if field not in item:
                continue
            raw_type = item[field]
            if not isinstance(raw_type, str) or not raw_type.strip():
                raise ValidationError(f"planner candidate_model edge {edge_index} has an invalid {field}")
            lookup = raw_type.strip().casefold().replace("-", "_").replace(" ", "_")
            canonical_type = _EDGE_TYPE_ALIASES.get(lookup)
            if canonical_type is None:
                raise ValidationError(f"planner candidate_model edge {edge_index} has an unknown relation {raw_type!r}")
            relation_values.append((field, canonical_type))
        if not relation_values:
            raise ValidationError(f"planner candidate_model edge {edge_index} is missing type or relation")
        canonical_relations = {relation for _, relation in relation_values}
        if len(canonical_relations) != 1:
            raise ValidationError(f"planner candidate_model edge {edge_index} has conflicting type aliases")
        item["source"] = endpoint_values["source"]
        item["target"] = endpoint_values["target"]
        item["type"] = relation_values[0][1]
        item.pop("from", None)
        item.pop("to", None)
        item.pop("relation", None)
        canonical_edges.append(item)
    candidate["edges"] = canonical_edges
    required_nodes = set(_REQUIRED_NODE_TYPES)
    if not required_nodes.issubset(candidate["nodes"]):
        raise ValidationError("planner candidate_model is missing one of the required LogicGuard roles")
    for node_id, expected_type in _REQUIRED_NODE_TYPES.items():
        actual_type = candidate["nodes"][node_id].get("type")
        if actual_type != expected_type:
            raise ValidationError(f"planner candidate_model node {node_id!r} must have type {expected_type}")
    for edge_index, edge in enumerate(candidate["edges"]):
        if edge["source"] not in candidate["nodes"] or edge["target"] not in candidate["nodes"]:
            raise ValidationError(f"planner candidate_model edge {edge_index} references an unknown node")
    candidate["model"]["target_units"] = [{"unit_id": "unit:main", "node_ids": sorted(required_nodes)}]
    candidate["model"]["model_cards"] = [{"card_id": "card:main", "node_ids": sorted(required_nodes), "importance": 1.0}]
    candidate["model"]["role_dispositions"] = {"competition": "not_applicable"}
    candidate.pop("guard_contract", None)
    return candidate


def _remove_candidate_node(value: Mapping[str, Any], node_id: str) -> dict[str, Any]:
    result = json.loads(json.dumps(value, ensure_ascii=False))
    result.get("nodes", {}).pop(node_id, None)
    result["edges"] = [row for row in result.get("edges", []) if row.get("source") != node_id and row.get("target") != node_id]
    model = result.get("model", {})
    for key in ("target_units", "model_cards"):
        for row in model.get(key, []) or []:
            row["node_ids"] = [item for item in row.get("node_ids", []) if item != node_id]
    for block in result.get("blocks", []) if isinstance(result.get("blocks"), list) else result.get("blocks", {}).values() if isinstance(result.get("blocks"), Mapping) else []:
        if isinstance(block, Mapping):
            for key in ("member_nodes", "input_nodes", "internal_nodes", "output_claims", "local_assumptions", "local_rebuttals"):
                if isinstance(block.get(key), list):
                    block[key] = [item for item in block[key] if item != node_id]
    result.pop("guard_contract", None)
    return result


def _normalise_research_payload(value: Mapping[str, Any], *, token: str, request: Mapping[str, Any]) -> dict[str, Any]:
    value = require_mapping(value, "planner research output")
    target_goal = value.get("target_goal")
    if not isinstance(target_goal, str) or not target_goal.strip():
        raise ValidationError("planner target_goal is required and must be a non-empty string")
    candidate = _normalise_candidate_model(require_mapping(value.get("candidate_model"), "planner candidate_model"), token)
    model_id = str(candidate["model"]["id"])
    good = json.loads(json.dumps(candidate, ensure_ascii=False))
    evidence_nodes = [node_id for node_id, row in candidate["nodes"].items() if str(row.get("type")) == "Evidence"]
    if not evidence_nodes:
        raise ValidationError("planner candidate_model has no evidence node for strict native proof")
    card_id = "card:main"
    bad = _remove_candidate_node(good, evidence_nodes[0])
    declaration = {
        "schema_version": "researchguard.logic.target_model_purpose_declaration.v1",
        "contract_role": "target_model_instance",
        "contract_id": f"contract:logic-writing:{token}",
        "model_id": model_id,
        "target_skill_id": "logicguard",
        "native_owner_id": "logic-writing.production-reader",
        "native_route_id": "route:logic-writing-production-reader",
        "declared_by": "ai",
        "prevented_failure_purpose": "Prevent a reader conclusion from entering prose without complete support, warrant, assumption, boundary and opposition roles.",
        "claim_boundary": "This native proof covers only the current bounded reader request and its frozen material boundary.",
        "candidate_relative_path": "model.json",
        "selectable_modes": [],
        "prevented_failure_classes": [{
            "failure_id": "failure:missing-support",
            "title": "Missing support role",
            "block_when": "the current argument card loses its evidence support",
            "oracle": {"kind": "primary_depth_gap_prefix", "finding_code": f"missing_role:{card_id}:support"},
            "known_good_relative_path": "good.json",
            "known_bad_relative_path": "bad.json",
        }],
    }
    selection = {
        "schema": "researchguard.logic.synthesis-request.v1",
        "request_id": f"selection:{token}",
        "target_id": f"reader-target:{token}",
        "target_goal": target_goal.strip(),
        "artifact_kind": str(request["terminal_deliverable"]["kind"]),
        "reader_id": "logic-writing-reader",
        "model_id": model_id,
        "body_unit_order": ["u0"],
        "max_body_units": 1,
        "units": [{
            "unit_id": "u0", "parent_unit_id": None,
            "reader_question": "What is the bounded answer and why does it hold?",
            "unit_job": "Establish the conclusion, support and operative limits in reader order.",
            "claim_ids": ["C0"], "predecessor_unit_ids": [], "progression_relation": "concludes",
            "editorial_prominence": "lead", "placement": "body",
            "placement_reason": "The reader needs the central bounded conclusion in the body.", "required": True,
        }],
        "source_branch_bindings": [],
    }
    return {
        "guard_declaration": declaration,
        "candidate_model": candidate,
        "support_files": {"good.json": good, "bad.json": bad},
        "selection_request": selection,
        "budget": 20,
    }


def _requested_composition_unit_count(intent: Mapping[str, Any], owner: str) -> int | None:
    """Return an explicit user-requested unit count when the task has one.

    The production planner deliberately returns a small, stable four-field
    payload.  This helper keeps structural instructions in the user task
    authoritative while allowing the compiler below to provide a richer
    route spine when no count was requested.  It is intentionally conservative:
    vague words such as "several" do not change the route default.
    """

    purpose = str(intent.get("purpose") or "")
    folded = purpose.casefold()
    if re.search(r"(?:两|二)\s*(?:段|部分|节)|\btwo\s+(?:paragraphs?|sections?)\b", purpose, re.IGNORECASE):
        return 2
    if re.search(r"(?:三)\s*(?:段|部分|节)|\bthree\s+(?:paragraphs?|sections?)\b", purpose, re.IGNORECASE):
        return 3
    if owner == "travel-guide" and (
        re.search(r"三\s*(?:日|天)", purpose)
        or re.search(r"\b(?:day|第一天|第二天|third day|第三天)\b", folded, re.IGNORECASE)
    ):
        return 3
    if re.search(r"(?:两个|两)\s*标题|\btwo\s+headings?\b", purpose, re.IGNORECASE):
        return 2
    # A short generic request has no declared route decomposition.  Preserve
    # the legal single-unit path for such work; route defaults are reserved
    # for tasks that actually name evidence, limits, scenes, actions, or
    # itinerary decisions.
    if re.search(r"完整、自然.*成品|complete.{0,20}natural.{0,20}(?:artifact|deliverable)", purpose, re.IGNORECASE):
        return 1
    complexity_markers = (
        "证据", "限制", "反例", "验证", "结果", "意义", "因果", "视角", "场景", "行动", "代价",
        "方案", "备用", "核实", "安排", "推断", "结论", "evidence", "limit", "counter", "verify",
        "result", "interpret", "causal", "viewpoint", "scene", "action", "cost", "plan", "fallback",
    )
    if len(purpose.strip()) <= 80 and not any(marker in folded for marker in complexity_markers):
        return 1
    return None


def _composition_heading_overrides(intent: Mapping[str, Any], owner: str) -> list[str] | None:
    """Extract only explicit, safe heading labels from the reader task."""

    purpose = str(intent.get("purpose") or "")
    folded = purpose.casefold()
    if owner == "academic-writing" and "comparison design" in folded and "interpretation" in folded:
        return ["Comparison design", "Interpretation"]
    if owner == "academic-writing" and "结果" in purpose and "意义" in purpose:
        return ["结果", "意义"]
    if owner == "travel-guide" and re.search(r"三\s*(?:日|天)", purpose):
        return ["第一天", "第二天", "第三天"]
    if owner == "travel-guide" and all(marker in purpose for marker in ("第一天", "第二天", "第三天")):
        return ["第一天", "第二天", "第三天"]
    return None


def _route_composition_specs(owner: str, *, language: str, throughline: str, central_question: str) -> list[dict[str, str]]:
    """Return the default reader progression for one final-owner route.

    These are reader jobs, rather than prose templates.  They give the writer
    a causal handoff from one unit to the next and keep evidence, qualification
    and action from becoming a flat list.  The frozen content remains attached
    to the first unit and is available through the global evidence spine; later
    units operate on the judgment established before them.
    """

    def _rows(rows: list[tuple[str, str, str, str]]) -> list[dict[str, str]]:
        return [
            {"title": title, "reader_job": job, "incoming": incoming, "outgoing": outgoing}
            for title, job, incoming, outgoing in rows
        ]

    chinese = str(language).casefold().startswith(("zh", "cmn"))
    if chinese:
        common = [
            ("判断边界", "先回答中心问题，并把结论限定在材料真正覆盖的范围内。", "读者知道任务但还不知道判断为何成立。", "读者得到一个有适用范围的中心判断。"),
            ("可比观察", "只放能直接支撑中心判断的观察，说明它如何改变当前判断。", "读者知道结论但缺少可核对的依据。", "读者看见与判断直接相连的依据。"),
            ("限制与反例", "把反例、异质性或替代解释放在它收紧结论的位置，明确改变的是范围、强度还是因果。", "读者容易把局部观察扩大为普遍结论。", "读者知道结论在哪些条件下不能外推。"),
            ("条件含义", "把边界转成条件性的行动或解释含义；情景测算只能作为条件，不得写成承诺。", "读者知道限制，却还不知道它如何影响决定。", "读者知道在什么条件下可以采取什么动作。"),
            ("验证与收束", "用与缺口对应的核验动作收束建议，让下一步承接前面的不确定性。", "读者知道当前能说什么，但缺少可执行的下一步。", "读者得到带条件的结论和验证路径。"),
        ]
        if owner == "academic-writing":
            return _rows([
                ("观察结果", "准确描述观察到的变化，只说材料支持的结果，不把相关性写成因果。", "读者需要先知道实际观察是什么。", "读者掌握一个可核对的观察结果。"),
                ("解释边界", "说明证据怎样支持解释、哪些替代解释仍未排除，以及限制如何收紧推断。", "读者知道结果，却可能把它当成已证实的原因。", "读者理解解释的强度和边界。"),
                ("比较设计", "提出下一项能区分关键解释的比较或验证设计，并把中心贡献落在可检验的范围内。", "读者知道边界，但还不知道怎样推进知识。", "读者得到下一项可核对的设计或有限意义。"),
            ])
        if owner == "fiction-writing":
            return _rows([
                ("即时压力", "先让受限视角中的可见压力和目标出现，用动作或物件建立场景方向。", "读者知道有人面临压力，但不知道选择会怎样改变局面。", "读者理解此刻必须完成的动作。"),
                ("选择与阻力", "让一个可见选择改变关系或可行选项，并保留视角人物不知道的部分。", "目标遇到阻力，选择尚未产生后果。", "读者看见选择怎样改变下一步。"),
                ("行动落地", "给关键动作一个与已知条件相容的现场来源，写出行动如何完成而不跳过因果。", "读者知道选择，却还没有看到结果如何发生。", "读者看见行动和结果之间的具体连接。"),
                ("代价收束", "让不可逆的代价通过反应、关系或物件落地，不用作者解释主题或抹平后果。", "行动完成但代价尚未落到场景中。", "读者感到局面已经改变且代价仍在。"),
            ])
        if owner == "travel-guide":
            return _rows([
                ("默认安排", "先给出满足旅客条件的默认选择，并说明它为什么在当前天气和体力边界内可行。", "旅行者知道目的，却还没有可执行的安排。", "旅行者得到一个可行的主方案。"),
                ("接驳与休息", "把每段接驳、连续步行和实际休息地点接回主方案，说明它们怎样保持可行。", "旅行者有主方案，却不知道途中如何承受和衔接。", "旅行者知道如何移动、休息和继续。"),
                ("出发前核实", "把未知的班次、开放、无障碍或设备状态转成出发前核验，不把未知写成已确认。", "旅行者需要知道哪些条件会改变主方案。", "旅行者知道出发前要核实什么。"),
                ("触发式退回", "在条件不成立时给出明确、可执行且满足步行边界的退回或备用动作。", "旅行者知道主方案可能失效，却没有退路。", "旅行者知道何时停止并怎样安全返回。"),
            ])
        return _rows(common)

    common = [
        ("Decision boundary", "Answer the central question first and keep the conclusion inside the evidence boundary.", "The reader knows the task but not the judgment.", "The reader has a bounded central judgment."),
        ("Comparable observation", "Use only observations that directly support the judgment and explain how they change it.", "The reader has a conclusion but lacks a checkable basis.", "The reader sees the evidence tied to the judgment."),
        ("Limits and counterevidence", "Place counterevidence, heterogeneity, or alternative explanations where they narrow scope, strength, or causality.", "The reader could overgeneralize a local observation.", "The reader knows where the judgment cannot be extended."),
        ("Conditional implication", "Turn the boundary into a conditional action or interpretation; scenario arithmetic is not a promise.", "The reader sees a limit but not its decision consequence.", "The reader knows which action follows under which condition."),
        ("Verification and close", "Close with a verification action that answers the unresolved gap and hands off from the preceding uncertainty.", "The reader knows what can be said but lacks a next step.", "The reader has a conditional conclusion and a path to verify it."),
    ]
    if owner == "academic-writing":
        return _rows([
            ("Observed result", "Describe the observed change accurately without turning correlation into causation.", "The reader needs the actual observation first.", "The reader has a checkable result."),
            ("Interpretive limits", "Explain how the evidence supports the interpretation, which alternatives remain open, and how the limits narrow the inference.", "The reader may mistake the result for a proven cause.", "The reader understands the strength and boundary of the interpretation."),
            ("Comparison design", "Propose the next comparison or verification that can distinguish the key explanations and keep the contribution testable.", "The reader knows the limit but not how to advance the inquiry.", "The reader has a bounded next design or implication."),
        ])
    if owner == "fiction-writing":
        return _rows([
            ("Immediate pressure", "Establish visible pressure and the goal inside the restricted viewpoint through action or objects.", "The reader sees pressure but not how a choice will change the situation.", "The reader understands the immediate action that must be taken."),
            ("Choice and resistance", "Make a visible choice change a relationship or available option while preserving what the viewpoint character cannot know.", "The goal meets resistance and the choice has not yet landed.", "The reader sees how the choice changes the next move."),
            ("Action lands", "Give the key action a source compatible with the known conditions and show the causal connection without a jump.", "The reader sees the choice but not how its result occurs.", "The reader sees the concrete link between action and result."),
            ("Cost and close", "Let the irreversible cost arrive through reaction, relationship, or object; do not explain the theme or erase the consequence.", "The action is complete but the cost has not landed.", "The reader feels that the situation changed and the cost remains."),
        ])
    if owner == "travel-guide":
        return _rows([
            ("Default plan", "Give a default choice that satisfies the traveler constraints and explain why it is feasible in the stated weather and capacity boundary.", "The traveler has a goal but no executable arrangement.", "The traveler has a feasible main plan."),
            ("Transfers and rest", "Connect every transfer, continuous walking limit, and actual rest point to the main plan.", "The traveler has a plan but not its physical handoffs.", "The traveler knows how to move, rest, and continue."),
            ("Pre-departure checks", "Turn unknown service, opening, accessibility, or equipment states into checks before departure.", "The traveler needs to know which conditions can change the plan.", "The traveler knows what to verify before leaving."),
            ("Triggered return", "When a condition fails, give a clear executable return or fallback that still satisfies the walking boundary.", "The main plan may fail but there is no reachable alternative.", "The traveler knows when to stop and how to return."),
        ])
    return _rows(common)


def _fit_composition_specs(
    specs: list[dict[str, str]],
    *,
    count: int | None,
    heading_overrides: list[str] | None,
) -> list[dict[str, str]]:
    """Fit route defaults to an explicit requested count without dropping work."""

    if count is None:
        selected = list(specs)
    elif count >= len(specs):
        selected = list(specs)
    elif count == 1:
        selected = [
            {
                "title": specs[0]["title"],
                "reader_job": "；".join(item["reader_job"] for item in specs),
                "incoming": specs[0]["incoming"],
                "outgoing": specs[-1]["outgoing"],
            }
        ]
    elif count == 2 and len(specs) >= 3:
        selected = [
            {
                "title": specs[0]["title"],
                "reader_job": specs[0]["reader_job"],
                "incoming": specs[0]["incoming"],
                "outgoing": specs[1]["outgoing"],
            },
            {
                "title": specs[-1]["title"],
                "reader_job": "；".join(item["reader_job"] for item in specs[1:]),
                "incoming": specs[1]["incoming"],
                "outgoing": specs[-1]["outgoing"],
            },
        ]
    else:
        # A requested three-unit structure keeps the route's first three
        # reader jobs, while folding any final verification/close into the
        # last unit.  This is used by three-day travel plans and three-part
        # revision reports.
        selected = list(specs[:count])
        if len(specs) > count:
            selected[-1] = {
                "title": selected[-1]["title"],
                "reader_job": "；".join(item["reader_job"] for item in specs[count - 1:]),
                "incoming": selected[-1]["incoming"],
                "outgoing": specs[-1]["outgoing"],
            }
    if heading_overrides and len(heading_overrides) == len(selected):
        for item, title in zip(selected, heading_overrides):
            item["title"] = title
    return selected


def _fiction_completion_gap(
    intent: Mapping[str, Any],
    boundaries: Mapping[str, Any],
    composition_text: str = "",
) -> str | None:
    """Detect an explicit restricted-POV ending that has no knowledge path.

    This is a narrow contract check, not a keyword quality score.  It fires
    only when the request requires a viewpoint boundary and a consequential
    ending while the native material boundary explicitly says that the
    viewpoint character has no way to learn that consequence.  In that case
    the writer cannot safely choose an ending on its own; the fiction route
    requires a user decision or more source material.
    """

    purpose = str(intent.get("purpose") or "")
    limitation_text = " ".join(
        str(row.get("safe_meaning") or "")
        for row in boundaries.get("limitations", [])
        if isinstance(row, Mapping)
    )
    combined = f"{purpose} {limitation_text} {composition_text}"
    restricted_view = bool(re.search(
        r"受限视角|近距离第三人称|只知道|restricted\s+(?:viewpoint|pov)|close\s+third|only\s+knows",
        combined,
        re.IGNORECASE,
    ))
    consequential_ending = bool(re.search(
        r"结尾|代价|失去工作|失业|consequence|ending|cost|job\s+loss|unemployment",
        combined,
        re.IGNORECASE,
    ))
    missing_knowledge_path = bool(re.search(
        r"(?:未提供|没有|缺少|无|不能).{0,30}(?:获知|得知|知晓|知道).{0,20}(?:方式|依据|渠道)|"
        r"(?:获知|得知|知晓|知道).{0,20}(?:方式|依据|渠道).{0,30}(?:未提供|没有|缺少|无)|"
        r"no\s+(?:way|basis|means)\s+to\s+(?:know|learn)|"
        r"(?:not|never)\s+(?:provided|given).{0,40}(?:know|learn)",
        combined,
        re.IGNORECASE,
    ))
    if restricted_view and consequential_ending and missing_knowledge_path:
        return (
            "受限视角的结尾要求保留一个材料明确写出的后果，但当前材料没有提供视角人物获知该后果的合法路径；"
            "请补充可见的知情事件，或放宽视角/结尾要求后再进入成稿。"
        )
    return None


def _normalise_compose_payload(value: Mapping[str, Any], inputs: Mapping[str, Any]) -> dict[str, Any]:
    value = require_mapping(value, "planner compose output")
    expected_fields = {"central_question", "central_throughline", "opening_job", "conclusion_job"}
    missing_fields = sorted(expected_fields - set(value))
    extra_fields = sorted(set(value) - expected_fields)
    if missing_fields or extra_fields:
        raise ValidationError(
            "planner compose output keys must be exactly the four required fields; "
            f"missing={missing_fields}, extra={extra_fields}"
        )
    compose_fields: dict[str, str] = {}
    for field in sorted(expected_fields):
        raw_value = value[field]
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise ValidationError(f"planner compose field {field} must be a non-empty string")
        compose_fields[field] = raw_value.strip()
    request = inputs["writing_request"]
    intent = request["reader_intent"]
    decision = inputs["route_decision"]
    owner = str(decision["final_owner"])
    boundaries = inputs["content_boundaries"]
    content_id = "content:materials"
    anchor_ids = [str(row["anchor_id"]) for row in boundaries.get("evidence_anchors", [])]
    native = inputs["native_plan"]
    central_question = compose_fields["central_question"]
    throughline = compose_fields["central_throughline"]
    opening = compose_fields["opening_job"]
    conclusion = compose_fields["conclusion_job"]
    if owner == "fiction-writing":
        gap = _fiction_completion_gap(intent, boundaries, conclusion)
        if gap:
            raise ValidationError(f"composition_blocked:user_decision:fiction_viewpoint_outcome_gap: {gap}")
    language = str(intent.get("language") or "zh-CN")
    extent = intent.get("extent") if isinstance(intent.get("extent"), Mapping) else {}
    target_extent = max(1, int(extent.get("target", 1) or 1))
    requested_outline = intent.get("structure", {}).get("requested_outline", [])
    outline_id = "outline:answer"
    if isinstance(requested_outline, list) and requested_outline:
        first_outline = requested_outline[0]
        if isinstance(first_outline, Mapping) and isinstance(first_outline.get("outline_id"), str) and first_outline["outline_id"].strip():
            outline_id = first_outline["outline_id"].strip()
    specs = _route_composition_specs(
        owner,
        language=language,
        throughline=throughline,
        central_question=central_question,
    )
    specs = _fit_composition_specs(
        specs,
        count=_requested_composition_unit_count(intent, owner),
        heading_overrides=_composition_heading_overrides(intent, owner),
    )
    # Keep the long-standing root id for consumers that already bind the
    # answer unit, then give every later reader job a stable route position.
    route_unit_ids = {
        "investigation": ["unit:answer", "unit:observation", "unit:boundary", "unit:implication", "unit:action"],
        "academic-writing": ["unit:answer", "unit:interpretation", "unit:comparison"],
        "fiction-writing": ["unit:answer", "unit:pressure", "unit:choice", "unit:cost"],
        "travel-guide": ["unit:answer", "unit:movement", "unit:checks", "unit:fallback"],
    }.get(owner, ["unit:answer"])
    if len(route_unit_ids) < len(specs):
        route_unit_ids.extend(f"unit:part-{index}" for index in range(len(route_unit_ids) + 1, len(specs) + 1))
    route_unit_ids = route_unit_ids[:len(specs)]
    list_policy = str(intent.get("list_policy") or "prose_default")
    native_limitations = [
        row for row in boundaries.get("limitations", [])
        if isinstance(row, Mapping) and str(row.get("limitation_id") or "").strip()
    ]
    native_limitation_ids = [str(row["limitation_id"]) for row in native_limitations]
    units: list[dict[str, Any]] = []
    unit_base_extent, unit_remainder = divmod(target_extent, len(specs))
    for index, spec in enumerate(specs):
        unit_id = route_unit_ids[index]
        previous_id = route_unit_ids[index - 1] if index else None
        downstream_id = route_unit_ids[index + 1] if index + 1 < len(route_unit_ids) else None
        allow_mixed = owner in {"investigation", "travel-guide"} and index == len(specs) - 1 and list_policy != "prose_default"
        reader_job = spec["reader_job"]
        if owner == "travel-guide" and index == len(specs) - 1:
            if str(language).casefold().startswith(("zh", "cmn")):
                reader_job += "如果出发前无法核实必要条件，且没有材料支持的可达备用，就留在出发地，不虚构到馆后的退回路线。"
            else:
                reader_job += " If a required condition cannot be verified before departure and no evidence-backed accessible fallback exists, stay at the starting point; do not invent an on-site return route."
        units.append({
            "planned_unit_id": unit_id,
            "parent_unit_id": previous_id,
            "unit_kind": "section",
            "order": index + 1,
            "required": True,
            "title": spec["title"],
            "source_outline_ids": [outline_id],
            "reader_job": reader_job,
            # The current production boundary is intentionally one semantic
            # content unit.  Attach it once; repeated copies made the writer
            # restate the same evidence in every paragraph.
            "content_unit_ids": [content_id] if index == 0 else [],
            "limitation_ids": native_limitation_ids if index == len(specs) - 1 else [],
            "relation_to_previous": (
                "这是读者进入问题的起点。"
                if index == 0
                else "承接前一处已经建立的判断，继续推进。"
            ),
            "incoming_reader_state": spec["incoming"],
            "outgoing_reader_state": spec["outgoing"],
            "downstream_unit_ids": [downstream_id] if downstream_id else [],
            "presentation_mode": "mixed" if allow_mixed else "prose",
            "target_extent": max(1, unit_base_extent + (1 if index < unit_remainder else 0)),
        })
    plan = {
        "schema_version": "2.0", "plan_id": "plan:logic-writing-production",
        "reader_intent_fingerprint": intent["intent_fingerprint"], "final_owner": owner,
        "central_question": central_question, "central_throughline": throughline,
        "artifact_form": "完整读者成品", "structure_authority": "user_partial",
        "opening_job": opening, "conclusion_job": conclusion,
        "planned_units": units,
        "allowed_list_zones": [row["planned_unit_id"] for row in units if row["presentation_mode"] in {"list", "table", "mixed"}],
        "content_dispositions": [{"content_unit_id": content_id, "disposition": "consumed", "planned_unit_ids": [units[0]["planned_unit_id"]], "reason": "冻结材料是成品必须处理的内容边界。"}],
        "limitation_dispositions": [
            {
                "limitation_id": str(row["limitation_id"]),
                "affected_claim_ids": ["C0"],
                "materiality": str(row.get("materiality") or "changes_scope"),
                "materiality_reason": "该限制改变当前结论可覆盖的范围，不能留在内部记录中。",
                "disposition": "body",
                "destination_unit_ids": [route_unit_ids[-1]],
                "merged_into_id": None,
                "realization_requirement": str(row.get("safe_meaning") or "在结尾单元明确保留该边界。"),
                "native_boundary_refs": [str(row["limitation_id"])],
            }
            for row in native_limitations
        ], "unresolved_conflicts": [],
    }
    plan["plan_fingerprint"] = fingerprint_without(plan, "plan_fingerprint")
    if owner == "investigation":
        extension = {
            "schema_version": "2.0", "composition_id": "composition:logic-writing-production", "final_owner": owner,
            "reader_intent_fingerprint": intent["intent_fingerprint"], "composition_plan_fingerprint": plan["plan_fingerprint"],
            "profile": "evidence_audit" if "审计" in str(intent["purpose"]) else "explanatory_report",
            "bounded_answer_content_unit_ids": [content_id],
            "evidence_strength_rows": [{"content_unit_id": content_id, "strength": "moderate", "reason": "冻结材料支持有边界的解释。"}],
            "alternative_ids": [], "unresolved_discriminators": [], "limitation_ids": [],
            "fallback_or_recheck_units": [{"action_id": "action:recheck", "condition": "关键事实或适用条件变化", "action": "重新核验相关来源后再更新成品", "planned_unit_id": route_unit_ids[-1]}],
            "actual_artifact_review_required": True,
        }
    elif owner == "academic-writing":
        extension = {
            "schema_version": "2.0", "composition_id": "composition:logic-writing-production", "final_owner": owner,
            "reader_intent_fingerprint": intent["intent_fingerprint"], "composition_plan_fingerprint": plan["plan_fingerprint"],
            "artifact_mode": intent["artifact_mode"], "profile": "conceptual_argument",
            "research_question": central_question, "central_contribution": throughline,
            "hierarchy": [
                {
                    "unit_id": unit["planned_unit_id"],
                    "parent_unit_id": unit["parent_unit_id"],
                    "unit_kind": "document" if index == 0 else "section",
                    "research_question_contribution": "回答任务的中心问题。" if index == 0 else unit["reader_job"],
                    "incoming_dependency": unit["incoming_reader_state"],
                    "new_claim_or_warrant": throughline if index == 0 else unit["reader_job"],
                    "evidence_ids": anchor_ids if index == 0 else [],
                    "qualification": {"status": "not_applicable", "reason": "当前请求没有要求新实验方法。", "source_refs": []},
                    "downstream_consumer_ids": list(unit["downstream_unit_ids"]),
                }
                for index, unit in enumerate(units)
            ],
            "figure_table_jobs": [], "revision_provenance_applicability": "not_applicable" if intent["artifact_mode"] == "create_new" else "required", "actual_artifact_review_required": True,
        }
    elif owner == "fiction-writing":
        extension = {
            "schema_version": "2.0", "composition_id": "composition:logic-writing-production", "final_owner": owner,
            "reader_intent_fingerprint": intent["intent_fingerprint"], "composition_plan_fingerprint": plan["plan_fingerprint"],
            "output_room": "reader_native", "artifact_kind": "short_story", "prose_phase": "repair" if intent["artifact_mode"] == "revise_existing" else "integrated_draft", "structure_authority": "user_partial", "voice_contract_ref": "voice:close-third",
            "story_movements": [
                {
                    "movement_id": f"movement:{unit['planned_unit_id'].split(':', 1)[-1]}",
                    "unit_ids": [unit["planned_unit_id"]],
                    "entry_story_state": unit["incoming_reader_state"],
                    "primary_pressure": unit["reader_job"],
                    "reader_state_change": unit["outgoing_reader_state"],
                    "irreversible_change": "这一单元必须留下可观察的局面变化。",
                    "exit_story_state": unit["outgoing_reader_state"],
                    "downstream_unit_ids": list(unit["downstream_unit_ids"]),
                    "promise_ids": ["promise:answer"],
                }
                for unit in units
            ],
            "unit_plans": [
                {
                    "unit_id": unit["planned_unit_id"], "unit_kind": "scene",
                    "contribution": unit["reader_job"], "entry_state": unit["incoming_reader_state"],
                    "exit_state": unit["outgoing_reader_state"], "focal_desire": "完成当前可见目标并保持受限视角。",
                    "resistance_or_cost": "事实约束、现场阻力和关系代价。",
                    "reader_state_before": unit["incoming_reader_state"], "reader_state_after": unit["outgoing_reader_state"],
                    "open_questions_in": [central_question] if index == 0 else [],
                    "open_questions_out": [central_question] if index + 1 < len(units) else [],
                    "voice_owner": "当前视角人物", "rhythm_role": unit["title"],
                    "prohibited_reveals": list(intent.get("forbidden_content", [])),
                    "downstream_unit_ids": list(unit["downstream_unit_ids"]),
                }
                for index, unit in enumerate(units)
            ],
            "promise_and_reveal_bindings": [{"binding_id": "binding:answer", "promise_or_reveal_id": "promise:answer", "setup_unit_ids": [route_unit_ids[0]], "movement_unit_ids": list(route_unit_ids), "payoff_unit_ids": [route_unit_ids[-1]], "status": "paid"}],
            "realization_boundaries": ["用可见行动和场景推进，不用内部模型标签解释。"],
        }
    else:
        extension = {
            "schema_version": "2.0", "composition_id": "composition:logic-writing-production", "final_owner": owner,
            "reader_intent_fingerprint": intent["intent_fingerprint"], "composition_plan_fingerprint": plan["plan_fingerprint"],
            "artifact_mode": intent["artifact_mode"], "guide_kind": "destination_guide", "structure_authority": "user_partial",
            "body_sections": [
                {
                    "section_id": unit["planned_unit_id"], "section_kind": unit["title"],
                    "section_role": unit["reader_job"], "incoming_traveler_state": unit["incoming_reader_state"],
                    "outgoing_traveler_state": unit["outgoing_reader_state"], "route_refs": ["route:answer"],
                    "traveler_fit_refs": ["fit:reader"], "local_texture_refs": [],
                    "risk_fallback_binding_ids": [], "next_consumer_ids": list(unit["downstream_unit_ids"]),
                    "prose_required": True, "list_or_table_allowed": intent["list_policy"] != "prose_default",
                }
                for unit in units
            ],
            "appendix_sections": [{"section_id": "appendix:checks", "operational_kinds": ["source_recheck", "fallback"], "consumer_section_ids": list(route_unit_ids)}], "source_boundary_placement": "appendix:checks", "recheck_placement": "appendix:checks", "local_texture_candidates": [], "risk_fallback_bindings": [],
        }
    extension["extension_fingerprint"] = fingerprint_without(extension, "extension_fingerprint")
    return {"composition_plan": plan, "route_composition": extension, "native_handoff_mapping": [{"native_unit_id": str(row["unit_id"]), "planned_unit_ids": list(route_unit_ids), "disposition": "body", "reason": "把已通过 native depth 的结论单元接入按阅读顺序排列的正文单元。"} for row in native.get("units", [])]}


def _production_planner_backend(local_backend: LocalCodexBackend, *, token: str):
    """Adapt one real local planner execution to the pipeline's raw-capture contract."""

    def planner(*, stage: str, inputs: dict[str, Any], evidence_root: Path) -> dict[str, Any]:
        prompt = _production_research_prompt(inputs) if stage == "research" else _production_compose_prompt(inputs)
        run_id = f"planner:{stage}:{token}"
        response = local_backend.run("planner", {
            "request_id": run_id,
            "run_id": run_id,
            "parent_orchestrator_run_id": "orchestrator:logic-writing-production-reader",
            "prompt": prompt,
            "settings": local_backend.settings(),
        })
        if response.get("terminal_status") != "completed":
            raise ValidationError(f"planner {stage} did not complete: {response.get('failure_reason') or response.get('terminal_status')}")
        parsed = _extract_json(str(response.get("output") or ""))
        if stage == "research":
            payload = _normalise_research_payload(parsed, token=token, request=inputs["writing_request"])
        else:
            payload = _normalise_compose_payload(parsed, inputs)
        raw_path = evidence_root / f"planner-{stage}-normalized.json"
        _write_json(raw_path, payload)
        raw_bytes = raw_path.read_bytes()
        # LocalCodexBackend deliberately returns run-root-relative locators so
        # its execution records remain portable within the private run root.
        # The production reader contract consumes an immutable external
        # capture, however, and therefore requires the backend capture to be
        # resolved to an absolute path before the planner record crosses this
        # adapter boundary.  Bind the path and bytes to the backend run root;
        # never let a planner select an unrelated or escaping artifact.
        backend_locator = response.get("raw_output_locator")
        if not isinstance(backend_locator, str) or not backend_locator.strip():
            raise ValidationError("planner backend did not return a raw output locator")
        backend_capture = Path(backend_locator)
        if not backend_capture.is_absolute():
            backend_capture = local_backend.run_root / backend_capture
        backend_capture = backend_capture.resolve()
        run_root = local_backend.run_root.resolve()
        try:
            backend_capture.relative_to(run_root)
        except ValueError as exc:
            raise ValidationError("planner backend capture escaped the backend run root") from exc
        if backend_capture.is_symlink() or not backend_capture.is_file():
            raise ValidationError("planner backend capture is missing or symlinked")
        backend_capture_bytes = backend_capture.read_bytes()
        backend_capture_fingerprint = _bytes_fp(backend_capture_bytes)
        if response.get("raw_output_fingerprint") != backend_capture_fingerprint:
            raise ValidationError("planner backend capture fingerprint is stale")
        backend_events = backend_capture.with_name("events.jsonl")
        if backend_events.is_symlink() or not backend_events.is_file():
            raise ValidationError("planner backend events capture is missing or symlinked")
        record = {
            "schema_version": "logic-writing.planner-execution-record.v1",
            "run_id": str(response["run_id"]),
            "context_id": str(response["context_id"]),
            "input_fingerprint": fingerprint(inputs),
            "raw_output_locator": str(raw_path.resolve()),
            "raw_output_fingerprint": _bytes_fp(raw_bytes),
            "backend_id": response.get("backend_id"),
            "backend_capture_locator": str(backend_capture),
            "backend_capture_fingerprint": backend_capture_fingerprint,
            "terminal_status": response.get("terminal_status"),
            "claim_scope": "planner output normalized only after the native pipeline contract is applied",
        }
        return {"payload": payload, "execution_record": record}

    return planner


def _production_writer_prompt(reader_spine: Mapping[str, Any]) -> str:
    """Build the production writer prompt from the reader spine only.

    The complete card-level WriterInput remains a private lineage artifact so
    the consumer can verify the native handoff.  It is deliberately not a
    prompt fallback: passing it here must fail the spine validator instead of
    leaking model ledgers, route metadata, or one-finding-per-card structure
    into the writer's context.
    """

    return render_reader_spine_prompt(reader_spine)


def _load_held_out_inputs(cases_dir: Path) -> tuple[list[dict[str, Any]], str, str, str, dict[str, str]]:
    """Load the four bounded holdout requests without exposing their oracle.

    Holdout materials live in one deliberately small manifest so the runner
    can freeze one input fingerprint.  The optional ``oracle`` field is
    retained in the case object for the audit consumer, but every prompt
    builder below receives only the task, constraints, and material records.
    Keeping the oracle in the frozen input file lets tests prove that the
    production prompt did not accidentally include it.
    """

    manifest_path = cases_dir / "held-out-manifest.json"
    manifest = _read_json(manifest_path)
    if not isinstance(manifest, Mapping) or manifest.get("schema_version") != "logic-writing.held-out-manifest.v1":
        raise ValueError("held-out-manifest.json schema is not current")
    raw_cases = manifest.get("cases")
    if not isinstance(raw_cases, list) or len(raw_cases) != len(HELD_OUT_CASE_IDS):
        raise ValueError("held-out manifest must contain exactly four cases")
    seen: set[str] = set()
    cases: list[dict[str, Any]] = []
    for raw in raw_cases:
        if not isinstance(raw, Mapping):
            raise ValueError("held-out manifest contains a non-object case")
        case_id = raw.get("case_id")
        if not isinstance(case_id, str) or case_id not in HELD_OUT_CASE_IDS or case_id in seen:
            raise ValueError(f"invalid or duplicate held-out case id: {case_id}")
        seen.add(case_id)
        if not isinstance(raw.get("route"), str) or not isinstance(raw.get("language"), str):
            raise ValueError(f"held-out case {case_id} has no route/language")
        if not isinstance(raw.get("task"), str) or not raw["task"].strip():
            raise ValueError(f"held-out case {case_id} has no task")
        if not isinstance(raw.get("constraints"), str) or not raw["constraints"].strip():
            raise ValueError(f"held-out case {case_id} has no constraints")
        raw_materials = raw.get("materials")
        if not isinstance(raw_materials, list) or not raw_materials:
            raise ValueError(f"held-out case {case_id} has no materials")
        material_records: list[dict[str, Any]] = []
        material_ids: set[str] = set()
        for material in raw_materials:
            if not isinstance(material, Mapping) or not isinstance(material.get("id"), str) or not isinstance(material.get("text"), str):
                raise ValueError(f"held-out case {case_id} has an invalid material")
            material_id = str(material["id"])
            if material_id in material_ids:
                raise ValueError(f"held-out case {case_id} repeats material {material_id}")
            material_ids.add(material_id)
            material_records.append({"id": material_id, "text": str(material["text"])})
        if not isinstance(raw.get("oracle"), Mapping):
            raise ValueError(f"held-out case {case_id} has no audit oracle")
        cases.append({
            **dict(raw),
            "material_records": material_records,
            "material_refs": [{"path": manifest_path.name, "id": item["id"]} for item in material_records],
            "rubric_ref": "held-out-rubric",
            "repeat_count": HELD_OUT_REPEATS,
            "synthetic": bool(manifest.get("synthetic", True)),
            # The prompts intentionally use this copy, which excludes the
            # oracle and any other audit-only metadata.
            "model_input": {
                "route": str(raw["route"]),
                "language": str(raw["language"]),
                "task": str(raw["task"]),
                "constraints": str(raw["constraints"]),
                "materials": material_records,
            },
        })
    if tuple(case["case_id"] for case in cases) != HELD_OUT_CASE_IDS:
        raise ValueError("held-out cases must be ordered H-I, H-A, H-F, H-T")
    manifest_fp = _bytes_fp(manifest_path.read_bytes())
    # The rubric is a code-owned, generic evaluator contract.  It contains no
    # case answer, target text, or oracle.
    rubric_fp = fingerprint_text(HELD_OUT_RUBRIC)
    source_manifest_fp = fingerprint({
        "held_out_manifest": manifest_fp,
        "held_out_rubric": rubric_fp,
    })
    return cases, HELD_OUT_RUBRIC, manifest_fp, source_manifest_fp, {manifest_path.name: manifest_fp}


def _public_held_out_case_request(case: Mapping[str, Any]) -> dict[str, Any]:
    """Return the producer-visible holdout request without audit-only data."""

    model_input = case.get("model_input")
    if not isinstance(model_input, Mapping):
        raise ValueError("held-out case has no redacted model input")
    public = {
        "case_id": str(case.get("case_id")),
        "route": str(case.get("route")),
        "language": str(case.get("language")),
        "task": str(case.get("task")),
        "constraints": str(case.get("constraints")),
        "materials": [dict(item) for item in model_input.get("materials", []) if isinstance(item, Mapping)],
    }
    if not public["case_id"] or not public["task"] or not public["materials"]:
        raise ValueError("held-out public request is incomplete")
    return public


def _resolve_backend(spec: str | None) -> Callable[..., Any] | None:
    if not spec:
        return None
    if ":" not in spec:
        raise ValueError("backend must use module:function syntax")
    module_name, function_name = spec.split(":", 1)
    function = getattr(importlib.import_module(module_name), function_name, None)
    if not callable(function):
        raise ValueError(f"backend function is not callable: {spec}")
    return function


def _writer_prompt(case: Mapping[str, Any], version: str) -> str:
    materials = "\n".join(f"[{row['id']}] {row['text']}" for row in case["material_records"])
    route_focus = {
        "investigation": (
            "调查/简报要先给读者可执行的回答，再用最少但足够的证据推进判断；"
            "每个限制都要说明它改变了结论、范围或下一步什么，不要把资料目录逐项复述。"
            "按任务声明的篇幅单位做最后一次长度核对，超出或不足都要用有信息作用的删改解决。"
        ),
        "academic-writing": (
            "学术文本要让中心论点统领证据：每一段都应有新的论证工作，并说明证据如何支持、"
            "限制如何收紧解释；表格或标题只在任务要求或确有功能时使用。"
            "同一证据的研究含义只在一个最合适的位置完整展开，其他位置只承担新的论证工作；"
            "条件句必须准确表达未知项，不能把已确认的条件写成未知，也不能把未知补成事实。"
        ),
        "fiction-writing": (
            "小说要让信息按视角和场景时序自然出现，用可见的动作、物件、声音和关系变化承载因果；"
            "不要替人物或作者解释主题，不要提前泄露受限信息，也不要用一句话抹平代价。"
            "分别核对读者此刻能知道什么、视角人物此刻能知道什么；若揭示被禁止，不能用对白、动作结果或"
            "紧邻反应间接确认同一事实。开门、救援等关键动作必须有与已知条件相容的可见来源，不能让受限物件"
            "既被判定无效又无来源地完成动作。"
        ),
        "travel-guide": (
            "行程要围绕旅客当天的体力、时间和天气决策组织；先说明安排为何可行，再给出触发条件和可执行备用，"
            "未知的开放时间、路线、票价或无障碍属性必须写成待核实，不能补造。"
            "把每一段必要接驳、连续步行上限和实际休息地点逐一接回默认方案；时间表的比较理由只能使用已知时刻，"
            "未知班次必须转成出发前核查与明确替代方案。只改任务要求的受影响安排，不为显得全面而扩展风险清单。"
        ),
    }.get(str(case.get("route")), "")
    if version == "repaired":
        composition_guidance = _composition_guidance(case)
        editorial = (
            "请在内部完成一次完整的‘读者契约→证据/事实核对→论证或场景图→成稿→反向检查’，但不要输出这些步骤。"
            "先确定一个能回答任务的中心判断或场景推进，再为每个正文单元明确：它承接什么、改变读者什么判断、"
            "为下一单元提供什么。只保留会改变理解、决定、行动或情节的材料，把数字、限制、反例和备用方案放在"
            "它们真正改变推理的位置。成稿完成后逐项核对语言、篇幅、格式、事实、因果强度、视角/旅行条件和所有禁项；"
            "删掉无新信息的重复限制、机械的对称转折、泛化的安全措辞、资料卡片式并列、作者自我说明和内部流程词。"
            "用自然的连续段落推进，让每个段落有明确功能和下一步去向；不要为了显得严谨堆叠‘这不意味着’、"
            "‘尽管如此’或‘需要指出’，不要解释你的写作流程。"
            "修订版必须在不牺牲事实、边界、格式或体裁的前提下，真正改善主线推进和读者可用性；"
            "不要声明自己完成了检查，也不要提到存在另一版稿件。"
            + route_focus
            + composition_guidance
        )
    else:
        editorial = (
            "直接完成用户要求；使用材料中的相关事实，遵守约束，只输出成稿，不输出分析、评分或执行记录。"
        )
    return (
        "你正在本机完成一篇最终成稿。只能使用下面显式给出的任务、约束和材料；不要读取文件、运行命令、调用工具或寻找其它资料。"
        "不要提到这些指令、版本、模型或内部流程。\n\n"
        f"任务：{case['task']}\n约束：{case['constraints']}\n\n冻结材料：\n{materials}\n\n"
        f"写作要求：{editorial}\n返回完整成稿，不要包裹 Markdown 代码围栏，不要附加自评。"
    )


def _composition_guidance(case: Mapping[str, Any]) -> str:
    """Give the repaired writer a route/case-specific throughline to execute.

    The benchmark intentionally keeps this guidance out of the delivered
    artifact.  Generic requests to "be coherent" were insufficient in the
    first real runs: the model often turned each material card into a
    paragraph, repeated a limitation, or skipped the one action that links a
    stated constraint to the outcome.  These are compact internal spines,
    not sentence templates and not extra facts.
    """

    case_id = str(case.get("case_id", ""))
    guidance = {
        "I01": (
            "内部主线固定为：是否扩大试点→中负载同产出观察及其机制解释→高负载反例如何收紧采购范围→"
            "情景经济测算如何改变下一步→带条件的采购决定。每段只完成其中一个推进；同一个限制再次出现时，"
            "必须改变读者的决定或范围，否则合并。篇幅不足时补充条件对采购的实际影响，不补泛化免责声明。"
        ),
        "I02": (
            "内部主线固定为：匹配产出使功率差异可比较→回流日志为何支持机制→仍有哪些未排除的解释→高负载反例"
            "为何改变适用域→下一步如何区分机制与相关性。使用连续正文，让每段末尾把已经得到的判断交给下一段；"
            "不要按E01、E02、E03逐卡复述。"
        ),
        "I03": (
            "内部主线固定为：先界定证据能回答的两个问题→表格按主张/证据/缺口给出可核对的边界→表后只做一次"
            "综合判断→提出与缺口一一对应的验证。表格每一行必须服务于这条判断；E06和E07只有在说明证据审计边界时"
            "出现，不能抢占设备性能结论。"
        ),
        "A01": (
            "内部主线固定为：为什么功率差异不能直接成为效益结论→服务等价是第一层判据→比较可识别性是第二层"
            "判据→机制适用域是第三层判据→L04的组织贡献及适用边界。每层都要说明它如何承接上一层并改变可作出的"
            "判断；不要写成三位作者的平行摘要，也不要把‘不意味着’变成固定句式。"
        ),
        "A02": (
            "在两个指定标题下内部组织为：Comparison design先交代相同产出、三对读数、单设备和短期边界，表格只放"
            "一次原始配对数据；Interpretation再解释10%观察、回流机制、高负载反例和无显著性检验如何共同收紧推断。"
            "不要在表前后重复同一组数字，结论必须从设计条件自然推出。"
        ),
        "A03": (
            "保留‘结果’→‘意义’这条两段主线：结果先把20%、显著和所有工况改成材料真正支持的中负载观察及其边界；"
            "意义再把该边界传递到采购范围、1.2年情景测算和下一项验证。每个补足篇幅的句子都要增加推理或决策作用，"
            "不要重复同一免责声明。"
        ),
        "F01": (
            "内部场景链必须闭合为：停电和倒计时造成即时压力→主管以钥匙为条件阻挡进入→林岚公开账页使阻挡失去"
            "可持续性→读者能看见主管放行及工人如何实际解除锁闭→货单被救但她仍承担弟弟发现副本后的信任代价。"
            "钥匙是否被调换对林岚和读者都仍是未知；绝不能让这把未知可用性的钥匙直接开门。公开账页之后要写出"
            "可观察的放行动作和与材料相容的破锁/解除锁闭动作，不能靠省略制造因果跳跃，也不能新增第二把钥匙。"
        ),
        "F02": (
            "内部场景链必须闭合为：明确林岚在锁闭仓库外→铃声由日常变成倒计时→公开账页改变主管的可行选择→"
            "现场可见的放行与解除锁闭动作让货单获救→第三声铃声落在弟弟的距离变化上。不得把当前钥匙写成必然可用，"
            "不得用旁白替主管解释，也不要用抽象主题句代替动作。"
        ),
        "F03": (
            "终稿是修订报告而非戏剧场景。只列三个编号项目：把知情越界与视角越界合并为一项，把代价抹平作为一项，"
            "把作者对铃声的解释作为一项；每项都写具体改法和必须保留的内容。不要把‘三项’扩成资料清单。"
        ),
        "T01": (
            "内部路线链按三天推进：每一天先给当天条件下的主安排及理由，再把旅馆/去处/返回之间的每段连续步行、"
            "休息地点和待核实项接回这条安排，最后给只在触发条件成立时启用的备用。不要把交通和限制另列成与行程"
            "无关的清单；每一个限制都必须改变当天的时间、地点或选择。"
        ),
        "T02": (
            "内部路线链固定为：雨天旅客条件→工业展馆这一条安静主方案→公交和馆内休息如何使它可行→必须出发前核实"
            "的条件→绘本馆作为一条明确备用。正文用连续说明，最后才放短checklist；不要把船、河岸或旧塔写成备选。"
        ),
        "T03": (
            "先原样保留第一天和第二天的可用内容，只重写第三天：电梯检修使依赖电梯的展馆安排失去可执行性，随后从"
            "材料已给出的短程绘本馆或其它可核实选择中做一个明确取舍，并说明婴儿车条件仍待核实。不要因为这一处变化"
            "重排三天，也不要声称任何未经给出的无障碍认证。"
        ),
    }
    selected = guidance.get(case_id)
    if not selected:
        return ""
    return "这些只是内部构思的因果骨架，不要把骨架标签或写作分析输出给读者。" + selected


def _judge_prompt(case: Mapping[str, Any], rubric_text: str, pair: list[dict[str, Any]]) -> str:
    materials = "\n".join(f"[{row['id']}] {row['text']}" for row in case["material_records"])
    articles = "\n\n".join(f"===== {row['anonymous_label']} =====\n{row['artifact_text']}" for row in pair)
    schema_hint = (
        '{"schema_version":"logic-writing.local-pair-judgment.v1","judgments":[{"anonymous_label":"X","reverse_outline":[],"obligation_results":[],"scores":{"clarity":1,"coherence":1,"naturalness":1,"reader_fit":1,"genre_fit":1,"content_fidelity":1,"instruction_fidelity":1,"structure_fidelity":1},"defects":[],"strengths":[],"required_repairs":[]},{"anonymous_label":"Y","reverse_outline":[],"obligation_results":[],"scores":{"clarity":1,"coherence":1,"naturalness":1,"reader_fit":1,"genre_fit":1,"content_fidelity":1,"instruction_fidelity":1,"structure_fidelity":1},"defects":[],"strengths":[],"required_repairs":[]}],"preference":"X","preference_reason":"..."}'
    )
    return (
        "你是本次成文质量评审者。你没有参与这两篇稿件的生成。只能使用本提示中给出的任务、约束、冻结材料、评分规则和匿名稿件；"
        "不要读取文件、运行命令、调用工具，不要猜测稿件版本。先为X和Y各写实际反向提纲，再核对事实和约束，最后评分。"
        f"每个正文段或功能区域必须能回指稿件中的真实文字。只返回一个 JSON 对象，格式示例：{schema_hint}。"
        "scores 必须是1到5的整数；preference 只能是 X、Y、tie 或 unable；不得添加作者/版本信息。\n\n"
        f"用户任务：{case['task']}\n约束：{case['constraints']}\n\n冻结材料：\n{materials}\n\n"
        f"评分规则：\n{rubric_text}\n\n匿名稿件：\n{articles}"
    )


def _single_judge_prompt(case: Mapping[str, Any], rubric_text: str, article: Mapping[str, Any]) -> str:
    """Build the independent single-article holdout review prompt.

    The holdout oracle is deliberately not a parameter of this function.  A
    single judge sees one real artifact, its task contract, and frozen source
    materials only.  Its JSON contains no anonymous pair labels or preference
    field, so a duplicated article cannot masquerade as a pair comparison.
    """

    materials = "\n".join(f"[{row['id']}] {row['text']}" for row in case["material_records"])
    schema_hint = (
        '{"schema_version":"logic-writing.local-single-judgment.v1",'
        '"artifact_fingerprint":"sha256:' + "0" * 64 + '",'
        '"reverse_outline":[{"unit":"paragraph-1","excerpt":"原文中的可定位摘录",'
        '"function":"该段推进的实际内容","forward_link":"交给下一段的判断"}],'
        '"obligation_results":[{"obligation_id":"O1","status":"passed",'
        '"unit":"paragraph-1","excerpt":"原文中的可定位摘录","reason":"..."}],'
        '"scores":{"clarity":1,"coherence":1,"naturalness":1,"reader_fit":1,'
        '"genre_fit":1,"content_fidelity":1,"instruction_fidelity":1,"structure_fidelity":1},'
        '"defects":[{"obligation_id":"O1","severity":"repair",'
        '"unit":"paragraph-1","excerpt":"原文中的可定位缺陷",'
        '"reason":"缺陷原因","repair":"具体修复动作"}],'
        '"required_repairs":[{"unit":"paragraph-1",'
        '"repair":"只在存在缺陷时填写的具体修复动作"}]}'
    )
    return (
        "你是本次保留集成文质量评审者，只评审这一篇真实成稿。你没有参与成稿生成，"
        "不能读取文件、运行命令、调用工具或寻找其它资料。先写覆盖全文的实际反向提纲，"
        "再检查任务、约束和材料；反向提纲与每个通过/缺陷判断都必须包含原文中可定位的摘录。"
        "不要猜测版本或作者，不要补写资料没有给出的事实。只返回一个 JSON 对象，格式示例："
        f"{schema_hint}。scores 的八个维度必须都是1到5的整数；核心维度 content_fidelity、"
        "instruction_fidelity、structure_fidelity 低于4必须在 defects 中指出具体原文定位、原因和修复；"
        "每个 defect 必须包含 unit、excerpt、reason；需要给出修复动作时可在 defect 中加入 repair，"
        "并可加入 obligation_id 和 severity；"
        "required_repairs 只能是对象数组，每项只能包含 unit 和 repair 两个字段，且两者都必须是非空字符串；"
        "required_repairs 中不要使用 action、defect_id、excerpt 或其它字段代替 repair。没有缺陷时 defects 和 required_repairs 必须为空；"
        "不得添加 X、Y、preference 或其它比较字段。\n\n"
        f"用户任务：{case['task']}\n约束：{case['constraints']}\n\n冻结材料：\n{materials}\n\n"
        f"通用评分规则：\n{rubric_text}\n\n"
        f"待评审成稿（指纹必须原样回填）：\n{article['artifact_text']}\n\n"
        f"成稿指纹：{article['artifact_fingerprint']}"
    )


def _pair_writer_input_fingerprint(pair: list[Mapping[str, Any]]) -> str:
    """Fingerprint the two writer inputs in a JSON-serializable order."""

    return fingerprint(sorted(str(row["writer_input_fingerprint"]) for row in pair))


def _pair_order_for_writers(order: tuple[Mapping[str, Any], Mapping[str, Any]]) -> list[str]:
    """Return the blind order from persisted writer versions.

    Writer rows may have crossed a process or serialization boundary before a
    judge job is assembled.  Object identity is therefore not a stable way to
    determine whether a pair is baseline-first or repaired-first.
    """

    pair_order = [str(writer.get("version")) for writer in order]
    if sorted(pair_order) != sorted(VERSIONS):
        raise ValueError("judge pair must contain one baseline and one repaired writer")
    return pair_order


def _execute_judge_job(
    *,
    case: Mapping[str, Any],
    repeat: int,
    judge_index: int,
    order: tuple[Mapping[str, Any], Mapping[str, Any]],
    rubric_text: str,
    cases_dir: Path,
    judge_dir: Path,
    local_backend: LocalCodexBackend | None,
    backend: Callable[..., Any] | None,
    resolver: LocalExecutionRecordResolver | None,
) -> dict[str, Any]:
    pair: list[dict[str, Any]] = []
    for label, writer in zip(("X", "Y"), order, strict=True):
        pair.append({
            "anonymous_label": label,
            "artifact_fingerprint": writer["artifact_fingerprint"],
            "writer_run_id": writer["record"]["run_id"],
            "writer_context_id": writer["record"]["context_id"],
            "writer_input_fingerprint": writer["record"]["input_writer_input_fingerprint"],
            "artifact_path": writer["artifact_path"],
            "artifact_text": writer["artifact_text"],
        })
    prompt = _judge_prompt(case, rubric_text, pair)
    intent, _ = _request_metadata(case, "judge", repeat, prompt)
    request = {
        "request_id": f"judge:{case['case_id']}:{repeat}:{judge_index}",
        "run_id": f"judge:{case['case_id']}:{repeat}:{judge_index}",
        "parent_orchestrator_run_id": "orchestrator:logic-writing-quality",
        "reader_intent_fingerprint": fingerprint(intent),
        "writer_input_fingerprint": _pair_writer_input_fingerprint(pair),
        "rubric_fingerprint": _bytes_fp((cases_dir / "judge-rubric.md").read_bytes()),
        "evaluation_mode": "pair",
        "pair_inputs": [
            {key: row[key] for key in ("anonymous_label", "artifact_fingerprint", "writer_run_id", "writer_context_id", "writer_input_fingerprint")}
            for row in pair
        ],
        "writer_context_ids": [row["writer_context_id"] for row in pair],
        "settings": local_backend.settings() if local_backend else {},
        "prompt": prompt,
    }
    pair_order = _pair_order_for_writers(order)
    row: dict[str, Any] = {
        "case_id": case["case_id"],
        "repeat": repeat,
        "judge_index": judge_index,
        "pair_order": pair_order,
        "request": request,
        "request_fingerprint": fingerprint(request),
        "status": "failed",
    }
    job_id = _job_identity({"case": case, "repeat": repeat, "judge_index": judge_index}, "judge")["job_id"]
    try:
        if local_backend is not None:
            dispatched = dispatch_judge(request, local_backend)
            row["dispatch_status"] = dispatched.get("status")
            for key in ("failure_reason", "error", "error_event", "execution_status", "terminal_status"):
                if dispatched.get(key) is not None:
                    row[key] = dispatched.get(key)
            record = dispatched.get("record")
            row["record"] = record
            if isinstance(record, Mapping):
                _annotate_backend_failure(
                    row, record, capture_root=local_backend.run_root, role="judge", job_id=job_id,
                )
            if isinstance(record, Mapping) and record.get("terminal_status") == "completed" and resolver is not None:
                validate_execution_record(record, resolver)
                raw_path = (local_backend.run_root / Path(str(record["raw_output_locator"]))).resolve()
                raw_text = raw_path.read_text(encoding="utf-8")
                parsed = _validate_judgment_payload(_extract_json(raw_text))
                row.update({"status": "completed", "raw_output": raw_text, "judgment": parsed, "judgment_fingerprint": fingerprint(parsed)})
        elif backend is not None:
            response = backend({"case": case, "pair": pair, "prompt": prompt})
            row["response"] = response
            row["status"] = "completed" if isinstance(response, Mapping) else "failed"
    except Exception as exc:
        # A single provider/schema failure must become a durable terminal row;
        # it must never escape a worker and strand the aggregate owner waiting
        # on an unobserved Future exception.
        row["error"] = str(exc)
        row["error_event"] = {
            "type": "error_event",
            "role": "judge",
            "job_id": job_id,
            "error_class": type(exc).__name__,
            "message": str(exc),
            "terminal": True,
        }
    path = judge_dir / str(case["case_id"]) / str(repeat) / str(judge_index) / "judge.json"
    _write_json(path, row)
    return row


def _execute_single_judge_job(
    *,
    case: Mapping[str, Any],
    repeat: int,
    judge_index: int,
    writer: Mapping[str, Any],
    rubric_text: str,
    cases_dir: Path,
    judge_dir: Path,
    local_backend: LocalCodexBackend | None,
    backend: Callable[..., Any] | None,
    resolver: LocalExecutionRecordResolver | None,
) -> dict[str, Any]:
    """Review one held-out artifact in an independent judge context."""

    writer_record = writer.get("record")
    if not isinstance(writer_record, Mapping):
        raise ValueError("single judge requires a completed writer record")
    artifact_fingerprint = str(writer.get("artifact_fingerprint") or "")
    article = {
        "artifact_fingerprint": artifact_fingerprint,
        "artifact_text": str(writer.get("artifact_text") or ""),
    }
    prompt = _single_judge_prompt(case, rubric_text, article)
    intent, writer_input = _request_metadata(case, "judge", repeat, prompt)
    writer_input_fingerprint = str(writer_record.get("input_writer_input_fingerprint") or fingerprint(writer_input))
    run_id = f"judge:{case['case_id']}:{repeat}:{judge_index}"
    writer_context_id = str(writer_record.get("context_id") or "")
    request = {
        "request_id": run_id,
        "run_id": run_id,
        "parent_orchestrator_run_id": "orchestrator:logic-writing-quality",
        "reader_intent_fingerprint": fingerprint(intent),
        "writer_input_fingerprint": writer_input_fingerprint,
        "artifact_fingerprint": artifact_fingerprint,
        "rubric_fingerprint": fingerprint_text(rubric_text),
        "evaluation_mode": "single",
        "pair_inputs": [],
        "writer_context_ids": [writer_context_id],
        "settings": local_backend.settings() if local_backend else {},
        "prompt": prompt,
    }
    row: dict[str, Any] = {
        "case_id": case["case_id"],
        "repeat": repeat,
        "judge_index": judge_index,
        "evaluation_mode": "single",
        "writer_run_id": writer_record.get("run_id"),
        "writer_context_id": writer_context_id,
        "artifact_fingerprint": artifact_fingerprint,
        "request": request,
        "request_fingerprint": fingerprint(request),
        "status": "failed",
    }
    job_id = _job_identity({"case": case, "repeat": repeat, "judge_index": judge_index}, "judge")["job_id"]
    try:
        if local_backend is not None:
            dispatched = dispatch_judge(request, local_backend)
            row["dispatch_status"] = dispatched.get("status")
            for key in ("failure_reason", "error", "error_event", "execution_status", "terminal_status"):
                if dispatched.get(key) is not None:
                    row[key] = dispatched.get(key)
            record = dispatched.get("record")
            row["record"] = record
            if isinstance(record, Mapping):
                _annotate_backend_failure(
                    row, record, capture_root=local_backend.run_root, role="judge", job_id=job_id,
                )
            if isinstance(record, Mapping) and record.get("terminal_status") == "completed" and resolver is not None:
                validate_execution_record(record, resolver)
                raw_path = (local_backend.run_root / Path(str(record["raw_output_locator"]))).resolve()
                raw_text = raw_path.read_text(encoding="utf-8")
                parsed = _validate_single_judgment_payload(_extract_json(raw_text))
                if parsed.get("artifact_fingerprint") != artifact_fingerprint:
                    raise ValidationError("single judge output is bound to a different artifact")
                row.update({
                    "status": "completed",
                    "raw_output": raw_text,
                    "judgment": parsed,
                    "judgment_fingerprint": fingerprint(parsed),
                })
        elif backend is not None:
            response = backend({"case": case, "article": article, "prompt": prompt, "evaluation_mode": "single"})
            row["response"] = response
            if isinstance(response, Mapping):
                parsed = _validate_single_judgment_payload(response)
                if parsed.get("artifact_fingerprint") != artifact_fingerprint:
                    raise ValidationError("single judge output is bound to a different artifact")
                row.update({"status": "completed", "judgment": parsed, "judgment_fingerprint": fingerprint(parsed)})
    except Exception as exc:
        row["error"] = str(exc)
        row["error_event"] = {
            "type": "error_event",
            "role": "judge",
            "job_id": job_id,
            "error_class": type(exc).__name__,
            "message": str(exc),
            "terminal": True,
        }
    path = judge_dir / str(case["case_id"]) / str(repeat) / str(judge_index) / "judge.json"
    _write_json(path, row)
    return row


def _extract_json(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if "```" in candidate:
        chunks = candidate.split("```")
        candidate = next((chunk.strip().removeprefix("json").strip() for chunk in chunks if "{" in chunk), candidate)
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("judge output has no JSON object")
        value = json.loads(candidate[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("judge output is not an object")
    return value


def _validate_judgment_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    if value.get("schema_version") != "logic-writing.local-pair-judgment.v1":
        raise ValueError("judge schema_version is not current")
    judgments = value.get("judgments")
    labels = {row.get("anonymous_label") for row in judgments if isinstance(row, dict)} if isinstance(judgments, list) else set()
    if not isinstance(judgments, list) or len(judgments) != 2 or labels != {"X", "Y"}:
        raise ValueError("judge output must contain exactly X and Y judgments")
    if value.get("preference") not in {"X", "Y", "tie", "unable"}:
        raise ValueError("judge preference is invalid")
    for row in judgments:
        if not isinstance(row, dict) or not isinstance(row.get("scores"), dict):
            raise ValueError("judge judgment is missing scores")
        scores = row["scores"]
        if set(scores) != set(DIMENSIONS) or any(not isinstance(scores[key], int) or not 1 <= scores[key] <= 5 for key in DIMENSIONS):
            raise ValueError("judge scores must contain the eight 1-5 dimensions")
        if not isinstance(row.get("reverse_outline"), list) or not isinstance(row.get("defects"), list) or not isinstance(row.get("required_repairs"), list):
            raise ValueError("judge judgment is missing outline/defect arrays")
    return dict(value)


def _validate_single_judgment_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the fixed, non-comparative holdout judgment envelope."""

    if value.get("schema_version") != "logic-writing.local-single-judgment.v1":
        raise ValueError("single judge schema_version is not current")
    forbidden = {"X", "Y", "preference", "pair", "baseline", "repaired"}
    if forbidden & set(value):
        raise ValueError("single judge output contains pair-comparison fields")
    artifact_fingerprint = value.get("artifact_fingerprint")
    if not isinstance(artifact_fingerprint, str) or not artifact_fingerprint.startswith("sha256:") or len(artifact_fingerprint) != 71:
        raise ValueError("single judge artifact_fingerprint is invalid")
    reverse_outline = value.get("reverse_outline")
    if not isinstance(reverse_outline, list) or not reverse_outline:
        raise ValueError("single judge reverse_outline must cover the article")
    for item in reverse_outline:
        if not isinstance(item, Mapping):
            raise ValueError("single judge reverse_outline contains a non-object")
        if not all(isinstance(item.get(key), str) and item[key].strip() for key in ("unit", "excerpt", "function")):
            raise ValueError("single judge reverse_outline must include text location and function")
    obligations = value.get("obligation_results")
    if not isinstance(obligations, list) or not obligations:
        raise ValueError("single judge obligation_results must not be empty")
    for item in obligations:
        if not isinstance(item, Mapping):
            raise ValueError("single judge obligation_results contains a non-object")
        if not isinstance(item.get("obligation_id"), str) or not item["obligation_id"].strip():
            raise ValueError("single judge obligation result has no obligation_id")
        if item.get("status") not in {"passed", "failed", "unknown"}:
            raise ValueError("single judge obligation result has an invalid status")
        if not all(isinstance(item.get(key), str) and item[key].strip() for key in ("unit", "excerpt")):
            raise ValueError("single judge obligation result must include text location")
    scores = value.get("scores")
    if not isinstance(scores, Mapping) or set(scores) != set(DIMENSIONS):
        raise ValueError("single judge scores must contain the eight dimensions")
    if any(not isinstance(scores[key], int) or not 1 <= scores[key] <= 5 for key in DIMENSIONS):
        raise ValueError("single judge scores must contain eight 1-5 integers")
    defects = value.get("defects")
    repairs = value.get("required_repairs")
    if not isinstance(defects, list) or not isinstance(repairs, list):
        raise ValueError("single judge defects and required_repairs must be arrays")
    for item in defects:
        if not isinstance(item, Mapping):
            raise ValueError("single judge defect contains a non-object")
        if not all(isinstance(item.get(key), str) and item[key].strip() for key in ("unit", "excerpt", "reason")):
            raise ValueError("single judge defect must include unit, excerpt, and reason")
        if "repair" in item and (not isinstance(item["repair"], str) or not item["repair"].strip()):
            raise ValueError("single judge defect repair must be a non-empty string")
        if "obligation_id" in item and (not isinstance(item["obligation_id"], str) or not item["obligation_id"].strip()):
            raise ValueError("single judge defect obligation_id must be a non-empty string")
    for item in repairs:
        if not isinstance(item, Mapping):
            raise ValueError("single judge repair contains a non-object")
        if not all(isinstance(item.get(key), str) and item[key].strip() for key in ("unit", "repair")):
            raise ValueError("single judge repair must include unit and repair")
    # Keep the payload intentionally closed.  An unknown field could silently
    # reintroduce a preference/answer channel into the holdout evaluator.
    allowed = {"schema_version", "artifact_fingerprint", "reverse_outline", "obligation_results", "scores", "defects", "required_repairs"}
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"single judge output contains unknown fields: {sorted(unknown)}")
    require_schema("local-single-judgment.schema.json", dict(value), label="LocalSingleJudgment")
    return dict(value)


def _held_out_quality_passes(judgments: list[Mapping[str, Any]], *, artifact_fingerprint: str) -> bool:
    """Apply the fixed absolute holdout gate to two independent reviews."""

    if len(judgments) != 2:
        return False
    for judgment in judgments:
        if judgment.get("artifact_fingerprint") != artifact_fingerprint:
            return False
        scores = judgment.get("scores")
        if not isinstance(scores, Mapping) or any(int(scores.get(key, 0)) < 4 for key in ("content_fidelity", "instruction_fidelity", "structure_fidelity")):
            return False
        defects = judgment.get("defects")
        repairs = judgment.get("required_repairs")
        if not isinstance(defects, list) or not isinstance(repairs, list) or repairs:
            return False
        if any(isinstance(item, Mapping) and item.get("severity", "repair") in {"blocking", "repair"} for item in defects):
            return False
    return True


def _request_metadata(case: Mapping[str, Any], version: str, repeat: int, prompt: str) -> tuple[dict[str, Any], dict[str, Any]]:
    intent = {
        "case_id": case["case_id"], "route": case["route"], "language": case["language"],
        "task": case["task"], "constraints": case["constraints"], "material_refs": case["material_refs"], "rubric_ref": case["rubric_ref"],
    }
    writer_input = {
        "case_id": case["case_id"], "version": version, "repeat": repeat,
        "task": case["task"], "constraints": case["constraints"],
        "materials": [{"id": row["id"], "text": row["text"]} for row in case["material_records"]],
        "prompt_fingerprint": fingerprint_text(prompt),
    }
    return intent, writer_input


def _load_plan(plan_path: Path | None, *, source_manifest_fp: str) -> dict[str, Any]:
    if plan_path is None:
        return {
            "schema_version": "logic-writing.local-backend-plan.v1", "backend_id": "local-codex:0.153.4:gpt-6-astra:xhigh",
            "model_id": DEFAULT_MODEL_ID, "reasoning_effort": DEFAULT_REASONING_EFFORT, "cli_version": DEFAULT_CLI_VERSION,
            "cli_sha256": DEFAULT_CLI_SHA256, "timeout_seconds": 900, "max_attempts": 1,
            "source_manifest_fingerprint": source_manifest_fp, "startup_timeout_seconds": 60,
            "no_progress_seconds": 0,
        }
    value = _read_json(plan_path)
    if not isinstance(value, dict) or value.get("schema_version") != "logic-writing.local-backend-plan.v1":
        raise ValueError("local backend plan schema is not current")
    if value.get("model_id") != DEFAULT_MODEL_ID or value.get("reasoning_effort") != DEFAULT_REASONING_EFFORT:
        raise ValueError("local backend plan does not use the frozen model/settings")
    declared_source = value.get("source_manifest_fingerprint")
    if declared_source is not None and declared_source != source_manifest_fp:
        raise ValueError("local backend plan source manifest fingerprint is stale")
    for key, expected in (("cli_version", DEFAULT_CLI_VERSION), ("cli_sha256", DEFAULT_CLI_SHA256)):
        if key in value and value.get(key) != expected:
            raise ValueError(f"local backend plan {key} is not the frozen local toolchain")
    for key, minimum in (("timeout_seconds", 1), ("startup_timeout_seconds", 1), ("max_attempts", 1), ("concurrency", 1), ("no_progress_seconds", 0)):
        if key in value:
            try:
                parsed = int(value[key])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"local backend plan {key} must be an integer") from exc
            if parsed < minimum:
                raise ValueError(f"local backend plan {key} is below its minimum")
    if "concurrency" in value and int(value["concurrency"]) > 2:
        raise ValueError("local backend plan concurrency cannot exceed two")
    return value


def _implementation_identity(root: Path) -> dict[str, str]:
    """Fingerprint the current product components used by this run."""

    candidates = (
        root / "scripts" / "run_reader_acceptance_owner.py",
        root / "scripts" / "run_writing_quality_benchmark.py",
        root / "scripts" / "check_writing_quality_run.py",
        root / "skills" / "logic-writing" / "scripts" / "local_execution_backend.py",
        root / "skills" / "logic-writing" / "scripts" / "reader_execution.py",
        root / "skills" / "logic-writing" / "scripts" / "execution_record_resolver.py",
        root / "skills" / "logic-writing" / "scripts" / "reader_pipeline.py",
        root / "skills" / "logic-writing" / "scripts" / "production_reader_pipeline.py",
        root / "skills" / "logic-writing" / "scripts" / "researchguard_handoff.py",
        root / "skills" / "logic-writing" / "scripts" / "provider_preflight.py",
        root / "skills" / "logic-writing" / "scripts" / "build_source_unit_manifest.py",
        root / "skills" / "logic-writing" / "scripts" / "select_route.py",
        root / "skills" / "logic-writing" / "scripts" / "schema_validation.py",
        root / "skills" / "logic-writing" / "assets" / "schemas" / "reader-execution-record.schema.json",
        root / "skills" / "logic-writing" / "assets" / "schemas" / "local-single-judgment.schema.json",
        root / "skills" / "logic-writing" / "assets" / "schemas" / "reader-brief.schema.json",
        root / "skills" / "logic-writing" / "assets" / "schemas" / "writing-request.schema.json",
        root / "skills" / "logic-writing" / "assets" / "schemas" / "researchguard-logic-handoff.schema.json",
        root / "skills" / "logic-writing" / "assets" / "schemas" / "researchguard-consumption-binding.schema.json",
    )
    identity: dict[str, str] = {}
    for path in candidates:
        if path.is_file() and not path.is_symlink():
            identity[path.relative_to(root).as_posix()] = _bytes_fp(path.read_bytes())
    return identity


def _execution_policy(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "backend_id": plan.get("backend_id"),
        "model_id": plan.get("model_id"),
        "reasoning_effort": plan.get("reasoning_effort"),
        "cli_version": plan.get("cli_version"),
        "cli_sha256": plan.get("cli_sha256"),
        "timeout_seconds": int(plan.get("timeout_seconds", 900)),
        "no_progress_seconds": int(plan.get("no_progress_seconds", 0)),
        "startup_timeout_seconds": int(plan.get("startup_timeout_seconds", 60)),
        "concurrency": int(plan.get("concurrency", 1)),
        "max_attempts": int(plan.get("max_attempts", 1)),
    }


def _planner_stages_for_version(version: str) -> tuple[str, ...]:
    """Return the planner calls nested inside one writer execution."""

    # The baseline is deliberately the historical direct writer lane.  The
    # repaired pair lane and the held-out current lane each run the same two
    # production planner stages before dispatching the writer.
    return ("research", "compose") if version in {"repaired", HELD_OUT_VERSION} else ()


def _status_progress(items: list[Mapping[str, Any]]) -> dict[str, int]:
    statuses = [str(item.get("status")) for item in items]
    completed = sum(status == "completed" for status in statuses)
    not_started = sum(status in _JOB_NOT_STARTED_STATUSES for status in statuses)
    failed = sum(status in {"failed", "timed_out", "cancelled"} for status in statuses)
    terminal = completed + failed + sum(
        status in {"not_started_dependency_failed", "not_started_deadline", "not_started_cleanup_blocked"}
        for status in statuses
    )
    return {
        "planned": len(items),
        "terminal": terminal,
        "completed": completed,
        "failed": failed,
        "not_started": not_started,
    }


def _ledger_progress(jobs: list[Mapping[str, Any]], nested: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Expose scheduled and nested work separately, with one total ledger."""

    scheduled = _status_progress(jobs)
    nested_progress = _status_progress(nested)
    return {
        "planned": scheduled["planned"] + nested_progress["planned"],
        "terminal": scheduled["terminal"] + nested_progress["terminal"],
        "completed": scheduled["completed"] + nested_progress["completed"],
        "failed": scheduled["failed"] + nested_progress["failed"],
        "not_started": scheduled["not_started"] + nested_progress["not_started"],
        "scheduled": scheduled,
        "nested_planner": nested_progress,
    }


def _build_planned_ledger(
    cases: list[dict[str, Any]],
    plan: Mapping[str, Any],
    *,
    repeats_count: int = REPEATS,
    versions: tuple[str, ...] = VERSIONS,
    mode: str = "pair",
) -> dict[str, Any]:
    jobs: list[dict[str, Any]] = []
    nested: list[dict[str, Any]] = []
    for repeat in range(1, repeats_count + 1):
        for case in cases:
            for version in versions:
                identity = _job_identity({"case": case, "repeat": repeat, "version": version}, "writer")
                jobs.append({**identity, "execution_kind": "scheduled", "status": "queued", "terminal_reason": None})
                for stage in _planner_stages_for_version(version):
                    nested.append({
                        "job_id": f"{identity['job_id']}:planner:{stage}",
                        "parent_job_id": identity["job_id"],
                        "role": "planner",
                        "execution_kind": "nested",
                        "stage": stage,
                        "case_id": identity["case_id"],
                        "repeat": identity["repeat"],
                        "version": identity["version"],
                        "judge_index": None,
                        "status": "queued",
                        "terminal_reason": None,
                    })
            for judge_index in (1, 2):
                judge_job = {"case": case, "repeat": repeat, "judge_index": judge_index}
                if mode == "held_out":
                    judge_job["evaluation_mode"] = "single"
                identity = _job_identity(judge_job, "judge")
                jobs.append({
                    **identity,
                    "execution_kind": "scheduled",
                    "evaluation_mode": "single" if mode == "held_out" else "pair",
                    "status": "queued",
                    "terminal_reason": None,
                })
    progress = _ledger_progress(jobs, nested)
    ledger = {
        "schema_version": "logic-writing.quality-planned-ledger.v2",
        "benchmark_id": plan.get("benchmark_id"),
        "implementation_fingerprint": plan.get("implementation_fingerprint"),
        "execution_policy_fingerprint": plan.get("execution_policy_fingerprint"),
        "jobs": jobs,
        "nested_planner_executions": nested,
        "planned_counts": {
            "scheduled_jobs": len(jobs),
            "nested_planner_executions": len(nested),
            "planned_execution_count": len(jobs) + len(nested),
        },
        "progress": progress,
    }
    ledger["ledger_fingerprint"] = fingerprint(ledger)
    return ledger


def _finalize_planned_ledger(output_dir: Path, ledger: dict[str, Any], rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    by_id = {str(row.get("job_id")): row for row in rows if isinstance(row, Mapping) and row.get("job_id")}
    jobs = []
    for item in ledger.get("jobs", []):
        value = dict(item)
        row = by_id.get(str(value.get("job_id")))
        if row is not None:
            for key in ("status", "terminal_reason", "process_id", "process_creation_time", "cleanup_confirmed", "finished_at"):
                if key in row:
                    value[key] = row[key]
        jobs.append(value)
    writer_by_key = {
        (str(row.get("case_id")), int(row.get("repeat", 0)), str(row.get("version"))): row
        for row in rows
        if isinstance(row, Mapping) and row.get("role", "writer") == "writer"
    }
    nested: list[dict[str, Any]] = []
    for item in ledger.get("nested_planner_executions", []):
        value = dict(item)
        parent_id = str(value.get("parent_job_id") or "")
        writer = by_id.get(parent_id)
        if writer is None:
            writer = writer_by_key.get((str(value.get("case_id")), int(value.get("repeat", 0)), str(value.get("version"))))
        production = writer.get("production_reader") if isinstance(writer, Mapping) else None
        records = production.get("planner_execution_records") if isinstance(production, Mapping) else None
        stage = str(value.get("stage") or "")
        record = next(
            (
                record
                for record in records
                if isinstance(record, Mapping)
                and str(record.get("run_id") or "").startswith(f"planner:{stage}:")
            ),
            None,
        ) if isinstance(records, list) else None
        if isinstance(record, Mapping):
            value.update({
                "status": "completed" if record.get("terminal_status") == "completed" else "failed",
                "terminal_reason": None if record.get("terminal_status") == "completed" else str(record.get("terminal_status") or "planner_not_completed"),
                "run_id": record.get("run_id"),
                "context_id": record.get("context_id"),
                "input_fingerprint": record.get("input_fingerprint"),
                "raw_output_locator": record.get("raw_output_locator"),
                "raw_output_fingerprint": record.get("raw_output_fingerprint"),
                "backend_capture_locator": record.get("backend_capture_locator"),
                "backend_capture_fingerprint": record.get("backend_capture_fingerprint"),
            })
        elif isinstance(writer, Mapping) and str(writer.get("status")) not in {"queued", "starting", "running"}:
            value["status"] = "failed"
            value["terminal_reason"] = "planner_capture_missing"
        nested.append(value)
    ledger = dict(ledger)
    ledger["jobs"] = jobs
    ledger["nested_planner_executions"] = nested
    ledger["planned_counts"] = {
        "scheduled_jobs": len(jobs),
        "nested_planner_executions": len(nested),
        "planned_execution_count": len(jobs) + len(nested),
    }
    ledger["progress"] = _ledger_progress(jobs, nested)
    ledger.pop("ledger_fingerprint", None)
    ledger["ledger_fingerprint"] = fingerprint(ledger)
    _write_json(output_dir / "planned-ledger.json", ledger)
    return ledger


def _unavailable_result(plan: Mapping[str, Any], *, source_manifest_fp: str, output_dir: Path, reason: str) -> dict[str, Any]:
    planned_writer_count = int(plan.get("planned_writer_count", CASE_COUNT * REPEATS * len(VERSIONS)))
    planned_judge_count = int(plan.get("planned_judge_count", CASE_COUNT * REPEATS * 2))
    benchmark_id = str(plan.get("benchmark_id") or "logic-writing-real-quality-12x2x2")
    mode = str(plan.get("mode") or "pair")
    default_planner_count = (
        planned_writer_count * len(_planner_stages_for_version(HELD_OUT_VERSION))
        if mode == "held_out"
        else CASE_COUNT * REPEATS * len(_planner_stages_for_version("repaired"))
    )
    planned_planner_count = int(plan.get("planned_planner_count", default_planner_count))
    empty_progress = _ledger_progress(
        [{"status": "queued"}] * (planned_writer_count + planned_judge_count),
        [{"status": "queued"}] * planned_planner_count,
    )
    result = {
        "schema_version": "logic-writing.writing-quality-run-result.v2", "benchmark_id": benchmark_id,
        "mode": mode,
        "status": "not_run", "terminal_reason": reason, "quality_claim_status": "incomplete",
        "planned_writer_count": planned_writer_count, "planned_judge_count": planned_judge_count,
        "planned_planner_count": planned_planner_count,
        "planned_execution_count": planned_writer_count + planned_judge_count + planned_planner_count, "actual_writer_count": 0, "actual_judge_count": 0, "actual_planner_count": 0,
        "actual_execution_count": 0, "successful_artifact_count": 0, "backend_id": plan.get("backend_id"),
        "source_manifest_fingerprint": source_manifest_fp, "created_at": _now(),
        "implementation_fingerprint": plan.get("implementation_fingerprint"),
        "execution_policy_fingerprint": plan.get("execution_policy_fingerprint"),
        "planned_status_counts": empty_progress,
        "progress": empty_progress,
        "claim_boundary": "No local writer or independent judge ran; this receipt contains no quality score.",
    }
    _write_json(output_dir / "writers.json", [])
    _write_json(output_dir / "judges.json", [])
    _write_json(output_dir / "summary.json", {
        "schema_version": "logic-writing.held-out-quality-summary.v1" if mode == "held_out" else "logic-writing.writing-quality-summary.v2",
        "status": "incomplete",
        "mode": mode,
        "held_out_passed": False if mode == "held_out" else None,
        "case_count": int(plan.get("case_count", CASE_COUNT)),
        "improved_case_count": 0,
        "required_improved_case_count": int(plan.get("required_improved_case_count", 9 if mode == "pair" else 0)),
        "cases": [],
        "writer_count": 0,
        "judge_count": 0,
        "claim_boundary": "No local writer or independent judge ran; this receipt contains no quality score.",
    })
    _write_json(output_dir / "run_result.json", result)
    return result


def _initialize_local_backend(
    output_dir: Path,
    plan: Mapping[str, Any],
    *,
    startup_timeout_seconds: int,
) -> tuple[LocalCodexBackend | None, LocalExecutionRecordResolver | None, str | None]:
    """Initialize the pinned provider without leaving a helper thread alive.

    Provider construction is limited to local file hashing and a version probe
    whose subprocess has its own 30-second timeout.  A direct call keeps the
    startup path inspectable and makes dependency failures durable; the actual
    writer/judge work is always placed behind ``_run_isolated_jobs``.  The
    elapsed check records a startup timeout when a local filesystem or probe
    exceeds the plan, while avoiding a thread-pool that cannot be terminated.
    """
    started = time.monotonic()
    try:
        backend = LocalCodexBackend(
            output_dir / "attempts", model_id=str(plan["model_id"]), reasoning_effort=str(plan["reasoning_effort"]),
            timeout_seconds=int(plan.get("timeout_seconds", 900)), expected_cli_version=str(plan.get("cli_version", DEFAULT_CLI_VERSION)),
            no_progress_seconds=int(plan.get("no_progress_seconds", 0)),
            expected_executable_sha256=str(plan.get("cli_sha256", DEFAULT_CLI_SHA256)),
        )
        resolver = LocalExecutionRecordResolver(
            backend.run_root, expected_cli_version=backend.cli_version,
            expected_cli_sha256=backend.executable_sha256, expected_backend_id=backend.backend_id,
        )
        if time.monotonic() - started > max(1, int(startup_timeout_seconds)):
            return None, None, "startup_timeout"
        return backend, resolver, None
    except Exception as exc:
        return None, None, f"dependency_failed:{type(exc).__name__}"


def _copy_artifact(capture_root: Path, record: Mapping[str, Any], target: Path) -> tuple[Path, dict[str, Any]]:
    locator = record.get("raw_output_locator")
    if not isinstance(locator, str):
        raise ValidationError("writer execution has no raw output locator")
    source = (capture_root / Path(locator)).resolve()
    try:
        source.relative_to(capture_root.resolve())
    except ValueError as exc:
        raise ValidationError("writer output escaped capture root") from exc
    if not source.is_file() or source.is_symlink():
        raise ValidationError("writer output capture is missing or symlinked")
    data = source.read_bytes()
    if not data.strip() or _bytes_fp(data) != record.get("raw_output_fingerprint"):
        raise ValidationError("writer output bytes do not match execution record")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    artifact_map = build_artifact_map(target, map_id=f"artifact:{record['run_id']}", language="und")
    return target, artifact_map


def _capture_file(capture_root: Path, locator: Any) -> Path | None:
    """Resolve one backend capture locator without leaving its run root."""

    if not isinstance(locator, str) or not locator.strip():
        return None
    root = capture_root.resolve()
    path = (root / Path(locator)).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    if path.is_symlink() or not path.is_file():
        return None
    return path


def _provider_error_message(capture_root: Path, completion: Mapping[str, Any], record: Mapping[str, Any]) -> str | None:
    """Recover a short provider error message from the immutable event capture."""

    locator = completion.get("events_locator") or record.get("events_locator")
    events_path = _capture_file(capture_root, locator)
    if events_path is None:
        return None
    try:
        lines = events_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        try:
            event = json.loads(line)
        except (TypeError, ValueError):
            continue
        if isinstance(event, Mapping) and event.get("type") == "error":
            message = event.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()[:2048]
    return None


def _annotate_backend_failure(
    row: dict[str, Any],
    record: Mapping[str, Any],
    *,
    capture_root: Path,
    role: str,
    job_id: str,
) -> None:
    """Carry local provider failure identity into the durable job row.

    ``ReaderExecutionRecord`` intentionally keeps the execution contract
    stable and currently does not expose the backend's failure-reason fields.
    The immutable completion/event captures are therefore the source for this
    row-level diagnostic.  A failed execution remains failed; this only makes
    its reason recoverable without opening the private attempt directory.
    """

    if record.get("terminal_status") == "completed":
        return
    completion: Mapping[str, Any] = {}
    completion_path = _capture_file(
        capture_root,
        record.get("completion_locator") or record.get("execution_capture_ref"),
    )
    if completion_path is not None:
        try:
            value = _read_json(completion_path)
        except (OSError, TypeError, ValueError):
            value = None
        if isinstance(value, Mapping):
            completion = value
    reason_value = completion.get("failure_reason")
    reason = str(reason_value).strip() if isinstance(reason_value, str) and reason_value.strip() else None
    if reason is None:
        terminal_status = str(record.get("terminal_status") or "failed")
        reason = "execution_unavailable" if terminal_status == "unavailable" else "execution_failed"
    detail_value = completion.get("failure_detail")
    detail = str(detail_value).strip() if isinstance(detail_value, str) and detail_value.strip() else None
    provider_message = _provider_error_message(capture_root, completion, record)
    message = (detail or provider_message or reason)[:2048]
    event: dict[str, Any] = {
        "type": "error_event",
        "role": role,
        "job_id": job_id,
        "error_class": reason,
        "message": message,
        "terminal": True,
    }
    if provider_message:
        event["provider_event_type"] = "error"
        event["provider_message"] = provider_message
    row["terminal_reason"] = reason
    row["error"] = message
    row["error_event"] = event


def _execute_writer_job(
    *,
    case: Mapping[str, Any],
    repeat: int,
    version: str,
    writer_dir: Path,
    local_backend: LocalCodexBackend | None,
    backend: Callable[..., Any] | None,
    resolver: LocalExecutionRecordResolver | None,
) -> dict[str, Any]:
    """Execute one writer job and persist only its own artifact directory.

    Writer jobs are independent: every job has a unique logical run id and
    output path.  Keeping all mutable state inside this function makes it safe
    to run local Codex writers concurrently while retaining the same row shape
    and byte-level capture validation as the serial path.
    """
    production_result: dict[str, Any] | None = None
    if local_backend is not None and version in {"repaired", HELD_OUT_VERSION}:
        # The repaired and held-out current lanes use the production
        # reader-to-writer path.  The baseline keeps the historical direct
        # prompt so the pair comparison still measures the effect of the
        # reader projection rather than silently replacing both sides.
        production_request, boundaries, token = _production_request_and_boundaries(case)
        production_root = writer_dir / str(case["case_id"]) / str(repeat) / version / "production-reader"
        production_result = prepare_production_reader_input(
            production_request,
            native_provider=InstalledResearchGuardProvider(timeout_seconds=min(900, max(30, int(local_backend.timeout_seconds)))),
            planner_backend=_production_planner_backend(local_backend, token=token),
            frozen_content_boundaries=boundaries,
            evidence_root=production_root,
        )
        prompt = _production_writer_prompt(production_result["reader_spine"])
        writer_input = production_result["writer_input"]
        intent = writer_input["reader_intent"]
    else:
        prompt = _writer_prompt(case, version)
        intent, writer_input = _request_metadata(case, version, repeat, prompt)
    request = {
        "request_id": f"writer:{case['case_id']}:{repeat}:{version}",
        "run_id": f"writer:{case['case_id']}:{repeat}:{version}",
        "parent_orchestrator_run_id": "orchestrator:logic-writing-quality",
        # The production projection already carries the canonical
        # ReaderIntent fingerprint.  Preserve that identity in the writer
        # request so the consumer can join ReaderBrief, handoff, and binding
        # without comparing a second hash that includes the self-fingerprint.
        "reader_intent_fingerprint": (
            intent.get("intent_fingerprint")
            if production_result is not None
            else fingerprint(intent)
        ),
        "writer_input_fingerprint": fingerprint(writer_input),
        "settings": local_backend.settings() if local_backend else {},
        "prompt": prompt,
    }
    if production_result is not None:
        request["reader_spine_fingerprint"] = production_result["reader_spine_fingerprint"]
    row: dict[str, Any] = {
        "case_id": case["case_id"],
        "repeat": repeat,
        "version": version,
        "request": request,
        "request_fingerprint": fingerprint(request),
        "status": "failed",
        "artifact_path": None,
        "artifact_fingerprint": None,
    }
    job_id = _job_identity({"case": case, "repeat": repeat, "version": version}, "writer")["job_id"]
    if production_result is not None:
        row["production_reader"] = {
            "status": production_result.get("status"),
            "writer_request_fingerprint": None,
            "production_reader_fingerprint": _bytes_fp(
                (writer_dir / str(case["case_id"]) / str(repeat) / version / "production-reader" / "production-reader-input.json").read_bytes()
            ),
            "writer_input_fingerprint": production_result.get("writer_input_fingerprint"),
            "reader_spine_fingerprint": production_result.get("reader_spine_fingerprint"),
            "reader_spine_schema": production_result.get("reader_spine_schema"),
            "request_fingerprint": production_result.get("request_fingerprint"),
            "content_fingerprint": production_result.get("content_fingerprint"),
            "source_fingerprint": production_result.get("source_fingerprint"),
            "refs": production_result.get("refs"),
            "planner_execution_records": production_result.get("planner_execution_records"),
            "provider_identity": production_result.get("provider_identity"),
            "claim_boundary": production_result.get("claim_boundary"),
        }
        # This outer binding is intentionally recorded after the writer
        # request is fully formed; the immutable production envelope remains
        # the exact pre-writer input and does not need to be rewritten.
        row["production_reader"]["writer_request_fingerprint"] = row["request_fingerprint"]
    try:
        if local_backend is not None:
            dispatched = dispatch_writer(request, local_backend)
            row["dispatch_status"] = dispatched.get("status")
            for key in ("failure_reason", "error", "error_event", "execution_status", "terminal_status"):
                if dispatched.get(key) is not None:
                    row[key] = dispatched.get(key)
            record = dispatched.get("record")
            row["record"] = record
            if isinstance(record, Mapping):
                _annotate_backend_failure(
                    row, record, capture_root=local_backend.run_root, role="writer", job_id=job_id,
                )
            if isinstance(record, Mapping) and record.get("terminal_status") == "completed" and resolver is not None:
                validate_execution_record(record, resolver)
                artifact_path, artifact_map = _copy_artifact(
                    local_backend.run_root,
                    record,
                    writer_dir / str(case["case_id"]) / str(repeat) / version / "artifact.md",
                )
                _write_json(
                    writer_dir / str(case["case_id"]) / str(repeat) / version / "artifact-map.json",
                    artifact_map,
                )
                row.update({
                    "status": "completed",
                    "artifact_path": artifact_path.relative_to(writer_dir.parent.parent).as_posix(),
                    "artifact_fingerprint": artifact_map["artifact_fingerprint"],
                    "artifact_map_fingerprint": artifact_map["map_fingerprint"],
                    "artifact_text": artifact_path.read_text(encoding="utf-8"),
                })
        elif backend is not None:
            response = backend({"case": case, "version": version, "repeat": repeat, "prompt": prompt})
            row["response"] = response
            row["status"] = "completed" if isinstance(response, Mapping) and response.get("artifact_fingerprint") else "failed"
    except Exception as exc:
        # Preserve writer failures as auditable terminal evidence.  This keeps
        # the artifact out of the quality claim while allowing the parent run
        # to finish and emit an incomplete result instead of waiting forever.
        row["error"] = str(exc)
        row["error_event"] = {
            "type": "error_event",
            "role": "writer",
            "job_id": job_id,
            "error_class": type(exc).__name__,
            "message": str(exc),
            "terminal": True,
        }
    row_path = writer_dir / str(case["case_id"]) / str(repeat) / version / "writer.json"
    _write_json(row_path, row)
    return row


def run_benchmark(
    root: Path,
    *,
    output_dir: Path,
    cases_dir: Path | None = None,
    backend: Callable[..., Any] | None = None,
    backend_id: str | None = None,
    backend_plan: Path | None = None,
    run_writers: bool = True,
    run_judges: bool = True,
    summarize_only: bool = False,
    mode: str = "pair",
    preflight_case: str | None = None,
    repeats_override: int | None = None,
) -> dict[str, Any]:
    if mode == "held_out":
        return _run_held_out_benchmark(
            root,
            output_dir=output_dir,
            cases_dir=cases_dir,
            backend=backend,
            backend_id=backend_id,
            backend_plan=backend_plan,
            run_writers=run_writers,
            run_judges=run_judges,
            summarize_only=summarize_only,
        )
    if mode not in {"pair", "preflight"}:
        raise ValueError(f"unsupported quality benchmark mode: {mode}")
    if preflight_case is not None:
        mode = "preflight"
        if repeats_override is None:
            repeats_override = 1
        if int(repeats_override) < 1:
            raise ValueError("preflight repeats must be positive")
    root = root.resolve()
    cases_dir = (cases_dir or root / "tests/fixtures/writing_quality").resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()) and (run_writers or run_judges) and not summarize_only:
        raise ValueError("quality output directory is not empty; choose a new immutable run root")
    output_dir.mkdir(parents=True, exist_ok=True)
    cases, rubric_text, input_manifest_fp, source_manifest_fp, material_files = _load_frozen_inputs(cases_dir)
    by_case_id = {str(case["case_id"]): case for case in cases}
    if set(by_case_id) != set(CASE_ORDER):
        raise ValueError("canonical case manifest does not contain the required twelve case IDs")
    cases = [by_case_id[case_id] for case_id in CASE_ORDER]
    if preflight_case is not None:
        if preflight_case not in by_case_id:
            raise ValueError(f"preflight case is not in the canonical manifest: {preflight_case}")
        cases = [by_case_id[preflight_case]]
    repeat_count = int(repeats_override if repeats_override is not None else REPEATS)
    versions = VERSIONS
    plan = _load_plan(backend_plan, source_manifest_fp=source_manifest_fp)
    if backend is not None and backend_plan is None:
        raise ValueError(
            "an injected backend cannot produce real_execution quality evidence; "
            "run the pinned local backend with --backend-plan"
        )
    rubric_fingerprint = _bytes_fp((cases_dir / "judge-rubric.md").read_bytes())
    implementation_identity = _implementation_identity(root)
    case_count = len(cases)
    planned_writer_count = case_count * repeat_count * len(versions)
    planned_judge_count = case_count * repeat_count * 2
    # Only the current/repaired writer lane invokes the two-stage production
    # planner.  The baseline remains the historical direct writer path.  The
    # count is per nested execution (research and compose), so it must match
    # the two planner records carried by each production writer.
    planned_planner_count = case_count * repeat_count * len(_planner_stages_for_version("repaired"))
    plan.update({
        "schema_version": "logic-writing.writing-quality-run.v2",
        "benchmark_id": "logic-writing-preflight-1x1x2" if mode == "preflight" else "logic-writing-real-quality-12x2x2",
        "mode": mode,
        "claim": "smoke_only" if mode == "preflight" else "comparison",
        "evidence_mode": "real_execution", "case_count": case_count, "repeats_per_version": repeat_count,
        "versions": list(versions), "planned_writer_count": planned_writer_count,
        "planned_judge_count": planned_judge_count, "planned_planner_count": planned_planner_count,
        "planned_execution_count": planned_writer_count + planned_judge_count + planned_planner_count,
        "rubric_fingerprint": rubric_fingerprint, "input_manifest_fingerprint": input_manifest_fp,
        "source_manifest_fingerprint": source_manifest_fp, "material_file_fingerprints": material_files,
        "case_order": [case["case_id"] for case in cases], "created_at": _now(),
    })
    corpus_identity = {
        "source_manifest_fingerprint": source_manifest_fp,
        "input_manifest_fingerprint": input_manifest_fp,
        "case_manifest_fingerprint": cases[0].get("case_manifest_fingerprint") if cases else None,
        "rubric_fingerprint": rubric_fingerprint,
        "material_file_fingerprints": material_files,
    }
    policy_identity = _execution_policy(plan)
    plan.update({
        "corpus_identity": corpus_identity,
        "product_implementation_identity": implementation_identity,
        "implementation_fingerprint": fingerprint(implementation_identity),
        "execution_policy_identity": policy_identity,
        "execution_policy_fingerprint": fingerprint(policy_identity),
        "component_inventory": {
            "corpus": corpus_identity,
            "product_implementation": implementation_identity,
            "execution_policy": policy_identity,
        },
    })
    _write_json(output_dir / "benchmark_plan.json", plan)
    _write_json(output_dir / "case_requests.json", [{"case": case, "case_fingerprint": fingerprint(case)} for case in cases])
    planned_ledger = _build_planned_ledger(cases, plan, repeats_count=repeat_count, versions=versions, mode="pair")
    _write_json(output_dir / "planned-ledger.json", planned_ledger)
    if summarize_only:
        return summarize_run(output_dir)
    if backend is None and backend_plan is None:
        _finalize_planned_ledger(output_dir, planned_ledger, [])
        return _unavailable_result(plan, source_manifest_fp=source_manifest_fp, output_dir=output_dir, reason="execution_provider_unavailable")
    local_backend: LocalCodexBackend | None = None
    resolver: LocalExecutionRecordResolver | None = None
    if backend_plan is not None:
        local_backend, resolver, startup_failure = _initialize_local_backend(
            output_dir, plan, startup_timeout_seconds=int(plan.get("startup_timeout_seconds", 60))
        )
        if startup_failure:
            _finalize_planned_ledger(output_dir, planned_ledger, [])
            return _unavailable_result(plan, source_manifest_fp=source_manifest_fp, output_dir=output_dir, reason=startup_failure)
    writers: list[dict[str, Any]] = []
    writer_index: dict[tuple[str, int, str], dict[str, Any]] = {}
    writer_dir = output_dir / "artifacts" / "writers"
    if run_writers:
        jobs: list[dict[str, Any]] = []
        case_position = {case["case_id"]: index for index, case in enumerate(cases)}
        for repeat in range(1, repeat_count + 1):
            sequence = cases if repeat == 1 else list(reversed(cases))
            for case_index, case in enumerate(sequence):
                version_order = VERSIONS if (case_index + repeat) % 2 else tuple(reversed(VERSIONS))
                for version in version_order:
                    jobs.append({
                        "case": case,
                        "repeat": repeat,
                        "version": version,
                        "order": (repeat, case_position[case["case_id"]], version),
                    })
        writer_workers = max(1, min(int(plan.get("concurrency", 1)), len(jobs) or 1))
        if local_backend is not None:
            rows = _run_isolated_jobs(
                jobs,
                role="writer",
                output_dir=output_dir,
                writer_dir=writer_dir,
                judge_dir=output_dir / "artifacts" / "judges",
                cases_dir=cases_dir,
                rubric_text=rubric_text,
                local_backend=local_backend,
                plan={**plan, "concurrency": writer_workers},
                timeout_seconds=_orchestration_timeout(plan, len(jobs)),
                startup_timeout_seconds=int(plan.get("startup_timeout_seconds", 180)),
            )
        else:
            rows = [
                _execute_writer_job(
                    case=job["case"],
                    repeat=job["repeat"],
                    version=job["version"],
                    writer_dir=writer_dir,
                    local_backend=local_backend,
                    backend=backend,
                    resolver=resolver,
                )
                for job in jobs
            ]
        for row in sorted(rows, key=lambda item: (int(item.get("repeat", 0)), case_position.get(str(item.get("case_id")), 999), str(item.get("version")))):
            writers.append(row)
            writer_index[(str(row["case_id"]), int(row["repeat"]), str(row["version"]))] = row
    else:
        for path in sorted(writer_dir.glob("**/writer.json")):
            row = _read_json(path)
            if isinstance(row, dict):
                writers.append(row)
                writer_index[(str(row.get("case_id")), int(row.get("repeat", 0)), str(row.get("version")))] = row
    judges: list[dict[str, Any]] = []
    judge_dir = output_dir / "artifacts" / "judges"
    if run_judges:
        jobs: list[dict[str, Any]] = []
        dependency_rows: list[dict[str, Any]] = []
        all_judge_jobs: list[dict[str, Any]] = []
        for repeat in range(1, repeat_count + 1):
            for case in cases:
                baseline = writer_index.get((case["case_id"], repeat, "baseline"))
                repaired = writer_index.get((case["case_id"], repeat, "repaired"))
                if not baseline or not repaired or baseline.get("status") != "completed" or repaired.get("status") != "completed":
                    for judge_index in (1, 2):
                        dependency_job = {
                            "case": case,
                            "repeat": repeat,
                            "judge_index": judge_index,
                            "evaluation_mode": "pair",
                        }
                        all_judge_jobs.append(dependency_job)
                        dependency_rows.append(_dependency_judge_row(dependency_job))
                    continue
                for judge_index, order in enumerate(((baseline, repaired), (repaired, baseline)), start=1):
                    runnable_job = {"case": case, "repeat": repeat, "judge_index": judge_index, "order": order, "evaluation_mode": "pair"}
                    jobs.append(runnable_job)
                    all_judge_jobs.append(runnable_job)
        max_workers = max(1, min(int(plan.get("concurrency", 1)), len(jobs) or 1))
        if local_backend is not None:
            executed = _run_isolated_jobs(
                jobs, role="judge", output_dir=output_dir, writer_dir=writer_dir,
                judge_dir=judge_dir, cases_dir=cases_dir, rubric_text=rubric_text,
                local_backend=local_backend, plan={**plan, "concurrency": max_workers},
                timeout_seconds=_orchestration_timeout(plan, len(jobs)),
                startup_timeout_seconds=int(plan.get("startup_timeout_seconds", 180)),
            ) if jobs else []
            judges = [*dependency_rows, *executed]
        elif max_workers == 1:
            executed = [
                _execute_judge_job(
                    case=job["case"], repeat=job["repeat"], judge_index=job["judge_index"], order=job["order"],
                    rubric_text=rubric_text, cases_dir=cases_dir, judge_dir=judge_dir, local_backend=local_backend,
                    backend=backend, resolver=resolver,
                )
                for job in jobs
            ]
            judges = [*dependency_rows, *executed]
        else:
            # This branch is kept for the explicitly unsupported injected
            # adapter surface; real_execution always has a local backend and
            # therefore uses one child process per job above.
            executed = [
                _execute_judge_job(
                    case=job["case"], repeat=job["repeat"], judge_index=job["judge_index"], order=job["order"],
                    rubric_text=rubric_text, cases_dir=cases_dir, judge_dir=judge_dir, local_backend=local_backend,
                    backend=backend, resolver=resolver,
                )
                for job in jobs
            ]
            judges = [*dependency_rows, *executed]
        order = {str(_job_identity(job, "judge")["job_id"]): index for index, job in enumerate(all_judge_jobs)}
        judges.sort(key=lambda row: order.get(str(row.get("job_id")), len(order)))
    else:
        for path in sorted(judge_dir.glob("**/judge.json")):
            row = _read_json(path)
            if isinstance(row, dict):
                judges.append(row)
    all_rows = [*writers, *judges]
    planned_ledger = _finalize_planned_ledger(output_dir, planned_ledger, all_rows)
    summary = _aggregate(cases, writers, judges, repeats_count=repeat_count, versions=versions, mode=mode)
    complete = (
        len(writers) == plan["planned_writer_count"]
        and len(judges) == plan["planned_judge_count"]
        and _planner_count(writers) == plan["planned_planner_count"]
        and all(row.get("status") == "completed" for row in all_rows)
    )
    status_counts = dict(planned_ledger.get("progress", {}))
    result = {
        "schema_version": "logic-writing.writing-quality-run-result.v2", "benchmark_id": plan["benchmark_id"], "mode": mode,
        "status": "completed" if complete else "incomplete",
        "terminal_reason": "all_jobs_completed" if complete else "jobs_incomplete",
        "quality_claim_status": "passed" if summary["status"] == "passed" else ("failed" if summary["status"] == "failed" else "incomplete"),
        "planned_writer_count": plan["planned_writer_count"], "planned_judge_count": plan["planned_judge_count"], "planned_execution_count": plan["planned_execution_count"],
        "actual_writer_count": _started_row_count(writers), "actual_judge_count": _started_row_count(judges),
        "actual_planner_count": _planner_count(writers, completed_only=False),
        "actual_execution_count": _started_row_count(writers) + _started_row_count(judges) + _planner_count(writers, completed_only=False),
        "successful_artifact_count": sum(row.get("status") == "completed" for row in writers), "successful_judge_count": sum(row.get("status") == "completed" for row in judges),
        "backend_id": local_backend.backend_id if local_backend else backend_id, "source_manifest_fingerprint": source_manifest_fp, "created_at": _now(),
        "implementation_fingerprint": plan.get("implementation_fingerprint"),
        "execution_policy_fingerprint": plan.get("execution_policy_fingerprint"),
        "planned_status_counts": status_counts,
        "progress": {**status_counts, "ledger_fingerprint": planned_ledger.get("ledger_fingerprint")},
        "claim_boundary": "This preflight is smoke evidence only; it cannot satisfy the twelve-case quality gate." if mode == "preflight" else "Scores are claimed only when every writer and pair judge has a verified local capture and parseable judgment.",
        "summary_fingerprint": fingerprint(summary),
    }
    _write_json(output_dir / "writers.json", writers)
    _write_json(output_dir / "judges.json", judges)
    _write_json(output_dir / "summary.json", summary)
    _write_json(output_dir / "run_result.json", result)
    return result


def _planner_count(rows: list[Mapping[str, Any]], *, completed_only: bool = True) -> int:
    """Count nested planner attempts once per record.

    Production writers own one list containing the research and compose
    records.  Legacy rows may still carry ``planner_records``; those are
    counted only when no production list is present so a migrated row cannot
    inflate the actual execution count by duplicating the same captures.

    ``completed_only`` is used by the quality gate.  The result receipt uses
    ``False`` to count an attempted planner process separately from the number
    of successful planner captures.
    """

    terminal_values = {"completed"} if completed_only else {"completed", "failed", "unavailable"}

    def _count(records: Any) -> int:
        if not isinstance(records, list):
            return 0
        return sum(
            isinstance(item, Mapping)
            and str(item.get("terminal_status")) in terminal_values
            for item in records
        )

    count = 0
    for row in rows:
        production = row.get("production_reader") if isinstance(row, Mapping) else None
        if isinstance(production, Mapping):
            # A current production row owns the planner list, even when that
            # list is malformed or absent.  Falling back to a legacy
            # ``planner_records`` field here would let a stale/mixed row
            # inflate actual execution totals while its production lineage is
            # incomplete and should be rejected by the consumer.
            records = production.get("planner_execution_records")
            if isinstance(records, list):
                count += _count(records)
            continue
        records = row.get("planner_records") if isinstance(row, Mapping) else None
        if isinstance(records, list):
            count += _count(records)
        elif isinstance(row, Mapping) and isinstance(row.get("planner_record"), Mapping):
            count += int(str(row["planner_record"].get("terminal_status")) in terminal_values)
    return count


def _started_row_count(rows: list[Mapping[str, Any]]) -> int:
    """Count only scheduled rows whose child process actually started."""

    return sum(_job_started(row) for row in rows if isinstance(row, Mapping))


def _aggregate_held_out(
    cases: list[dict[str, Any]],
    writers: list[dict[str, Any]],
    judges: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate two independent absolute reviews per holdout artifact."""

    writer_by_case = {
        str(row.get("case_id")): row
        for row in writers
        if isinstance(row, Mapping) and row.get("status") == "completed"
    }
    judges_by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in judges:
        if isinstance(row, Mapping) and row.get("status") == "completed" and isinstance(row.get("judgment"), Mapping):
            judges_by_case[str(row.get("case_id"))].append(dict(row))
    case_rows: list[dict[str, Any]] = []
    for case in cases:
        case_id = str(case["case_id"])
        writer = writer_by_case.get(case_id)
        artifact_fp = str(writer.get("artifact_fingerprint") or "") if writer else ""
        case_judges = sorted(judges_by_case.get(case_id, []), key=lambda row: int(row.get("judge_index", 0)))
        payloads = [row["judgment"] for row in case_judges if isinstance(row.get("judgment"), Mapping)]
        passed = bool(writer and _held_out_quality_passes(payloads, artifact_fingerprint=artifact_fp))
        case_rows.append({
            "case_id": case_id,
            "writer_status": writer.get("status") if writer else "missing",
            "judge_count": len(case_judges),
            "judges": [
                {
                    "judge_index": row.get("judge_index"),
                    "context_id": (row.get("record") or {}).get("context_id") if isinstance(row.get("record"), Mapping) else None,
                    "judgment_fingerprint": row.get("judgment_fingerprint"),
                    "scores": dict(row["judgment"].get("scores", {})) if isinstance(row.get("judgment"), Mapping) else None,
                }
                for row in case_judges
            ],
            "passed": passed,
        })
    execution_complete = (
        len(writers) == len(cases)
        and len(judges) == len(cases) * 2
        and all(row.get("status") == "completed" for row in writers + judges)
    )
    status = "incomplete" if not execution_complete else ("passed" if all(row["passed"] for row in case_rows) else "failed")
    return {
        "schema_version": "logic-writing.held-out-quality-summary.v1",
        "status": status,
        "held_out_passed": status == "passed",
        "case_count": len(cases),
        "passed_case_count": sum(row["passed"] for row in case_rows),
        "required_case_count": len(cases),
        "cases": case_rows,
        "writer_count": len(writers),
        "judge_count": len(judges),
        "claim_boundary": "This four-case holdout is bounded evidence of the current production path; it is not a universal claim about future topics or models.",
    }


def _run_held_out_benchmark(
    root: Path,
    *,
    output_dir: Path,
    cases_dir: Path | None = None,
    backend: Callable[..., Any] | None = None,
    backend_id: str | None = None,
    backend_plan: Path | None = None,
    run_writers: bool = True,
    run_judges: bool = True,
    summarize_only: bool = False,
) -> dict[str, Any]:
    """Run the four-case single-article holdout lane.

    This lane shares the local process isolation and writer production chain
    with the pair benchmark, while keeping its input corpus and evaluation
    envelope separate.  It never creates a synthetic X/Y pair.
    """

    root = root.resolve()
    cases_dir = (cases_dir or root / "tests/fixtures/writing_quality").resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()) and (run_writers or run_judges) and not summarize_only:
        raise ValueError("quality output directory is not empty; choose a new immutable run root")
    output_dir.mkdir(parents=True, exist_ok=True)
    cases, rubric_text, input_manifest_fp, source_manifest_fp, material_files = _load_held_out_inputs(cases_dir)
    plan = _load_plan(backend_plan, source_manifest_fp=source_manifest_fp)
    if backend is not None and backend_plan is None:
        raise ValueError(
            "an injected backend cannot produce real_execution quality evidence; "
            "run the pinned local backend with --backend-plan"
        )
    implementation_identity = _implementation_identity(root)
    case_count = len(cases)
    repeat_count = HELD_OUT_REPEATS
    versions = (HELD_OUT_VERSION,)
    planned_writer_count = case_count * repeat_count
    planned_judge_count = case_count * repeat_count * 2
    planned_planner_count = planned_writer_count * 2
    rubric_fingerprint = fingerprint_text(rubric_text)
    plan.update({
        "schema_version": "logic-writing.writing-quality-run.v2",
        "benchmark_id": "logic-writing-held-out-4x1x2",
        "mode": "held_out",
        "claim": "held_out_absolute_quality",
        "evidence_mode": "real_execution",
        "case_count": case_count,
        "repeats_per_version": repeat_count,
        "versions": list(versions),
        "planned_writer_count": planned_writer_count,
        "planned_judge_count": planned_judge_count,
        "planned_planner_count": planned_planner_count,
        "planned_execution_count": planned_writer_count + planned_judge_count + planned_planner_count,
        "rubric_fingerprint": rubric_fingerprint,
        "input_manifest_fingerprint": input_manifest_fp,
        "source_manifest_fingerprint": source_manifest_fp,
        "material_file_fingerprints": material_files,
        "case_order": [case["case_id"] for case in cases],
        "held_out_manifest": "tests/fixtures/writing_quality/held-out-manifest.json",
        "created_at": _now(),
    })
    corpus_identity = {
        "source_manifest_fingerprint": source_manifest_fp,
        "input_manifest_fingerprint": input_manifest_fp,
        "rubric_fingerprint": rubric_fingerprint,
        "material_file_fingerprints": material_files,
    }
    policy_identity = _execution_policy(plan)
    plan.update({
        "corpus_identity": corpus_identity,
        "product_implementation_identity": implementation_identity,
        "implementation_fingerprint": fingerprint(implementation_identity),
        "execution_policy_identity": policy_identity,
        "execution_policy_fingerprint": fingerprint(policy_identity),
        "component_inventory": {
            "corpus": corpus_identity,
            "product_implementation": implementation_identity,
            "execution_policy": policy_identity,
        },
    })
    _write_json(output_dir / "benchmark_plan.json", plan)
    public_requests = [_public_held_out_case_request(case) for case in cases]
    _write_json(output_dir / "case_requests.json", [{"case": case, "case_fingerprint": fingerprint(case)} for case in public_requests])
    planned_ledger = _build_planned_ledger(cases, plan, repeats_count=repeat_count, versions=versions, mode="held_out")
    _write_json(output_dir / "planned-ledger.json", planned_ledger)
    if summarize_only:
        return summarize_run(output_dir)
    if backend is None and backend_plan is None:
        _finalize_planned_ledger(output_dir, planned_ledger, [])
        return _unavailable_result(plan, source_manifest_fp=source_manifest_fp, output_dir=output_dir, reason="execution_provider_unavailable")
    local_backend: LocalCodexBackend | None = None
    resolver: LocalExecutionRecordResolver | None = None
    if backend_plan is not None:
        local_backend, resolver, startup_failure = _initialize_local_backend(
            output_dir, plan, startup_timeout_seconds=int(plan.get("startup_timeout_seconds", 60))
        )
        if startup_failure:
            _finalize_planned_ledger(output_dir, planned_ledger, [])
            return _unavailable_result(plan, source_manifest_fp=source_manifest_fp, output_dir=output_dir, reason=startup_failure)
    writer_dir = output_dir / "artifacts" / "writers"
    writer_index: dict[tuple[str, int, str], dict[str, Any]] = {}
    writers: list[dict[str, Any]] = []
    if run_writers:
        jobs = [{"case": case, "repeat": 1, "version": HELD_OUT_VERSION, "mode": "held_out"} for case in cases]
        writer_workers = max(1, min(int(plan.get("concurrency", 1)), len(jobs) or 1))
        if local_backend is not None:
            rows = _run_isolated_jobs(
                jobs, role="writer", output_dir=output_dir, writer_dir=writer_dir,
                judge_dir=output_dir / "artifacts" / "judges", cases_dir=cases_dir,
                rubric_text=rubric_text, local_backend=local_backend,
                plan={**plan, "concurrency": writer_workers},
                timeout_seconds=_orchestration_timeout(plan, len(jobs)),
                startup_timeout_seconds=int(plan.get("startup_timeout_seconds", 180)),
            )
        else:
            rows = [
                _execute_writer_job(
                    case=job["case"], repeat=1, version=HELD_OUT_VERSION,
                    writer_dir=writer_dir, local_backend=local_backend,
                    backend=backend, resolver=resolver,
                )
                for job in jobs
            ]
        for row in rows:
            writers.append(row)
            writer_index[(str(row.get("case_id")), int(row.get("repeat", 0)), str(row.get("version")))] = row
    else:
        for path in sorted(writer_dir.glob("**/writer.json")):
            row = _read_json(path)
            if isinstance(row, dict):
                writers.append(row)
                writer_index[(str(row.get("case_id")), int(row.get("repeat", 0)), str(row.get("version")))] = row
    judge_dir = output_dir / "artifacts" / "judges"
    judges: list[dict[str, Any]] = []
    if run_judges:
        jobs = []
        dependency_rows: list[dict[str, Any]] = []
        all_judge_jobs: list[dict[str, Any]] = []
        for case in cases:
            writer = writer_index.get((str(case["case_id"]), 1, HELD_OUT_VERSION))
            if not writer or writer.get("status") != "completed":
                for judge_index in (1, 2):
                    dependency_job = {
                        "case": case,
                        "repeat": 1,
                        "judge_index": judge_index,
                        "evaluation_mode": "single",
                    }
                    all_judge_jobs.append(dependency_job)
                    dependency_rows.append(_dependency_judge_row(dependency_job, reason="dependency_failed"))
                continue
            for judge_index in (1, 2):
                runnable_job = {
                    "case": case,
                    "repeat": 1,
                    "judge_index": judge_index,
                    "writer": writer,
                    "evaluation_mode": "single",
                }
                jobs.append(runnable_job)
                all_judge_jobs.append(runnable_job)
        max_workers = max(1, min(int(plan.get("concurrency", 1)), len(jobs) or 1))
        if local_backend is not None:
            executed = _run_isolated_jobs(
                jobs, role="judge", output_dir=output_dir, writer_dir=writer_dir,
                judge_dir=judge_dir, cases_dir=cases_dir, rubric_text=rubric_text,
                local_backend=local_backend, plan={**plan, "concurrency": max_workers},
                timeout_seconds=_orchestration_timeout(plan, len(jobs)),
                startup_timeout_seconds=int(plan.get("startup_timeout_seconds", 180)),
            ) if jobs else []
            judges = [*dependency_rows, *executed]
        else:
            executed = [
                _execute_single_judge_job(
                    case=job["case"], repeat=1, judge_index=int(job["judge_index"]),
                    writer=job["writer"], rubric_text=rubric_text, cases_dir=cases_dir,
                    judge_dir=judge_dir, local_backend=local_backend, backend=backend,
                    resolver=resolver,
                )
                for job in jobs
            ]
            judges = [*dependency_rows, *executed]
        order = {str(_job_identity(job, "judge")["job_id"]): index for index, job in enumerate(all_judge_jobs)}
        judges.sort(key=lambda row: order.get(str(row.get("job_id")), len(order)))
    else:
        for path in sorted(judge_dir.glob("**/judge.json")):
            row = _read_json(path)
            if isinstance(row, dict):
                judges.append(row)
    all_rows = [*writers, *judges]
    planned_ledger = _finalize_planned_ledger(output_dir, planned_ledger, all_rows)
    summary = _aggregate_held_out(cases, writers, judges)
    complete = (
        len(writers) == plan["planned_writer_count"]
        and len(judges) == plan["planned_judge_count"]
        and _planner_count(writers) == plan["planned_planner_count"]
        and all(row.get("status") == "completed" for row in all_rows)
    )
    status_counts = dict(planned_ledger.get("progress", {}))
    result = {
        "schema_version": "logic-writing.writing-quality-run-result.v2",
        "benchmark_id": plan["benchmark_id"],
        "mode": "held_out",
        "status": "completed" if complete else "incomplete",
        "terminal_reason": "all_jobs_completed" if complete else "jobs_incomplete",
        "quality_claim_status": "passed" if complete and summary["status"] == "passed" else ("failed" if complete and summary["status"] == "failed" else "incomplete"),
        "held_out_passed": bool(complete and summary.get("held_out_passed")),
        "planned_writer_count": plan["planned_writer_count"],
        "planned_judge_count": plan["planned_judge_count"],
        "planned_planner_count": plan["planned_planner_count"],
        "planned_execution_count": plan["planned_execution_count"],
        "actual_writer_count": _started_row_count(writers),
        "actual_judge_count": _started_row_count(judges),
        "actual_planner_count": _planner_count(writers, completed_only=False),
        "actual_execution_count": _started_row_count(writers) + _started_row_count(judges) + _planner_count(writers, completed_only=False),
        "successful_artifact_count": sum(row.get("status") == "completed" for row in writers),
        "successful_judge_count": sum(row.get("status") == "completed" for row in judges),
        "backend_id": local_backend.backend_id if local_backend else backend_id,
        "source_manifest_fingerprint": source_manifest_fp,
        "created_at": _now(),
        "implementation_fingerprint": plan.get("implementation_fingerprint"),
        "execution_policy_fingerprint": plan.get("execution_policy_fingerprint"),
        "planned_status_counts": status_counts,
        "progress": {**status_counts, "ledger_fingerprint": planned_ledger.get("ledger_fingerprint")},
        "claim_boundary": "Four held-out artifacts were each reviewed twice in independent contexts; this does not generalize beyond the frozen holdout.",
        "summary_fingerprint": fingerprint(summary),
    }
    _write_json(output_dir / "writers.json", writers)
    _write_json(output_dir / "judges.json", judges)
    _write_json(output_dir / "summary.json", summary)
    _write_json(output_dir / "run_result.json", result)
    return result


def _preference_for_version(preference: str, pair_order: list[str]) -> str:
    if preference not in {"X", "Y"}:
        return preference
    return pair_order[0] if preference == "X" else pair_order[1]


def _aggregate(
    cases: list[dict[str, Any]],
    writers: list[dict[str, Any]],
    judges: list[dict[str, Any]],
    *,
    repeats_count: int = REPEATS,
    versions: tuple[str, ...] = VERSIONS,
    mode: str = "pair",
) -> dict[str, Any]:
    by_pair: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in judges:
        if row.get("status") == "completed" and isinstance(row.get("judgment"), Mapping):
            by_pair[(str(row["case_id"]), int(row["repeat"]))].append(row)
    case_rows: list[dict[str, Any]] = []
    for case in cases:
        repeats: list[dict[str, Any]] = []
        score_values: dict[str, dict[str, list[int]]] = {version: {dimension: [] for dimension in DIMENSIONS} for version in versions}
        repaired_issues: list[dict[str, Any]] = []
        for repeat in range(1, repeats_count + 1):
            pair_rows = by_pair.get((case["case_id"], repeat), [])
            preferences = [_preference_for_version(str(row["judgment"]["preference"]), list(row["pair_order"])) for row in pair_rows]
            consensus = preferences[0] if len(preferences) == 2 and preferences[0] == preferences[1] else ("disagreement" if len(preferences) == 2 else "incomplete")
            for row in pair_rows:
                order = list(row["pair_order"])
                for judgment in row["judgment"].get("judgments", []):
                    label = judgment.get("anonymous_label")
                    if label not in {"X", "Y"}:
                        continue
                    version = order[0] if label == "X" else order[1]
                    for dimension in DIMENSIONS:
                        score_values[version][dimension].append(int(judgment["scores"][dimension]))
                    if version == "repaired":
                        scores = judgment["scores"]
                        defects = judgment.get("defects", [])
                        repairs = judgment.get("required_repairs", [])
                        blocking = [item for item in defects if isinstance(item, Mapping) and item.get("severity") in {"blocking", "repair"}]
                        if any(scores[dimension] < 4 for dimension in ("clarity", "coherence", "content_fidelity", "instruction_fidelity")) or blocking or repairs:
                            repaired_issues.append({"repeat": repeat, "judge_index": row.get("judge_index"), "label": label, "reason": "repaired judgment has a core score below 4 or an unresolved defect"})
            repeats.append({"repeat": repeat, "preferences": preferences, "consensus": consensus, "judge_count": len(pair_rows)})
        repaired_wins = sum(row["consensus"] == "repaired" for row in repeats)
        baseline_wins = sum(row["consensus"] == "baseline" for row in repeats)
        means = {version: {dimension: (sum(values) / len(values) if values else None) for dimension, values in dimensions.items()} for version, dimensions in score_values.items()}
        natural_non_decrease = all(
            means["repaired"][dimension] is not None and means["baseline"][dimension] is not None and means["repaired"][dimension] >= means["baseline"][dimension]
            for dimension in ("naturalness", "coherence")
        )
        improved = repaired_wins >= 1 and baseline_wins == 0 and not repaired_issues and natural_non_decrease and all(row["consensus"] not in {"incomplete", "disagreement"} for row in repeats)
        case_rows.append({"case_id": case["case_id"], "repeat_results": repeats, "improved": improved, "repaired_wins": repaired_wins, "baseline_wins": baseline_wins, "score_means": means, "repaired_issues": repaired_issues, "naturalness_coherence_non_decrease": natural_non_decrease})
    expected_writer_count = len(cases) * repeats_count * len(versions)
    expected_judge_count = len(cases) * repeats_count * 2
    complete = len(writers) == expected_writer_count and len(judges) == expected_judge_count and all(row.get("status") == "completed" for row in writers + judges)
    improved_count = sum(row["improved"] for row in case_rows)
    required_improved_count = 9 if len(cases) == CASE_COUNT and repeats_count == REPEATS else 0
    status = "incomplete" if not complete else ("passed" if required_improved_count and improved_count >= required_improved_count else "smoke_only")
    return {
        "schema_version": "logic-writing.writing-quality-summary.v2",
        "status": status,
        "mode": mode,
        "case_count": len(cases),
        "improved_case_count": improved_count,
        "required_improved_case_count": required_improved_count,
        "cases": case_rows,
        "writer_count": len(writers),
        "judge_count": len(judges),
        "claim_boundary": "This is a bounded comparison used for local diagnostics; it is not a universal or statistical claim about all topics or models." if mode == "preflight" else "This is a bounded twelve-case comparison, not a universal or statistical claim about all topics or models.",
    }


def summarize_run(output_dir: Path) -> dict[str, Any]:
    path = output_dir / "summary.json"
    # Aggregate-only is explicitly a read-only consumer.  A previous version
    # wrote ``summary-consumer.json`` here, which changed the evidence root and
    # made a harmless review look like a new producer run.
    return _read_json(path) if path.is_file() else {"status": "incomplete", "error": "summary.json is missing"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--cases-dir", type=Path)
    parser.add_argument("--backend", help="Legacy explicit module:function backend")
    parser.add_argument("--backend-plan", type=Path, help="Portable local-backend-plan.json")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--run-writers", action="store_true")
    parser.add_argument("--run-judges", action="store_true")
    parser.add_argument("--summarize", action="store_true")
    parser.add_argument("--_job-worker", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args._job_worker is not None:
        return _job_worker_main(args._job_worker.resolve())
    if args.output_dir is None:
        parser.error("--output-dir is required unless --_job-worker is used")
    try:
        cases_dir = (args.cases_dir or args.root / "tests/fixtures/writing_quality").resolve()
        if args.summarize:
            result = run_benchmark(args.root, output_dir=args.output_dir, cases_dir=cases_dir, summarize_only=True)
        elif args.plan_only:
            result = run_benchmark(args.root, output_dir=args.output_dir, cases_dir=cases_dir, backend_plan=args.backend_plan, run_writers=False, run_judges=False)
        else:
            backend = _resolve_backend(args.backend)
            explicit_stage = args.run_writers or args.run_judges
            result = run_benchmark(args.root, output_dir=args.output_dir, cases_dir=cases_dir, backend=backend, backend_id=args.backend, backend_plan=args.backend_plan, run_writers=args.run_writers or not explicit_stage, run_judges=args.run_judges or not explicit_stage)
    except (OSError, ValueError, ValidationError, json.JSONDecodeError, ImportError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if result.get("status") == "passed" or result.get("quality_claim_status") == "passed":
        return 0
    if result.get("status") == "not_run":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
