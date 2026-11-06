"""A saved provider row belongs to one report case, not the last matching ID."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from urllib.parse import quote

import pytest

from claim_readings import build_sensors, check_text, plan_readings, provider_sensors, reading_risks


REQUEST = 'Evaluate both inlet cases. Inlet A is 25 °C and Inlet B ranges from 10 to 12 °C.'


def reference(path, row='mix.T_2_K'):
    return 'pg-report://' + quote(str(path), safe='') + '#' + quote(row, safe='')


def report(tmp_path, name, temperature=283.15, *, source_range=False, inlet=2):
    folder = tmp_path / name
    folder.mkdir(parents=True)
    question = folder / 'question.txt'
    question.write_text(REQUEST, encoding='utf-8')
    digest = hashlib.sha256(question.read_bytes()).hexdigest()
    row = dict(id=f'mix.T_{inlet}_K', value=temperature, unit='K', colour='green',
               reason='original agrees', source_digest=digest,
               source_entity='Inlet ' + ('A' if inlet == 1 else 'B'), input_group=f'mix.inlet_{inlet}')
    if source_range:
        row.update(lower=283.15, upper=285.15, reason='inside; the AI chose the point')
    path = folder / 'report.json'
    path.write_text(json.dumps(dict(audit_pass=True, metadata=dict(
        sources=dict(question=dict(path='question.txt', sha256=digest)), source_readings=[row]))), encoding='utf-8')
    return dict(provider='physicsguard', path=str(path))


def brief(reports, refs, text='Inlet B is 10 °C.'):
    return dict(request=REQUEST, provider_reports=reports, content_boundaries=dict(
        evidence_anchors=[], content_units=[dict(content_unit_id='content:case', safe_meaning=text,
                                               evidence_anchor_ids=[], model_row_ids=refs)]))


def colors(value):
    return [row['colour'] for row in value if 'raw' in row and row['raw']]


def test_duplicate_report_rows_are_explicitly_ambiguous_instead_of_last_wins(tmp_path):
    a, b = report(tmp_path, 'cold'), report(tmp_path, 'warm', 285.15)
    outcomes = []
    for refs in ([a, b], [b, a]):
        rows, issues = provider_sensors(refs, REQUEST)
        state = build_sensors(brief(refs, ['pg:mix.T_2_K']))
        found = check_text('Inlet B is 10 °C.', [], ['pg:mix.T_2_K'], state)
        assert colors(found) == ['grey']
        assert any('ambiguous' in row['reason'] for row in issues)
        assert rows['pg:mix.T_2_K']['ambiguous_report_refs']
        outcomes.append(found[0]['reason'])
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize('reverse', [False, True])
def test_qualified_report_selects_the_case_and_wrong_value_stays_red(tmp_path, reverse):
    a, b = report(tmp_path, 'cold'), report(tmp_path, 'warm', 285.15)
    reports = [b, a] if reverse else [a, b]
    selected = reference(a['path'])
    value = brief(reports, [selected])
    state = build_sensors(value)
    assert colors(check_text('Inlet B is 10 °C.', [], [selected], state)) == ['green']
    assert colors(check_text('Inlet B is 12 °C.', [], [selected], state)) == ['red']
    row = state['pg_rows'][selected]
    assert Path(row['report_path']).samefile(a['path'])
    assert row['report_digest'] == 'sha256:' + hashlib.sha256(Path(a['path']).read_bytes()).hexdigest()
    assert not [issue for issue in state['issues'] if 'ambiguous' in issue['reason']]


def test_same_value_and_source_digest_do_not_merge_different_report_files(tmp_path):
    a, b = report(tmp_path, 'first'), report(tmp_path, 'second')
    state = build_sensors(brief([a, b], ['pg:mix.T_2_K']))
    assert colors(check_text('Inlet B is 10 °C.', [], ['pg:mix.T_2_K'], state)) == ['grey']
    assert state['pg_rows'][reference(a['path'])]['report_path'] != state['pg_rows'][reference(b['path'])]['report_path']


def test_same_physical_report_repeated_is_still_one_case(tmp_path):
    a = report(tmp_path, 'cold')
    alias = dict(a, path=str(Path(a['path']).parent / '.' / 'report.json'))
    state = build_sensors(brief([a, alias, a], ['pg:mix.T_2_K']))
    assert colors(check_text('Inlet B is 10 °C.', [], ['pg:mix.T_2_K'], state)) == ['green']
    assert not [issue for issue in state['issues'] if 'ambiguous' in issue['reason']]


def test_missing_qualified_case_cannot_borrow_the_request_number(tmp_path):
    a = report(tmp_path, 'cold')
    selected = reference(tmp_path / 'absent.json')
    state = build_sensors(brief([a], [selected]))
    assert colors(check_text('Inlet A is 25 °C.', [], [selected], state)) == ['grey']


def test_selected_case_source_change_is_not_replaced_by_another_report(tmp_path):
    a, b = report(tmp_path, 'cold'), report(tmp_path, 'warm', 285.15)
    (Path(a['path']).parent / 'question.txt').write_text('changed', encoding='utf-8')
    selected = reference(a['path'])
    state = build_sensors(brief([a, b], [selected]))
    assert any(issue['colour'] == 'red' and 'stale' in issue['reason'] for issue in state['issues'])
    assert colors(check_text('Inlet B is 10 °C.', [], [selected], state)) == ['grey']


def test_each_inlet_does_not_assemble_a_pair_from_different_reports(tmp_path):
    a = report(tmp_path, 'left', 298.15, inlet=1)
    b = report(tmp_path, 'right', 298.15, inlet=2)
    selected = [reference(a['path'], 'mix.T_1_K'), reference(b['path'])]
    state = build_sensors(brief([a, b], selected, 'Each inlet is 25 °C.'))
    assert colors(check_text('Each inlet is 25 °C.', [], selected, state)) == ['grey']


def test_each_inlet_uses_only_a_complete_selected_report(tmp_path):
    a, b = report(tmp_path, 'complete', 298.15, inlet=1), report(tmp_path, 'other', 285.15)
    path = Path(a['path']); doc = json.loads(path.read_text())
    second = dict(doc['metadata']['source_readings'][0], id='mix.T_2_K', source_entity='Inlet B', input_group='mix.inlet_2')
    doc['metadata']['source_readings'].append(second); path.write_text(json.dumps(doc), encoding='utf-8')
    selected = [reference(a['path'], 'mix.T_1_K'), reference(a['path'])]
    state = build_sensors(brief([a, b], selected, 'Each inlet is 25 °C.'))
    assert colors(check_text('Each inlet is 25 °C.', [], selected, state)) == ['green']


def test_chosen_point_stays_conditional_in_reader_risks(tmp_path):
    a, b = report(tmp_path, 'cold', source_range=True), report(tmp_path, 'warm', 285.15, source_range=True)
    selected = reference(a['path'])
    value = brief([a, b], [selected])
    results = plan_readings(value)
    assert colors(results) == ['green']
    risks = reading_risks(results)
    assert any('selected point' in row['reason'] and 'independent measurement' in row['reason'] for row in risks)
    assert all('warm' not in row['reason'] for row in risks)


@pytest.mark.parametrize('path', ['case #1% 汉/report.json', r'C:\cases\A #1%汉.json'])
def test_report_ref_escapes_paths_and_row_ids_independently(path):
    from provider_refs import report_row_ref, split_report_row_ref
    identity = 'mix.T#value%:K'
    encoded = report_row_ref(path, identity)
    assert split_report_row_ref(encoded) == (path, identity)
    assert encoded.count('#') == 1
    assert '%23' in encoded and '%25' in encoded


@pytest.mark.parametrize('value', ['pg-report://missing-delimiter', 'pg-report://#row', 'pg-report://path#', 'pg-report://path#bad#row',
                                  'pg-report://bad%ZZ#row', 'pg-report://%FF#row'])
def test_invalid_qualified_reference_is_not_a_legacy_fallback(value):
    from provider_refs import split_report_row_ref
    from _common import ValidationError
    with pytest.raises(ValidationError):
        split_report_row_ref(value)


def test_saved_relative_reference_moves_with_the_existing_report_path(tmp_path):
    import shutil
    from _common import dump_json, load_request
    source = tmp_path / 'original'
    a = report(source, 'case #percent%汉')
    selected = reference(a['path'])
    value = brief([a], [selected])
    request_file = source / 'brief.json'
    dump_json(dict(reader_brief=value), request_file)
    raw = json.loads(request_file.read_text(encoding='utf-8'))
    saved = raw['reader_brief']
    assert saved['provider_reports'][0]['path'] == 'case #percent%汉/report.json'
    assert saved['content_boundaries']['content_units'][0]['model_row_ids'] == [reference('case #percent%汉/report.json')]
    restored = load_request(request_file)['reader_brief']
    assert restored == value
    relocated = tmp_path / 'moved'
    shutil.copytree(source, relocated)
    moved = load_request(relocated / 'brief.json')['reader_brief']
    state = build_sensors(moved)
    new_ref = moved['content_boundaries']['content_units'][0]['model_row_ids'][0]
    assert colors(check_text('Inlet B is 10 °C.', [], [new_ref], state)) == ['green']
    assert str(relocated) in state['pg_rows'][new_ref]['report_path']


def test_qualified_refs_extend_only_model_row_ids_in_both_public_schemas(tmp_path):
    from _common import require_schema, ValidationError
    from tests.v2_support import make_reader_chain
    chain = make_reader_chain(tmp_path)
    value = reference('case #1% 汉/report.json', 'mix.T_2_K')
    current = copy.deepcopy(chain['reader_brief'])
    current['content_boundaries']['content_units'][0]['model_row_ids'] = [value]
    require_schema('reader-brief.schema.json', current, label='ReaderBrief')
    shared = copy.deepcopy(chain['shared_writing'])
    shared['unit_bindings'][0]['model_row_ids'] = [value]
    require_schema('shared-writing-contract.schema.json', shared, label='SharedWriting')
    shared['contract_id'] = value
    with pytest.raises(ValidationError):
        require_schema('shared-writing-contract.schema.json', shared, label='SharedWriting')


def test_same_evidence_digest_is_independent_of_legacy_or_qualified_alias(tmp_path):
    from claim_readings import reading_source_digest
    a = report(tmp_path, 'cold')
    state = build_sensors(brief([a], ['pg:mix.T_2_K']))
    qualified = reference(a['path'])
    assert reading_source_digest([], ['pg:mix.T_2_K'], state) == reading_source_digest([], [qualified], state)
    assert reading_source_digest([], [qualified, 'pg:mix.T_2_K'], state) == reading_source_digest([], [qualified], state)


def test_conditional_case_scope_reaches_the_actual_closure_provider_boundary(tmp_path):
    from derive_closure import provider_checks
    a = report(tmp_path, 'cold', source_range=True)
    selected = reference(a['path'])
    value = brief([a], [selected])
    checks, risks, passed = provider_checks('fiction-writing', value, {}, [a])
    assert passed and checks[0]['status'] == 'passed'
    assert any('selected point' in row['reason'] and 'independent measurement' in row['reason'] for row in risks)


def test_hardlinked_report_in_another_directory_keeps_its_source_base(tmp_path):
    a = report(tmp_path, 'valid')
    other = tmp_path / 'other'; other.mkdir()
    (other / 'question.txt').write_text('changed source', encoding='utf-8')
    alias = other / 'report.json'; alias.hardlink_to(Path(a['path']))
    b = dict(provider='physicsguard', path=str(alias))
    selected = reference(alias)
    state = build_sensors(brief([a, b], [selected]))
    assert any(issue['colour'] == 'red' and 'stale:question.txt' in issue['reason'] for issue in state['issues'])
    assert colors(check_text('Inlet B is 10 °C.', [], [selected], state)) == ['grey']


def native_reports(tmp_path):
    import shutil
    import yaml
    from physicsguard.core.hierarchy import HierarchicalAuditRunner
    from physicsguard.io.hierarchy_loader import load_hierarchical_audit_spec
    from physicsguard.io.observation_loader import load_observed_values
    from build_reader_brief import validate_request
    from tests.v2_support import make_reader_chain
    from derive_closure import provider_checks
    source = Path(__file__).resolve().parents[1] / 'fixtures' / 'provider_cases'
    request = (source / 'question_mix.txt').read_text(encoding='utf-8')
    reports = []
    for name, value in [('cold', 10.), ('warm', 12.)]:
        folder = tmp_path / name; folder.mkdir()
        shutil.copyfile(source / 'audit_mix.yaml', folder / 'audit_mix.yaml')
        (folder / 'question_mix.txt').write_text(request, encoding='utf-8')
        observed = yaml.safe_load((source / 'mix_range.yaml').read_text())
        observed['observation_name'] = name
        observed['variables']['mix.T_2_K']['raw_value'] = value
        observed['variables']['mix.m_dot_out_kg_s']['value'] = 11 / 60
        observed['variables']['mix.T_out_K']['value'] = (5 * 70 + 6 * value) / 11 + 273.15
        case = folder / 'case.yaml'; case.write_text(yaml.safe_dump(observed, sort_keys=False))
        runner = HierarchicalAuditRunner(load_hierarchical_audit_spec(folder / 'audit_mix.yaml'))
        native = runner.to_dict(runner.evaluate_observed(load_observed_values(case), skip_unobserved=True))
        assert native['audit_pass'] is True
        path = folder / 'report.json'; path.write_text(json.dumps(native), encoding='utf-8')
        reports.append(dict(provider='physicsguard', path=str(path)))
    return reports, request


def test_two_actual_native_reports_keep_case_values_and_conditional_scope(tmp_path):
    from build_reader_brief import validate_request
    from tests.v2_support import make_reader_chain
    from derive_closure import provider_checks
    reports, request = native_reports(tmp_path)
    chain = make_reader_chain(tmp_path / 'protocol', owner='fiction-writing', language='en')
    selected = reference(reports[0]['path'])
    bounds = copy.deepcopy(chain['reader_brief']['content_boundaries'])
    bounds['content_units'][0].update(safe_meaning='Inlet B is 10 °C.', evidence_anchor_ids=[], model_row_ids=[selected])
    inputs = dict(route_decision=chain['route_decision'], content_boundaries=bounds,
                  composition_plan=chain['plan'], route_composition=chain['route_composition'],
                  brief_id='brief:case', request=request, provider_reports=reports)
    for ordered in [reports, list(reversed(reports))]:
        result = validate_request(dict(inputs, provider_reports=ordered))
        assert result['status'] == 'current_pass'
        assert colors(result['source_readings']) == ['green']
        assert any('selected point' in r['reason'] for r in result['residual_risk'])
        checks, risks, passed = provider_checks('fiction-writing', result['reader_brief'], {}, ordered)
        assert passed and all(c['status'] == 'passed' for c in checks)
        assert any('not an independent measurement' in r['reason'] for r in risks)
        state = build_sensors(result['reader_brief'])
        assert colors(check_text('Inlet B is 12 °C.', [], [selected], state)) == ['red']


def test_old_legal_nonqualified_ids_are_not_reinterpreted_as_paths():
    from provider_refs import split_report_row_ref, rewrite_row_ref
    for identity in ['model:throughline', 'pg-report:old-label']:
        assert split_report_row_ref(identity) is None
        assert rewrite_row_ref(identity, lambda path: 'changed') == identity


@pytest.mark.parametrize('provider', ['worldguard', 'researchguard'])
def test_other_provider_grey_readings_are_not_filtered_by_physics_row_bindings(tmp_path, provider):
    question = tmp_path / 'original.txt'; question.write_text('A conditional source.', encoding='utf-8')
    digest = hashlib.sha256(question.read_bytes()).hexdigest()
    path = tmp_path / 'native.json'
    path.write_text(json.dumps(dict(input_digests=[dict(path=question.name, sha256=digest)],
        source_readings=[dict(id='unknown', colour='grey', reason='conditional native scope', source_digest=digest)])))
    value = brief([dict(provider=provider, path=str(path))], [], 'Explain the conditional result.')
    state = build_sensors(value)
    issue, = state['issues']
    assert issue['id'] == provider + ':unknown' and issue['colour'] == 'grey'
    assert 'row_refs' not in issue
    assert any(row['reason'] == 'conditional native scope' for row in reading_risks(plan_readings(value)))


@pytest.mark.parametrize('invalid', [None, [23], ['model:throughline', None]])
def test_invalid_model_row_ids_reach_the_schema_rejection(tmp_path, invalid):
    from _common import load_request, require_schema, ValidationError
    from tests.v2_support import make_reader_chain
    chain = make_reader_chain(tmp_path / 'protocol')
    value = copy.deepcopy(chain['reader_brief'])
    value['content_boundaries']['content_units'][0]['model_row_ids'] = invalid
    path = tmp_path / 'input.json'; path.write_text(json.dumps(dict(reader_brief=value)))
    loaded = load_request(path)['reader_brief']
    with pytest.raises(ValidationError, match='model_row_ids'):
        require_schema('reader-brief.schema.json', loaded, label='ReaderBrief')


def test_native_case_scope_survives_actual_derive_closure(tmp_path, monkeypatch):
    # Existing protocol reviews/scores are fixture evidence, not writing-quality measurements.
    from tests import v2_support as fixture
    from reader_plan import build_reader_brief
    from artifact_map import build_artifact_map
    from reader_checks import build_reader_audit
    from _common import fill_fingerprint
    from run_chain import _stamp_judgment
    from review_snapshot import snapshot
    from derive_closure import derive_closure
    reports, request = native_reports(tmp_path)
    selected = reference(reports[0]['path'])
    original_factory = fixture.make_reader_chain

    def make_case_chain(workdir, owner='academic-writing', **kwargs):
        chain = original_factory(workdir, owner, **kwargs)
        bounds = copy.deepcopy(chain['reader_brief']['content_boundaries'])
        bounds['content_units'][0].update(safe_meaning='Inlet B is 10 °C.', model_row_ids=[selected])
        value = build_reader_brief(route_decision=chain['route_decision'], content_boundaries=bounds,
            composition_plan=chain['plan'], route_composition=chain['route_composition'],
            brief_id=chain['reader_brief']['brief_id'], request=request, provider_reports=reports)
        path = chain['artifact_path']; text = path.read_text(encoding='utf-8')
        first = text.index('\n\n') + 2
        path.write_text(text[:first] + 'Inlet B is 10 °C. ' + text[first:], encoding='utf-8')
        amap = build_artifact_map(path, map_id=chain['artifact_map']['map_id'], language='en')
        body = [row for row in amap['units'] if row['unit_kind'] in {'paragraph', 'list', 'table', 'quote', 'scene'}]
        shared = copy.deepcopy(chain['shared_writing'])
        shared.update(reader_brief_fingerprint=value['brief_fingerprint'], artifact_map_fingerprint=amap['map_fingerprint'],
                      artifact_fingerprint=amap['artifact_fingerprint'])
        for binding in shared['unit_bindings']:
            binding['model_row_ids'] = [selected]
            binding['artifact_unit_ids'] = [row['artifact_unit_id'] for row in body]
            binding['artifact_spans'] = [dict(artifact_unit_id=row['artifact_unit_id'], locator=row['locator'],
                                            content_fingerprint=row['content_fingerprint']) for row in body]
        del shared['contract_fingerprint']; fill_fingerprint(shared, 'contract_fingerprint')
        audit = build_reader_audit(audit_id=chain['deterministic_audit']['audit_id'], artifact_map=amap,
                                  reader_brief=value, shared_writing=shared, audited_at=fixture.NOW)
        chain.update(reader_brief=value, artifact_map=amap, shared_writing=shared, deterministic_audit=audit,
                     paragraph=next(row for row in body if row['unit_kind'] == 'paragraph'))
        return chain

    monkeypatch.setattr(fixture, 'make_reader_chain', make_case_chain)
    chain = fixture.complete_chain(tmp_path / 'chain', owner='academic-writing', language='en')
    chain['provider_reports'] = reports
    chain['judgment'] = _stamp_judgment(fixture.closure_input(chain, reviewed=False))
    chain['reviewed_text'] = snapshot(chain['artifact_map'], basis='first_review', changed_units=[])
    closure = derive_closure(fixture.closure_input(chain))['closure']
    assert all(row['passed'] for row in closure['provider_checks'] if row['provider'] == 'physicsguard')
    assert any(row['defect_id'].startswith('physicsguard:case_point:')
               and 'not an independent measurement' in row['reason'] for row in closure['residual_risk'])


def test_malformed_new_scheme_cannot_fall_back_to_a_matching_request_number():
    from _common import ValidationError
    state = dict(anchors={}, passages={}, documents={}, issues=[], pg_rows={}, request=[])
    with pytest.raises(ValidationError, match='invalid qualified'):
        check_text('25 W', [], ['pg-report://missing-delimiter'], state)
