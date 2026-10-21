from __future__ import annotations

from copy import deepcopy
import json

import pytest

from _common import ValidationError, fingerprint, fingerprint_text, fingerprint_without
from reader_pipeline import build_artifact_map, build_reader_audit, build_repair_request, record_repair_result
from tests.v2_support import complete_chain, closure_input
from tests.v2_support import derive_protocol_closure as derive_closure


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


def _current_evidence(chain: dict, output: dict, defect_ids: list[str]) -> dict:
    """Build the current judgment evidence for the revised artifact; no live judge or quality claim."""
    units = [row for row in output["units"] if row["unit_kind"] in {"paragraph", "list", "table", "quote", "scene"}]
    def evidence(unit):
        excerpt = unit["text"][:60]
        return {"artifact_unit_id": unit["artifact_unit_id"], "locator": unit["locator"],
                "excerpt": excerpt, "excerpt_fingerprint": fingerprint_text(excerpt)}
    current = deepcopy(chain["judgment"])
    shared = deepcopy(chain["shared_writing"])
    shared.update(artifact_map_fingerprint=output["map_fingerprint"], artifact_fingerprint=output["artifact_fingerprint"])
    shared["unit_bindings"][0].update(
        artifact_unit_ids=[row["artifact_unit_id"] for row in units],
        artifact_spans=[{key: row[key] for key in ("artifact_unit_id", "locator", "content_fingerprint")} for row in units],
    )
    shared["contract_fingerprint"] = fingerprint_without(shared, "contract_fingerprint")
    audit = build_reader_audit(audit_id="audit:current", artifact_map=output,
                               reader_brief=chain["reader_brief"], shared_writing=shared)
    route = deepcopy(chain["route_review"])
    route.update(artifact_map_fingerprint=output["map_fingerprint"], artifact_fingerprint=output["artifact_fingerprint"])
    for row in route["dimensions"]:
        row["status"] = "passed"
        row["evidence"] = [evidence(units[0])]
    route.update(findings=[], required_repairs=[], status="passed")
    route["review_fingerprint"] = fingerprint_without(route, "review_fingerprint")
    current.update(artifact_fingerprint=output["artifact_fingerprint"], artifact_map_fingerprint=output["map_fingerprint"],
                   shared_writing_contract_fingerprint=shared["contract_fingerprint"],
                   deterministic_audit_fingerprint=audit["audit_fingerprint"], route_audit_fingerprint=route["review_fingerprint"])
    for row, unit in zip(current["reverse_outline"], units, strict=True):
        row["artifact_unit_id"] = unit["artifact_unit_id"]
        row["evidence"] = evidence(unit)
    current["strengths"][0]["evidence"] = evidence(units[0])
    current["defects"] = [{"observation_id": defect_id, "dimension": "coherence",
                           "message": "The current artifact still has this bounded defect.",
                           "severity": "repair", "evidence": evidence(units[0])} for defect_id in defect_ids]
    current["required_repairs"] = [] if not defect_ids else [{
        "repair_id": "repair:coherence", "defect_ids": defect_ids,
        "target_unit_ids": [units[0]["artifact_unit_id"]],
        "required_change": "Rebuild the opening-to-conclusion dependency.",
        "repair_owner": current["final_owner"],
    }]
    current["scores"] = {key: 3 if defect_ids else 5 for key in current["scores"]}
    current["status"] = "repair" if defect_ids else "passed"
    current["judgment_fingerprint"] = fingerprint_without(current, "judgment_fingerprint")
    return {"current_judgment": current, "reader_brief": chain["reader_brief"],
            "shared_writing": shared, "deterministic_audit": audit,
            "route_composition": chain["route_composition"], "route_review": route}


def _record(chain: dict, request: dict, output: dict, *, defects: list[str], **kwargs) -> dict:
    return record_repair_result(
        request=request, output_artifact_map=output,
        changed_unit_ids=kwargs.pop("changed_unit_ids", [chain["paragraph"]["artifact_unit_id"]]),
        preserved_content_unit_ids=["content:answer"],
        preservation_violations=kwargs.pop("preservation_violations", []), remaining_defect_ids=defects,
        **_current_evidence(chain, output, defects),
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
    fabricated = deepcopy(chain["judgment"])
    fabricated.update(artifact_fingerprint=output["artifact_fingerprint"], artifact_map_fingerprint=output["map_fingerprint"],
                      defects=[], required_repairs=[], status="passed")
    fabricated["judgment_fingerprint"] = fingerprint_without(fabricated, "judgment_fingerprint")
    with pytest.raises(ValidationError):
        record_repair_result(request=request, output_artifact_map=output,
            changed_unit_ids=[], preserved_content_unit_ids=[], preservation_violations=[],
            remaining_defect_ids=[], current_judgment=fabricated)


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


def test_captured_strict_subset_can_progress_while_judgment_still_needs_repair(tmp_path):
    chain = complete_chain(tmp_path, pass_quality=False)
    second = deepcopy(chain["judgment"]["defects"][0])
    second["observation_id"] = "judge:second"
    chain["judgment"]["defects"].append(second)
    chain["judgment"]["required_repairs"][0]["defect_ids"].append("judge:second")
    chain["judgment"]["judgment_fingerprint"] = fingerprint_without(chain["judgment"], "judgment_fingerprint")
    request = _request(chain)
    output = _changed_output(chain)
    result = _record(chain, request, output, defects=["judge:defect"])
    assert result["progress_status"] == "progressed"
    assert result["verification_evidence"]["status"] == "current"


@pytest.mark.parametrize("tamper", ["status", "remaining_ids"])
def test_current_judgment_and_remaining_defects_cannot_be_rewritten(tmp_path, tamper):
    chain = complete_chain(tmp_path, pass_quality=False)
    request = _request(chain)
    output = _changed_output(chain)
    evidence = _current_evidence(chain, output, ["judge:defect"])
    remaining = ["judge:defect"]
    if tamper == "status":
        evidence["current_judgment"]["status"] = "passed"
        evidence["current_judgment"]["judgment_fingerprint"] = fingerprint_without(evidence["current_judgment"], "judgment_fingerprint")
    else:
        remaining = []
    with pytest.raises(ValidationError):
        record_repair_result(request=request, output_artifact_map=output,
            changed_unit_ids=[chain["paragraph"]["artifact_unit_id"]], preserved_content_unit_ids=["content:answer"],
            preservation_violations=[], remaining_defect_ids=remaining, **evidence)


def test_same_bytes_cannot_progress_even_with_current_captured_pass(tmp_path):
    chain = complete_chain(tmp_path, pass_quality=False)
    result = _record(chain, _request(chain), chain["artifact_map"], defects=[])
    assert result["progress_status"] == "no_progress"
    assert result["verification_evidence"]["status"] == "current"
