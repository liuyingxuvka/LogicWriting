"""Released single-report inputs stay useful; unsupported old proofs are not upgraded."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from claim_readings import build_sensors, plan_readings
from schema_validation import SchemaValidationError, assert_schema_valid, validate_schema


FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures' / 'saved_contract_compatibility'


def _legacy_single_report(tmp_path):
    source = tmp_path / 'single_report'
    shutil.copytree(FIXTURES / 'single_report', source)
    return source


def _legacy_brief(source, *, value='18.837'):
    return dict(
        request=(source / 'question.txt').read_text(encoding='utf-8'),
        provider_reports=[dict(provider='physicsguard', path=str(source / 'pg-result.json'))],
        content_boundaries=dict(evidence_anchors=[], citation_duties=[], content_units=[
            dict(content_unit_id='heater-result', safe_meaning=f'The heater power is {value} kW.',
                 evidence_anchor_ids=[], model_row_ids=['pg:heater.Q_dot_W'])]))


def test_single_report_saved_by_431_and_432_keeps_its_scalar_binding(tmp_path):
    source = _legacy_single_report(tmp_path)
    report = source / 'pg-result.json'
    before = report.read_bytes()
    brief = _legacy_brief(source)
    sensors = build_sensors(brief)
    assert sensors['issues'] == []
    assert [row['colour'] for row in plan_readings(brief, sensors=sensors)] == ['green']
    assert [row['colour'] for row in plan_readings(_legacy_brief(source, value='28.837'), sensors=sensors)] == ['red']
    assert 'source_entity' not in sensors['pg_rows']['pg:heater.Q_dot_W']
    assert report.read_bytes() == before


@pytest.mark.parametrize('changed', ['audit', 'request'])
def test_old_saved_report_does_not_gain_fresh_evidence_after_input_changes(tmp_path, changed):
    source = _legacy_single_report(tmp_path)
    brief = _legacy_brief(source)
    if changed == 'audit':
        with (source / 'audit.yaml').open('ab') as handle:
            handle.write(b'\n# changed after the saved report\n')
    else:
        brief['request'] = 'Use a different request.'
    sensors = build_sensors(brief)
    assert any(row['colour'] == 'red' and 'stale:' in row['reason'] for row in sensors['issues'])
    assert 'pg:heater.Q_dot_W' not in sensors['pg_rows']
    assert all(row['colour'] != 'green' for row in plan_readings(brief, sensors=sensors))


def test_released_432_brief_remains_a_valid_saved_input_without_mutation():
    path = FIXTURES / 'v4.3.2-reader-brief.json'
    before = path.read_bytes()
    brief = json.loads(before)
    original = copy.deepcopy(brief)
    assert_schema_valid('reader-brief.schema.json', brief)
    assert brief == original
    assert path.read_bytes() == before


def test_real_historical_brief_is_refused_without_filling_new_evidence_fields():
    path = FIXTURES / 'v3.0.2-reader-brief.json'
    before = path.read_bytes()
    brief = json.loads(before)
    original = copy.deepcopy(brief)
    assert brief['schema_version'] == '2.0'
    assert 'writer_input' not in brief and 'request' not in brief
    issues = validate_schema('reader-brief.schema.json', brief)
    assert any(issue.keyword == 'required' and 'writer_input' in issue.message for issue in issues)
    with pytest.raises(SchemaValidationError, match='writer_input'):
        assert_schema_valid('reader-brief.schema.json', brief)
    assert brief == original
    assert path.read_bytes() == before


def test_frozen_compatibility_inputs_retain_the_released_bytes():
    provenance = json.loads((FIXTURES / 'provenance.json').read_text(encoding='utf-8'))
    for row in provenance['fixtures']:
        assert hashlib.sha256((FIXTURES / row['path']).read_bytes()).hexdigest() == row['sha256']
    report = next(row for row in provenance['fixtures'] if row['path'] == 'single_report/pg-result.json')
    assert report['unchanged_at'] == [
        'ada2fd96490ec1bc2c82bce67b7ff9cac846713b',
        '97c0738fd4a4b6871cef3bb1fbd31670736197b5',
    ]
