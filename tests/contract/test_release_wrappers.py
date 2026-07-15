from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


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
