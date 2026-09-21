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


def test_public_document_and_source_release_contracts_pass():
    public_docs = _load("check_public_docs")
    release = _load("check_release_surface")
    assert public_docs.check(ROOT)["status"] == "passed"
    assert release.check(
        ROOT,
        mode="source",
        repository="liuyingxuvka/LogicWriting",
        require_clean=False,
        require_head=False,
    )["status"] == "passed"


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
    router = tmp_path / ".skillguard" / "global-router"
    router.mkdir(parents=True)
    (tmp_path / "skills" / "research-investigation-workflow").mkdir(parents=True)
    registry = {
        "items": [
            {
                "skill_id": "logic-writing",
                "status": "current",
                "route_entrypoint": {"authority_decision": "current"},
            },
            {
                "skill_id": "research-investigation-workflow",
                "status": "blocked",
                "route_entrypoint": {"authority_decision": "blocked"},
            },
        ]
    }
    (router / "global_registry.json").write_text(json.dumps(registry), encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("current route: logic-writing\n", encoding="utf-8")
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


def test_frozen_validation_observes_runnable_unreadable_executable(monkeypatch):
    runner = _load("run_frozen_validation")
    executable = Path(sys.executable)
    original_file_hash = runner._file_hash

    def unreadable_alias(path: Path):
        if Path(path) == executable:
            raise OSError(22, "simulated app-execution alias")
        return original_file_hash(path)

    monkeypatch.setattr(runner, "_resolve_executable", lambda _name: str(executable))
    monkeypatch.setattr(runner, "_file_hash", unreadable_alias)
    observation = runner._toolchain_observation(
        {"command": "python", "toolchain_identity": "python-runtime"}
    )

    assert observation["executable_hash"] == "unavailable"
    assert observation["executable_path_hash"].startswith("sha256:")
    assert observation["executable_version_probe_hash"].startswith("sha256:")


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


def test_skillguard_project_owner_stages_stable_project_identity(tmp_path, monkeypatch):
    authority = _load("check_skillguard_authority")
    repository = tmp_path / "random-frozen-root"
    target = repository / "skills" / "logic-writing"
    codex_home = tmp_path / "codex-home"
    scripts = codex_home / "skills" / "skillguard" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "skillguard.py").write_text("# provider\n", encoding="utf-8")
    (scripts / "skillguard_compile.py").write_text(
        "# provider\n", encoding="utf-8"
    )
    (repository / ".skillguard").mkdir(parents=True)
    (repository / ".skillguard" / "author-project.json").write_text(
        json.dumps({"project_id": "LogicWriting"}), encoding="utf-8"
    )
    (repository / "AGENTS.md").write_text("project contract\n", encoding="utf-8")
    (target / ".skillguard").mkdir(parents=True)
    (target / "SKILL.md").write_text("skill contract\n", encoding="utf-8")
    for name in (
        "contract-source.json",
        "compiled-contract.json",
        "check-manifest.json",
    ):
        (target / ".skillguard" / name).write_text("{}\n", encoding="utf-8")

    observed = {}

    def fake_run(command, *, cwd, timeout):
        observed["root"] = cwd
        assert timeout == 900
        assert cwd.name == "LogicWriting"
        assert not (cwd / ".git").exists()
        assert (cwd / "AGENTS.md").is_file()
        assert (cwd / ".skillguard" / "author-project.json").is_file()
        assert command[2] == "maintainer-audit"
        assert (cwd / "skills" / "logic-writing" / "SKILL.md").is_file()
        root_arg = Path(command[command.index("--root") + 1])
        assert root_arg == cwd
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {"status": "pass", "decision": "pass", "findings": []}
            ),
            stderr="",
        )

    monkeypatch.setattr(authority, "run", fake_run)
    report = authority.check(repository, target, codex_home, "project")

    assert report["status"] == "passed"
    assert report["execution_projection"] == "stable-project-id"
    assert report["provider_result"]["status"] == "pass"
    assert not observed["root"].exists()


