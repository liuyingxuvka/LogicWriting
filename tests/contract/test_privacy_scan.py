from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "logic_writing_check_privacy",
    ROOT / "scripts" / "check_privacy.py",
)
assert SPEC is not None and SPEC.loader is not None
check_privacy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_privacy)


def test_privacy_scan_includes_its_own_source():
    report = check_privacy.scan(ROOT)

    assert report["status"] == "passed"
    assert not report["findings"]


def test_private_case_digest_rejects_matching_ngram_without_plaintext_rule(
    tmp_path, monkeypatch
):
    phrase = "neutral private sentinel"
    digest = hashlib.sha256(phrase.encode("utf-8")).hexdigest()
    monkeypatch.setattr(check_privacy, "SENSITIVE_NGRAM_HASHES", {3: {digest}})
    (tmp_path / "candidate.md").write_text(
        f"Public material followed by {phrase} and more text.",
        encoding="utf-8",
    )

    report = check_privacy.scan(tmp_path)

    assert report["status"] == "failed"
    assert report["findings"] == [
        {"path": "candidate.md", "pattern": "private_case_marker"}
    ]
