from __future__ import annotations

import copy

import pytest

from _common import ValidationError, fingerprint
from derive_closure import derive_closure
from tests.v2_support import closure_input, complete_chain


@pytest.mark.parametrize(
    "owner",
    ["investigation", "academic-writing", "fiction-writing", "travel-guide"],
)
def test_complete_current_chain_closes(owner, tmp_path):
    result = derive_closure(closure_input(complete_chain(tmp_path, owner)))
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


def test_two_actual_no_progress_results_stop_only_same_lineage(tmp_path):
    chain = complete_chain(tmp_path, pass_quality=False)
    artifact = chain["artifact_map"]["artifact_fingerprint"]
    defect_fp = fingerprint(["judge:defect"])
    first = {
        "schema_version": "2.0", "repair_id": "repair:one",
        "request_fingerprint": fingerprint({"request": 1}),
        "defect_lineage": "lineage:one",
        "input_artifact_fingerprint": fingerprint({"before": 1}),
        "output_artifact_fingerprint": artifact,
        "changed_unit_ids": [], "preservation_check": {
            "status": "passed", "preserved_content_unit_ids": ["content:answer"], "violations": [],
        },
        "remaining_defect_set_fingerprint": defect_fp,
        "progress_status": "no_progress",
        "rerun_required": ["artifact_map", "shared_writing", "deterministic_audit", "route_audit", "reader_judgment"],
    }
    first["result_fingerprint"] = fingerprint(first)
    second = copy.deepcopy(first)
    second["repair_id"] = "repair:two"
    second["request_fingerprint"] = fingerprint({"request": 2})
    second["input_artifact_fingerprint"] = artifact
    second["result_fingerprint"] = fingerprint(second)
    chain["repair_results"] = [first, second]
    result = derive_closure(closure_input(chain))
    assert result["closure"]["status"] == "no_progress_blocked"
    assert result["closure"]["terminal"] is True


def test_foreign_reader_intent_is_rejected(tmp_path):
    request = closure_input(complete_chain(tmp_path))
    request["reader_brief"] = copy.deepcopy(request["reader_brief"])
    request["reader_brief"]["reader_intent_fingerprint"] = fingerprint({"foreign": True})
    with pytest.raises(ValidationError):
        derive_closure(request)
