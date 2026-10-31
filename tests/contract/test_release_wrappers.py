from __future__ import annotations

import copy
import importlib.util
import json
import shutil
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


def test_skill_static_validator_accepts_placeholder_detector_source():
    validator = _load("validate_skill")
    report = validator.validate_skill(ROOT / "skills" / "logic-writing")

    assert report["status"] == "passed"
    assert report["errors"] == []


def test_skill_validator_counts_no_lines_or_characters(tmp_path):
    validator = _load("validate_skill")
    skill = tmp_path / "logic-writing"
    shutil.copytree(ROOT / "skills" / "logic-writing", skill)
    skill_md = skill / "SKILL.md"
    padded = skill_md.read_text(encoding="utf-8") + "\n" + "<!-- padding -->\n" * 150
    skill_md.write_text(padded, encoding="utf-8")

    report = validator.validate_skill(skill)
    assert report["status"] == "passed", report["errors"]

    description = next(line for line in padded.splitlines() if line.startswith("description:"))
    short = padded.replace(description, "description: Use for academic and investigation pieces.", 1)
    skill_md.write_text(short, encoding="utf-8")
    report = validator.validate_skill(skill)
    assert report["status"] == "passed", report["errors"]

    skill_md.write_text(short.replace("academic and investigation", "academic", 1), encoding="utf-8")
    report = validator.validate_skill(skill)
    assert report["status"] == "failed"
    assert report["errors"] == ["frontmatter description must explain both activation routes"]


def test_public_docs_fallback_scans_every_file(tmp_path, monkeypatch):
    public_docs = _load("check_public_docs")
    monkeypatch.setattr(public_docs, "git_lines", lambda *_args: [])
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "coordination.md").write_text("local only\n", encoding="utf-8")
    (docs / "architecture.md").write_text("public\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")

    inventory = public_docs._public_inventory(tmp_path)

    # Outside git nothing is hidden: an executor journal is public inventory and is rejected.
    assert {"docs/coordination.md", "docs/architecture.md"} <= inventory
    assert ".git/HEAD" not in inventory


def test_public_docs_reject_executor_journals(monkeypatch):
    public_docs = _load("check_public_docs")
    monkeypatch.setattr(public_docs, "_public_inventory", lambda _root: {"SLIM_LOG.md", "XR_LOG.md"})

    report = public_docs.check(ROOT)

    assert report["status"] == "failed"
    assert "internal_record_is_public:SLIM_LOG.md" in report["findings"]
    assert "internal_record_is_public:XR_LOG.md" in report["findings"]


def test_privacy_fallback_scans_every_file(tmp_path, monkeypatch):
    privacy = _load("check_privacy")
    monkeypatch.setattr(privacy, "git_lines", lambda *_args: [])
    machine_path = "C:" + chr(92) + "Users" + chr(92) + "example" + chr(92) + "secret"
    docs = tmp_path / "docs"
    docs.mkdir()
    public = docs / "architecture.md"
    public.write_text("public and portable\n", encoding="utf-8")
    cache = tmp_path / "run-artifacts"
    cache.mkdir()
    (cache / "local.json").write_text(json.dumps({"path": machine_path}), encoding="utf-8")

    assert privacy.scan(tmp_path)["status"] == "passed"

    public.write_text(machine_path, encoding="utf-8")
    assert privacy.scan(tmp_path)["status"] == "failed"
