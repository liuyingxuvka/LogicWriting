from __future__ import annotations

import json
from pathlib import Path

import run_reader_acceptance_owner as owner


def test_owner_initialization_failure_leaves_incomplete_receipt_set(tmp_path):
    root = Path(__file__).resolve().parents[2]
    output_dir = tmp_path / "producer-output"

    result = owner.run_owner(
        root,
        output_dir=output_dir,
        backend_plan=tmp_path / "missing-local-backend-plan.json",
    )

    assert result["status"] == "incomplete"
    assert result["terminal_reason"].startswith("producer_initialization_failed:")
    for name in (
        "benchmark_plan.json",
        "planned-ledger.json",
        "writers.json",
        "judges.json",
        "summary.json",
        "run_result.json",
        "output-manifest.json",
        "producer-result.json",
        "dependency-index.json",
    ):
        assert (output_dir / name).is_file(), name

    manifest = json.loads((output_dir / "output-manifest.json").read_text(encoding="utf-8"))
    assert manifest["evidence_mode"] == "real_execution"
    assert manifest["terminal_status"] == "incomplete"
    assert manifest["writer_count"] == 0
    assert manifest["judge_count"] == 0
    assert json.loads((output_dir / "writers.json").read_text(encoding="utf-8")) == []
    assert json.loads((output_dir / "judges.json").read_text(encoding="utf-8")) == []


def test_aggregate_only_is_read_only_and_does_not_enter_benchmark(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    output_dir = tmp_path / "existing-run"
    output_dir.mkdir()
    stale = {
        "mode": "pair",
        "source_manifest_fingerprint": "sha256:" + "0" * 64,
        "implementation_fingerprint": "sha256:" + "0" * 64,
        "execution_policy_fingerprint": "sha256:" + "0" * 64,
        "backend_id": "old-backend",
        "model_id": "old-model",
        "reasoning_effort": "old-effort",
        "cli_version": "old-cli",
        "cli_sha256": "sha256:" + "0" * 64,
    }
    values = {
        "benchmark_plan.json": stale,
        "output-manifest.json": stale,
        "run_result.json": stale,
        "summary.json": {"status": "incomplete"},
    }
    for name, value in values.items():
        (output_dir / name).write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    before = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in output_dir.iterdir()}

    def should_not_run(*args, **kwargs):
        raise AssertionError("aggregate-only must not enter the benchmark runner")

    monkeypatch.setattr(owner, "run_benchmark", should_not_run)
    result = owner.run_owner(
        root,
        output_dir=output_dir,
        backend_plan=None,
        run_writers=False,
        run_judges=False,
        aggregate_only=True,
    )

    assert result["status"] == "stale"
    assert result["read_only"] is True
    assert result["aggregate_only"] is True
    after = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in output_dir.iterdir()}
    assert after == before
