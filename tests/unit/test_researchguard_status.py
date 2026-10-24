"""One saved native verdict and source-owned anchor import, without execution."""
from __future__ import annotations

import copy
import json

import pytest
import yaml

from _common import ValidationError, load_request
from researchguard_status import assess_research_verdict, fill_anchors_from_research


def _report():
    return {"verdict": {"search": "stop_sufficient", "root_claim": {
        "id": "h-main", "wording_license": "assert", "reason": "Native support is sufficient."},
        "live_hypotheses": ["h-main"], "contested": False, "errors": 0},
        "hypotheses": [{"id": "h-main"}, {"id": "h-other"}]}


@pytest.mark.parametrize("case,passed,reason", [
    ("clean", True, "stop_sufficient"),
    ("errors", False, "research errors 1"),
    ("search", False, "search continue_search"),
    ("withhold", False, "root claim h-main withhold"),
    ("alternative", False, "alternative_status_conflict:h-other"),
    ("contested", True, "stop_sufficient"),
    ("source_only", True, "no assert license"),
    ("source_only_competitors", False, "root claim unavailable"),
])
def test_researchguard_verdict_decides_the_provider_check(case, passed, reason):
    document, alternatives = _report(), []
    verdict = document["verdict"]
    if case == "errors":
        verdict["errors"] = 1
    elif case == "search":
        verdict["search"] = "continue_search"
    elif case == "withhold":
        verdict["live_hypotheses"].append("h-other")
        verdict["root_claim"].update(wording_license="withhold", reason="Native counterevidence remains.")
    elif case == "alternative":
        document["hypotheses"][1]["experiment"] = {"status": "eliminated"}
        alternatives = [{"alternative_id": "h-other", "status": "live"}]
    elif case == "contested":
        verdict["contested"] = True
    elif case.startswith("source_only"):
        verdict["root_claim"] = None
        if case.endswith("competitors"):
            verdict["live_hypotheses"].append("h-other")
    before = copy.deepcopy(document)
    result = assess_research_verdict(document, alternatives)
    assert result["passed"] is passed
    assert reason in result["reason"]
    assert document == before
    assert any(row["defect_id"] == "research:contested" for row in result["residual_risk"]) is (case == "contested")
    if case == "source_only":
        assert any(row["defect_id"] == "research:root_claim_not_run" for row in result["residual_risk"])
        result = assess_research_verdict(document, [{"alternative_id": "h-main", "status": "live"}])
        assert result["passed"] is False and "root claim unavailable" in result["reason"]


def test_unreadable_verdict_is_not_a_provider_pass():
    for document in ({}, {"status": "current_pass"}, {"verdict": None}):
        result = assess_research_verdict(document)
        assert result["status"] == "unreadable" and result["passed"] is False
    document = _report()
    document["verdict"]["search"] = []
    assert assess_research_verdict(document)["status"] == "unreadable"


@pytest.mark.parametrize("conflict_field", ["source_id", "locator"])
def test_handwritten_anchor_conflict_is_atomic_and_missing_anchors_import(tmp_path, conflict_field):
    research = tmp_path / "research"
    research.mkdir()
    (research / "research.yaml").write_text(yaml.safe_dump({"schema": "researchguard.research.v1", "models": {"source": "source.yaml"}}))
    native = {"sources": [{"source_id": "s", "cannot_support_structural_use": "Only the quoted scope."}],
        "anchors": [{"anchor_id": "new", "source_id": "s", "locator": "p2", "normalized_summary": "New observed content."},
                    {"anchor_id": "existing", "source_id": "s", "locator": "p1", "text": "Native observed content."}]}
    (research / "source.yaml").write_text(yaml.safe_dump(native))
    authored = {"anchor_id": "existing", "source_id": "s", "locator": "p1", "relation": "limit",
                "boundary": "Author scope remains unchanged.", "observed_summary": "Author summary remains unchanged."}
    authored[conflict_field] = "conflicting owner"
    request = {"research_folder": str(research), "content_boundaries": {"evidence_anchors": [authored]}}
    before = copy.deepcopy(request)
    with pytest.raises(ValidationError, match="anchor_conflict:existing"):
        fill_anchors_from_research(request)
    assert request == before
    authored[conflict_field] = "s" if conflict_field == "source_id" else "p1"
    preserved = copy.deepcopy(authored)
    assert fill_anchors_from_research(request) is request
    assert request["content_boundaries"]["evidence_anchors"][0] == preserved
    assert request["content_boundaries"]["evidence_anchors"][1] == {
        "anchor_id": "new", "source_id": "s", "locator": "p2", "relation": "support",
        "observed_summary": "New observed content.", "boundary": "Only the quoted scope."}


def test_request_resolves_research_folder_and_retires_the_old_field(tmp_path):
    path = tmp_path / "request.json"
    path.write_text(json.dumps({"research_folder": "research"}))
    assert load_request(path)["research_folder"] == str((tmp_path / "research").resolve())
    path.write_text(json.dumps({"sourceguard_model": "old.yaml"}))
    with pytest.raises(ValidationError, match="sourceguard_model.*retired.*research_folder"):
        load_request(path)
    with pytest.raises(ValidationError, match="sourceguard_model.*retired.*research_folder"):
        fill_anchors_from_research({"sourceguard_model": ""})
