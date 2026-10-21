from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALL = ROOT / "scripts" / "install_skill.py"


def run(*args):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, cwd=ROOT)


def test_install_copies_runtime_skill_without_repository_fixtures(tmp_path):
    assert run(INSTALL, "--target", tmp_path).returncode == 0
    installed = tmp_path / "logic-writing"
    assert (installed / "SKILL.md").is_file()
    assert (installed / "scripts" / "derive_closure.py").is_file()
    assert (installed / "routes" / "travel" / "scripts" / "fixture_mutation.py").is_file()
    assert not (installed / "routes" / "fiction" / "examples").exists()
    assert not (installed / "routes" / "travel" / "examples").exists()
    assert not list(installed.rglob("run_*_regression.py"))
    assert not list(installed.rglob("__pycache__"))
    assert run(INSTALL, "--target", tmp_path, "--check").returncode == 0
    validated = run(ROOT / "scripts" / "validate_skill.py", "--skill-root", installed)
    assert validated.returncode == 0, validated.stdout + validated.stderr
    for script in ("scripts/select_route.py", "routes/travel/scripts/validate_travel_plan.py"):
        assert run(installed / script, "--help").returncode == 0, script


def test_check_reports_a_changed_installed_copy(tmp_path):
    assert run(INSTALL, "--target", tmp_path).returncode == 0
    skill = tmp_path / "logic-writing" / "SKILL.md"
    skill.write_text(skill.read_text(encoding="utf-8") + "\nlocal edit\n", encoding="utf-8")
    checked = run(INSTALL, "--target", tmp_path, "--check")
    assert checked.returncode == 1
    assert "differs: SKILL.md" in checked.stdout
