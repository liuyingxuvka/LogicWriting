from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


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


def test_route_smoke_covers_both_owners_and_bounded_child():
    routes = _load("check_installed_routes")
    report = routes.check(ROOT / "skills" / "logic-writing")
    assert report["status"] == "passed"
    assert [item["scenario"] for item in report["scenarios"]] == [
        "investigation",
        "academic-writing",
        "academic-with-investigation-child",
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


def test_reader_judgment_owner_prepares_and_validates_runtime_inputs(tmp_path):
    judgment = _load("check_reader_judgment")
    runtime_root = tmp_path / "reader-judgment-owner"

    report = judgment.check(ROOT, runtime_root)

    assert report["status"] == "passed"
    assert report["preparation_status"] == "passed"
    assert report["judgment_status"] == "current_pass"
    assert (runtime_root / "reader-quality-judgment.json").is_file()
    assert (runtime_root / "reader-quality-judgment-result.json").is_file()


def test_frozen_boundary_excludes_runtime_inputs_and_internal_records():
    runner = _load("run_frozen_validation")
    for relative in (
        "run-artifacts/reader-quality-judgment.json",
        "openspec/changes/create-logic-writing/verification-report.json",
        "openspec/changes/create-logic-writing/verification-receipts/receipt.json",
        "docs/coordination.md",
        "docs/flowguard_adoption_log.md",
        ".flowguard/adoption_log.jsonl",
    ):
        assert runner._is_ignored(Path(relative), explicit=True)

    contract = yaml.safe_load(
        (ROOT / "openspec/changes/create-logic-writing/verification-contract.yaml")
        .read_text(encoding="utf-8")
    )
    judgment = next(
        item for item in contract["checks"] if item["id"] == "check.reader.judgment"
    )
    assert judgment["args"] == [
        "scripts/check_reader_judgment.py",
        "--root",
        ".",
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
        ".flowguard/adoption_log.jsonl",
        "docs/coordination.md",
        "docs/flowguard_adoption_log.md",
    }.issubset(exclusions)


def test_frozen_public_checks_bind_concrete_admitted_source_manifests():
    runner = _load("run_frozen_validation")
    contract = yaml.safe_load(
        (ROOT / "openspec/changes/create-logic-writing/verification-contract.yaml")
        .read_text(encoding="utf-8")
    )
    checks = {item["id"]: item for item in contract["checks"]}
    required = {
        ".gitattributes",
        ".gitignore",
        ".logicguard/readme-capability-model.yaml",
        ".skillguard/project.json",
        "AGENTS.md",
        "CHANGELOG.md",
        "README.md",
        "README.zh-CN.md",
        "pyproject.toml",
        "scripts/_release_common.py",
        "scripts/check_privacy.py",
        "scripts/check_public_docs.py",
        "scripts/check_release_surface.py",
        "skills/logic-writing/.skillguard/checks/evaluate_contract_calibration.py",
        "skills/logic-writing/.skillguard/evidence-specs/semantic.json",
        "skills/logic-writing/.skillguard/fixtures/contract-depth-positive.json",
    }
    forbidden = {
        ".flowguard/adoption_log.jsonl",
        "docs/coordination.md",
        "docs/flowguard_adoption_log.md",
        "openspec/changes/create-logic-writing/verification-report.json",
    }

    manifests = []
    for check_id in (
        "check.public.docs",
        "check.privacy",
        "check.release.source",
    ):
        check = checks[check_id]
        assert "." not in {str(item) for item in check["input_selectors"]}
        manifest = runner._check_manifest(ROOT, check)
        assert required.issubset(manifest)
        assert forbidden.isdisjoint(manifest)
        manifests.append(manifest)

    assert manifests[0] == manifests[1] == manifests[2]
    assert checks["check.release.source"]["args"] == [
        "scripts/check_release_surface.py",
        "--root",
        ".",
        "--mode",
        "source",
        "--json",
    ]


def test_public_docs_frozen_fallback_uses_contract_admission(tmp_path, monkeypatch):
    public_docs = _load("check_public_docs")
    monkeypatch.setattr(public_docs, "git_lines", lambda *_args: [])
    contract_path = (
        tmp_path
        / "openspec"
        / "changes"
        / "create-logic-writing"
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
        / "changes"
        / "create-logic-writing"
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
