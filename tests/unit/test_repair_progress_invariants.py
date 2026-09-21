from __future__ import annotations

from copy import deepcopy

import pytest

from _common import ValidationError, fingerprint, fingerprint_without
from reader_pipeline import build_artifact_map, build_repair_request, record_repair_result
from tests.v2_support import complete_chain, closure_input
from derive_closure import derive_closure


def _request(chain: dict) -> dict:
    return build_repair_request(
        repair_id="repair:test",
        attempt_number=1,
        reader_brief=chain["reader_brief"],
        artifact_map=chain["artifact_map"],
        shared_writing=chain["shared_writing"],
        deterministic_audit=chain["deterministic_audit"],
        route_review=chain["route_review"],
        judgment=chain["judgment"],
        defect_lineage="lineage:test",
    )


def _changed_output(chain: dict, *, suffix: str = " 修补后的句子。") -> dict:
    path = chain["artifact_path"]
    path.write_text(path.read_text(encoding="utf-8") + suffix, encoding="utf-8")
    return build_artifact_map(path, map_id="map:changed", language=chain["artifact_map"]["language"])


def _current_judgment(chain: dict, output: dict, defect_ids: list[str]) -> dict:
    current = deepcopy(chain["judgment"])
    current["artifact_fingerprint"] = output["artifact_fingerprint"]
    current["artifact_map_fingerprint"] = output["map_fingerprint"]
    current["defects"] = [
        {
            "observation_id": defect_id,
            "dimension": "coherence",
            "message": "The current artifact still has this bounded defect.",
            "severity": "repair",
            "evidence": chain["judgment"]["defects"][0]["evidence"],
        }
        for defect_id in defect_ids
    ]
    current["required_repairs"] = [] if not defect_ids else [{
        "repair_id": "repair:coherence",
        "defect_ids": defect_ids,
        "target_unit_ids": [chain["paragraph"]["artifact_unit_id"]],
        "required_change": "Rebuild the opening-to-conclusion dependency.",
        "repair_owner": chain["judgment"]["final_owner"],
    }]
    current["status"] = "passed" if not defect_ids else "repair"
    current["judgment_fingerprint"] = fingerprint_without(current, "judgment_fingerprint")
    return current


def _record(chain: dict, request: dict, output: dict, *, defects: list[str], **kwargs) -> dict:
    return record_repair_result(
        request=request,
        output_artifact_map=output,
        changed_unit_ids=kwargs.pop("changed_unit_ids", [chain["paragraph"]["artifact_unit_id"]]),
        preserved_content_unit_ids=["content:answer"],
        preservation_violations=kwargs.pop("preservation_violations", []),
        remaining_defect_ids=defects,
        current_judgment=_current_judgment(chain, output, defects),
    )


def test_request_uses_current_judgment_defects_and_v21_contract(tmp_path):
    chain = complete_chain(tmp_path, pass_quality=False)
    request = _request(chain)
    assert request["schema_version"] == "2.1"
    assert request["initial_defect_ids"] == ["judge:defect"]
    assert request["defect_set_fingerprint"] == fingerprint(["judge:defect"])


def test_empty_judgment_defects_cannot_bypass_upstream_failure(tmp_path):
    chain = complete_chain(tmp_path, pass_quality=False)
    judgment = deepcopy(chain["judgment"])
    judgment["defects"] = []
    judgment["required_repairs"] = []
    judgment["status"] = "repair"
    judgment["judgment_fingerprint"] = fingerprint_without(judgment, "judgment_fingerprint")
    with pytest.raises(ValidationError, match="must expose"):
        build_repair_request(
            repair_id="repair:empty",
            attempt_number=1,
            reader_brief=chain["reader_brief"],
            artifact_map=chain["artifact_map"],
            shared_writing=chain["shared_writing"],
            deterministic_audit=chain["deterministic_audit"],
            route_review=chain["route_review"],
            judgment=judgment,
            defect_lineage="lineage:test",
        )


