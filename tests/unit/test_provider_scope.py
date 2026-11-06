"""Existing identity fields bind literal facts to their actual role and source scope."""
import hashlib
import json

import pytest
import yaml

from artifact_map import build_artifact_map
from claim_readings import _physical_row, check_text, plan_readings, text_readings


def _captured_brief(tmp_path, original, quote, meaning, *, request=''):
    project = tmp_path / 'research'
    (project / 'captures').mkdir(parents=True)
    raw = original.encode('utf-8')
    (project / 'captures/source.md').write_bytes(raw)
    manifest = {'files': {'source.md': {'source_id': 's', 'sha256': hashlib.sha256(raw).hexdigest()}},
                'anchors': {'a': {'file': 'source.md', 'quote': quote}}}
    (project / 'captures.yaml').write_text(yaml.safe_dump(manifest), encoding='utf-8')
    unit = dict(content_unit_id='fact', safe_meaning=meaning, evidence_anchor_ids=['a'], model_row_ids=[])
    return dict(request=request, research_folder=str(project), content_boundaries=dict(
        content_units=[unit], evidence_anchors=[dict(anchor_id='a', source_id='s')], citation_duties=[]))


def _text_rows(tmp_path, brief, text):
    piece = tmp_path / 'piece.md'; piece.write_text(text, encoding='utf-8')
    artifact = build_artifact_map(piece, map_id='map:scope', language='en')
    paragraphs = [row['artifact_unit_id'] for row in artifact['units'] if row['unit_kind'] == 'paragraph']
    shared = dict(unit_bindings=[dict(planned_unit_id='p', content_unit_ids=['fact'],
                                    model_row_ids=[], artifact_unit_ids=paragraphs)])
    return text_readings(brief, artifact, shared)


def test_assumed_budget_value_does_not_become_a_measured_result(tmp_path):
    original = '# Trial\n\n## Result\n\nThe measured power is 6 kW.\n\nThe unrelated equipment budget assumes 10 kW.\n'
    brief = _captured_brief(tmp_path, original, 'The measured power is 6 kW.', 'The measured power is 6 kW.')
    assert all(row['colour'] == 'green' for row in plan_readings(brief))
    assert all(row['colour'] == 'green' for row in _text_rows(tmp_path, brief, 'The measured power is 6 kW.'))
    brief['content_boundaries']['content_units'][0]['safe_meaning'] = 'The measured power is 10 kW.'
    assert any(row['colour'] == 'red' for row in plan_readings(brief))
    assert any(row['colour'] == 'red' for row in _text_rows(tmp_path, brief, 'The measured power is 10 kW.'))


@pytest.mark.parametrize('sentence, expected', [
    ('The expected power is 10 kW.', 'green'),
    ('The measured power is 10 kW.', 'red'),
    ('The power is 10 kW.', 'grey'),
])
def test_an_explicit_assumption_keeps_its_scope(tmp_path, sentence, expected):
    brief = _captured_brief(tmp_path, '# Power\n\nThe design assumes 10 kW.\n',
                            'The design assumes 10 kW.', sentence)
    assert [row['colour'] for row in _text_rows(tmp_path, brief, sentence)] == [expected]


def test_declared_experiment_is_usable_but_not_an_independent_measurement():
    from researchguard_status import assess_research_verdict
    document = dict(verdict=dict(errors=0, search='stop_sufficient', contested=False,
                                live_hypotheses=['h'], root_claim=dict(id='h', wording_license='assert', reason='conditional model')),
                    hypotheses=[dict(id='h')], experiment_observation_checks=[
                        dict(id='obs:e:a', colour='grey', basis='caller_declared', reason='semantic label has no unique captured literal')])
    result = assess_research_verdict(document)
    assert result['passed']
    assert result['residual_risk'][0]['defect_id'] == 'research:observation_declared:obs:e:a'
    assert 'conditional' in result['residual_risk'][0]['reason']


@pytest.mark.parametrize('broken', [None, '', {}, [None], [{}], [dict(id='a', colour='grey', basis='caller_declared', reason=None)]])
def test_damaged_optional_observation_report_stays_unreadable(broken):
    from researchguard_status import assess_research_verdict
    document = dict(verdict=dict(errors=0, search='stop_sufficient', contested=False,
                                live_hypotheses=['h'], root_claim=dict(id='h', wording_license='assert', reason='conditional model')),
                    hypotheses=[dict(id='h')], experiment_observation_checks=broken)
    result = assess_research_verdict(document)
    assert result['status'] == 'unreadable'
    assert 'experiment_observation_checks' in result['reason']