def test_frozen_boundary_excludes_runtime_inputs_and_internal_records():
    runner = _load("run_frozen_validation")
    for relative in (
        "run-artifacts/reader-quality-judgment.json",
        "openspec/changes/create-logic-writing/verification-report.json",
        "openspec/changes/create-logic-writing/verification-receipts/receipt.json",
        "docs/coordination.md",
        "docs/flowguard_adoption_log.md",
        ".flowguard/adoption_log.jsonl",
        ".flowguard/history/legacy.json",
        ".flowguard/structure/reverse-surfaces/current-discovery.json",
    ):
        assert runner._is_ignored(Path(relative), explicit=True)

    assert runner.DEFAULT_CONTRACT == Path("openspec/verification-contract.yaml")
    contract = yaml.safe_load(
        (ROOT / runner.DEFAULT_CONTRACT).read_text(encoding="utf-8")
    )
    checks = {item["id"]: item for item in contract["checks"]}
    judgment = next(
        item for item in contract["checks"] if item["id"] == "check.reader.judgment"
    )
    assert judgment["args"] == [
        "scripts/check_reader_judgment.py",
        "--root",
        ".",
        "--runtime-root",
        "{owner_run_root}",
        "--dependency-producer",
        "check.reader.execution-quality-producer",
        "--json",
    ]
    assert checks["check.reader.execution-quality-producer"]["args"] == [
        "scripts/run_reader_acceptance_owner.py",
        "--root",
        ".",
        "--backend-plan",
        "tests/fixtures/writing_quality/local-backend-plan.json",
        "--preflight-run-root",
        "{dependency:check.reader.preflight-producer:run_root}",
        "--held-out-run-root",
        "{dependency:check.reader.heldout-producer:run_root}",
        "--output-dir",
        "{owner_run_root}",
        "--json",
    ]
    assert checks["check.writing.quality-benchmark"]["args"] == [
        "scripts/check_writing_quality_run.py",
        "--root",
        ".",
        "--run-root",
        "{dependency:check.reader.execution-quality-producer:run_root}",
        "--held-out-run-root",
        "{dependency:check.reader.heldout-producer:run_root}",
        "--dependency-producer",
        "check.reader.execution-quality-producer",
        "--json",
    ]
    assert not any(
        str(selector).startswith("run-artifacts/")
        for selector in judgment["input_selectors"]
    )
    exclusions = set(contract["freshness"]["exclude"])
    assert {
        "**/verification-report.json",
        "**/verification-receipts/**",
        "**/.flowguard/evidence/**",
        "**/.flowguard/history/**",
        "**/.flowguard/structure/reverse-surfaces/**",
        "**/.storyline-*/**",
        "**/.probe-*/**",
        "**/kb/history/**",
        ".flowguard/adoption_log.jsonl",
        "docs/coordination.md",
        "docs/flowguard_adoption_log.md",
    }.issubset(exclusions)


def test_manifest_reuses_frozen_hashes_and_caches_unlisted_paths(monkeypatch, tmp_path):
    runner = _load("run_frozen_validation")
    root = tmp_path / "repo"
    root.mkdir()
    cached = root / "cached.txt"
    uncached = root / "uncached.txt"
    cached.write_text("cached\n", encoding="utf-8")
    uncached.write_text("uncached\n", encoding="utf-8")
    monkeypatch.setattr(
        runner,
        "_selector_files",
        lambda _root, selector: [cached if selector == "cached.txt" else uncached],
    )
    calls = []
    monkeypatch.setattr(
        runner,
        "_file_hash",
        lambda path: calls.append(path) or "sha256:computed",
    )

    known_hashes = {"cached.txt": "sha256:frozen"}
    assert runner._manifest(root, ["cached.txt"], known_hashes=known_hashes) == {
        "cached.txt": "sha256:frozen"
    }
    assert calls == []

    assert runner._manifest(root, ["uncached.txt"], known_hashes=known_hashes) == {
        "uncached.txt": "sha256:computed"
    }
    assert calls == [uncached]
    assert known_hashes["uncached.txt"] == "sha256:computed"


