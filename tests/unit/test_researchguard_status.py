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
        "anchor_id": "new", "source_id": "s", "locator": "p2", "relation": "context",
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


def test_report_from_another_folder_fails_the_provider_check(tmp_path):
    import shutil
    from pathlib import Path
    from derive_closure import provider_checks
    from researchguard_status import research_report_identity_problems

    example = Path(__file__).resolve().parents[2] / "skills/logic-writing/assets/examples/investigation"
    folder = tmp_path / "research"
    shutil.copytree(example / "research", folder)
    saved = json.loads((example / "research-status.json").read_text(encoding="utf-8"))
    assert research_report_identity_problems(saved, str(folder)) == []

    # The probe: another question's report (Ever Given), same passing verdict shape.
    foreign = copy.deepcopy(saved)
    foreign["question"] = "Why did container freight rates surge in 2021?"
    foreign["hypotheses"] = [{"id": "h_suez", "text": "The Suez blockage caused the surge."}]
    foreign["verdict"]["live_hypotheses"] = ["h_suez"]
    import hashlib
    index=yaml.safe_load((folder/'research.yaml').read_text())
    index.update(question=foreign['question'],hypotheses=foreign['hypotheses'])
    for row in foreign['input_digests']:
        if row['path']=='research.yaml':row['sha256']=hashlib.sha256(yaml.safe_dump(index,sort_keys=False).encode()).hexdigest()
    report = tmp_path / "research-status.json"
    report.write_text(json.dumps(foreign), encoding="utf-8")
    rows, risks, passed = provider_checks("investigation", {"research_folder": str(folder)}, {},
                                          [{"provider": "researchguard", "path": str(report)}])
    assert not passed and rows[0]["status"] == "failed"
    assert rows[0]["reason"].startswith("research_report_stale:research.yaml")
    assert any(row["defect_id"] == "provider:researchguard" for row in risks)

    source = folder / "source.yaml"
    model = yaml.safe_load(source.read_text(encoding="utf-8"))
    model["anchors"] = model["anchors"][1:]
    source.write_text(yaml.safe_dump(model, sort_keys=False), encoding="utf-8")
    assert research_report_identity_problems(saved, str(folder)) == ["research_report_stale:source.yaml"]

    report.write_text(json.dumps(saved), encoding="utf-8")
    rows, _risks, passed = provider_checks("investigation", {}, {}, [{"provider": "researchguard", "path": str(report)}])
    assert not passed and rows[0]["reason"].startswith("research_report_unbound:research_folder")
    rows, _risks, passed = provider_checks("investigation", {"research_folder": str(example / "research")}, {},
                                           [{"provider": "researchguard", "path": str(report)}])
    assert passed and rows[0]["status"] == "passed"


def test_imported_anchor_takes_the_research_direction(tmp_path):
    import shutil
    from pathlib import Path
    from reader_fill import fill_brief_fingerprints

    fixture = Path(__file__).resolve().parents[1] / "fixtures/research"
    folder = tmp_path / "research"
    shutil.copytree(fixture, folder)

    def imported(**extra):
        request = {"research_folder": str(folder), "content_boundaries": {"evidence_anchors": []}, **extra}
        fill_brief_fingerprints(request)
        return {row["anchor_id"]: row["relation"] for row in request["content_boundaries"]["evidence_anchors"]}

    status = str(folder / "research-status.json")
    assert imported(research_status=status) == {"a-oppose": "counter", "a-mixed": "counter", "a-limit": "limit",
                                                 "a-support": "support", "a-none": "context"}
    assert set(imported().values()) == {"context"}

    # A handwritten relation may be weaker than the research, never the opposite.
    def handwritten(anchor_id, locator, relation):
        return {"anchor_id": anchor_id, "source_id": "s-report", "locator": locator, "relation": relation,
                "observed_summary": "Author summary.", "boundary": "Author scope."}
    request = {"research_folder": str(folder), "research_status": status,
               "content_boundaries": {"evidence_anchors": [handwritten("a-oppose", "p. 1", "support")]}}
    before = copy.deepcopy(request)
    with pytest.raises(ValidationError, match="anchor_relation_conflict:a-oppose"):
        fill_brief_fingerprints(request)
    assert request == before
    request["content_boundaries"]["evidence_anchors"] = [handwritten("a-support", "p. 4", "counter")]
    with pytest.raises(ValidationError, match="anchor_relation_conflict:a-support"):
        fill_brief_fingerprints(request)
    request["content_boundaries"]["evidence_anchors"] = [handwritten("a-oppose", "p. 1", "limit")]
    fill_brief_fingerprints(request)
    assert request["content_boundaries"]["evidence_anchors"][0]["relation"] == "limit"

    with pytest.raises(ValidationError, match="research_status needs research_folder"):
        fill_brief_fingerprints({"research_status": status, "content_boundaries": {"evidence_anchors": []}})
    other = json.loads((folder / "research-status.json").read_text(encoding="utf-8"))
    other["question"] = "Another question?"
    import hashlib
    index=yaml.safe_load((folder/'research.yaml').read_text())
    index['question']=other['question']
    for row in other['input_digests']:
        if row['path']=='research.yaml':row['sha256']=hashlib.sha256(yaml.safe_dump(index,sort_keys=False).encode()).hexdigest()
    (folder / "research-status.json").write_text(json.dumps(other), encoding="utf-8")
    with pytest.raises(ValidationError, match="research_report_stale:research.yaml"):
        imported(research_status=status)