@pytest.mark.parametrize('value, expected', [(6, 'green'), (10, 'red')])
def test_question_echo_cannot_overwrite_a_compatible_captured_measurement(tmp_path, value, expected):
    brief = _captured_brief(tmp_path, '# Trial\n\nThe measured power is 6 kW.\n',
                            'The measured power is 6 kW.', 'The measured power is 6 kW.',
                            request='Could the measured power be 10 kW?')
    assert [row['colour'] for row in _text_rows(tmp_path, brief, f'The measured power is {value} kW.')] == [expected]


@pytest.mark.parametrize('sentence, expected', [
    ('Northside visits went from 38,900 in 2024 to 41,200 in 2025.', 'green'),
    ('Northside visits went from 41,200 in 2024 to 38,900 in 2025.', 'red'),
])
def test_equal_table_values_keep_their_explicit_year_columns(tmp_path, sentence, expected):
    original = '# Visits\n\n| Branch | Visits | |\n|---|---|---|\n| | 2024 | 2025 |\n| Northside | 38,900 | 41,200 |\n\nThe board recorded annual visits.\n'
    brief = _captured_brief(tmp_path, original, 'The board recorded annual visits.', sentence)
    rows = _text_rows(tmp_path, brief, sentence)
    assert any(row['colour'] == expected for row in rows)
    if expected == 'green':
        assert not any(row['colour'] == 'red' for row in rows)


def _physics_sensors():
    rows = {
        'pg:mix.T_1_K': _physical_row(dict(value=298.15, unit='K', source_entity='Inlet A', input_group='mix.inlet_1'), True),
        'pg:mix.T_2_K': _physical_row(dict(value=313.15, unit='K', source_entity='Inlet B', input_group='mix.inlet_2'), True),
    }
    # The requested values must not override a contradictory selected entity.
    from claim_readings import readings
    request = 'Inlet A is 25 °C; Inlet B is 40 °C. Could Inlet B also be 25 °C?'
    return dict(anchors={}, passages={}, documents={}, issues=[], pg_rows=rows,
                request=[(row, dict(sentence=request)) for row in readings(request)])


@pytest.mark.parametrize('sentence, ids, expected', [
    ('Inlet A is 25 °C.', ['pg:mix.T_1_K'], 'green'),
    ('Inlet B is 40 °C.', ['pg:mix.T_2_K'], 'green'),
    ('Inlet B is 25 °C.', ['pg:mix.T_1_K'], 'red'),
    ('Inlet B is 25 °C.', ['pg:mix.T_1_K', 'pg:mix.T_2_K'], 'red'),
    ('Inlet A and Inlet B are both 25 °C.', ['pg:mix.T_1_K', 'pg:mix.T_2_K'], 'red'),
    ('The temperature is 25 °C.', ['pg:mix.T_1_K'], 'grey'),
])
def test_green_physics_rows_do_not_loan_their_value_to_a_different_entity(sentence, ids, expected):
    rows = check_text(sentence, [], ids, _physics_sensors())
    assert [row['colour'] for row in rows] == [expected]


@pytest.mark.parametrize('sentence, expected', [
    ('Inlet A is 25 °C; Inlet B is 40 °C.', ['green', 'green']),
    ('Inlet A is 25 °C and Inlet B is 40 °C.', ['green', 'green']),
    ('Inlet A is 25 °C in all conditions; Inlet B is 40 °C.', ['green', 'green']),
    ('Inlet A is 40 °C; Inlet B is 25 °C.', ['red', 'red']),
    ('Inlet A and Inlet B are both 40 °C.', ['red']),
    ('Both Inlet A and Inlet B are 40 °C.', ['red']),
    ('Inlet A and Inlet B are 40 °C.', ['red']),
    ('Each inlet is 40 °C.', ['red']),
    ('Inlet A or Inlet B is 25 °C.', ['grey']),
])
def test_each_physics_reading_keeps_its_finite_clause(sentence, expected):
    rows = check_text(sentence, [], ['pg:mix.T_1_K', 'pg:mix.T_2_K'], _physics_sensors())
    assert [row['colour'] for row in rows] == expected


@pytest.mark.parametrize('sentence', ['Both Inlet A and Inlet B are 25 °C.', 'Inlet A and Inlet B are both 25 °C.',
                                     'Each inlet is 25 °C.'])
def test_a_correct_explicit_shared_value_remains_usable(sentence):
    state = _physics_sensors()
    state['pg_rows']['pg:mix.T_2_K'] = _physical_row(
        dict(value=298.15, unit='K', source_entity='Inlet B', input_group='mix.inlet_2'), True)
    assert [row['colour'] for row in check_text(sentence, [], ['pg:mix.T_1_K', 'pg:mix.T_2_K'], state)] == ['green']