def test_reader_quality_contract_has_one_six_node_chain_and_two_terminal_consumers():
    contract = yaml.safe_load(
        (ROOT / "openspec" / "verification-contract.yaml").read_text(encoding="utf-8")
    )
    checks = {str(item["id"]): item for item in contract["checks"]}
    expected = {
        "check.reader.preflight-producer": ["check.tests.archive-lifecycle"],
        "check.reader.heldout-producer": ["check.reader.preflight-producer"],
        "check.reader.execution-quality-producer": ["check.reader.heldout-producer"],
        "check.reader.judgment": ["check.reader.execution-quality-producer"],
        "check.writing.quality-benchmark": ["check.reader.execution-quality-producer"],
    }
    # The release subgraph is the archive node plus these five reader nodes:
    # three producers and two read-only consumers.
    assert set(expected).issubset(checks)
    for check_id, dependencies in expected.items():
        assert checks[check_id]["depends_on_receipts"] == dependencies
    assert "--preflight-case" in checks["check.reader.preflight-producer"]["args"]
    assert "--held-out-only" in checks["check.reader.heldout-producer"]["args"]
    assert "--preflight-run-root" in checks["check.reader.execution-quality-producer"]["args"]
    assert "--held-out-run-root" in checks["check.reader.execution-quality-producer"]["args"]
    assert "{owner_run_root}" in checks["check.reader.judgment"]["args"]
    assert "{dependency:check.reader.execution-quality-producer:run_root}" in checks["check.writing.quality-benchmark"]["args"]
    assert "--held-out-run-root" in checks["check.writing.quality-benchmark"]["args"]


def test_frozen_public_checks_bind_concrete_admitted_source_manifests():
    runner = _load("run_frozen_validation")
    contract = yaml.safe_load(
        (ROOT / runner.DEFAULT_CONTRACT).read_text(encoding="utf-8")
    )
    checks = {item["id"]: item for item in contract["checks"]}
    required = {
        ".gitattributes",
        ".gitignore",
        ".logicguard/readme-capability-model.yaml",
        ".skillguard/author-project.json",
        "AGENTS.md",
        "CHANGELOG.md",
        "README.md",
        "README.zh-CN.md",
        "pyproject.toml",
        "scripts/_release_common.py",
        "scripts/check_privacy.py",
        "scripts/check_public_docs.py",
        "scripts/check_release_surface.py",
        "scripts/author/evaluate_contract_calibration.py",
        "skills/logic-writing/.skillguard/evidence-specs/semantic.json",
        "skills/logic-writing/.skillguard/fixtures/contract-depth-positive.json",
    }
    forbidden = {
        ".flowguard/adoption_log.jsonl",
        "docs/coordination.md",
        "docs/flowguard_adoption_log.md",
        "openspec/changes/create-logic-writing/verification-report.json",
    }

    selector_sets = []
    for check_id in (
        "check.public.docs",
        "check.privacy",
        "check.release.source",
    ):
        check = checks[check_id]
        assert "." not in {str(item) for item in check["input_selectors"]}
        selectors = {str(selector) for selector in check["input_selectors"]}
        selector_sets.append(selectors)

        # The release runner performs the actual content manifest walk.  This
        # contract test only guards the stable selector surface and the
        # explicit runtime exclusions; expanding the large live repository
        # here would duplicate the frozen validation's disk I/O.
        assert all(
            path in selectors
            or any(selector.startswith(path.split("/", 1)[0] + "/") for selector in selectors)
            for path in required
        )
        assert all(runner._is_ignored(Path(path), explicit=False) for path in forbidden)

    assert selector_sets[0] == selector_sets[1] == selector_sets[2]
    assert checks["check.release.source"]["args"] == [
        "scripts/check_release_surface.py",
        "--root",
        ".",
        "--mode",
        "source",
        "--json",
    ]


def _minimal_frozen_contract() -> dict[str, object]:
    return {
        "contract_version": "test-v1",
        "freshness": {"watch": ["source.txt"], "exclude": []},
        "checks": [
            {
                "id": "check.one",
                "kind": "command",
                "semantic_check_id": "test.one",
                "execution_id": "test-one-v1",
                "toolchain_identity": "python-test-runtime",
                "input_selectors": ["source.txt"],
                "depends_on_receipts": [],
                "command": "python",
                "args": ["-c", "pass", "--output-dir", "{owner_run_root}"],
                "timeout_seconds": 30,
                "expected": {"exit_code": 0},
            }
        ],
    }


