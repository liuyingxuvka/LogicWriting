from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import run_reader_acceptance_owner as owner


ROOT = Path(__file__).resolve().parents[2]
BACKEND_PLAN = ROOT / "tests" / "fixtures" / "writing_quality" / "local-backend-plan.json"


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _complete_preflight(root: Path) -> dict[str, object]:
    expected = owner._current_preflight_identity(ROOT, BACKEND_PLAN)
    plan_identity = dict(expected["plan"])
    plan = {
        **plan_identity,
        "schema_version": "logic-writing.writing-quality-run.v2",
        "benchmark_id": "logic-writing-preflight-1x1x2",
        "mode": "preflight",
        "claim": "smoke_only",
        "evidence_mode": "real_execution",
        "case_count": 1,
        "case_order": ["I01"],
        "implementation_fingerprint": expected["implementation_fingerprint"],
        "execution_policy_fingerprint": expected["execution_policy_fingerprint"],
        "source_manifest_fingerprint": expected["source_manifest_fingerprint"],
        "planned_writer_count": 2,
        "planned_judge_count": 2,
        "planned_planner_count": 1,
    }
    manifest = {
        "schema_version": "logic-writing.execution-quality-output.v1",
        "producer_check_id": owner.PRODUCER_ID,
        "unit_id": "unit:logic-writing",
        "mode": "preflight",
        "evidence_mode": "real_execution",
        "source_manifest_fingerprint": expected["source_manifest_fingerprint"],
        "toolchain_fingerprint": expected["toolchain_fingerprint"],
        "terminal_status": "completed",
        "writer_count": 2,
        "judge_count": 2,
        "planner_count": 1,
    }
    result = {
        "schema_version": "logic-writing.writing-quality-run-result.v2",
        "benchmark_id": "logic-writing-preflight-1x1x2",
        "mode": "preflight",
        "status": "completed",
        "quality_claim_status": "incomplete",
        "actual_writer_count": 2,
        "actual_judge_count": 2,
        "actual_planner_count": 1,
        "source_manifest_fingerprint": expected["source_manifest_fingerprint"],
        "implementation_fingerprint": expected["implementation_fingerprint"],
        "execution_policy_fingerprint": expected["execution_policy_fingerprint"],
    }
    producer = {
        "schema_version": "logic-writing.reader-acceptance-owner-result.v1",
        "producer_check_id": owner.PRODUCER_ID,
        "status": "passed",
        "mode": "preflight",
    }
    _write(root / "benchmark_plan.json", plan)
    _write(root / "output-manifest.json", manifest)
    _write(root / "run_result.json", result)
    _write(root / "producer-result.json", producer)
    return {"expected": expected, "plan": plan, "manifest": manifest, "result": result, "producer": producer}


def test_complete_preflight_dependency_is_accepted(tmp_path: Path):
    _complete_preflight(tmp_path)
    report = owner._validate_preflight_dependency(ROOT, tmp_path, BACKEND_PLAN)
    assert report["status"] == "passed"
    assert report["source_manifest_fingerprint"]
    assert report["implementation_fingerprint"]
    assert report["toolchain_fingerprint"]


def test_missing_preflight_is_explicitly_required(tmp_path: Path):
    report = owner._validate_preflight_dependency(ROOT, tmp_path / "missing", BACKEND_PLAN)
    assert report["status"] == "preflight_required"
    assert "missing" in report["error"]


@pytest.mark.parametrize("field", ["source_manifest_fingerprint", "implementation_fingerprint"])
def test_preflight_plan_identity_drift_is_rejected(tmp_path: Path, field: str):
    bundle = _complete_preflight(tmp_path)
    plan = copy.deepcopy(bundle["plan"])
    plan[field] = "sha256:" + "0" * 64
    _write(tmp_path / "benchmark_plan.json", plan)
    report = owner._validate_preflight_dependency(ROOT, tmp_path, BACKEND_PLAN)
    assert report["status"] == "preflight_required"
    assert field in report["error"]


def test_preflight_toolchain_identity_drift_is_rejected(tmp_path: Path):
    bundle = _complete_preflight(tmp_path)
    manifest = copy.deepcopy(bundle["manifest"])
    manifest["toolchain_fingerprint"] = "sha256:" + "1" * 64
    _write(tmp_path / "output-manifest.json", manifest)
    report = owner._validate_preflight_dependency(ROOT, tmp_path, BACKEND_PLAN)
    assert report["status"] == "preflight_required"
    assert "toolchain_fingerprint" in report["error"]


def test_preflight_gate_blocks_full_pair_before_run(tmp_path: Path, monkeypatch):
    called = False

    def should_not_run(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("quality run must not start without I01 preflight")

    monkeypatch.setattr(owner, "run_benchmark", should_not_run)
    result = owner.run_owner(
        ROOT,
        output_dir=tmp_path / "pair",
        backend_plan=BACKEND_PLAN,
        run_writers=True,
        run_judges=True,
    )
    assert called is False
    assert result["status"] == "incomplete"
    assert result["terminal_reason"] == "preflight_required"
    assert "preflight run root" in result["error"]
    persisted = json.loads((tmp_path / "pair" / "run_result.json").read_text(encoding="utf-8"))
    assert persisted["terminal_reason"] == "preflight_required"


def test_preflight_lane_skips_its_own_dependency_gate(tmp_path: Path, monkeypatch):
    called = {}

    def fake_run(*args, **kwargs):
        called.update(kwargs)
        raise ValueError("synthetic preflight setup failure")

    def should_not_validate(*args, **kwargs):
        raise AssertionError("preflight lane must not require a previous preflight")

    monkeypatch.setattr(owner, "run_benchmark", fake_run)
    monkeypatch.setattr(owner, "_validate_preflight_dependency", should_not_validate)
    result = owner.run_owner(
        ROOT,
        output_dir=tmp_path / "preflight",
        backend_plan=BACKEND_PLAN,
        preflight_case="I01",
        repeats=1,
    )
    assert called["preflight_case"] == "I01"
    assert result["status"] == "incomplete"
    assert result["mode"] == "preflight"
    assert result["terminal_reason"].startswith("producer_initialization_failed:")