@pytest.mark.parametrize('scope', ['incomplete', 'multiple_models'])
def test_each_inlet_cannot_guess_an_incomplete_or_ambiguous_native_group(scope):
    state = _physics_sensors()
    if scope == 'incomplete':
        del state['pg_rows']['pg:mix.T_2_K']
    else:
        state['pg_rows']['pg:other.T_1_K'] = _physical_row(
            dict(value=298.15, unit='K', source_entity='Inlet C', input_group='other.inlet_1'), True)
    assert [row['colour'] for row in check_text('Each inlet is 25 °C.', [],
            ['pg:mix.T_1_K', 'pg:mix.T_2_K'], state)] == ['grey']


@pytest.mark.parametrize('sentence, expected', [
    ('Inlet A supplies 5 L/min.', ['grey']),
    ('Inlet B supplies 5 L/min.', ['grey']),
    ('Inlet A supplies 5 L/min; Inlet B supplies 6 L/min.', ['grey', 'grey']),
    ('Each inlet is at 5 L/min.', ['grey']),
])
@pytest.mark.parametrize('request_echo', [False, True])
def test_native_entity_dimensions_cannot_fall_back_to_a_requested_number(sentence, expected, request_echo):
    from claim_readings import readings
    state = _physics_sensors()
    state['pg_rows'] = {
        'pg:mix.flow_1': _physical_row(dict(value=1/12, unit='kg/s', source_entity='Inlet A', input_group='mix.inlet_1'), True),
        'pg:mix.flow_2': _physical_row(dict(value=.1, unit='kg/s', source_entity='Inlet B', input_group='mix.inlet_2'), True),
    }
    question = 'Inlet A supplies 5 L/min; Inlet B supplies 6 L/min.'
    state['request'] = [(row, dict(sentence=question)) for row in readings(question)] if request_echo else []
    rows = check_text(sentence, [], ['pg:mix.flow_1', 'pg:mix.flow_2'], state)
    assert [row['colour'] for row in rows] == expected
    assert all('no compatible quantity' in row['reason'] for row in rows)


@pytest.mark.parametrize('has_role, text, expected, owner', [
    (True, 'Inlet B is 40 °C.', 'green', 'captured source entity'),
    (True, 'Inlet B is 25 °C.', 'red', 'claimed value'),
    (False, 'Inlet B is 40 °C.', 'green', 'PhysicsGuard'),
    (False, 'Inlet B is 25 °C.', 'green', 'PhysicsGuard'),
])
def test_old_scalar_reports_are_distinct_from_native_entity_reports(has_role, text, expected, owner):
    state = _physics_sensors()
    state['request'] = []
    if not has_role:
        for row in state['pg_rows'].values():
            del row['source_entity']
            del row['input_group']
    row, = check_text(text, [], ['pg:mix.T_1_K', 'pg:mix.T_2_K'], state)
    assert row['colour'] == expected
    assert owner in row['reason']
    if not has_role:
        assert 'entity' not in row['reason']


@pytest.mark.parametrize('text', ['Inlet A is 10–12 °C.', 'Inlet B is 10–12 °C.',
                                'Inlet B reads 25.', 'Inlet B reads 25%.', 'Inlet B is 25 psi.'])
def test_scalar_native_roles_do_not_claim_to_verify_other_reading_forms(text):
    from claim_readings import readings
    state = _physics_sensors()
    state['request'] = [(row, dict(sentence=text)) for row in readings(text)]
    row, = check_text(text, [], ['pg:mix.T_1_K', 'pg:mix.T_2_K'], state)
    assert row['colour'] == 'grey'
    assert 'role/value agreement was not checked' in row['reason']


def test_a_legacy_compatible_scalar_cannot_wash_an_incompatible_native_role():
    state = _physics_sensors()
    state['pg_rows']['pg:legacy'] = _physical_row(dict(value=5., unit='L/min'), True)
    row, = check_text('Inlet B supplies 5 L/min.', [], ['pg:mix.T_2_K', 'pg:legacy'], state)
    assert row['colour'] == 'grey'
    assert 'no compatible quantity' in row['reason']


@pytest.mark.parametrize('text, expected', [
    ('Inlet A is 25 °C.', ['grey']),
    ('Inlet A is 25 °C; Inlet B is 40 °C.', ['grey', 'green']),
    ('Inlet A and Inlet B are both 40 °C.', ['grey']),
    ('Both Inlet A and Inlet B are 25 °C.', ['red']),
])
def test_each_entity_needs_its_own_compatible_native_quantity(text, expected):
    state = _physics_sensors()
    state['pg_rows']['pg:mix.flow_1'] = _physical_row(
        dict(value=.1, unit='kg/s', source_entity='Inlet A', input_group='mix.inlet_1'), True)
    rows = check_text(text, [], ['pg:mix.flow_1', 'pg:mix.T_2_K'], state)
    assert [row['colour'] for row in rows] == expected