def _write_json_file(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _minimal_frozen_receipts(runner, root: Path, receipts: Path, contract: dict[str, object]) -> None:
    check = contract["checks"][0]
    assert isinstance(check, dict)
    snapshot_id, snapshot_manifest = runner._global_snapshot(root, contract)
    revision = runner._inventory_revision(contract)
    inputs = runner._check_manifest(
        root,
        check,
        known_hashes=dict(snapshot_manifest),
    )
    attempt_root = receipts / "attempts" / "check.one" / "attempt-1"
    run_root = attempt_root / "run"
    run_root.mkdir(parents=True)
    result = {
        "check_id": "check.one",
        "execution_fingerprint": "sha256:" + "a" * 64,
        "exit_code": 0,
        "timed_out": False,
        "cleanup_confirmed": True,
    }
    result["result_fingerprint"] = runner._hash(result)
    result_path = attempt_root / "result.json"
    _write_json_file(result_path, result)
    receipt = {
        "schema_version": "logic_writing_validation_receipt.v1",
        "check_id": "check.one",
        "semantic_check_id": "test.one",
        "execution_id": "test-one-v1",
        "execution_fingerprint": result["execution_fingerprint"],
        "status": "passed",
        "terminal_status": "passed",
        "exit_code": 0,
        "inventory_revision": revision,
        "artifact_version": snapshot_id,
        "verifier_version": runner.VERIFIER_VERSION,
        "input_manifest_hash": runner._hash(inputs),
        "dependency_receipt_hashes": {},
        "covered_obligation_ids": [],
        "result_path": result_path.relative_to(receipts).as_posix(),
        "result_fingerprint": result["result_fingerprint"],
        "timed_out": False,
        "cleanup_confirmed": True,
        "owner_context": {
            "owner_id": "check.one",
            "attempt_root": attempt_root.relative_to(receipts).as_posix(),
            "run_root": run_root.relative_to(receipts).as_posix(),
        },
        "claim_boundary": "test",
    }
    receipt["receipt_hash"] = runner._receipt_hash(receipt)
    success_path = receipts / "success" / "check.one" / ("a" * 64 + ".json")
    _write_json_file(success_path, receipt)
    mesh_payload = {"status": "passed", "owner_count": 1}
    mesh_path = receipts / "test-mesh-terminal.json"
    _write_json_file(mesh_path, mesh_payload)
    parent = {
        "schema_version": "logic_writing_validation_index.v1",
        "status": "passed",
        "verifier_version": runner.VERIFIER_VERSION,
        "inventory_revision": revision,
        "frozen_snapshot_id": snapshot_id,
        "frozen_snapshot_file_count": len(snapshot_manifest),
        "execution_owner_count": 1,
        "receipt_consumer_count": 0,
        "git_clean_required": False,
        "git_clean_observed": False,
        "toolchain_observations": {},
        "executed_check_ids": ["check.one"],
        "reused_check_ids": [],
        "receipts": {"check.one": receipt},
        "consumer_owners": {},
        "test_mesh": {
            "status": "passed",
            "result_path": mesh_path.relative_to(receipts).as_posix(),
            "result_hash": runner._hash(mesh_payload),
        },
        "claim_boundary": "test",
    }
    parent["index_hash"] = runner._hash(parent)
    _write_json_file(receipts / "index.json", parent)


def test_frozen_audit_only_is_pure_read_and_revalidates_existing_parent(monkeypatch, tmp_path):
    runner = _load("run_frozen_validation")
    root = tmp_path / "repo"
    (root / "openspec").mkdir(parents=True)
    (root / "source.txt").write_text("source\n", encoding="utf-8")
    contract = _minimal_frozen_contract()
    _write_json_file(root / "openspec" / "verification-contract.yaml", contract)
    # The custom helper writes JSON, which is valid YAML for this focused
    # contract and keeps the audit fixture deterministic.
    receipts = tmp_path / "receipts"
    _minimal_frozen_receipts(runner, root, receipts, contract)
    before = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    monkeypatch.setattr(runner, "_execute", lambda *args, **kwargs: pytest.fail("audit must not start a child"))
    monkeypatch.setattr(runner, "_toolchain_observation", lambda *args, **kwargs: pytest.fail("audit must not probe a tool"))
    monkeypatch.setattr(runner, "_single_owner_lock", lambda *args, **kwargs: pytest.fail("audit must not acquire a lock"))
    report = runner.run_validation(
        root,
        Path("openspec/verification-contract.yaml"),
        receipts,
        audit_only=True,
        require_clean_git=False,
    )
    after = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert report["status"] == "passed"
    assert report["audit_only"] is True
    assert report["executed_check_ids"] == []
    assert before == after


def test_frozen_validation_creates_private_attempt_and_passes_owner_context(monkeypatch, tmp_path):
    runner = _load("run_frozen_validation")
    root = tmp_path / "repo"
    (root / "openspec").mkdir(parents=True)
    (root / "source.txt").write_text("source\n", encoding="utf-8")
    contract = _minimal_frozen_contract()
    _write_json_file(root / "openspec" / "verification-contract.yaml", contract)
    receipts = tmp_path / "receipts"
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        runner,
        "_toolchain_observation",
        lambda check: {"declared_identity": check["toolchain_identity"], "observation_hash": "sha256:" + "b" * 64},
    )

    def fake_execute(command, *, cwd, timeout, env=None):
        calls.append({"command": command, "env": env})
        if ".flowguard/test_mesh/run_checks.py" in command:
            assert env is None
            return {
                "exit_code": 0,
                "stdout": json.dumps({"status": "passed", "owner_count": 1}),
                "stderr": "",
                "timed_out": False,
                "cleanup_confirmed": True,
                "remaining_process_ids": [],
                "elapsed_seconds": 0.01,
            }
        assert env is not None
        owner_root = Path(env["LW_VALIDATION_OWNER_RUN_ROOT"])
        attempt_root = Path(env["LW_VALIDATION_OWNER_ATTEMPT_ROOT"])
        assert owner_root.is_dir()
        assert attempt_root.is_dir()
        assert owner_root != attempt_root
        assert command[-1] == str(owner_root)
        return {
            "exit_code": 0,
            "stdout": "owner ok",
            "stderr": "",
            "timed_out": False,
            "cleanup_confirmed": True,
            "remaining_process_ids": [],
            "elapsed_seconds": 0.01,
        }

    monkeypatch.setattr(runner, "_execute", fake_execute)
    report = runner.run_validation(
        root,
        Path("openspec/verification-contract.yaml"),
        receipts,
        audit_only=False,
        require_clean_git=False,
    )
    assert report["status"] == "passed"
    assert len(calls) == 1
    owner_attempts = list((receipts / "attempts" / "check.one").iterdir())
    assert len(owner_attempts) == 1
    assert (owner_attempts[0] / "run").is_dir()


