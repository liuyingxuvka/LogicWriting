from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_writing_quality_benchmark as benchmark


class FakeBackend:
    run_root = Path("C:/fake-quality-attempts")
    executable = Path("C:/fake/codex.exe")
    model_id = "gpt-6-astra"
    reasoning_effort = "xhigh"
    timeout_seconds = 1
    no_progress_seconds = 0
    cli_version = "0.153.4"
    executable_sha256 = "a" * 64


def _jobs(count: int) -> list[dict[str, object]]:
    return [
        {"case": {"case_id": f"I0{index}"}, "repeat": 1, "version": "baseline"}
        for index in range(1, count + 1)
    ]


def _plan(**overrides):
    return {"concurrency": 1, "timeout_seconds": 1, **overrides}


def test_summarize_only_reads_without_materializing_a_plan(tmp_path, monkeypatch):
    output_dir = tmp_path / "existing-run"
    output_dir.mkdir()
    summary = {"status": "incomplete", "case_count": 0}
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary) + "\n", encoding="utf-8")
    before = (summary_path.read_bytes(), summary_path.stat().st_mtime_ns)

    def should_not_load_inputs(*args, **kwargs):
        raise AssertionError("summary-only mode must not materialize benchmark inputs")

    monkeypatch.setattr(benchmark, "_load_frozen_inputs", should_not_load_inputs)
    result = benchmark.run_benchmark(
        tmp_path,
        output_dir=output_dir,
        backend_plan=tmp_path / "missing-plan.json",
        summarize_only=True,
    )

    assert result == summary
    assert (summary_path.read_bytes(), summary_path.stat().st_mtime_ns) == before
    assert not (output_dir / "benchmark_plan.json").exists()


def test_atomic_json_publication_retries_transient_access_denied(tmp_path, monkeypatch):
    target = tmp_path / "progress.json"
    real_replace = benchmark.os.replace
    attempts = 0

    def flaky_replace(source, destination):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError(5, "access denied", str(destination))
        return real_replace(source, destination)

    monkeypatch.setattr(benchmark.os, "replace", flaky_replace)
    benchmark._write_json_atomic(target, {"status": "running"})

    assert attempts == 3
    assert json.loads(target.read_text(encoding="utf-8")) == {"status": "running"}


def test_job_failure_rows_carry_identity_and_cleanup_gate():
    row = benchmark._job_row(_jobs(1)[0], "writer", status="not_started_deadline", terminal_reason="batch_deadline")
    assert row["job_id"] == "writer:I01:1:baseline"
    assert row["role"] == "writer"
    assert row["status"] == "not_started_deadline"
    assert row["process_id"] is None
    assert row["process_creation_time"] is None
    assert row["cleanup_confirmed"] is False
    assert row["cleanup_evidence"]["required"] is True
    assert row["error_event"]["job_id"] == row["job_id"]


def test_isolated_jobs_reject_duplicate_identity_before_dispatch(monkeypatch, tmp_path):
    monkeypatch.setattr(
        benchmark.subprocess,
        "Popen",
        lambda *args, **kwargs: pytest.fail("duplicate jobs must be rejected before Popen"),
    )
    with pytest.raises(Exception, match="duplicate writer job identity"):
        benchmark._run_isolated_jobs(
            [_jobs(1)[0], _jobs(1)[0]],
            role="writer",
            output_dir=tmp_path,
            writer_dir=tmp_path / "artifacts" / "writers",
            judge_dir=tmp_path / "artifacts" / "judges",
            cases_dir=tmp_path,
            rubric_text="fake rubric",
            local_backend=FakeBackend(),
            plan=_plan(),
            timeout_seconds=1,
            startup_timeout_seconds=1,
        )


