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
    assert not (installed / "routes" / "travel" / "scripts" / "fixture_mutation.py").exists()
    assert not list(installed.rglob(".gitkeep"))
    assert not (installed / "routes" / "fiction" / "examples").exists()
    assert not (installed / "routes" / "travel" / "examples").exists()
    assert not list(installed.rglob("run_*_regression.py"))
    assert not list(installed.rglob("__pycache__"))
    guide = ROOT / "tests/fixtures/trials/trialC/guide.md"
    checked_guide = run(installed / "routes/travel/scripts/validate_travel_text_outputs.py", "--guide", guide, "--json")
    assert checked_guide.returncode == 1, checked_guide.stdout + checked_guide.stderr
    assert '"warnings"' in checked_guide.stdout
    assert run(INSTALL, "--target", tmp_path, "--check").returncode == 0
    validated = run(ROOT / "scripts" / "validate_skill.py", "--skill-root", installed)
    assert validated.returncode == 0, validated.stdout + validated.stderr
    for script in ("scripts/select_route.py", "routes/travel/scripts/validate_travel_plan.py", "routes/travel/scripts/validate_travel_text_outputs.py"):
        assert run(installed / script, "--help").returncode == 0, script


def test_check_reports_a_changed_installed_copy(tmp_path):
    assert run(INSTALL, "--target", tmp_path).returncode == 0
    skill = tmp_path / "logic-writing" / "SKILL.md"
    skill.write_text(skill.read_text(encoding="utf-8") + "\nlocal edit\n", encoding="utf-8")
    checked = run(INSTALL, "--target", tmp_path, "--check")
    assert checked.returncode == 1
    assert "differs: SKILL.md" in checked.stdout


def test_comparison_rechecks_same_size_and_mtime_bytes_in_one_process(tmp_path):
    import importlib.util
    import os
    import shutil

    spec = importlib.util.spec_from_file_location("installer_byte_check", INSTALL)
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    source, target = tmp_path / "source", tmp_path / "target"
    names = ("SKILL.md", "agents/openai.yaml")
    for name in names:
        for root in (source, target):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(installer.SOURCE / name, path)
    assert installer.differences(source, target) == []
    for name in names:
        path = target / name
        original, stat = path.read_bytes(), path.stat()
        path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        assert path.stat().st_size == stat.st_size
        assert path.stat().st_mtime_ns == stat.st_mtime_ns
        assert installer.differences(source, target) == [f"differs: {name}"]
        path.write_bytes(original)
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        assert installer.differences(source, target) == []
