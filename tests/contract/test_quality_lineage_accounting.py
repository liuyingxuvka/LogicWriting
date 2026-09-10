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
    events_path, _ = production_pipeline._read_planner_events(record, "compose")
    assert events_path == capture.with_name("events.jsonl")
