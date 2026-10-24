from __future__ import annotations

import copy

import pytest

from _common import ValidationError, fingerprint_without
from reader_binding import validate_shared_writing
from tests.v2_support import make_reader_chain


def test_current_plan_to_byte_binding_passes(tmp_path):
    chain = make_reader_chain(tmp_path, "fiction-writing")
    value = validate_shared_writing(
        chain["shared_writing"],
        artifact_map=chain["artifact_map"],
        reader_brief=chain["reader_brief"],
    )
    assert value["artifact_fingerprint"] == chain["artifact_map"]["artifact_fingerprint"]


def test_material_byte_change_stales_artifact_map(tmp_path):
    chain = make_reader_chain(tmp_path)
    chain["artifact_path"].write_text("changed", encoding="utf-8")
    with pytest.raises(ValidationError, match="stale"):
        validate_shared_writing(
            chain["shared_writing"],
            artifact_map=chain["artifact_map"],
            reader_brief=chain["reader_brief"],
        )


def test_required_plan_unit_must_bind_actual_span(tmp_path):
    chain = make_reader_chain(tmp_path)
    contract = copy.deepcopy(chain["shared_writing"])
    contract["unit_bindings"] = []
    contract["contract_fingerprint"] = fingerprint_without(contract, "contract_fingerprint")
    with pytest.raises(ValidationError):
        validate_shared_writing(
            contract,
            artifact_map=chain["artifact_map"],
            reader_brief=chain["reader_brief"],
        )


def test_sibling_route_contract_is_rejected(tmp_path):
    chain = make_reader_chain(tmp_path, "travel-guide")
    contract = copy.deepcopy(chain["shared_writing"])
    contract["final_owner"] = "fiction-writing"
    contract["contract_fingerprint"] = fingerprint_without(contract, "contract_fingerprint")
    with pytest.raises(ValidationError, match="final_owner"):
        validate_shared_writing(
            contract,
            artifact_map=chain["artifact_map"],
            reader_brief=chain["reader_brief"],
        )


def test_contract_and_route_review_fingerprints_are_filled(monkeypatch, tmp_path):
    from pathlib import Path

    from tests.v2_support import complete_chain

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "skills" / "logic-writing" / "routes" / "investigation" / "scripts"))
    from validate_investigation_artifact import validate_investigation_artifact
    from validate_shared_writing import validate_shared_writing

    chain = complete_chain(tmp_path)
    contract = copy.deepcopy(chain["shared_writing"])
    for field in ("route_decision_fingerprint", "reader_intent_fingerprint", "reader_brief_fingerprint",
                  "composition_plan_fingerprint", "route_extension_fingerprint", "artifact_map_fingerprint",
                  "artifact_fingerprint", "contract_fingerprint"):
        del contract[field]
    for binding in contract["unit_bindings"]:
        for span in binding["artifact_spans"]:
            span.pop("locator", None), span.pop("content_fingerprint", None)
    checked = validate_shared_writing({"contract": contract, "artifact_map": chain["artifact_map"],
                                       "reader_brief": chain["reader_brief"]})
    assert checked["status"] == "current_pass"
    assert checked["shared_writing"] == chain["shared_writing"]

    review = copy.deepcopy(chain["route_review"])
    for field in ("route_extension_fingerprint", "artifact_map_fingerprint", "artifact_fingerprint", "review_fingerprint"):
        del review[field]
    for row in review["dimensions"]:
        for evidence in row["evidence"]:
            evidence.pop("locator", None), evidence.pop("excerpt_fingerprint", None)
    reviewed = validate_investigation_artifact({"review": review, "route_composition": chain["route_composition"],
                                                "artifact_map": chain["artifact_map"]})
    assert reviewed["route_review"] == chain["route_review"]


@pytest.mark.parametrize("record_key, location", [
    ("contract", "artifact_spans"), ("contract", "artifact_unit_ids"),
    ("shared_writing", "artifact_spans"), ("shared_writing", "artifact_unit_ids"),
    ("review", "dimensions"), ("review", "findings"),
    ("route_review", "dimensions"), ("route_review", "findings"),
])
def test_binding_to_a_vanished_unit_names_the_unit_before_any_fill(tmp_path, record_key, location):
    from reader_fill import fill_check_fingerprints
    from tests.v2_support import complete_chain

    chain = complete_chain(tmp_path, pass_quality=False)
    contract = copy.deepcopy(chain["shared_writing"])
    contract.pop("contract_fingerprint")
    contract.pop("reader_brief_fingerprint")
    request = {"artifact_map": chain["artifact_map"], "reader_brief": chain["reader_brief"],
               "contract": contract}
    missing = "artifact:paragraph:9999"
    if location in {"artifact_spans", "artifact_unit_ids"}:
        if record_key != "contract":
            request[record_key] = copy.deepcopy(contract)
        binding = request[record_key]["unit_bindings"][0]
        if location == "artifact_spans":
            binding["artifact_spans"][0] = {**binding["artifact_spans"][0], "artifact_unit_id": missing}
        else:
            binding["artifact_unit_ids"] = [missing]
        prefix = f"binding {binding['binding_id']}"
    else:
        review = copy.deepcopy(chain["route_review"])
        request[record_key] = review
        if location == "dimensions":
            evidence = review["dimensions"][0]["evidence"][0]
            review["dimensions"][0]["evidence"][0] = {**evidence, "artifact_unit_id": missing}
        else:
            evidence = review["findings"][0]["evidence"]
            review["findings"][0]["evidence"] = {**evidence, "artifact_unit_id": missing}
        prefix = "review evidence"
    original = copy.deepcopy(request)
    with pytest.raises(ValidationError) as raised:
        fill_check_fingerprints(request)
    message = str(raised.value)
    assert message.startswith(f"{prefix} names artifact unit {missing}, which is not in the current ArtifactMap")
    unit_ids = [row["artifact_unit_id"] for row in chain["artifact_map"]["units"]]
    assert f"{unit_ids[0]} … {unit_ids[-1]}" in message
    assert request == original


