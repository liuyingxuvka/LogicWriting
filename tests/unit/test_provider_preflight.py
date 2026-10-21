from __future__ import annotations

from pathlib import Path

import provider_preflight


def test_documents_provider_accepts_the_docx_skill(tmp_path: Path):
    root = tmp_path / "docx"
    root.mkdir()
    (root / "SKILL.md").write_text("---\nname: docx\n---\nCreate and edit .docx files.\n", encoding="utf-8")
    result = provider_preflight.preflight("documents", provider_root=str(root))
    assert result["status"] == "current_pass"
    assert result["evidence"]["provider_id_matches"] is True


def test_worldguard_is_found_next_to_logic_writing(monkeypatch, tmp_path: Path):
    from types import SimpleNamespace
    root = tmp_path / "skills" / "worldguard"
    (root / "runtime/worldguard").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "SKILL.md").write_text("---\nname: worldguard\n---\nPortable world checks.\n", encoding="utf-8")
    (root / "runtime/worldguard/__init__.py").write_text('__version__ = "0.7.15"\n', encoding="utf-8")
    (root / "runtime/worldguard/cli.py").write_text("def main(): pass\n", encoding="utf-8")
    (root / "scripts/run_worldguard.py").write_text(
        'from pathlib import Path\nimport sys\nRUNTIME_ROOT = Path(__file__).resolve().parents[1] / "runtime"\n'
        'if str(RUNTIME_ROOT) not in sys.path:\n    sys.path.insert(0, str(RUNTIME_ROOT))\n'
        'from worldguard.cli import main\n', encoding="utf-8")
    local_scripts = tmp_path / "skills/logic-writing/scripts"
    local_scripts.mkdir(parents=True)
    monkeypatch.setattr(provider_preflight, "__file__", str(local_scripts / "provider_preflight.py"))
    monkeypatch.setattr(provider_preflight.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="--contract --example"))
    result = provider_preflight.preflight("worldguard")
    assert result["status"] == "current_pass"
    assert result["evidence"]["provider_root_source"] == "sibling_skill"


def test_worldguard_repository_skill_uses_the_repository_package(monkeypatch, tmp_path: Path):
    from types import SimpleNamespace

    repo = tmp_path / "worldguard-repo"
    root = repo / "skills" / "worldguard"
    (root / "scripts").mkdir(parents=True)
    (repo / "worldguard").mkdir()
    (root / "SKILL.md").write_text("---\nname: worldguard\n---\nPortable world checks.\n", encoding="utf-8")
    (root / "scripts/run_worldguard.py").write_text(
        'from pathlib import Path\nimport sys\nRUNTIME_ROOT = Path(__file__).resolve().parents[1] / "runtime"\n'
        'if (RUNTIME_ROOT / "worldguard" / "__init__.py").is_file():\n    sys.path.insert(0, str(RUNTIME_ROOT))\n'
        'from worldguard.cli import main\n', encoding="utf-8")
    (repo / "worldguard/__init__.py").write_text('__version__ = "0.7.16"\n', encoding="utf-8")
    (repo / "worldguard/cli.py").write_text("def main(): pass\n", encoding="utf-8")
    monkeypatch.setattr(
        provider_preflight.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="--contract --example"),
    )

    result = provider_preflight.preflight("worldguard", provider_root=str(root))

    assert result["status"] == "current_pass"
    assert result["evidence"]["provider_version"] == "0.7.16"
