from __future__ import annotations

import copy
import importlib.util
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from _common import fingerprint


def _load(name: str):
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"logic_writing_{name}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module




def test_quality_consumer_imports_from_repository_root():
    quality = _load("check_writing_quality_run")
    assert callable(quality.check)
    assert callable(quality.main)


def test_quality_batch_deadline_scales_to_concurrency_waves():
    benchmark = _load("run_writing_quality_benchmark")
    plan = {"timeout_seconds": 900, "concurrency": 2}
    assert benchmark._orchestration_timeout(plan, 48) == 21600
    assert benchmark._orchestration_timeout(
        {**plan, "orchestration_timeout_seconds": 120}, 48
    ) == 120


def test_parallel_quality_jobs_close_startup_without_any_result():
    benchmark = _load("run_writing_quality_benchmark")
    executor = ThreadPoolExecutor(max_workers=1)
    release = threading.Event()
    try:
        rows = benchmark._parallel_jobs(
            executor, [{"case": {"case_id": "A01"}}],
            lambda _job: release.wait(10), timeout_seconds=10,
            startup_timeout_seconds=1, role="writer",
        )
    finally:
        release.set()
        executor.shutdown(wait=False, cancel_futures=True)
    assert rows[0]["error_event"]["error_class"] == "StartupDispatchTimeout"
    assert rows[0]["error_event"]["terminal"] is True


def test_reader_acceptance_owner_requires_explicit_aggregate_only_for_existing_captures():
    owner = _load("run_reader_acceptance_owner")
    assert owner.resolve_stage_selection(
        run_writers=False, run_judges=False, aggregate_only=True
    ) == (False, False)
    assert owner.resolve_stage_selection(
        run_writers=True, run_judges=False, aggregate_only=False
    ) == (True, False)
    assert owner.resolve_stage_selection(
        run_writers=False, run_judges=True, aggregate_only=False
    ) == (False, True)
    assert owner.resolve_stage_selection(
        run_writers=False, run_judges=False, aggregate_only=False
    ) == (True, True)
    with pytest.raises(ValueError, match="cannot be combined"):
        owner.resolve_stage_selection(
            run_writers=True, run_judges=False, aggregate_only=True
        )


def test_pair_writer_input_fingerprint_is_json_serializable_and_order_independent():
    benchmark = _load("run_writing_quality_benchmark")
    first = benchmark._pair_writer_input_fingerprint(
        [{"writer_input_fingerprint": "sha256:b"}, {"writer_input_fingerprint": "sha256:a"}]
    )
    second = benchmark._pair_writer_input_fingerprint(
        [{"writer_input_fingerprint": "sha256:a"}, {"writer_input_fingerprint": "sha256:b"}]
    )
    assert first == second


def test_judge_pair_order_uses_persisted_writer_versions():
    benchmark = _load("run_writing_quality_benchmark")
    assert benchmark._pair_order_for_writers(
        ({"version": "repaired"}, {"version": "baseline"})
    ) == ["repaired", "baseline"]
    with pytest.raises(ValueError, match="one baseline and one repaired"):
        benchmark._pair_order_for_writers(
            ({"version": "baseline"}, {"version": "baseline"})
        )


def test_parallel_quality_jobs_close_missing_terminal_result():
    benchmark = _load("run_writing_quality_benchmark")

    def stuck(_job):
        time.sleep(2)
        return {"status": "completed"}

    executor = ThreadPoolExecutor(max_workers=1)
    started = time.monotonic()
    rows = benchmark._parallel_jobs(
        executor, [{"case": {"case_id": "T01"}, "repeat": 1}], stuck,
        timeout_seconds=1, role="judge"
    )
    assert time.monotonic() - started < 1.8
    assert rows[0]["status"] == "failed"
    assert rows[0]["error_event"]["type"] == "error_event"
    assert rows[0]["error_event"]["error_class"] == "OrchestrationTimeout"


def test_real_quality_runner_rejects_injected_backend_without_local_plan(tmp_path):
    benchmark = _load("run_writing_quality_benchmark")

    def shaped_backend(_request):
        return {"artifact_fingerprint": "sha256:shaped"}

    with pytest.raises(ValueError, match="injected backend cannot produce real_execution"):
        benchmark.run_benchmark(
            ROOT,
            output_dir=tmp_path / "quality",
            backend=shaped_backend,
            backend_id="authorized-test-provider",
            execute_live=True,
            max_model_calls=1,
        )


def test_route_smoke_covers_both_owners_and_bounded_child():
    routes = _load("check_installed_routes")
    report = routes.check(ROOT / "skills" / "logic-writing")
    assert report["status"] == "passed"
    assert [item["scenario"] for item in report["scenarios"]] == [
        "investigation",
        "academic-writing",
        "academic-with-investigation-child",
        "fiction-writing",
        "travel-guide",
    ]


