from __future__ import annotations

import copy

import pytest

from _common import ValidationError, fingerprint
from tests.v2_support import derive_protocol_closure as derive_closure
from tests.v2_support import closure_input, complete_chain


@pytest.mark.parametrize(
    "owner",
    ["investigation", "academic-writing", "fiction-writing", "travel-guide"],
)
def test_complete_current_chain_closes(owner, tmp_path, monkeypatch):
    import derive_closure as closure_module
    import reader_pipeline
    from pathlib import Path
    chain = complete_chain(tmp_path, owner)
    request = closure_input(chain)
    original_map = reader_pipeline.validate_artifact_map
    original_audit = reader_pipeline._build_reader_audit_from_current
    calls = {"map": 0, "audit": 0}
    def mapped(value):
        calls["map"] += 1
        return original_map(value)
    def audited(**kwargs):
        calls["audit"] += 1
        return original_audit(**kwargs)
    monkeypatch.setattr(closure_module, "validate_artifact_map", mapped)
    monkeypatch.setattr(reader_pipeline, "validate_artifact_map", mapped)
    monkeypatch.setattr(closure_module, "_build_reader_audit_from_current", audited)
    monkeypatch.setattr(reader_pipeline, "_build_reader_audit_from_current", audited)
    result = derive_closure(request)
    assert calls == {"map": 1, "audit": 1}
    # The actual public final boundary cannot license a synthetic marker.
    with pytest.raises(ValidationError, match="capture resolver"):
        closure_module.derive_closure(request)
    from execution_record_resolver import LocalExecutionRecordResolver
    with pytest.raises(ValidationError):
        closure_module.derive_closure(request, execution_resolver=LocalExecutionRecordResolver(tmp_path))
    def changed_during_audit(**kwargs):
        report = original_audit(**kwargs)
        artifact = Path(chain["artifact_map"]["artifact_path"])
        artifact.write_bytes(artifact.read_bytes() + b"changed")
        return report
    monkeypatch.setattr(closure_module, "_build_reader_audit_from_current", changed_during_audit)
    with pytest.raises(ValidationError, match="stale during closure"):
        derive_closure(request)
    assert result["closure"]["status"] == "passed"
    assert result["closure"]["terminal"] is True
    assert result["closure"]["broad_claim_allowed"] is True


def test_quality_failure_blocks_without_claiming_terminal(tmp_path):
    result = derive_closure(closure_input(complete_chain(tmp_path, pass_quality=False)))
    assert result["closure"]["status"] == "blocked"
    assert result["closure"]["terminal"] is False


def test_repeating_closure_does_not_count_as_repair(tmp_path):
    request = closure_input(complete_chain(tmp_path, pass_quality=False))
    first = derive_closure(request)
    second = derive_closure(request)
    assert first["closure"]["status"] == second["closure"]["status"] == "blocked"


def test_one_actual_no_progress_result_stops_same_lineage(tmp_path):
    chain = complete_chain(tmp_path, pass_quality=False)
    artifact = chain["artifact_map"]["artifact_fingerprint"]
    defect_fp = fingerprint(["judge:defect"])
    first = {
        "schema_version": "2.1", "repair_id": "repair:one",
        "request_fingerprint": fingerprint({"request": 1}),
        "defect_lineage": "lineage:one",
        "input_artifact_fingerprint": fingerprint({"before": 1}),
        "output_artifact_fingerprint": artifact,
        "changed_unit_ids": [], "preservation_check": {
            "status": "passed", "preserved_content_unit_ids": ["content:answer"], "violations": [],
        },
        "remaining_defect_ids": ["judge:defect"],
        "remaining_defect_set_fingerprint": defect_fp,
        "verification_evidence": {
            "status": "current",
            "artifact_fingerprint": artifact,
            "artifact_map_fingerprint": chain["artifact_map"]["map_fingerprint"],
            "audit_fingerprint": chain["deterministic_audit"]["audit_fingerprint"],
            "route_audit_fingerprint": chain["route_review"]["review_fingerprint"],
            "judgment_fingerprint": chain["judgment"]["judgment_fingerprint"],
        },
        "progress_status": "no_progress",
        "rerun_required": ["artifact_map", "shared_writing", "deterministic_audit", "route_audit", "reader_judgment"],
    }
    first["result_fingerprint"] = fingerprint(first)
    chain["repair_results"] = [first]
    result = derive_closure(closure_input(chain))
    assert result["closure"]["status"] == "no_progress_blocked"
    assert result["closure"]["terminal"] is True


def test_foreign_reader_intent_is_rejected(tmp_path):
    request = closure_input(complete_chain(tmp_path))
    request["reader_brief"] = copy.deepcopy(request["reader_brief"])
    request["reader_brief"]["reader_intent_fingerprint"] = fingerprint({"foreign": True})
    with pytest.raises(ValidationError):
        derive_closure(request)
