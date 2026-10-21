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