def test_frozen_success_reuse_rejects_result_outside_its_attempt(tmp_path):
    runner = _load("run_frozen_validation")
    receipts = tmp_path / "receipts"
    attempt_root = receipts / "attempts" / "check.one" / "attempt-1"
    run_root = attempt_root / "run"
    run_root.mkdir(parents=True)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    execution_fingerprint = "sha256:" + "a" * 64
    result = {
        "check_id": "check.one",
        "execution_fingerprint": execution_fingerprint,
        "exit_code": 0,
        "timed_out": False,
        "cleanup_confirmed": True,
        "status": "passed",
    }
    result["result_fingerprint"] = runner._hash(result)
    foreign_result = foreign / "result.json"
    _write_json_file(foreign_result, result)
    receipt = {
        "check_id": "check.one",
        "status": "passed",
        "terminal_status": "passed",
        "exit_code": 0,
        "timed_out": False,
        "cleanup_confirmed": True,
        "execution_fingerprint": execution_fingerprint,
        "result_fingerprint": result["result_fingerprint"],
        # This is deliberately a self-consistent path that escapes the
        # private attempt.  A receipt hash alone must not make it reusable.
        "result_path": "../../../../foreign/result.json",
        "owner_context": {
            "owner_id": "check.one",
            "attempt_root": attempt_root.relative_to(receipts).as_posix(),
            "run_root": run_root.relative_to(receipts).as_posix(),
        },
    }
    receipt["receipt_hash"] = runner._receipt_hash(receipt)
    success = receipts / "success" / "check.one" / ("a" * 64 + ".json")
    _write_json_file(success, receipt)

    assert runner._load_current_success(
        success,
        execution_fingerprint,
        receipts=receipts,
        check_id="check.one",
    ) is None


