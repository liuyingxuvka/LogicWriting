from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

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


def test_isolated_jobs_never_submit_queued_work_after_batch_deadline(monkeypatch, tmp_path):
    calls: list[list[str]] = []

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
        lambda process, process_group_id=None: {
            "required": True,
            "confirmed": True,
            "root_pid": process.pid,
            "root_creation_time": "2026-09-09T00:00:00Z",
            "process_group_id": process_group_id,
            "termination_method": "fake",
        },
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
        lambda process, process_group_id=None: {
            "required": True,
            "confirmed": False,
            "root_pid": process.pid,
            "root_creation_time": "2026-09-09T00:00:00Z",
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