def test_global_route_checker_distinguishes_cutover_from_retirement(tmp_path):
    routing = _load("check_global_routing")
    (tmp_path / "skills" / "research-investigation-workflow").mkdir(parents=True)
    active = tmp_path / "skills" / "logic-writing"
    active.mkdir(parents=True)
    (active / "SKILL.md").write_text("---\nname: logic-writing\n---\n")
    assert routing.check(tmp_path, phase="cutover")["status"] == "passed"
    assert routing.check(tmp_path, phase="retired")["status"] == "failed"


def test_retirement_residual_checker_rejects_active_reference(tmp_path):
    residuals = _load("check_retirement_residuals")
    skills = tmp_path / "skills" / "supporting-skill"
    skills.mkdir(parents=True)
    (tmp_path / "AGENTS.md").write_text("logic-writing\n", encoding="utf-8")
    (skills / "SKILL.md").write_text("Use logic-writing.\n", encoding="utf-8")
    assert residuals.check(tmp_path)["status"] == "passed"
    (skills / "SKILL.md").write_text(
        "Use academic-thesis-revision-workflow.\n", encoding="utf-8"
    )
    assert residuals.check(tmp_path)["status"] == "failed"




def test_skill_static_validator_accepts_placeholder_detector_source():
    validator = _load("validate_skill")
    report = validator.validate_skill(ROOT / "skills" / "logic-writing")

    assert report["status"] == "passed"
    assert report["errors"] == []


def test_reader_judgment_owner_without_input_is_unavailable(tmp_path):
    judgment = _load("check_reader_judgment")
    runtime_root = tmp_path / "reader-judgment-owner"

    report = judgment.check(ROOT, runtime_root)

    assert report["status"] == "provider_unavailable"
    assert report["preparation_status"] == "not_run"
    assert report["judgment_status"] == "repair"
    assert report["execution_status"] == "execution_provider_unavailable"
    assert not (runtime_root / "reader-quality-judgment.json").exists()
    assert (runtime_root / "reader-quality-judgment-result.json").is_file()


def test_reader_judgment_owner_rejects_protocol_fixture_as_quality_evidence(tmp_path):
    judgment = _load("check_reader_judgment")
    preparation = _load("prepare_reader_quality_receipt")
    fixture_path = tmp_path / "protocol-only.json"
    preparation.prepare(ROOT, tmp_path / "receipts", fixture_path)

    report = judgment.check(
        ROOT,
        tmp_path / "reader-judgment-owner",
        input_path=fixture_path,
    )

    assert report["status"] == "provider_unavailable"
    assert report["judgment_status"] == "repair"
    assert report["execution_status"] == "execution_provider_unavailable"
    result = json.loads(
        (tmp_path / "reader-judgment-owner" / "reader-quality-judgment-result.json").read_text(
            encoding="utf-8"
        )
    )
    assert result["status"] == "provider_unavailable"
    assert "protocol-only" in result["errors"][0]