def test_isolated_jobs_never_submit_queued_work_after_batch_deadline(monkeypatch, tmp_path):
    calls: list[list[str]] = []
    cleanup_creation_times: list[str | None] = []

    class NeverExits:
        pid = 9021
        returncode = None

        def poll(self):
            return None

    def fake_popen(argv, **kwargs):
        calls.append(list(argv))
        return NeverExits()

    monkeypatch.setattr(benchmark.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        benchmark,
        "_terminate_process_tree",
        lambda process, process_group_id=None, root_creation_time=None: (
            cleanup_creation_times.append(root_creation_time)
            or {
                "required": True,
                "confirmed": True,
                "root_pid": process.pid,
                "root_creation_time": root_creation_time,
                "process_group_id": process_group_id,
                "termination_method": "fake",
            }
        ),
    )
    jobs = _jobs(3)
    rows = benchmark._run_isolated_jobs(
        jobs,
        role="writer",
        output_dir=tmp_path,
        writer_dir=tmp_path / "artifacts" / "writers",
        judge_dir=tmp_path / "artifacts" / "judges",
        cases_dir=tmp_path,
        rubric_text="fake rubric",
        local_backend=FakeBackend(),
        plan=_plan(concurrency=1),
        timeout_seconds=1,
        startup_timeout_seconds=30,
    )
    assert len(calls) == 1
    assert [row["status"] for row in rows] == ["timed_out", "not_started_deadline", "not_started_deadline"]
    assert rows[0]["terminal_reason"] == "batch_deadline"
    assert rows[0]["cleanup_confirmed"] is True
    assert rows[0]["process_id"] == 9021
    assert cleanup_creation_times == [rows[0]["process_creation_time"]]
    assert all(row["job_id"].startswith("writer:") for row in rows)


def test_isolated_job_start_failure_is_not_started_dependency_failure(monkeypatch, tmp_path):
    def fail(*args, **kwargs):
        raise OSError("fake child start failure")

    monkeypatch.setattr(benchmark.subprocess, "Popen", fail)
    rows = benchmark._run_isolated_jobs(
        _jobs(1),
        role="writer",
        output_dir=tmp_path,
        writer_dir=tmp_path / "artifacts" / "writers",
        judge_dir=tmp_path / "artifacts" / "judges",
        cases_dir=tmp_path,
        rubric_text="fake rubric",
        local_backend=FakeBackend(),
        plan=_plan(),
        timeout_seconds=1,
        startup_timeout_seconds=1,
    )
    assert rows[0]["status"] == "not_started_dependency_failed"
    assert rows[0]["terminal_reason"] == "start_failed"
    assert rows[0]["dependency_status"] == "failed"
    assert rows[0]["process_id"] is None
    assert rows[0]["cleanup_confirmed"] is False


