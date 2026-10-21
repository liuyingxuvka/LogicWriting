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