def test_reader_judgment_owner_rejects_shaped_but_uncaptured_execution_record(tmp_path):
    judgment = _load("check_reader_judgment")
    from tests.v2_support import complete_chain

    chain = complete_chain(tmp_path / "chain")
    envelope = {
        "evidence_mode": "recorded_execution",
        "judgment": copy.deepcopy(chain["judgment"]),
        "artifact_map": chain["artifact_map"],
        "reader_brief": chain["reader_brief"],
        "shared_writing": chain["shared_writing"],
        "deterministic_audit": chain["deterministic_audit"],
        "route_review": chain["route_review"],
    }
    record = copy.deepcopy(chain["reader_execution_records"][0])
    record.update(
        {
            "backend_id": "authorized-test-provider",
            "model_id": "test-reader-judge-v1",
            "provider_completion_ref": "provider://test-reader-judge-v1/run-1",
        }
    )
    record["record_fingerprint"] = fingerprint(
        {key: value for key, value in record.items() if key != "record_fingerprint"}
    )
    envelope["judgment"]["execution_record_fingerprint"] = record["record_fingerprint"]
    envelope["judgment"]["judgment_fingerprint"] = fingerprint(
        {key: value for key, value in envelope["judgment"].items() if key != "judgment_fingerprint"}
    )
    input_path = tmp_path / "current-judgment.json"
    input_path.write_text(
        json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    dispatch_path = tmp_path / "dispatch-result.json"
    dispatch_path.write_text(
        json.dumps({"status": "completed", "record": record}), encoding="utf-8"
    )

    report = judgment.check(
        ROOT,
        tmp_path / "reader-judgment-owner",
        input_path=input_path,
        execution_record_path=dispatch_path,
    )

    assert report["status"] == "repair"
    assert report["judgment_status"] == "repair"
    assert report["execution_status"] == "record_invalid"

    raw_record_path = tmp_path / "raw-record.json"
    raw_record_path.write_text(json.dumps(record), encoding="utf-8")
    raw_report = judgment.check(
        ROOT,
        tmp_path / "reader-judgment-owner-raw",
        input_path=input_path,
        execution_record_path=raw_record_path,
    )
    assert raw_report["status"] == "repair"
    assert raw_report["judgment_status"] == "repair"
    assert raw_report["execution_status"] == "record_invalid"


def test_reader_judgment_owner_missing_record_with_input_is_unavailable(tmp_path):
    judgment = _load("check_reader_judgment")
    from tests.v2_support import complete_chain

    chain = complete_chain(tmp_path / "chain")
    envelope = {
        "judgment": chain["judgment"],
        "artifact_map": chain["artifact_map"],
        "reader_brief": chain["reader_brief"],
        "shared_writing": chain["shared_writing"],
        "deterministic_audit": chain["deterministic_audit"],
        "route_review": chain["route_review"],
    }
    input_path = tmp_path / "missing-record.json"
    input_path.write_text(json.dumps(envelope), encoding="utf-8")

    report = judgment.check(
        ROOT,
        tmp_path / "reader-judgment-owner",
        input_path=input_path,
    )

    assert report["status"] == "provider_unavailable"
    assert report["judgment_status"] == "repair"
    assert report["execution_status"] == "execution_provider_unavailable"













def _write_json_file(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")












def test_quality_dependency_index_binds_manifest_hash(tmp_path):
    quality = _load("check_writing_quality_run")
    run_root = tmp_path / "producer"
    run_root.mkdir()
    manifest = {
        "producer_check_id": "check.reader.execution-quality-producer",
        "manifest_fingerprint": "sha256:" + "m" * 64,
        "source_manifest_fingerprint": "sha256:" + "s" * 64,
        "toolchain_fingerprint": "sha256:" + "t" * 64,
    }
    _write_json_file(run_root / "output-manifest.json", manifest)
    index = {
        "schema_version": "logic-writing.validation-dependency-index.v1",
        "consumer_check_id": "check.reader.execution-quality-producer",
        "current_source_fingerprint": manifest["source_manifest_fingerprint"],
        "current_toolchain_fingerprint": manifest["toolchain_fingerprint"],
        "dependencies": [],
        "producer_output_manifest_path": "output-manifest.json",
        "producer_output_manifest_fingerprint": "sha256:" + "x" * 64,
    }
    index["index_fingerprint"] = quality.fingerprint(
        {key: value for key, value in index.items() if key != "index_fingerprint"}
    )
    _write_json_file(run_root / "dependency-index.json", index)
    with pytest.raises(ValueError, match="manifest fingerprint does not match"):
        quality._validate_dependency_index(
            run_root,
            producer_id="check.reader.execution-quality-producer",
            manifest=manifest,
        )


def test_public_docs_frozen_fallback_uses_contract_admission(tmp_path, monkeypatch):
    public_docs = _load("check_public_docs")
    monkeypatch.setattr(public_docs, "git_lines", lambda *_args: [])
    contract_path = (
        tmp_path
        / "openspec"
        / "verification-contract.yaml"
    )
    contract_path.parent.mkdir(parents=True)
    contract_path.write_text(
        yaml.safe_dump(
            {
                "freshness": {
                    "exclude": [
                        "docs/coordination.md",
                        "docs/flowguard_adoption_log.md",
                    ]
                }
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "coordination.md").write_text("local only\n", encoding="utf-8")
    (docs / "flowguard_adoption_log.md").write_text(
        "local only\n", encoding="utf-8"
    )
    (docs / "architecture.md").write_text("public\n", encoding="utf-8")

    inventory = public_docs._public_inventory(tmp_path)

    assert "docs/coordination.md" not in inventory
    assert "docs/flowguard_adoption_log.md" not in inventory
    assert "docs/architecture.md" in inventory


def test_privacy_frozen_fallback_uses_contract_admission(tmp_path, monkeypatch):
    privacy = _load("check_privacy")
    monkeypatch.setattr(privacy, "git_lines", lambda *_args: [])
    contract_path = (
        tmp_path
        / "openspec"
        / "verification-contract.yaml"
    )
    contract_path.parent.mkdir(parents=True)
    contract_path.write_text(
        yaml.safe_dump(
            {
                "freshness": {
                    "exclude": [
                        "**/verification-report.json",
                        "**/verification-receipts/**",
                        "docs/coordination.md",
                    ]
                }
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    machine_path = "C:" + chr(92) + "Users" + chr(92) + "example" + chr(92) + "secret"
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "coordination.md").write_text(machine_path, encoding="utf-8")
    receipt = contract_path.parent / "verification-receipts" / "receipt.json"
    receipt.parent.mkdir()
    receipt.write_text(json.dumps({"path": machine_path}), encoding="utf-8")
    report_path = contract_path.parent / "verification-report.json"
    report_path.write_text(json.dumps({"path": machine_path}), encoding="utf-8")
    public = docs / "architecture.md"
    public.write_text("public and portable\n", encoding="utf-8")

    assert privacy.scan(tmp_path)["status"] == "passed"

    public.write_text(machine_path, encoding="utf-8")
    assert privacy.scan(tmp_path)["status"] == "failed"
