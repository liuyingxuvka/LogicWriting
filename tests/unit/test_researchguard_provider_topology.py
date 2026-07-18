from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import provider_preflight

from scripts.check_researchguard_topology import check


def _completed(argv, **_kwargs):
    if argv[1:] == ["--version"]:
        return SimpleNamespace(returncode=0, stdout="researchguard 0.1.0\n", stderr="")
    if argv[1:] in (["logic", "--help"], ["source", "--help"], ["trace", "--help"]):
        return SimpleNamespace(returncode=0, stdout="member help\n", stderr="")
    raise AssertionError(f"unexpected command: {argv}")


def test_each_member_uses_one_researchguard_console(monkeypatch):
    calls: list[list[str]] = []

    monkeypatch.setattr(provider_preflight.shutil, "which", lambda name: "RG" if name == "researchguard" else None)

    def recording_run(argv, **kwargs):
        calls.append(list(argv))
        return _completed(argv, **kwargs)

    monkeypatch.setattr(provider_preflight.subprocess, "run", recording_run)

    expected = {
        "logicguard": ("logic", "primary:researchguard:logic"),
        "sourceguard": ("source", "primary:researchguard:source"),
        "traceguard": ("trace", "primary:researchguard:trace"),
    }
    for member_id, (member_command, primary_path) in expected.items():
        result = provider_preflight.preflight(member_id)
        assert result["status"] == "current_pass"
        assert result["evidence"]["provider_console_id"] == "researchguard"
        assert result["evidence"]["member_command"] == member_command
        assert result["evidence"]["primary_path_id"] == primary_path
        assert result["evidence"]["suite_version"] == "0.1.0"

    assert calls == [
        ["RG", "--version"],
        ["RG", "logic", "--help"],
        ["RG", "--version"],
        ["RG", "source", "--help"],
        ["RG", "--version"],
        ["RG", "trace", "--help"],
    ]


def test_missing_console_blocks_without_old_module_import(monkeypatch):
    monkeypatch.setattr(provider_preflight.shutil, "which", lambda _name: None)
    monkeypatch.setattr(
        provider_preflight.importlib,
        "import_module",
        lambda name: (_ for _ in ()).throw(AssertionError(f"unexpected import: {name}")),
    )

    result = provider_preflight.preflight("logicguard")

    assert result["status"] == "provider_unavailable"
    assert result["evidence"]["console_resolved"] is False


def test_member_timeout_is_visible_and_has_no_retry(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(provider_preflight.shutil, "which", lambda _name: "RG")

    def timed_out(argv, **_kwargs):
        calls.append(list(argv))
        if argv[1:] == ["--version"]:
            return SimpleNamespace(returncode=0, stdout="researchguard 0.1.0\n", stderr="")
        raise subprocess.TimeoutExpired(argv, provider_preflight.PROBE_TIMEOUT_SECONDS)

    monkeypatch.setattr(provider_preflight.subprocess, "run", timed_out)

    result = provider_preflight.preflight("traceguard")

    assert result["status"] == "provider_unavailable"
    assert result["evidence"]["member_capability_probe"]["timed_out"] is True
    assert calls == [["RG", "--version"], ["RG", "trace", "--help"]]


def test_member_provider_root_is_rejected_before_console_execution(monkeypatch, tmp_path):
    monkeypatch.setattr(
        provider_preflight.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("console must not run")),
    )

    result = provider_preflight.preflight("sourceguard", provider_root=str(tmp_path))

    assert result["status"] == "blocked"
    assert "provider-root overrides" in result["evidence"]["reason"]


def test_current_consumer_has_zero_retired_researchguard_routes():
    root = Path(__file__).resolve().parents[2]
    report = check(root)

    assert report["ok"], report["findings"]
