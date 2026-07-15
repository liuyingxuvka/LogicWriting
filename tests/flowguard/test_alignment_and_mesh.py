"""Regression checks for FlowGuard alignment and validation ownership."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from flowguard import review_model_test_alignment, review_test_mesh


FLOWGUARD_ROOT = Path(__file__).resolve().parents[2] / ".flowguard"


def _load_model(name: str, child: str):
    path = FLOWGUARD_ROOT / child / "model.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_model_code_test_alignment_is_current_and_rejects_missing_actual_artifact_evidence():
    module = _load_model("logic_writing_alignment_model", "model_test_alignment")
    assert review_model_test_alignment(module.aligned_plan()).ok
    assert not review_model_test_alignment(module.broken_missing_actual_artifact_plan()).ok


def test_test_mesh_has_complete_structure_and_expected_pending_receipts():
    # Import by file path because both FlowGuard satellites conventionally use
    # a module named ``model``.
    module = _load_model("logic_writing_test_mesh_model", "test_mesh")

    plan = module.release_plan()
    report = review_test_mesh(plan)
    codes = {finding.code for finding in report.findings}
    assert not report.ok
    assert "missing_target_split_derivation" not in codes
    assert "target_split_partition_coverage_missing" not in codes
    assert "unregistered_partition_owner" not in codes

    broken = review_test_mesh(module.broken_missing_target_split_plan())
    assert not broken.ok
    assert "missing_target_split_derivation" in {finding.code for finding in broken.findings}


def test_frozen_execution_boundary_covers_runtime_and_internal_record_misses():
    path = FLOWGUARD_ROOT / "models" / "frozen_source_contract_exhaustion.py"
    spec = importlib.util.spec_from_file_location(
        "logic_writing_frozen_execution_boundary", path
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    report = module.review_frozen_execution_boundary()

    assert report.ok
    assert module.EXECUTION_BOUNDARY_MEMBERS == (
        "runtime-prerequisite-declared-as-source",
        "ignored-coordination-record-admitted",
        "ignored-adoption-record-admitted",
        "ignored-verification-output-admitted",
        "check-input-selector-unbound",
        "vcs-metadata-required-inside-frozen-root",
    )
    assert set(module.EXECUTION_CASE_IDS).issubset(
        {case.case_id for case in report.generated_cases}
    )
    assert len(report.coverage_receipts) == 1
