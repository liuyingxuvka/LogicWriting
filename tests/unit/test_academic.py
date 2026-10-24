from __future__ import annotations

import copy

import pytest

from _common import ValidationError, fingerprint
from tests.v2_support import derive_protocol_closure as derive_closure
from reader_plan import validate_revision_provenance
from reader_plan_core import validate_route_composition
from select_route import select_route
from tests.v2_support import closure_input, complete_chain, route_request


def test_academic_route_keeps_final_ownership_when_research_is_needed():
    decision = select_route(route_request("thesis_chapter", research=True))
    assert decision["final_owner"] == "academic-writing"
    assert decision["child_routes"] == ["investigation"]


def test_academic_composition_carries_question_contribution_and_hierarchy(tmp_path):
    chain = complete_chain(tmp_path, "academic-writing")
    route = validate_route_composition(
        chain["route_composition"],
        owner="academic-writing",
        reader_intent_fingerprint=chain["intent"]["intent_fingerprint"],
        composition_plan_fingerprint=chain["plan"]["plan_fingerprint"],
    )
    assert route["research_question"]
    assert route["central_contribution"]
    assert route["hierarchy"][0]["new_claim_or_warrant"]


def test_create_new_provenance_is_explicitly_not_applicable(tmp_path):
    chain = complete_chain(tmp_path, "academic-writing")
    provenance = validate_revision_provenance(
        chain["revision_provenance"],
        target_artifact_fingerprint=chain["artifact_map"]["artifact_fingerprint"],
    )
    assert provenance["applicability"] == "not_applicable"
    assert provenance["unit_treatments"] == []


def test_revision_provenance_must_bind_current_target_bytes(tmp_path):
    chain = complete_chain(tmp_path, "academic-writing")
    provenance = copy.deepcopy(chain["revision_provenance"])
    provenance["target_artifact_fingerprint"] = fingerprint({"old": True})
    provenance["provenance_fingerprint"] = fingerprint({
        key: value for key, value in provenance.items() if key != "provenance_fingerprint"
    })
    with pytest.raises(ValidationError, match="stale"):
        validate_revision_provenance(
            provenance,
            target_artifact_fingerprint=chain["artifact_map"]["artifact_fingerprint"],
        )


def test_academic_closure_binds_revision_and_actual_artifact_chain(tmp_path):
    chain = complete_chain(tmp_path, "academic-writing")
    closure = derive_closure(closure_input(chain))["closure"]
    assert closure["status"] == "passed"
    assert closure["revision_provenance_fingerprint"] == chain["revision_provenance"]["provenance_fingerprint"]


def test_academic_route_review_failure_blocks_final_claim(tmp_path):
    chain = complete_chain(tmp_path, "academic-writing", pass_quality=False)
    closure = derive_closure(closure_input(chain))["closure"]
    assert closure["status"] == "needs_repair"


def _revision_chain(tmp_path):
    from build_source_unit_manifest import build_source_unit_manifest
    chain = complete_chain(tmp_path, 'academic-writing', mode='revise_existing')
    source = tmp_path / 'old.md'
    source.write_text('An earlier source paragraph with a narrower explanation.\n', encoding='utf-8')
    manifest = build_source_unit_manifest(manifest_id='revision', source_path=source,
        target_path=chain['artifact_map']['artifact_path'])
    provenance = chain['revision_provenance']
    provenance.update(source_artifact_path=str(source), applicability='required', unit_treatments=[{
        'source_unit_id': manifest['source']['units'][0]['unit_id'],
        'target_unit_ids': [chain['artifact_map']['units'][-1]['artifact_unit_id']],
        'treatment': 'rewritten', 'authorization': 'Requested revision',
        'meaning_delta': 'Clarify the explanation', 'structure_delta': 'Integrate into the current paragraph'}])
    provenance.pop('source_artifact_fingerprint')
    provenance.pop('provenance_fingerprint')
    return chain, manifest


def test_create_new_needs_no_provenance_input(tmp_path):
    chain = complete_chain(tmp_path, 'academic-writing')
    request = closure_input(chain)
    request.pop('revision_provenance')
    result = derive_closure(request)['closure']
    assert result['status'] == 'passed'
    assert result['revision_provenance_fingerprint'] == derive_closure(request)['closure']['revision_provenance_fingerprint']


def test_revision_units_come_from_the_real_source_file(tmp_path):
    from reader_fill import fill_closure_fingerprints
    chain, manifest = _revision_chain(tmp_path)
    request = fill_closure_fingerprints(closure_input(chain))
    assert request['revision_provenance']['source_artifact_fingerprint'] == manifest['source']['artifact_fingerprint']
    assert derive_closure(request)['closure']['status'] == 'passed'


def test_invented_source_unit_is_rejected(tmp_path):
    chain, _ = _revision_chain(tmp_path)
    chain['revision_provenance']['unit_treatments'][0]['source_unit_id'] = 'anything-at-all'
    with pytest.raises(ValidationError, match='anything-at-all'):
        derive_closure(closure_input(chain))


def test_invented_target_unit_is_rejected(tmp_path):
    chain, _ = _revision_chain(tmp_path)
    chain['revision_provenance']['unit_treatments'][0]['target_unit_ids'] = ['nope']
    with pytest.raises(ValidationError, match='nope'):
        derive_closure(closure_input(chain))


def test_mode_must_match_reader_intent(tmp_path):
    chain = complete_chain(tmp_path, 'academic-writing')
    chain['revision_provenance'].update(artifact_mode='revise_existing', source_artifact_fingerprint='sha256:' + '0' * 64)
    with pytest.raises(ValidationError, match='revision provenance says revise_existing but ReaderIntent says create_new'):
        derive_closure(closure_input(chain))


def test_revision_source_digest_is_derived_and_checked_against_real_bytes(tmp_path):
    from reader_fill import fill_closure_fingerprints
    chain, _ = _revision_chain(tmp_path)
    request = fill_closure_fingerprints(closure_input(chain))
    source = tmp_path / 'old.md'
    source.write_text('The real source bytes have changed.\n')
    with pytest.raises(ValidationError, match='real source_artifact_path bytes'):
        derive_closure(request)


def test_revision_mode_requires_a_source_record(tmp_path):
    chain, _ = _revision_chain(tmp_path)
    request = closure_input(chain)
    request.pop('revision_provenance')
    with pytest.raises(ValidationError, match='requires revision_provenance'):
        derive_closure(request)


def test_source_path_is_relative_to_the_provenance_file(tmp_path):
    import json
    from _common import load_request
    child = tmp_path / 'records'
    child.mkdir()
    (child / 'provenance.json').write_text(json.dumps({'source_artifact_path': '../old.md'}))
    path = tmp_path / 'request.json'
    path.write_text(json.dumps({'revision_provenance': 'records/provenance.json'}))
    assert load_request(path)['revision_provenance']['source_artifact_path'] == str(tmp_path / 'old.md')