def test_isolated_child_dependency_failure_publishes_terminal_row(tmp_path):
    """A real worker process must leave a durable failure row before exit."""

    backend = FakeBackend()
    backend.run_root = tmp_path / "backend-captures"
    backend.executable = tmp_path / "missing-pinned-codex.exe"
    backend.executable_sha256 = "b" * 64
    rows = benchmark._run_isolated_jobs(
        _jobs(1),
        role="writer",
        output_dir=tmp_path / "quality-output",
        writer_dir=tmp_path / "quality-output" / "artifacts" / "writers",
        judge_dir=tmp_path / "quality-output" / "artifacts" / "judges",
        cases_dir=tmp_path,
        rubric_text="fake rubric",
        local_backend=backend,
        plan=_plan(),
        timeout_seconds=5,
        startup_timeout_seconds=2,
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "not_started_dependency_failed"
    assert row["terminal_reason"] == "dependency_failed"
    assert row["dependency_status"] == "failed"
    assert row["process_id"] is not None
    assert row["process_creation_time"]
    assert row["cleanup_confirmed"] is True
    assert row["cleanup_evidence"]["root_pid"] == row["process_id"]
    assert row["error_event"]["job_id"] == row["job_id"]
    assert row["error_event"]["terminal"] is True


def test_backend_cleanup_proof_survives_worker_tree_observation_gap(monkeypatch, tmp_path):
    """A completed backend record must not be relabeled as worker cleanup failure."""

    class CompletedWorker:
        pid = 7711

        def __init__(self):
            self.returncode = None
            self.poll_count = 0

        def poll(self):
            self.poll_count += 1
            if self.poll_count == 1:
                return None
            self.returncode = 0
            return 0

    worker = CompletedWorker()

    def fake_popen(argv, **kwargs):
        payload = json.loads(Path(argv[-1]).read_text(encoding="utf-8"))
        identity = benchmark._job_identity(payload["job"], payload["role"])
        benchmark._write_json_atomic(
            Path(payload["marker_path"]),
            {
                "schema_version": "logic-writing.quality-job-marker.v1",
                **identity,
                "status": "running",
                "process_id": worker.pid,
                "process_creation_time": "worker-created",
                "started_at": "worker-started",
                "role_execution_started": True,
            },
        )
        benchmark._write_json_atomic(
            Path(payload["candidate_path"]),
            {
                **benchmark._job_row(payload["job"], payload["role"], status="completed"),
                "status": "completed",
                "worker_process_id": worker.pid,
                "worker_process_creation_time": "worker-created",
                "record": {
                    "terminal_status": "completed",
                    "process_id": 8811,
                    "process_creation_time": "backend-created",
                    "descendant_cleanup_confirmed": True,
                },
            },
        )
        return worker

    monkeypatch.setattr(benchmark.subprocess, "Popen", fake_popen)
    # The worker has already exited when the aggregate parent checks its
    # descendants.  This is the Windows observation gap seen in the holdout
    # receipt; the backend record remains the authoritative child cleanup
    # proof for the CLI it actually launched.
    monkeypatch.setattr(benchmark, "_windows_descendant_pids", lambda *args, **kwargs: None)

    output_dir = tmp_path / "quality-output"
    rows = benchmark._run_isolated_jobs(
        _jobs(1),
        role="writer",
        output_dir=output_dir,
        writer_dir=output_dir / "artifacts" / "writers",
        judge_dir=output_dir / "artifacts" / "judges",
        cases_dir=tmp_path,
        rubric_text="fake rubric",
        local_backend=FakeBackend(),
        plan=_plan(),
        timeout_seconds=2,
        startup_timeout_seconds=2,
    )

    row = rows[0]
    assert row["status"] == "completed"
    assert row["cleanup_confirmed"] is True
    assert row["cleanup_evidence"]["worker_cleanup_confirmed"] is False
    assert row["cleanup_evidence"]["backend_cleanup_confirmed"] is True
    assert row["cleanup_evidence"]["confirmation_source"] == "backend_execution_record"
    assert row["cleanup_evidence"]["backend_process_id"] == 8811


def test_benchmark_source_has_no_thread_pool_final_isolation():
    source = Path(benchmark.__file__).read_text(encoding="utf-8")
    assert "ThreadPoolExecutor" not in source
    assert "_run_isolated_jobs" in source


def test_job_transition_rejects_illegal_and_duplicate_terminal_states():
    row = benchmark._job_row(_jobs(1)[0], "writer")
    benchmark._job_transition(row, "starting")
    benchmark._job_transition(row, "running")
    benchmark._job_transition(row, "failed", reason="nonzero_exit")
    with pytest.raises(Exception, match="duplicate terminal"):
        benchmark._job_transition(row, "failed", reason="late_result")
    with pytest.raises(Exception, match="late job transition"):
        benchmark._job_transition(row, "completed")


def test_cleanup_failure_stops_pending_jobs_and_writes_state_receipts(monkeypatch, tmp_path):
    class NeverExits:
        pid = 9022
        returncode = None

        def poll(self):
            return None

    monkeypatch.setattr(benchmark.subprocess, "Popen", lambda *args, **kwargs: NeverExits())
    monkeypatch.setattr(
        benchmark,
        "_terminate_process_tree",
        lambda process, process_group_id=None, root_creation_time=None: {
            "required": True,
            "confirmed": False,
            "root_pid": process.pid,
            "root_creation_time": root_creation_time,
            "process_group_id": process_group_id,
            "termination_method": "fake",
            "error": "descendant remains",
        },
    )
    output_dir = tmp_path / "quality-output"
    rows = benchmark._run_isolated_jobs(
        _jobs(3), role="writer", output_dir=output_dir,
        writer_dir=output_dir / "artifacts" / "writers",
        judge_dir=output_dir / "artifacts" / "judges", cases_dir=tmp_path,
        rubric_text="fake rubric", local_backend=FakeBackend(), plan=_plan(concurrency=1),
        timeout_seconds=2, startup_timeout_seconds=30,
    )
    assert [row["status"] for row in rows] == ["timed_out", "not_started_cleanup_blocked", "not_started_cleanup_blocked"]
    assert rows[0]["terminal_reason"] == "hard_timeout"
    assert rows[0]["cleanup_confirmed"] is False
    state_path = output_dir / "job-state-events.jsonl"
    progress_path = output_dir / "progress-summary.json"
    assert state_path.is_file() and len(state_path.read_text(encoding="utf-8").splitlines()) >= 6
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    assert progress["planned"] == 3
    assert progress["not_started"] == 2


def test_terminal_failure_stops_pending_and_cancels_live_siblings(monkeypatch, tmp_path):
    """A failed child must stop the lane instead of opening another wave."""

    calls: list[int] = []
    terminated: list[int] = []

    class FakeProcess:
        def __init__(self, pid: int, fails: bool):
            self.pid = pid
            self.returncode = None
            self._fails = fails
            self._polls = 0

        def poll(self):
            self._polls += 1
            if self._fails and self._polls >= 2:
                self.returncode = 0
                return 0
            return None

    processes: list[FakeProcess] = []

    def fake_popen(argv, **kwargs):
        payload = json.loads(Path(argv[-1]).read_text(encoding="utf-8"))
        process = FakeProcess(9400 + len(processes), fails=not processes)
        processes.append(process)
        calls.append(process.pid)
        identity = benchmark._job_identity(payload["job"], payload["role"])
        benchmark._write_json_atomic(
            Path(payload["marker_path"]),
            {
                "schema_version": "logic-writing.quality-job-marker.v1",
                **identity,
                "status": "running",
                "process_id": process.pid,
                "process_creation_time": f"worker-{process.pid}",
                "started_at": "worker-started",
                "role_execution_started": True,
            },
        )
        if process._fails:
            benchmark._write_json_atomic(
                Path(payload["candidate_path"]),
                {
                    **benchmark._job_row(
                        payload["job"], payload["role"],
                        status="failed", terminal_reason="provider_failed",
                    ),
                    "worker_process_id": process.pid,
                    "worker_process_creation_time": f"worker-{process.pid}",
                },
            )
        return process

    monkeypatch.setattr(benchmark.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(benchmark, "_windows_descendant_pids", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        benchmark,
        "_terminate_process_tree",
        lambda process, process_group_id=None, root_creation_time=None: (
            terminated.append(process.pid)
            or {
                "required": True,
                "confirmed": True,
                "root_pid": process.pid,
                "root_creation_time": root_creation_time,
                "process_group_id": process_group_id,
                "termination_method": "fake_fail_fast",
            }
        ),
    )

    output_dir = tmp_path / "quality-output"
    rows = benchmark._run_isolated_jobs(
        _jobs(3), role="writer", output_dir=output_dir,
        writer_dir=output_dir / "artifacts" / "writers",
        judge_dir=output_dir / "artifacts" / "judges", cases_dir=tmp_path,
        rubric_text="fake rubric", local_backend=FakeBackend(),
        plan=_plan(concurrency=2), timeout_seconds=3, startup_timeout_seconds=3,
    )

    assert calls == [9400, 9401]
    assert terminated == [9401]
    assert [row["status"] for row in rows] == [
        "failed", "cancelled", "not_started_dependency_failed",
    ]
    assert rows[0]["terminal_reason"] == "provider_failed"
    assert rows[1]["terminal_reason"].startswith("cancelled_after_batch_stopped_after_failed_job:")
    assert rows[1]["cleanup_confirmed"] is True
    assert rows[2]["terminal_reason"].startswith("batch_stopped_after_failed_job:")
    assert rows[2]["dependency_status"] == "not_started"


def test_start_failure_stops_the_remaining_queue(monkeypatch, tmp_path):
    """A child that cannot start must not allow a later wave to launch."""

    calls: list[list[str]] = []

    def fail_start(argv, **kwargs):
        calls.append(list(argv))
        raise OSError("fake child start failure")

    monkeypatch.setattr(benchmark.subprocess, "Popen", fail_start)
    rows = benchmark._run_isolated_jobs(
        _jobs(3), role="writer", output_dir=tmp_path / "quality-output",
        writer_dir=tmp_path / "quality-output" / "artifacts" / "writers",
        judge_dir=tmp_path / "quality-output" / "artifacts" / "judges", cases_dir=tmp_path,
        rubric_text="fake rubric", local_backend=FakeBackend(),
        plan=_plan(concurrency=2), timeout_seconds=3, startup_timeout_seconds=3,
    )

    assert len(calls) == 1
    assert rows[0]["status"] == "not_started_dependency_failed"
    assert rows[0]["terminal_reason"] == "start_failed"
    assert [row["status"] for row in rows[1:]] == [
        "not_started_dependency_failed", "not_started_dependency_failed",
    ]
    assert all(
        row["terminal_reason"].startswith("batch_stopped_after_failed_job:")
        for row in rows[1:]
    )


def test_canonical_publication_failure_is_terminal_and_auditable(
    monkeypatch, tmp_path
):
    """A parent row cannot remain completed when its canonical receipt is unavailable."""

    # Stop before a child is launched so the test isolates parent-owned
    # canonical publication without touching a real process or capture.
    monkeypatch.setattr(benchmark.subprocess, "Popen", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("start")))
    monkeypatch.setattr(
        benchmark,
        "_write_json_exclusive",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("read-only capture root")),
    )

    rows = benchmark._run_isolated_jobs(
        _jobs(1),
        role="writer",
        output_dir=tmp_path / "quality-output",
        writer_dir=tmp_path / "quality-output" / "artifacts" / "writers",
        judge_dir=tmp_path / "quality-output" / "artifacts" / "judges",
        cases_dir=tmp_path,
        rubric_text="fake rubric",
        local_backend=FakeBackend(),
        plan=_plan(),
        timeout_seconds=1,
        startup_timeout_seconds=1,
    )

    row = rows[0]
    assert row["status"] == "failed"
    assert row["terminal_reason"] == "canonical_publication_failed"
    assert row["canonical_publication_status"] == "failed"
    assert row["canonical_publication_error"] == "OSError: read-only capture root"
    assert row["error_event"]["error_class"] == "canonical_publication_failed"
    assert row["error_event"]["canonical_result_path"].endswith("writer.json")
    assert row["execution_status_before_canonical_publication"] == "not_started_dependency_failed"
    assert row["status_history"][-1]["status"] == "failed"
    state = json.loads(
        (tmp_path / "quality-output" / "job-state-events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[-1]
    )
    assert state["status"] == "failed"
    assert state["canonical_publication_status"] == "failed"
    assert state["canonical_publication_error"] == "OSError: read-only capture root"


def test_canonical_publication_conflict_preserves_existing_evidence(
    monkeypatch, tmp_path
):
    """An existing canonical row is never replaced and still blocks completion."""

    output_dir = tmp_path / "quality-output"
    canonical_path = output_dir / "artifacts" / "writers" / "I01" / "1" / "baseline" / "writer.json"
    canonical_path.parent.mkdir(parents=True)
    original = '{"status":"completed","owner":"previous-run"}\n'
    canonical_path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(
        benchmark.subprocess,
        "Popen",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("start")),
    )

    rows = benchmark._run_isolated_jobs(
        _jobs(1),
        role="writer",
        output_dir=output_dir,
        writer_dir=output_dir / "artifacts" / "writers",
        judge_dir=output_dir / "artifacts" / "judges",
        cases_dir=tmp_path,
        rubric_text="fake rubric",
        local_backend=FakeBackend(),
        plan=_plan(),
        timeout_seconds=1,
        startup_timeout_seconds=1,
    )

    row = rows[0]
    assert canonical_path.read_text(encoding="utf-8") == original
    assert row["status"] == "failed"
    assert row["terminal_reason"] == "canonical_publication_failed"
    assert row["canonical_publication_error"] == "canonical_result_already_exists"
    assert row["error_event"]["error_class"] == "canonical_publication_failed"