@pytest.mark.parametrize(
    ("defects", "expected"),
    [
        (["judge:defect"], "no_progress"),
        (["defect:new", "judge:defect"], "no_progress"),
        (["defect:new"], "no_progress"),
        ([], "progressed"),
    ],
)
def test_progress_requires_changed_bytes_and_strict_original_subset(
    tmp_path, defects, expected
):
    chain = complete_chain(tmp_path, pass_quality=False)
    request = _request(chain)
    output = _changed_output(chain)
    result = _record(chain, request, output, defects=defects)
    assert result["schema_version"] == "2.1"
    assert result["remaining_defect_ids"] == sorted(defects)
    assert result["progress_status"] == expected


def test_preservation_violation_blocks_even_when_defects_shrink(tmp_path):
    chain = complete_chain(tmp_path, pass_quality=False)
    request = _request(chain)
    output = _changed_output(chain)
    result = _record(
        chain,
        request,
        output,
        defects=[],
        preservation_violations=["content:answer"],
    )
    assert result["progress_status"] == "blocked"


def test_caller_list_cannot_authorize_progress_without_current_judgment(tmp_path):
    chain = complete_chain(tmp_path, pass_quality=False)
    request = _request(chain)
    output = _changed_output(chain)
    result = record_repair_result(
        request=request,
        output_artifact_map=output,
        changed_unit_ids=[chain["paragraph"]["artifact_unit_id"]],
        preserved_content_unit_ids=["content:answer"],
        preservation_violations=[],
        remaining_defect_ids=[],
    )
    assert result["progress_status"] == "blocked"
    assert result["verification_evidence"]["status"] == "missing"


def test_old_repair_request_schema_is_rejected(tmp_path):
    chain = complete_chain(tmp_path, pass_quality=False)
    request = _request(chain)
    request["schema_version"] = "2.0"
    request["request_fingerprint"] = fingerprint_without(request, "request_fingerprint")
    with pytest.raises(Exception):
        record_repair_result(
            request=request,
            output_artifact_map=chain["artifact_map"],
            changed_unit_ids=[],
            preserved_content_unit_ids=[],
            preservation_violations=[],
            remaining_defect_ids=["judge:defect"],
            current_judgment=chain["judgment"],
        )


def test_closure_rejects_tampered_remaining_ids_or_fingerprint(tmp_path):
    chain = complete_chain(tmp_path, pass_quality=False)
    artifact = chain["artifact_map"]["artifact_fingerprint"]
    result = {
        "schema_version": "2.1",
        "repair_id": "repair:tamper",
        "request_fingerprint": fingerprint({"request": "tamper"}),
        "defect_lineage": "lineage:tamper",
        "input_artifact_fingerprint": fingerprint({"before": "tamper"}),
        "output_artifact_fingerprint": artifact,
        "changed_unit_ids": [],
        "preservation_check": {
            "status": "passed",
            "preserved_content_unit_ids": ["content:answer"],
            "violations": [],
        },
        "remaining_defect_ids": ["judge:defect"],
        "remaining_defect_set_fingerprint": fingerprint(["wrong:id"]),
        "verification_evidence": {
            "status": "current",
            "artifact_fingerprint": artifact,
            "artifact_map_fingerprint": chain["artifact_map"]["map_fingerprint"],
            "audit_fingerprint": chain["deterministic_audit"]["audit_fingerprint"],
            "route_audit_fingerprint": chain["route_review"]["review_fingerprint"],
            "judgment_fingerprint": chain["judgment"]["judgment_fingerprint"],
        },
        "progress_status": "no_progress",
        "rerun_required": [
            "artifact_map", "shared_writing", "deterministic_audit",
            "route_audit", "reader_judgment",
        ],
    }
    result["result_fingerprint"] = fingerprint(result)
    chain["repair_results"] = [result]
    with pytest.raises(ValidationError, match="remaining defect set"):
        derive_closure(closure_input(chain))
