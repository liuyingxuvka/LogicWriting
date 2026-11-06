from __future__ import annotations

import copy

import pytest

from _common import ValidationError, fingerprint_text
from reader_checks import _verify_span_evidence
from world_refs import validate_world_refs, world_ref_unquoted, validate_world_claim_units


def _literal_world_check(tmp_path, text, *, native_time='07:10', receiver=None):
    import yaml
    world = {'claim': {'claim_id': 'c_access'}, 'inputs': {'events': [
        {'event_id': 'e_unlock', 'actor': 'Lena', 'at': native_time},
        {'event_id': 'e_later', 'actor': 'Tom', 'at': '08:00'},
    ]}}
    if receiver:
        world['inputs']['events'][0]['with'] = [receiver]
    path = tmp_path / 'world.yaml'
    path.write_text(yaml.safe_dump(world), encoding='utf-8')
    plan = {'planned_units': [{'planned_unit_id': 'scene', 'world_refs': ['e_unlock']}]}
    evidence = dict(artifact_unit_id='paragraph', locator='paragraph:1', excerpt=text,
                    excerpt_fingerprint=fingerprint_text(text))
    review = {'world_ref_checks': [dict(planned_unit_id='scene', world_ref='e_unlock', evidence=[evidence])]}
    shared = {'unit_bindings': [dict(planned_unit_id='scene', artifact_unit_ids=['paragraph'])]}
    units = {'paragraph': dict(artifact_unit_id='paragraph', locator='paragraph:1', text=text)}
    return world_ref_unquoted(plan, review, shared, lambda span: _verify_span_evidence(span, units),
                              composition={'world_contract': str(path)})


@pytest.mark.parametrize('text', ['Lena opened the door at 07:10.', 'The door opened at 07:10.'])
def test_correct_literal_world_event_remains_usable(tmp_path, text):
    assert _literal_world_check(tmp_path, text) == []


@pytest.mark.parametrize('text, field', [
    ('Lena opened the door at 08:00.', 'time'),
    ('Tom opened the door at 07:10.', 'actor'),
])
def test_same_green_world_cannot_loan_a_different_event_value(tmp_path, text, field):
    with pytest.raises(ValidationError, match='world_ref_value_disagrees:scene:e_unlock:' + field):
        _literal_world_check(tmp_path, text)


@pytest.mark.parametrize('day, rejected', [('6 November 2026', False), ('7 November 2026', True)])
def test_world_event_literal_date_keeps_its_native_day(tmp_path, day, rejected):
    if rejected:
        with pytest.raises(ValidationError, match='world_ref_value_disagrees:scene:e_unlock:date'):
            _literal_world_check(tmp_path, 'Lena opened the door on ' + day + '.', native_time='2026-11-06')
    else:
        assert _literal_world_check(tmp_path, 'Lena opened the door on ' + day + '.', native_time='2026-11-06') == []


@pytest.mark.parametrize('text, native_time, receiver, risk', [
    ('Lena opened the door at 07:10 or 08:00.', '07:10', None, 'time'),
    ('Lena opened the door at 07:10.', 't1', None, 'time'),
    ('Tom received the key at 07:10.', '07:10', 'Tom', 'role'),
])
def test_ambiguous_or_symbolic_world_scope_is_not_invented(tmp_path, text, native_time, receiver, risk):
    assert _literal_world_check(tmp_path, text, native_time=native_time, receiver=receiver) == [
        'world_ref_' + risk + '_unverified:scene:e_unlock']


