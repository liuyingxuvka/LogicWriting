from __future__ import annotations


def test_handwritten_anchor_conflicting_with_the_research_folder_is_an_error(tmp_path):
    from pathlib import Path
    import copy
    import json
    import pytest
    import yaml
    from _common import ValidationError, load_request
    from researchguard_status import fill_anchors_from_research

    model_path = Path(__file__).resolve().parents[1] / "fixtures/trials/trialA/sg-model-2.yaml"
    model = yaml.safe_load(model_path.read_text())
    research = tmp_path / "research"
    research.mkdir()
    source = research / "source.yaml"
    source.write_text(yaml.safe_dump(model, sort_keys=False))
    index_path = research / "research.yaml"
    index = {"schema": "researchguard.research.v1", "question": "Which conclusion fits the observed source?",
             "hypotheses": [{"id": "h-main", "text": "The scoped main conclusion."}],
             "models": {"source": "source.yaml"}}
    index_path.write_text(yaml.safe_dump(index))
    request_path = tmp_path / "brief.json"
    request_path.write_text(json.dumps({"research_folder": "research", "content_boundaries": {"evidence_anchors": []}}))
    request = load_request(request_path)
    fill_anchors_from_research(request)
    anchors = request["content_boundaries"]["evidence_anchors"]
    assert len(anchors) == 5
    assert [(a["anchor_id"], a["source_id"], a["locator"]) for a in anchors] == [
        (a["anchor_id"], a["source_id"], a["locator"]) for a in model["anchors"]]
    anchors[0].update(relation="counter", observed_summary="Handwritten", boundary="Limited")
    original = dict(anchors[0])
    fill_anchors_from_research(request)
    assert len(anchors) == 5 and anchors[0] == original

    before = copy.deepcopy(request)
    original_source_id = model["anchors"][0]["source_id"]
    model["sources"].append({"source_id": "src-other"})
    model["anchors"][0]["source_id"] = "src-other"
    source.write_text(yaml.safe_dump(model, sort_keys=False))
    with pytest.raises(ValidationError, match=f"anchor_conflict:{original['anchor_id']}"):
        fill_anchors_from_research(request)
    assert request == before
    model["anchors"][0]["source_id"] = original_source_id
    source.write_text(yaml.safe_dump(model, sort_keys=False))

    relative = research / "relative.yaml"
    relative.write_text("sources: [{source_id: s, cannot_support_structural_use: No extrapolation}]\nanchors: [{anchor_id: a, source_id: s, locator: line=1, text: quote}]\n")
    index["models"]["source"] = "relative.yaml"
    index_path.write_text(yaml.safe_dump(index))
    request_path.write_text(json.dumps({"research_folder": "research/research.yaml"}))
    request = load_request(request_path)
    fill_anchors_from_research(request)
    assert request["content_boundaries"]["evidence_anchors"][0]["boundary"] == "No extrapolation"
