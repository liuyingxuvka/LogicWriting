"""Static contracts for production-reader lineage and quality accounting."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
SKILL_SCRIPTS = ROOT / "skills" / "logic-writing" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))

import production_reader_pipeline as production_pipeline
import local_execution_backend as execution_backend
from build_source_unit_manifest import fingerprint_bytes


def _load(name: str):
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"logic_writing_{name}_lineage", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_planned_ledger_separates_scheduled_jobs_from_nested_planners(tmp_path):
    benchmark = _load("run_writing_quality_benchmark")
    cases = [{"case_id": "H-I"}]
    ledger = benchmark._build_planned_ledger(
        cases,
        {"benchmark_id": "logic-writing-held-out-4x1x2"},
        repeats_count=1,
        versions=(benchmark.HELD_OUT_VERSION,),
        mode="held_out",
    )

    assert len(ledger["jobs"]) == 3  # one scheduled writer and two judges
    assert len(ledger["nested_planner_executions"]) == 2
    assert ledger["planned_counts"] == {
        "scheduled_jobs": 3,
        "nested_planner_executions": 2,
        "planned_execution_count": 5,
    }
    assert ledger["progress"]["planned"] == 5
    assert ledger["progress"]["scheduled"]["planned"] == 3
    assert ledger["progress"]["nested_planner"]["planned"] == 2
    assert all(item["execution_kind"] == "nested" for item in ledger["nested_planner_executions"])


def test_quality_consumer_rejects_missing_production_reader_lineage(tmp_path):
    consumer = _load("check_writing_quality_run")
    artifact = tmp_path / "artifacts" / "writers" / "H-I" / "1" / "current" / "artifact.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("# captured article\n", encoding="utf-8")
    production_root = artifact.parent / "production-reader"
    production_root.mkdir()
    row = {
        "case_id": "H-I",
        "repeat": 1,
        "version": "current",
        "artifact_path": artifact.relative_to(tmp_path).as_posix(),
        "production_reader": {"status": "blocked"},
    }

    with pytest.raises(ValueError, match="ready_for_writer"):
        consumer._validate_production_reader_lineage(tmp_path, row)


def test_quality_consumer_resolves_execution_prompt_below_attempts_root(tmp_path):
    consumer = _load("check_writing_quality_run")
    capture = tmp_path / "attempts" / "writer" / "one" / "input.txt"
    capture.parent.mkdir(parents=True)
    capture.write_text("captured prompt\n", encoding="utf-8")

    resolved = consumer._execution_capture_path(tmp_path, "writer/one/input.txt")

    assert resolved == capture.resolve()


def test_quality_consumer_accounting_counts_nested_planners_in_total(tmp_path):
    benchmark = _load("run_writing_quality_benchmark")
    consumer = _load("check_writing_quality_run")
    plan = {
        "planned_writer_count": 1,
        "planned_judge_count": 2,
        "planned_planner_count": 2,
    }
    ledger = benchmark._build_planned_ledger(
        [{"case_id": "H-I"}],
        plan,
        repeats_count=1,
        versions=(benchmark.HELD_OUT_VERSION,),
        mode="held_out",
    )
    for item in ledger["jobs"]:
        item["status"] = "completed"
    for item in ledger["nested_planner_executions"]:
        item["status"] = "completed"
    ledger["progress"] = benchmark._ledger_progress(ledger["jobs"], ledger["nested_planner_executions"])
    ledger.pop("ledger_fingerprint", None)
    ledger["ledger_fingerprint"] = benchmark.fingerprint(ledger)
    benchmark._write_json(tmp_path / "planned-ledger.json", ledger)
    result = {
        "planned_execution_count": 5,
        "actual_writer_count": 1,
        "actual_judge_count": 2,
        "actual_planner_count": 2,
        "actual_execution_count": 5,
    }
    manifest = {
        "planned_writer_count": 1,
        "planned_judge_count": 2,
        "planned_planner_count": 2,
        "planned_execution_count": 5,
        "actual_execution_count": 5,
    }

    consumer._validate_execution_accounting(tmp_path, plan=plan, result=result, manifest=manifest)

    ledger["progress"]["planned"] = 3
    benchmark._write_json(tmp_path / "planned-ledger.json", ledger)
    with pytest.raises(ValueError, match="total progress"):
        consumer._validate_execution_accounting(tmp_path, plan=plan, result=result, manifest=manifest)


def test_quality_consumer_status_counts_match_not_started_dependency_semantics():
    consumer = _load("check_writing_quality_run")

    counts = consumer._status_counts([
        {"status": "queued"},
        {"status": "not_started_dependency_failed"},
        {"status": "failed"},
        {"status": "completed"},
    ])

    assert counts == {
        "planned": 4,
        "terminal": 3,
        "completed": 1,
        "failed": 1,
        "not_started": 2,
    }


def test_planner_count_does_not_fall_back_to_legacy_fields_for_production_rows():
    benchmark = _load("run_writing_quality_benchmark")
    assert benchmark._planner_count([
        {
            "production_reader": {
                "planner_execution_records": None,
                "planner_records": [{"terminal_status": "completed"}],
            },
        }
    ]) == 0
    assert benchmark._planner_count([
        {"production_reader": {"planner_execution_records": [{"run_id": "planner:research:x"}]}}
    ]) == 0
    assert benchmark._planner_count([
        {"production_reader": {"planner_execution_records": [{"terminal_status": "finished"}]}}
    ]) == 0
    assert benchmark._planner_count([
        {"planner_records": [{"run_id": "planner:research:x"}]}
    ]) == 0
    assert benchmark._planner_count([
        {"planner_record": {"terminal_status": "finished"}}
    ]) == 0


def test_planner_and_job_actual_counts_exclude_not_started_rows():
    benchmark = _load("run_writing_quality_benchmark")
    started = benchmark._job_row({"case": {"case_id": "I01"}, "repeat": 1, "version": "baseline"}, "writer", status="failed", terminal_reason="nonzero_exit")
    started["process_id"] = 1234
    not_started = benchmark._job_row({"case": {"case_id": "I02"}, "repeat": 1, "version": "baseline"}, "writer", status="not_started_dependency_failed", terminal_reason="start_failed")
    assert benchmark._started_row_count([started, not_started]) == 1
    assert benchmark._planner_count([{"planner_records": [{"terminal_status": "failed"}]}], completed_only=False) == 1
    assert benchmark._planner_count([{"planner_records": [{"terminal_status": "failed"}]}]) == 0


def test_provided_plan_with_stale_source_manifest_is_rejected(tmp_path):
    benchmark = _load("run_writing_quality_benchmark")
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        '{"schema_version":"logic-writing.local-backend-plan.v1",'
        '"model_id":"gpt-6-astra","reasoning_effort":"xhigh",'
        '"source_manifest_fingerprint":"sha256:' + '0' * 64 + '"}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="source manifest fingerprint is stale"):
        benchmark._load_plan(plan_path, source_manifest_fp="sha256:" + "1" * 64)


def test_production_planner_adapter_resolves_backend_capture_to_absolute_path(tmp_path):
    benchmark = _load("run_writing_quality_benchmark")

    class FakeBackend:
        run_root = tmp_path / "backend-run"

        def settings(self):
            return {"model": "fake", "reasoning_effort": "minimal"}

        def run(self, role, request):
            assert role == "planner"
            capture_dir = self.run_root / "planner" / "compose-attempt"
            capture_dir.mkdir(parents=True)
            capture = capture_dir / "output.txt"
            capture.write_text(
                json.dumps(
                    {
                        "central_question": "问题",
                        "central_throughline": "主线",
                        "opening_job": "开篇",
                        "conclusion_job": "结尾",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (capture_dir / "events.jsonl").write_text(
                '{"type":"thread.started","thread_id":"context:compose"}\n'
                '{"type":"error","message":"Reconnecting... 2/5 (stream disconnected before completion: DNS)"}\n'
                '{"item":{"type":"agent_message","text":"planner result"}}\n'
                '{"type":"turn.completed"}\n',
                encoding="utf-8",
            )
            return {
                "run_id": "planner:compose:adapter-test",
                "context_id": "context:compose",
                "terminal_status": "completed",
                "output": capture.read_text(encoding="utf-8"),
                "raw_output_locator": "planner/compose-attempt/output.txt",
                "raw_output_fingerprint": benchmark._bytes_fp(capture.read_bytes()),
                "backend_id": "fake-local-codex",
                "provider_errors_recoverable": True,
                "recoverable_provider_error_count": 1,
            }

    inputs = {
        "writing_request": {
            "reader_intent": {
                "intent_fingerprint": "sha256:" + "a" * 64,
                "artifact_mode": "create_new",
                "extent": {"target": 800},
                "list_policy": "prose_default",
                "purpose": "说明一个有边界的判断。",
            }
        },
        "route_decision": {"final_owner": "investigation"},
        "content_boundaries": {"evidence_anchors": []},
        "native_plan": {"units": []},
    }
    evidence_root = tmp_path / "planner-evidence"
    record = benchmark._production_planner_backend(FakeBackend(), token="adapter-test")(
        stage="compose", inputs=inputs, evidence_root=evidence_root
    )["execution_record"]

    capture = Path(record["backend_capture_locator"])
    assert capture.is_absolute()
    assert capture == (tmp_path / "backend-run" / "planner" / "compose-attempt" / "output.txt").resolve()
    assert record["backend_capture_fingerprint"] == benchmark._bytes_fp(capture.read_bytes())
    assert record["provider_errors_recoverable"] is True
    assert record["recoverable_provider_error_count"] == 1
    events_path, _ = production_pipeline._read_planner_events(record, "compose")
    assert events_path == capture.with_name("events.jsonl")


def test_production_planner_adapter_separates_physical_repeat_identity(tmp_path):
    benchmark = _load("run_writing_quality_benchmark")

    class FakeBackend:
        run_root = tmp_path / "backend-run"

        def __init__(self):
            self.run_ids = []

        def settings(self):
            return {"model": "fake", "reasoning_effort": "minimal"}

        def run(self, role, request):
            assert role == "planner"
            run_id = str(request["run_id"])
            self.run_ids.append(run_id)
            capture_dir = self.run_root / "planner" / run_id.replace(":", "_")
            capture_dir.mkdir(parents=True)
            capture = capture_dir / "output.txt"
            capture.write_text(
                json.dumps(
                    {
                        "central_question": "问题",
                        "central_throughline": "主线",
                        "opening_job": "开篇",
                        "conclusion_job": "结尾",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (capture_dir / "events.jsonl").write_text(
                '{"type":"thread.started","thread_id":"context:compose"}\n'
                '{"type":"agent_message","text":"planner result"}\n'
                '{"type":"turn.completed"}\n',
                encoding="utf-8",
            )
            return {
                "run_id": run_id,
                "context_id": "context:compose",
                "terminal_status": "completed",
                "output": capture.read_text(encoding="utf-8"),
                "raw_output_locator": str(capture.relative_to(self.run_root)),
                "raw_output_fingerprint": benchmark._bytes_fp(capture.read_bytes()),
                "backend_id": "fake-local-codex",
            }

    inputs = {
        "writing_request": {
            "reader_intent": {
                "intent_fingerprint": "sha256:" + "a" * 64,
                "artifact_mode": "create_new",
                "extent": {"target": 800},
                "list_policy": "prose_default",
                "purpose": "说明一个有边界的判断。",
            }
        },
        "route_decision": {"final_owner": "investigation"},
        "content_boundaries": {"evidence_anchors": []},
        "native_plan": {"units": []},
    }
    backend = FakeBackend()
    records = []
    for repeat in (1, 2):
        records.append(
            benchmark._production_planner_backend(
                backend,
                token="stable-request",
                execution_token=f"stable-request-r{repeat}",
            )(
                stage="compose",
                inputs=inputs,
                evidence_root=tmp_path / f"evidence-{repeat}",
            )["execution_record"]
        )

    assert backend.run_ids == [
        "planner:compose:stable-request-r1",
        "planner:compose:stable-request-r2",
    ]
    assert [row["run_id"] for row in records] == backend.run_ids


def test_atomic_receipt_temp_name_fits_deep_windows_paths(tmp_path, monkeypatch):
    parent = tmp_path
    while len(str(parent / "completion.json")) < 226:
        parent = parent / "x"
    parent.mkdir(parents=True)
    target = parent / "completion.json"
    assert len(str(target)) < 260

    replaced = []
    original_replace = execution_backend.os.replace

    def capture_replace(source, destination):
        replaced.append((str(source), str(destination)))
        return original_replace(source, destination)

    monkeypatch.setattr(execution_backend.os, "replace", capture_replace)
    execution_backend._write_json_atomic(target, {"status": "completed"})

    assert target.is_file()
    assert replaced
    assert len(replaced[0][0]) < 260
    assert len(Path(replaced[0][0]).name) <= 48


def _planner_event_record(tmp_path: Path, events: list[dict], **metadata) -> dict:
    capture = tmp_path / "backend" / "planner" / "compose" / "output.txt"
    capture.parent.mkdir(parents=True)
    capture.write_text('{"composition_plan": {}}\n', encoding="utf-8")
    events_path = capture.with_name("events.jsonl")
    events_path.write_text(
        "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events),
        encoding="utf-8",
    )
    return {
        "schema_version": "logic-writing.planner-execution-record.v1",
        "backend_capture_locator": str(capture),
        "backend_capture_fingerprint": fingerprint_bytes(capture.read_bytes()),
        "context_id": "ctx-compose",
        "terminal_status": "completed",
        "provider_errors_recoverable": False,
        "recoverable_provider_error_count": 0,
        **metadata,
    }


def test_planner_allows_recoverable_reconnect_before_completed_turn(tmp_path):
    events = [
        {"type": "thread.started", "thread_id": "ctx-compose"},
        {"type": "error", "message": "Reconnecting... 2/5 (stream disconnected before completion: DNS)"},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "planner result"}},
        {"type": "turn.completed"},
    ]
    record = _planner_event_record(
        tmp_path,
        events,
        provider_errors_recoverable=True,
        recoverable_provider_error_count=1,
    )

    events_path, _ = production_pipeline._read_planner_events(record, "compose")
    assert events_path.name == "events.jsonl"


def test_planner_keeps_generic_provider_error_fail_closed(tmp_path):
    events = [
        {"type": "thread.started", "thread_id": "ctx-compose"},
        {"type": "error", "message": "provider failed permanently"},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "planner result"}},
        {"type": "turn.completed"},
    ]
    record = _planner_event_record(
        tmp_path,
        events,
        provider_errors_recoverable=True,
        recoverable_provider_error_count=1,
    )

    with pytest.raises(production_pipeline.ProductionPipelineBlocked, match="planner_execution_failed"):
        production_pipeline._read_planner_events(record, "compose")


def test_planner_keeps_reconnect_after_completed_turn_fail_closed(tmp_path):
    events = [
        {"type": "thread.started", "thread_id": "ctx-compose"},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "planner result"}},
        {"type": "turn.completed"},
        {"type": "error", "message": "Reconnecting... 2/5 (stream disconnected before completion: DNS)"},
    ]
    record = _planner_event_record(
        tmp_path,
        events,
        provider_errors_recoverable=True,
        recoverable_provider_error_count=1,
    )

    with pytest.raises(production_pipeline.ProductionPipelineBlocked, match="planner_execution_failed"):
        production_pipeline._read_planner_events(record, "compose")