@pytest.mark.parametrize('text, failure', [
    ('Lena opened the door at 07:10.', None),
    ('Lena opened the door at 08:00.', 'time'),
    ('Tom opened the door at 07:10.', 'actor'),
])
def test_public_route_review_compares_current_prose_with_the_bound_native_event(tmp_path, text, failure):
    import yaml
    from _common import own_fingerprint
    from artifact_map import build_artifact_map
    from reader_checks import validate_route_artifact_review
    from reader_plan import build_reader_brief
    from route_inputs import route_extension_fingerprint
    from tests.v2_support import complete_chain
    chain = complete_chain(tmp_path, 'fiction-writing', language='en')
    world = tmp_path / 'world.yaml'
    world.write_text(yaml.safe_dump({'claim': {'claim_id': 'c_access'}, 'inputs': {'events': [
        dict(event_id='e_unlock', actor='Lena', at='07:10'),
        dict(event_id='e_later', actor='Tom', at='08:00')
    ]}}), encoding='utf-8')
    plan = copy.deepcopy(chain['plan'])
    plan['planned_units'][0]['world_refs'] = ['e_unlock']
    plan['plan_fingerprint'] = own_fingerprint(plan, 'plan_fingerprint')
    route = copy.deepcopy(chain['route_composition'])
    route.update(world_contract=str(world), composition_plan_fingerprint=plan['plan_fingerprint'])
    route['extension_fingerprint'] = route_extension_fingerprint(route)
    brief = build_reader_brief(route_decision=chain['route_decision'],
                               content_boundaries=chain['reader_brief']['content_boundaries'],
                               composition_plan=plan, route_composition=route,
                               brief_id='brief:world', request='Write this conditional scene.')
    chain['artifact_path'].write_text('# Scene\n\n' + text, encoding='utf-8')
    amap = build_artifact_map(chain['artifact_path'], map_id='map:world', language='en')
    unit = next(row for row in amap['units'] if row['unit_kind'] == 'paragraph')
    evidence = dict(artifact_unit_id=unit['artifact_unit_id'], locator=unit['locator'], excerpt=text,
                    excerpt_fingerprint=fingerprint_text(text))
    shared = copy.deepcopy(chain['shared_writing'])
    shared.update(reader_brief_fingerprint=brief['brief_fingerprint'],
                  composition_plan_fingerprint=plan['plan_fingerprint'],
                  route_extension_fingerprint=route['extension_fingerprint'],
                  artifact_map_fingerprint=amap['map_fingerprint'], artifact_fingerprint=amap['artifact_fingerprint'])
    shared['unit_bindings'][0].update(artifact_unit_ids=[unit['artifact_unit_id']], artifact_spans=[
        dict(artifact_unit_id=unit['artifact_unit_id'], locator=unit['locator'], content_fingerprint=unit['content_fingerprint'])])
    shared['contract_fingerprint'] = own_fingerprint(shared, 'contract_fingerprint')
    review = copy.deepcopy(chain['route_review'])
    review.update(route_extension_fingerprint=route['extension_fingerprint'],
                  artifact_map_fingerprint=amap['map_fingerprint'], artifact_fingerprint=amap['artifact_fingerprint'],
                  world_ref_checks=[dict(planned_unit_id=plan['planned_units'][0]['planned_unit_id'],
                                         world_ref='e_unlock', evidence=[evidence])])
    for dimension in review['dimensions']:
        dimension['evidence'] = [evidence]
    review['review_fingerprint'] = own_fingerprint(review, 'review_fingerprint')
    def check():
        return validate_route_artifact_review(review, owner='fiction-writing', route_composition=route,
                                              artifact_map=amap, reader_brief=brief, shared_writing=shared)
    if failure:
        with pytest.raises(ValidationError, match='world_ref_value_disagrees:.*:' + failure):
            check()
    else:
        assert check()['status'] == 'passed'


def test_world_refs_validate_literal_ids_and_composition_relative_paths(tmp_path):
    directory = tmp_path / "composition"
    directory.mkdir()
    (directory / "world.yaml").write_text(
        "claim: {claim_id: c_access}\ninputs:\n  events:\n    - {event_id: e_unlock, at: t1}\n",
        encoding="utf-8",
    )
    plan = {"planned_units": [{"planned_unit_id": "scene", "world_refs": ["e_unlock", "c_access"]}]}
    assert validate_world_refs(plan, {"world_contract": "world.yaml"}, directory) == {"scene": ("e_unlock", "c_access")}
    with pytest.raises(ValidationError, match="world_contract_missing"):
        validate_world_refs(plan, {}, directory)
    unknown = copy.deepcopy(plan)
    unknown["planned_units"][0]["world_refs"] = ["never_declared"]
    with pytest.raises(ValidationError, match="unknown_world_ref:scene:never_declared"):
        validate_world_refs(unknown, {"world_contract": "world.yaml"}, directory)
    assert validate_world_refs({"planned_units": [{"planned_unit_id": "ordinary"}]}, {}) == {}


def test_unquoted_world_reference_is_risk_and_only_actual_bound_text_counts():
    plan = {"planned_units": [{"planned_unit_id": "scene", "world_refs": ["e_unlock"]}]}
    text = "The key turned and the door opened."
    unit = {"artifact_unit_id": "paragraph", "locator": "paragraph:1", "text": text}
    units = {"paragraph": unit}
    evidence = {"artifact_unit_id": "paragraph", "locator": "paragraph:1", "excerpt": text,
                "excerpt_fingerprint": fingerprint_text(text)}
    shared = {"unit_bindings": [{"planned_unit_id": "scene", "artifact_unit_ids": ["paragraph"]}]}
    verify = lambda span: _verify_span_evidence(span, units)
    assert world_ref_unquoted(plan, {}, shared, verify) == ["world_ref_unquoted:scene:e_unlock"]
    review = {"world_ref_checks": [{"planned_unit_id": "scene", "world_ref": "e_unlock", "evidence": [evidence]}]}
    assert world_ref_unquoted(plan, review, shared, verify) == []
    wrong_text = copy.deepcopy(review)
    wrong_text["world_ref_checks"][0]["evidence"][0]["excerpt"] = "Words absent from the current artifact."
    with pytest.raises(ValidationError, match="absent"):
        world_ref_unquoted(plan, wrong_text, shared, verify)
    other_unit = {"unit_bindings": [{"planned_unit_id": "scene", "artifact_unit_ids": ["elsewhere"]}]}
    with pytest.raises(ValidationError, match="must belong"):
        world_ref_unquoted(plan, review, other_unit, verify)


def test_world_claim_source_row_is_a_plan_unit_with_world_references():
    plan = {"planned_units": [{"planned_unit_id": "scene", "world_refs": ["e_unlock"]},
                              {"planned_unit_id": "ordinary"}]}
    ledger = {"worldguard_claims": [{"id": "world-claim", "source_row_id": "scene"}]}
    assert validate_world_claim_units(ledger, plan) == []
    ledger["worldguard_claims"][0]["source_row_id"] = "ordinary"
    assert validate_world_claim_units(ledger, plan) == ["unit_not_in_plan:worldguard_claims:world-claim"]