def _quote_request(chain):
    contract = copy.deepcopy(chain['shared_writing'])
    for key in list(contract):
        if key.endswith('_fingerprint'):
            del contract[key]
    binding = contract['unit_bindings'][0]
    units = {u['artifact_unit_id']: u for u in chain['artifact_map']['units']}
    binding['anchor_excerpts'] = [units[i]['text'][:40] for i in binding.pop('artifact_unit_ids')]
    binding.pop('artifact_spans')
    return dict(contract=contract, artifact_map=chain['artifact_map'], reader_brief=chain['reader_brief'])


@pytest.mark.parametrize('invalid_later', ['quote', 'explicit_id', 'review'])
def test_quote_resolution_waits_for_whole_request_validation(tmp_path, invalid_later):
    from reader_fill import fill_check_fingerprints

    request = _quote_request(make_reader_chain(tmp_path))
    if invalid_later == 'review':
        request['review'] = {'dimensions': [{'evidence': [{'artifact_unit_id': 'artifact:paragraph:9999'}]}]}
        expected = 'review evidence names artifact unit artifact:paragraph:9999'
    else:
        later = copy.deepcopy(request['contract']['unit_bindings'][0])
        later['binding_id'] = 'binding:late'
        if invalid_later == 'quote':
            later['anchor_excerpts'] = ['This quote is absent from the current artifact.']
            expected = 'binding binding:late:.*is not in the current text'
        else:
            later.pop('anchor_excerpts')
            later['artifact_unit_ids'] = ['artifact:paragraph:9999']
            later['artifact_spans'] = [{'artifact_unit_id': 'artifact:paragraph:9999'}]
            expected = 'binding binding:late names artifact unit artifact:paragraph:9999'
        request['contract']['unit_bindings'].append(later)
    original = copy.deepcopy(request)
    with pytest.raises(ValidationError, match=expected):
        fill_check_fingerprints(request)
    assert request == original


def test_quote_binding_follows_renumbered_paragraphs(tmp_path):
    from artifact_map import build_artifact_map
    from reader_fill import fill_check_fingerprints
    chain = make_reader_chain(tmp_path, language='en')
    request = _quote_request(chain)
    original = fill_check_fingerprints(copy.deepcopy(request))['contract']['unit_bindings'][0]['artifact_unit_ids']
    path = chain['artifact_path']
    path.write_text('# A new opening\n\nAn additional introductory paragraph before the original text.\n\n' + path.read_text())
    request['artifact_map'] = build_artifact_map(path, map_id='map:renumbered', language='en')
    filled = fill_check_fingerprints(copy.deepcopy(request))
    current = validate_shared_writing(filled['contract'], artifact_map=request['artifact_map'], reader_brief=request['reader_brief'])
    assert current['unit_bindings'][0]['artifact_unit_ids'] != original
    assert current['unit_bindings'][0]['anchor_excerpts'] == request['contract']['unit_bindings'][0]['anchor_excerpts']


def test_missing_quote_fails_the_binding(tmp_path):
    from reader_fill import fill_check_fingerprints
    request = _quote_request(make_reader_chain(tmp_path))
    request['contract']['unit_bindings'][0]['anchor_excerpts'] = ['This passage is absent from the text.']
    with pytest.raises(ValidationError, match='binding binding:answer:.*is not in the current text'):
        fill_check_fingerprints(request)


def test_ambiguous_quote_asks_for_a_longer_one(tmp_path):
    from artifact_map import build_artifact_map
    from reader_fill import fill_check_fingerprints
    chain = make_reader_chain(tmp_path)
    request = _quote_request(chain)
    path = chain['artifact_path']
    quote = request['contract']['unit_bindings'][0]['anchor_excerpts'][0]
    path.write_text(path.read_text() + '\n\n' + quote + '\n')
    request['artifact_map'] = build_artifact_map(path, map_id='map:duplicate', language='zh-CN')
    with pytest.raises(ValidationError, match='in several units.*use a longer quote'):
        fill_check_fingerprints(request)


def test_quote_and_unit_id_must_agree(tmp_path):
    from reader_fill import fill_check_fingerprints
    request = _quote_request(make_reader_chain(tmp_path))
    request['contract']['unit_bindings'][0]['artifact_unit_ids'] = ['artifact:document']
    with pytest.raises(ValidationError, match='anchor_excerpts and artifact_unit_ids disagree'):
        fill_check_fingerprints(request)


def test_library_rechecks_the_quote_on_a_completed_contract(tmp_path):
    from reader_fill import fill_check_fingerprints
    chain = make_reader_chain(tmp_path)
    request = fill_check_fingerprints(_quote_request(chain))
    contract = request['contract']
    contract['unit_bindings'][0]['anchor_excerpts'] = ['A now missing quote in an otherwise current contract.']
    contract['contract_fingerprint'] = fingerprint_without(contract, 'contract_fingerprint')
    with pytest.raises(ValidationError, match='is not in the current text'):
        validate_shared_writing(contract, artifact_map=chain['artifact_map'], reader_brief=chain['reader_brief'])