def test_worker_marker_identity_mismatch_cannot_admit_completed_candidate(monkeypatch, tmp_path):
    class ExitsAfterProbe:
        pid = 9301

        def __init__(self):
            self.returncode = None
            self.probes = 0

        def poll(self):
            self.probes += 1
            if self.probes == 1:
                return None
            self.returncode = 0
            return 0

    worker = ExitsAfterProbe()

    def fake_popen(argv, **kwargs):
        payload = json.loads(Path(argv[-1]).read_text(encoding="utf-8"))
        identity = benchmark._job_identity(payload["job"], payload["role"])
        wrong_marker = {
            "schema_version": "logic-writing.quality-job-marker.v1",
            **identity,
            "job_id": "writer:wrong:1:baseline",
            "status": "running",
            "process_id": worker.pid,
            "process_creation_time": "worker-created",
            "started_at": "worker-started",
            "role_execution_started": False,
        }
        candidate = {
            **benchmark._job_row(payload["job"], payload["role"], status="completed"),
            "worker_process_id": worker.pid,
            "worker_process_creation_time": "worker-created",
        }
        benchmark._write_json_atomic(Path(payload["marker_path"]), wrong_marker)
        benchmark._write_json_atomic(Path(payload["candidate_path"]), candidate)
        return worker

    monkeypatch.setattr(benchmark.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(benchmark, "_windows_descendant_pids", lambda *args, **kwargs: [])
    output_dir = tmp_path / "quality-output"
    rows = benchmark._run_isolated_jobs(
        _jobs(1), role="writer", output_dir=output_dir,
        writer_dir=output_dir / "artifacts" / "writers",
        judge_dir=output_dir / "artifacts" / "judges", cases_dir=tmp_path,
        rubric_text="fake rubric", local_backend=FakeBackend(), plan=_plan(),
        timeout_seconds=2, startup_timeout_seconds=2,
    )

    row = rows[0]
    assert row["status"] == "not_started_dependency_failed"
    assert row["terminal_reason"] == "worker_marker_identity_mismatch"
    assert row["candidate_quarantined"] is True
    canonical = output_dir / "artifacts" / "writers" / "I01" / "1" / "baseline" / "writer.json"
    assert json.loads(canonical.read_text(encoding="utf-8"))["status"] == "not_started_dependency_failed"


def test_worker_candidate_identity_mismatch_is_quarantined(monkeypatch, tmp_path):
    class ExitsAfterProbe:
        pid = 9302

        def __init__(self):
            self.returncode = None
            self.probes = 0

        def poll(self):
            self.probes += 1
            if self.probes == 1:
                return None
            self.returncode = 0
            return 0

    worker = ExitsAfterProbe()

    def fake_popen(argv, **kwargs):
        payload = json.loads(Path(argv[-1]).read_text(encoding="utf-8"))
        identity = benchmark._job_identity(payload["job"], payload["role"])
        marker = {
            "schema_version": "logic-writing.quality-job-marker.v1",
            **identity,
            "status": "running",
            "process_id": worker.pid,
            "process_creation_time": "worker-created",
            "started_at": "worker-started",
            "role_execution_started": True,
        }
        candidate = {
            **benchmark._job_row(payload["job"], payload["role"], status="completed"),
            "job_id": "writer:wrong:1:baseline",
            "worker_process_id": worker.pid,
            "worker_process_creation_time": "worker-created",
        }
        benchmark._write_json_atomic(Path(payload["marker_path"]), marker)
        benchmark._write_json_atomic(Path(payload["candidate_path"]), candidate)
        return worker

    monkeypatch.setattr(benchmark.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(benchmark, "_windows_descendant_pids", lambda *args, **kwargs: [])
    output_dir = tmp_path / "quality-output"
    rows = benchmark._run_isolated_jobs(
        _jobs(1), role="writer", output_dir=output_dir,
        writer_dir=output_dir / "artifacts" / "writers",
        judge_dir=output_dir / "artifacts" / "judges", cases_dir=tmp_path,
        rubric_text="fake rubric", local_backend=FakeBackend(), plan=_plan(),
        timeout_seconds=2, startup_timeout_seconds=2,
    )

    row = rows[0]
    assert row["status"] == "failed"
    assert row["terminal_reason"] == "worker_candidate_identity_mismatch"
    assert row["candidate_quarantined"] is True
    canonical = output_dir / "artifacts" / "writers" / "I01" / "1" / "baseline" / "writer.json"
    assert json.loads(canonical.read_text(encoding="utf-8"))["status"] == "failed"


def test_worker_marker_does_not_count_provider_dispatch_before_role_record(monkeypatch, tmp_path):
    class Backend:
        run_root = tmp_path / "backend"
        cli_version = "0.154.0"
        executable_sha256 = "a" * 64
        backend_id = "fake-backend"

    payload = {
        "schema_version": "logic-writing.quality-job-payload.v1",
        "role": "writer",
        "job": {"case": {"case_id": "I01"}, "repeat": 1, "version": "baseline"},
        "row_path": str((tmp_path / "candidate.json").resolve()),
        "marker_path": str((tmp_path / "marker.json").resolve()),
        "writer_dir": str((tmp_path / "writers").resolve()),
        "judge_dir": str((tmp_path / "judges").resolve()),
        "cases_dir": str(tmp_path.resolve()),
        "rubric_text": "fake rubric",
        "backend_config": {},
        "implementation_fingerprint": None,
    }
    payload_path = tmp_path / "payload.json"
    benchmark._write_json(payload_path, payload)
    monkeypatch.setattr(benchmark, "LocalCodexBackend", lambda **kwargs: Backend())
    monkeypatch.setattr(benchmark, "LocalExecutionRecordResolver", lambda *args, **kwargs: object())
    monkeypatch.setattr(
        benchmark,
        "_execute_writer_job",
        lambda **kwargs: {"status": "failed", "role_execution_started": True},
    )

    assert benchmark._job_worker_main(payload_path) == 0
    row = json.loads((tmp_path / "candidate.json").read_text(encoding="utf-8"))
    marker = json.loads((tmp_path / "marker.json").read_text(encoding="utf-8"))
    assert marker["role_execution_started"] is False
    assert row["role_execution_started"] is False
    assert row["role_execution_started_at"] is None


def test_late_candidate_cannot_replace_parent_timeout(monkeypatch, tmp_path):
    class NeverExits:
        pid = 9303
        returncode = None

        def poll(self):
            return None

    late_written = threading.Event()
    late_threads: list[threading.Thread] = []

    def fake_popen(argv, **kwargs):
        payload = json.loads(Path(argv[-1]).read_text(encoding="utf-8"))

        def write_late_candidate():
            time.sleep(0.05)
            identity = benchmark._job_identity(payload["job"], payload["role"])
            benchmark._write_json_atomic(
                Path(payload["candidate_path"]),
                {
                    **benchmark._job_row(payload["job"], payload["role"], status="completed"),
                    **identity,
                    "worker_process_id": 9303,
                    "worker_process_creation_time": "worker-created",
                },
            )
            late_written.set()

        thread = threading.Thread(target=write_late_candidate, daemon=True)
        late_threads.append(thread)
        thread.start()
        return NeverExits()

    def terminate(process, process_group_id=None, root_creation_time=None):
        return {
            "required": True,
            "confirmed": True,
            "root_pid": process.pid,
            "root_creation_time": root_creation_time,
            "process_group_id": process_group_id,
            "termination_method": "fake",
        }

    monkeypatch.setattr(benchmark.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(benchmark, "_terminate_process_tree", terminate)
    output_dir = tmp_path / "quality-output"
    rows = benchmark._run_isolated_jobs(
        _jobs(1), role="writer", output_dir=output_dir,
        writer_dir=output_dir / "artifacts" / "writers",
        judge_dir=output_dir / "artifacts" / "judges", cases_dir=tmp_path,
        rubric_text="fake rubric", local_backend=FakeBackend(), plan=_plan(),
        timeout_seconds=1, startup_timeout_seconds=2,
    )
    assert late_written.wait(1.0)
    for thread in late_threads:
        thread.join(timeout=1.0)

    row = rows[0]
    assert row["status"] == "timed_out"
    assert row["terminal_reason"] == "batch_deadline"
    canonical = output_dir / "artifacts" / "writers" / "I01" / "1" / "baseline" / "writer.json"
    candidate = output_dir / "job-dispatch" / "writer" / "writer_I01_1_baseline.candidate-result.json"
    assert json.loads(canonical.read_text(encoding="utf-8"))["status"] == "timed_out"
    assert json.loads(candidate.read_text(encoding="utf-8"))["status"] == "completed"


def test_dependency_judge_row_preserves_planned_identity():
    row = benchmark._dependency_judge_row({"case": {"case_id": "I01"}, "repeat": 2, "judge_index": 1, "evaluation_mode": "pair"})
    assert row["job_id"] == "judge:I01:2:1"
    assert row["status"] == "not_started_dependency_failed"
    assert row["terminal_reason"] == "dependency_failed"
    assert row["process_id"] is None
    assert row["dependency_status"] == "failed"


def test_local_provider_error_event_is_preserved_in_judge_row(tmp_path):
    """A terminal provider error remains visible in the per-job receipt."""

    class ProviderErrorBackend(FakeBackend):
        def __init__(self, root: Path):
            self.run_root = root

        def settings(self):
            return {"model_id": self.model_id, "reasoning_effort": self.reasoning_effort}

        def run(self, role, request):
            assert role == "judge"
            relative_dir = Path("judge") / "judge_I01_1_1"
            capture_dir = self.run_root / relative_dir
            capture_dir.mkdir(parents=True)
            events_locator = (relative_dir / "events.jsonl").as_posix()
            benchmark._write_json(
                capture_dir / "completion.json",
                {
                    "failure_reason": "error_event",
                    "failure_detail": None,
                    "events_locator": events_locator,
                },
            )
            (capture_dir / "events.jsonl").write_text(
                json.dumps({"type": "error", "message": "stream disconnected before completion"}) + "\n",
                encoding="utf-8",
            )
            return {
                "backend_id": "fake-provider",
                "run_id": request["run_id"],
                "context_id": "ctx-judge-error",
                "parent_orchestrator_run_id": request["parent_orchestrator_run_id"],
                "model_id": self.model_id,
                "started_at": "2026-09-10T00:00:00Z",
                "finished_at": "2026-09-10T00:00:01Z",
                "terminal_status": "failed",
                "provider_completion_ref": "fake-provider:ctx-judge-error",
                "execution_capture_ref": (relative_dir / "completion.json").as_posix(),
                "completion_locator": (relative_dir / "completion.json").as_posix(),
                "events_locator": events_locator,
                "output": None,
            }

    fingerprint_value = "sha256:" + ("a" * 64)
    case = {
        "case_id": "I01",
        "route": "research",
        "language": "zh-CN",
        "task": "回答是否扩大试点",
        "constraints": "保持材料边界",
        "material_refs": [{"id": "E01", "path": "materials-a.json"}],
        "rubric_ref": "judge-rubric.md",
        "material_records": [{"id": "E01", "text": "中等负载测试结果"}],
    }
    writers = tuple(
        {
            "version": version,
            "artifact_fingerprint": fingerprint_value,
            "record": {
                "run_id": f"writer:I01:1:{version}",
                "context_id": f"ctx-{version}",
                "input_writer_input_fingerprint": fingerprint_value,
            },
            "artifact_path": f"writers/I01/1/{version}/artifact.md",
            "artifact_text": f"{version} article",
        }
        for version in ("baseline", "repaired")
    )
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    (cases_dir / "judge-rubric.md").write_text("rubric", encoding="utf-8")
    backend = ProviderErrorBackend(tmp_path / "attempts")
    judge_dir = tmp_path / "artifacts" / "judges"
    row = benchmark._execute_judge_job(
        case=case,
        repeat=1,
        judge_index=1,
        order=writers,
        rubric_text="rubric",
        cases_dir=cases_dir,
        judge_dir=judge_dir,
        local_backend=backend,
        backend=None,
        resolver=None,
    )

    assert row["status"] == "failed"
    assert row["terminal_reason"] == "error_event"
    assert row["error_event"] == {
        "type": "error_event",
        "role": "judge",
        "job_id": "judge:I01:1:1",
        "error_class": "error_event",
        "message": "stream disconnected before completion",
        "terminal": True,
        "provider_event_type": "error",
        "provider_message": "stream disconnected before completion",
    }
    persisted = json.loads((judge_dir / "I01" / "1" / "1" / "judge.json").read_text(encoding="utf-8"))
    assert persisted["error_event"]["error_class"] == "error_event"
