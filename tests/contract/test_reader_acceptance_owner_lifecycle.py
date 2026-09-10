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
