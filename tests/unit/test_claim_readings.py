"""Readings come from originals; typed summaries and matching substrings cannot license them."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from _common import ValidationError
from claim_readings import (
    agrees, check_text, plan_readings, provider_sensors, readings,
    text_readings, validate_plan_readings,
)


def sensors(*, original='', request=''):
    from claim_readings import passage_readings
    return dict(anchors={'a': {}}, passages={'a': dict(file='original.md', section='Facts',
                readings=passage_readings(original))} if original else {},
                request=[(row, dict(sentence=request)) for row in readings(request)],
                pg_rows={}, documents={}, issues=[])


def colours(text, original='', request=''):
    return [row['colour'] for row in check_text(text, ['a'], [], sensors(original=original, request=request))]


@pytest.mark.parametrize(('claim', 'original'), [
    ('1,200 W', '1.2 kW'), ('1\u202f200 W', '1.2 kW'), ('thirty-five minutes', '35 min'),
    ('kilograms per second: 0.525 kg/s', '0.525 kilograms per second'),
    ('between 5 and 10 percent', '5–10%'), ('about 4%', '3.6%'),
    ('almost 113,000', '112,750'), ('more than 21,000', '21,450'),
    ('3 March 2026', '2026-03-03'), ('quarter past eight', '08:15'),
    ('twenty past six in the evening', '18:20'), ('at noon', '12:00'),
    ('version 2.4.1', 'v2.4.1'),
])
def test_d3_d5_d7_value_readings(claim, original):
    assert colours(claim, original) == ['green']


@pytest.mark.parametrize(('claim', 'original'), [
    ('more than 4%', '3.6%'), ('between 10 and 15 percent', '5–10%'),
    ('2.4.2', '2.4.1'), ('13 March 2026', '3 March 2026'),
    ('twenty past seven in the evening', '18:20'), ('18 m/s', '18 km/h'),
])
def test_d5_d7_deliberately_wrong_readings_are_red(claim, original):
    assert colours(claim, original) == ['red']


@pytest.mark.parametrize(('claim', 'original', 'expected'), [
    ('-18.8 kW', '18.8 kW', 'red'),
    ('−18.8 kW', '18.8 kW', 'red'),
    ('18.8 kW', '-18.8 kW', 'red'),
    ('−18.8 kW', '-18800 W', 'green'),
    ('+18.8 kW', '18800 W', 'green'),
    ('5-10%', 'between 5 and 10 percent', 'green'),
])
def test_d5_signed_values_keep_their_sign_and_ranges_keep_their_separator(claim, original, expected):
    assert colours(claim, original) == [expected]


@pytest.mark.parametrize(('claim', 'original', 'expected'), [
    ('The ratio is 0.50.', 'The ratio is 0.5.', 'green'),
    ('The ratio is 1.20.', 'The ratio is 1.2.', 'green'),
    ('The ratio is 0.51.', 'The ratio is 0.5.', 'red'),
    ('Python 3.13', 'Python 3.130', 'red'),
    ('version 1.2', 'version 1.20', 'red'),
])
def test_d5_plain_decimals_compare_values_and_named_versions_keep_their_parts(claim, original, expected):
    assert colours(claim, original) == [expected]


def test_d4_unknown_units_are_refused_unless_same_words_in_original():
    assert colours('28.4 psi', '28.4 kW') == ['red']
    assert colours('28.4 psi', '28.4 psi') == ['green']


def test_d10_source_silent_sentence_is_grey():
    assert colours('The report does not say what happens in 2027.', 'The fare is fixed in 2026.') == ['grey']


def test_missing_original_never_uses_ai_summary():
    assert colours('The result is 95%.') == ['grey']
    assert colours('The result is 95%.', request='Report the result of 95%.') == ['green']


def test_d6_every_bound_same_quantity_row_is_tried():
    state=sensors()
    from claim_readings import _physical_row
    state['pg_rows']={'pg:in':_physical_row(dict(value=348.15,unit='K'),True),
                      'pg:out':_physical_row(dict(value=363.15,unit='K'),True)}
    result=check_text('90 °C', [], ['pg:in','pg:out'], state)
    assert [row['colour'] for row in result] == ['green']


def test_d8_table_value_needs_named_row_and_column():
    original='''# Visits
| Branch | 2024 | 2025 |
| --- | --- | --- |
| Eastgate | 52300 | 50100 |
| Northside | 38900 | 41200 |
'''
    assert colours('Eastgate fell to 41,200 in 2025.', original)[0] == 'red'
    assert all(row == 'green' for row in colours('Eastgate fell to 50,100 in 2025.', original))


def test_d9_d11_quote_and_speaker_and_ellipsis():
    state=sensors()
    original='# Council\n\n"We will not raise fares this year unless fuel prices rise again," said Jonas Berg.'
    state['documents']={'a':dict(text=original,path='council.md')}
    good=check_text('"We will not raise fares this year unless fuel prices rise again," said Jonas Berg.', ['a'],[],state)
    assert all(row['colour']=='green' for row in good)
    bad=check_text('"We will ... raise fares this year ... again," said Jonas Berg.', ['a'],[],state)
    assert any(row['colour']=='red' and 'not' in row['reason'] for row in bad)
    wrong=check_text('"We will not raise fares this year unless fuel prices rise again," said Marta Ruiz.', ['a'],[],state)
    assert any(row['colour']=='red' and 'speaker' in row['reason'] for row in wrong)


def test_request_hash_and_changed_provider_bytes_are_stale(tmp_path):
    question=tmp_path/'question.txt'; question.write_bytes(b'6 L/min and 15 C')
    report=tmp_path/'pg.json'
    saved=dict(audit_pass=True,input_digests=[dict(path='question.txt',sha256=hashlib.sha256(question.read_bytes()).hexdigest())],
               values={'heater.Q':dict(value=18837.0,unit='W',sourced=True)})
    report.write_text(json.dumps(saved))
    rows, issues=provider_sensors([dict(provider='physicsguard',path=str(report))],question.read_text())
    assert rows['pg:heater.Q']['sourced'] and not issues
    _, issues=provider_sensors([dict(provider='physicsguard',path=str(report))],'another request')
    assert 'stale:request_identity' in issues[0]['reason']
    question.write_text('changed original')
    _, issues=provider_sensors([dict(provider='physicsguard',path=str(report))],'6 L/min and 15 C')
    assert 'question.txt' in issues[0]['reason']


def test_plan_refuses_source_mismatch_and_audit_checks_real_text(monkeypatch):
    import claim_readings
    state=sensors(original='The rate is 5–10%.')
    brief=dict(request='',content_boundaries=dict(content_units=[dict(content_unit_id='cu:a',safe_meaning='The rate is 10–15%.',evidence_anchor_ids=['a'],model_row_ids=[])],
               evidence_anchors=[dict(anchor_id='a',source_id='source')],citation_duties=[]))
    monkeypatch.setattr(claim_readings,'build_sensors',lambda _:state)
    with pytest.raises(ValidationError,match='claim_value_not_in_source:cu:a'):
        validate_plan_readings(brief)
    brief['content_boundaries']['content_units'][0]['safe_meaning']='The rate is 5–10%.'
    rows=text_readings(brief,dict(units=[dict(artifact_unit_id='p1',text='The rate is 10–15%.')]),
                       dict(unit_bindings=[dict(content_unit_ids=['cu:a'],artifact_unit_ids=['p1'],model_row_ids=[])]))
    assert rows[0]['colour']=='red'


def test_provider_row_digest_is_checked_even_when_input_digest_matches(tmp_path):
    original=tmp_path/'source.txt';original.write_text('40 buses')
    digest=hashlib.sha256(original.read_bytes()).hexdigest()
    report=tmp_path/'wg.json'
    row=dict(id='claim:1',colour='green',reason='bound source',source_digest='sha256:'+digest)
    report.write_text(json.dumps(dict(input_digests=[dict(path='source.txt',sha256=digest)],source_readings=[row])))
    assert provider_sensors([dict(provider='worldguard',path=str(report))],'')[1] == []
    row['source_digest']='sha256:'+'0'*64
    report.write_text(json.dumps(dict(input_digests=[dict(path='source.txt',sha256=digest)],source_readings=[row])))
    assert 'stale:source_digest_unbound' in provider_sensors([dict(provider='worldguard',path=str(report))],'')[1][0]['reason']


def test_d2_unreadable_screen_exits_two_and_prints_error(tmp_path):
    source=tmp_path/'broken.json';source.write_text('{broken')
    script=Path(__file__).resolve().parents[2]/'skills/logic-writing/scripts/show_plan.py'
    result=subprocess.run([sys.executable,str(script),'--input',str(source)],capture_output=True,text=True)
    assert result.returncode==2
    assert 'show_plan:' in result.stdout and 'Expecting' in result.stdout


def test_number_drift_variant_is_rejected_by_current_artifact_audit(tmp_path):
    from artifact_map import build_artifact_map
    from known_bad import text_variants
    from tests.v2_support import make_reader_chain
    chain=make_reader_chain(tmp_path,language='en')
    brief=chain['reader_brief']
    # A saved original, rather than the AI's summary, licenses the number.
    original=chain['artifact_path'].read_text()
    chain['artifact_path'].write_text(original+'\n\nThe measured result is 25%.\n')
    amap=build_artifact_map(chain['artifact_path'],map_id='map:reading',language='en')
    paragraph=next(row for row in amap['units'] if '25%' in row['text'] and row['unit_kind']=='paragraph')
    folder=tmp_path/'research';(folder/'captures').mkdir(parents=True)
    data=b'# Measurement\n\nThe measured result is 25%.\n'
    (folder/'captures/measurement.md').write_bytes(data)
    import yaml
    (folder/'captures.yaml').write_text(yaml.safe_dump(dict(files={'measurement.md':dict(source_id='measured',sha256=hashlib.sha256(data).hexdigest())},anchors={'measurement':dict(file='measurement.md',quote='The measured result is 25%.')})))
    brief['research_folder']=str(folder)
    brief['content_boundaries']['evidence_anchors']=[dict(anchor_id='measurement',source_id='measured')]
    brief['content_boundaries']['content_units'][0]['evidence_anchor_ids']=['measurement']
    brief['content_boundaries']['content_units'][0]['safe_meaning']='The measured result is 25%.'
    shared=dict(unit_bindings=[dict(planned_unit_id=brief['composition_plan']['planned_units'][0]['planned_unit_id'],content_unit_ids=[brief['content_boundaries']['content_units'][0]['content_unit_id']],
                                   artifact_unit_ids=[paragraph['artifact_unit_id']],model_row_ids=[])])
    variants=text_variants(chain['artifact_path'].read_text(),reader_brief=brief,artifact_map=amap,shared_writing=shared,route_review={})
    drift=next(row for row in variants if row['kind']=='number-drift')
    assert '987654321%' in drift['text']
    mutated=dict(units=[dict(row,text=drift['text'] if row['artifact_unit_id']==paragraph['artifact_unit_id'] else row['text']) for row in amap['units']])
    assert any(row['colour']=='red' for row in text_readings(brief,mutated,shared))
    chain['artifact_path'].write_text(drift['text'])
    current = build_artifact_map(chain['artifact_path'], map_id='map:changed-reading', language='en')
    from reader_checks import build_reader_audit_from_current
    result = build_reader_audit_from_current(audit_id='audit:changed-reading', amap=current, brief=brief,
        contract=dict(chain['shared_writing'], unit_bindings=shared['unit_bindings']))
    assert result['status'] == 'repair'
    assert any(row['code'] == 'text_value_not_in_source' for row in result['findings'])


def test_build_reader_brief_rejects_wrong_bound_physics_value(tmp_path):
    from build_reader_brief import build_reader_brief
    from tests.v2_support import make_reader_chain
    chain=make_reader_chain(tmp_path,language='en')
    question=tmp_path/'question.txt'; question.write_text('Use the measured power of 25 W.')
    report=tmp_path/'pg-result.json'
    report.write_text(json.dumps(dict(audit_pass=True,input_digests=[dict(path='question.txt',sha256=hashlib.sha256(question.read_bytes()).hexdigest())],
              values={'heater.Q':dict(value=25,unit='W',sourced=True)})))
    boundaries=chain['reader_brief']['content_boundaries']
    boundaries['content_units'][0]['safe_meaning']='The power is 250 W.'
    boundaries['content_units'][0]['model_row_ids']=['pg:heater.Q']
    with pytest.raises(ValidationError,match='claim_value_not_in_source:content:answer'):
        build_reader_brief(route_decision=chain['route_decision'],content_boundaries=boundaries,
              composition_plan=chain['plan'],route_composition=chain['route_composition'],brief_id='brief:sourced',
              request=question.read_text(),provider_reports=[dict(provider='physicsguard',path=str(report))])


def test_physics_provider_reads_saved_result_without_running_the_tool(tmp_path):
    from derive_closure import provider_checks
    question=tmp_path/'question.txt';question.write_bytes(b'25 W')
    path=tmp_path/'pg.json'
    path.write_text(json.dumps(dict(audit_pass=True,input_digests=[dict(path='question.txt',sha256=hashlib.sha256(question.read_bytes()).hexdigest())],values={})))
    checks, risks, passed=provider_checks('fiction-writing',dict(request='25 W'),{},[dict(provider='physicsguard',path=str(path))])
    assert passed and checks[0]['status']=='passed' and not risks
    question.write_text('changed')
    checks, risks, passed=provider_checks('fiction-writing',dict(request='25 W'),{},[dict(provider='physicsguard',path=str(path))])
    assert not passed and 'stale' in checks[0]['reason']


def test_native_physics_rows_bind_request_and_every_original(tmp_path):
    question = tmp_path / 'question.txt'
    question.write_bytes(b'The measured power is 25 W.')
    table = tmp_path / 'measurements.csv'
    table.write_bytes(b't_s,power_W\n0,25\n')
    hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in (question, table)]
    path = tmp_path / 'physics.json'
    report = dict(audit_pass=True, metadata=dict(sources={
        'question': dict(path='question.txt', sha256=hashes[0]),
        'csv:measurements.csv': dict(path='measurements.csv', sha256=hashes[1])},
        source_readings=[dict(id='heater.Q', colour='green', reason='derived from checked values',
                             value=25, unit='W', source_digest=None, source_digests=hashes)]))
    path.write_text(json.dumps(report))
    rows, issues = provider_sensors([dict(provider='physicsguard', path=str(path))], question.read_text())
    assert not issues and rows['pg:heater.Q']['sourced']
    table.write_bytes(b't_s,power_W\n0,250\n')
    rows, issues = provider_sensors([dict(provider='physicsguard', path=str(path))], question.read_text())
    assert not rows and 'stale:measurements.csv' in issues[0]['reason']


def test_source_reading_identity_records_original_bytes(tmp_path):
    from tests.unit.test_claim_public_seeds import CASES, _prepare
    from claim_readings import build_sensors
    case = next(row for row in CASES if row['name'] == 's0_shipped')
    brief, _, _ = _prepare(case, tmp_path / 'case')
    rows = plan_readings(brief, sensors=build_sensors(brief))
    assert rows and len({row['id'] for row in rows}) == len(rows)
    assert all({'id', 'colour', 'reason', 'source_digest'} <= row.keys() for row in rows)
    assert all(row['source_digest'].startswith('sha256:') for row in rows if row['colour'] == 'green')


def test_missing_physicsguard_keeps_plain_brief_and_marks_units_grey(monkeypatch):
    import claim_readings
    monkeypatch.setattr(claim_readings, '_unit_reader', lambda: None)
    brief = dict(request='Give a plain explanation.', content_boundaries=dict(
        evidence_anchors=[], content_units=[dict(content_unit_id='plain', safe_meaning='Explain the conclusion.',
                                                evidence_anchor_ids=[], model_row_ids=[])]))
    assert plan_readings(brief) == []
    rows = check_text('The speed is 18 m/s.', ['a'], [], sensors(original='The speed is 18 km/h.'))
    assert rows and all(row['colour'] == 'grey' for row in rows)
    assert 'install PhysicsGuard' in rows[0]['reason']


def test_plain_brief_in_a_process_with_no_installed_guard_packages():
    scripts = Path(__file__).resolve().parents[2] / 'skills/logic-writing/scripts'
    command = '''
import json,sys
sys.path.insert(0, sys.argv[1])
from claim_readings import _unit_reader,check_text,plan_readings
brief=dict(request='Explain the conclusion.', content_boundaries=dict(evidence_anchors=[],
    content_units=[dict(content_unit_id='plain',safe_meaning='Explain the conclusion.',evidence_anchor_ids=[],model_row_ids=[])]))
assert _unit_reader() is None
assert plan_readings(brief)==[]
state=dict(anchors={},passages={},documents={},issues=[],request=[],pg_rows={})
rows=check_text('A power of 25 W.',[],[],state)
assert rows and all(row['colour']=='grey' for row in rows)
print(json.dumps(rows))
'''
    result = subprocess.run([sys.executable, '-S', '-c', command, str(scripts)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'install PhysicsGuard' in result.stdout


def test_world_rows_use_the_bound_world_folder_not_the_report_folder(tmp_path):
    world = tmp_path / 'world'
    world.mkdir()
    contract = world / 'world.yaml'
    contract.write_text('world: ferry\n')
    original = world / 'chapter.md'
    original.write_text('Departure at 18:20.')
    sources = [dict(path='chapter.md', sha256=hashlib.sha256(original.read_bytes()).hexdigest())]
    digest = hashlib.sha256(json.dumps(sources, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    output = tmp_path / 'reports'
    output.mkdir()
    saved = output / 'world.json'
    saved.write_text(json.dumps(dict(input_digests=sources, checked=dict(source_statuses=[
        dict(id='departure:0', colour='green', reason='source agrees', source_digest=digest, sources=sources)]))))
    report = dict(provider='worldguard', path=str(saved))
    assert provider_sensors([report], '', dict(world_contract=str(contract)))[1] == []
    original.write_text('Departure at 19:20.')
    assert 'stale:chapter.md' in provider_sensors([report], '', dict(world_contract=str(contract)))[1][0]['reason']


def test_actual_physicsguard_report_drives_the_bound_reading(tmp_path):
    import shutil
    fixture = Path(__file__).resolve().parents[1] / 'fixtures/claim_readings/originals/heater'
    folder = tmp_path / 'heater'
    shutil.copytree(fixture, folder)
    result = subprocess.run([sys.executable, '-m', 'physicsguard.cli', 'hierarchy', 'evaluate',
                             str(folder / 'audit.yaml'), str(folder / 'q_inputs.yaml'), '--json'],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    native = json.loads(result.stdout)
    assert native['metadata']['source_readings'] and native['metadata']['sources']
    saved = folder / 'native-pg.json'
    saved.write_text(result.stdout)
    request = (folder / 'question.txt').read_text()
    rows, issues = provider_sensors([dict(provider='physicsguard', path=str(saved))], request)
    assert not [issue for issue in issues if issue['colour'] == 'red']
    state = sensors(request=request)
    state['pg_rows'] = rows
    assert [row['colour'] for row in check_text('0.1 kg/s.', [], ['pg:heater.m_dot_kg_s'], state)] == ['green']
    assert [row['colour'] for row in check_text('18.8 kW.', [], ['pg:heater.Q_dot_W'], state)] == ['green']
    power_error = check_text('1.13 MW.', [], ['pg:heater.Q_dot_W'], state)
    assert power_error[0]['colour'] == 'red' and 'x60' in power_error[0]['reason']
    wrong = check_text('6 kg/s.', [], ['pg:heater.m_dot_kg_s'], state)
    assert wrong[0]['colour'] == 'red' and 'x60' in wrong[0]['reason']
    (folder / 'question.txt').write_text(request + '\nChanged input.')
    assert 'stale:' in provider_sensors([dict(provider='physicsguard', path=str(saved))], request)[1][0]['reason']


def test_unreferenced_physics_grey_rows_do_not_add_plan_noise(tmp_path):
    from claim_readings import build_sensors
    question = tmp_path / 'question.txt'
    question.write_text('The power is 25 W.')
    digest = hashlib.sha256(question.read_bytes()).hexdigest()
    report = tmp_path / 'physics.json'
    report.write_text(json.dumps(dict(audit_pass=True, metadata=dict(
        sources=dict(question=dict(path='question.txt', sha256=digest)), source_readings=[
            dict(id='checked', value=25, unit='W', colour='green', reason='original agrees', source_digest=digest),
            dict(id='unquoted', value=20, unit='W', colour='grey', reason='AI value', source_digest=None)]))))
    unit = dict(content_unit_id='power', safe_meaning='25 W', evidence_anchor_ids=[], model_row_ids=['pg:checked'])
    brief = dict(request=question.read_text(), provider_reports=[dict(provider='physicsguard', path=str(report))],
                 content_boundaries=dict(content_units=[unit], evidence_anchors=[]))
    assert build_sensors(brief)['issues'] == []
    assert [row['colour'] for row in plan_readings(brief)] == ['green']
    unit.update(safe_meaning='20 W', model_row_ids=['pg:unquoted'])
    assert build_sensors(brief)['issues'][0]['colour'] == 'grey'
    assert all(row['colour'] == 'grey' for row in plan_readings(brief))


def test_native_researchguard_capture_is_the_reading_owner(tmp_path):
    import yaml
    from researchguard.source.capture import capture_source, load_anchor_capture
    from claim_readings import build_sensors
    project = tmp_path / 'research'
    project.mkdir()
    (project / 'research.yaml').write_text(yaml.safe_dump(dict(models=dict(source='source.yaml'))))
    (project / 'source.yaml').write_text(yaml.safe_dump(dict(
        sources=[dict(source_id='measured', title='Control document')],
        anchors=[dict(anchor_id='measurement', source_id='measured', text='Measured power: 25 W.')])))
    original = tmp_path / 'original.md'
    original.write_text('# Control\n## Result\nMeasured power: 25 W.')
    capture_source(project, 'measured', file=original)
    saved = load_anchor_capture(project, 'measurement')
    assert saved['colour'] == 'green' and saved['source_digest']
    unit = dict(content_unit_id='power', safe_meaning='25 W', evidence_anchor_ids=['measurement'], model_row_ids=[])
    brief = dict(request='', research_folder=str(project), content_boundaries=dict(content_units=[unit],
                 evidence_anchors=[dict(anchor_id='measurement', source_id='measured')]))
    assert [row['colour'] for row in plan_readings(brief)] == ['green']
    unit['safe_meaning'] = '250 W'
    assert [row['colour'] for row in plan_readings(brief)] == ['red']
    Path(saved['path']).write_text('# Control\n## Result\nMeasured power: 250 W.')
    changed = build_sensors(brief)
    assert changed['issues'][0]['colour'] == 'red'
    assert 'changed' in changed['issues'][0]['reason']