def test_frozen_dependency_path_requires_passed_result_with_matching_hash(tmp_path):
    runner = _load("run_frozen_validation")
    receipts = tmp_path / "receipts"
    attempt_root = receipts / "attempts" / "check.one" / "attempt-1"
    run_root = attempt_root / "run"
    run_root.mkdir(parents=True)
    result = {
        "check_id": "check.one",
        "execution_fingerprint": "sha256:" + "b" * 64,
        "exit_code": 0,
        "timed_out": False,
        "cleanup_confirmed": True,
        "status": "passed",
    }
    result["result_fingerprint"] = runner._hash(result)
    result_path = attempt_root / "result.json"
    _write_json_file(result_path, result)
    receipt = {
        "check_id": "check.one",
        "status": "failed",
        "terminal_status": "failed",
        "exit_code": 1,
        "timed_out": False,
        "cleanup_confirmed": True,
        "execution_fingerprint": result["execution_fingerprint"],
        "result_fingerprint": result["result_fingerprint"],
        "result_path": result_path.relative_to(receipts).as_posix(),
        "owner_context": {
            "owner_id": "check.one",
            "attempt_root": attempt_root.relative_to(receipts).as_posix(),
            "run_root": run_root.relative_to(receipts).as_posix(),
        },
    }
    receipt["receipt_hash"] = runner._receipt_hash(receipt)
    with pytest.raises(ValueError, match="dependency_owner_not_passed"):
        runner._dependency_owner_run_root(
            "check.one",
            index={"check.one": receipt},
            consumers={},
            receipts=receipts,
        )


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


def test_live_release_consumers_do_not_depend_on_change_lifecycle_contracts():
    stable = ROOT / "openspec" / "verification-contract.yaml"
    assert stable.is_file()

    live_roots = (
        ROOT / "AGENTS.md",
        ROOT / "scripts",
        ROOT / "tests",
        ROOT / ".flowguard",
    )
    forbidden = "/".join(
        ("openspec", "changes", "create-logic-writing", "verification-contract.yaml")
    )
    findings = []
    for root in live_roots:
        paths = [root] if root.is_file() else root.rglob("*")
        for path in paths:
            if not path.is_file() or path.suffix.lower() not in {".md", ".py", ".json", ".yaml", ".yml"}:
                continue
            relative = path.relative_to(ROOT).as_posix()
            if relative in {
                ".flowguard/adoption_log.jsonl",
                "docs/flowguard_adoption_log.md",
            }:
                continue
            if forbidden in path.read_text(encoding="utf-8", errors="replace"):
                findings.append(relative)

    assert findings == []


def test_stable_release_contract_requires_post_archive_complete_gate():
    contract = yaml.safe_load(
        (ROOT / "openspec" / "verification-contract.yaml").read_text(
            encoding="utf-8"
        )
    )
    checks = {item["id"]: item for item in contract["checks"]}

    assert {
        "check.models.alignment",
        "check.models.full",
        "check.testmesh.plan",
        "check.public.docs",
        "check.privacy",
        "check.release.source",
        "check.tests.full",
        "check.skillguard.project",
        "check.openspec.strict",
    }.issubset(checks)
    assert checks["check.tests.full"]["args"] == ["-m", "pytest", "-q"]
    assert checks["check.openspec.strict"]["args"] == [
        "validate",
        "--all",
        "--strict",
    ]
    assert "check.tests.full" in checks["check.openspec.strict"][
        "depends_on_receipts"
    ]
