"""Explicit review binding on short, existing pieces; default runs never stamp."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

import pytest
import yaml

from _common import fill_fingerprint, fingerprint, load_request, require_exact_fingerprint
from derive_closure import CLOSURE_INPUT_FILES
from reader_fill import fill_closure_fingerprints
from run_chain import main, run_chain

EXAMPLES = Path(__file__).resolve().parents[2] / 'skills/logic-writing/assets/examples'


def _copy(tmp_path):
    folder = tmp_path / 'investigation'
    shutil.copytree(EXAMPLES / 'investigation', folder)
    return folder


def _stamp(folder, capsys):
    with patch.object(sys, 'argv', ['run_chain.py', str(folder), '--stamp-review']):
        try:code = main()
        except SystemExit as exc:code = exc.code
    return code, capsys.readouterr().out


def test_stamp_review_writes_the_fingerprints(tmp_path, capsys):
    folder = _copy(tmp_path)
    path = folder / 'closure-input.json'
    before = json.loads(path.read_text())
    code, output = _stamp(folder, capsys)
    assert code == 0
    saved = json.loads(path.read_text())
    assert f"stamped: closure-input.json judgment {saved['judgment']['judgment_id']}" in output
    fields = {'reader_intent_fingerprint', 'reader_brief_fingerprint', 'composition_plan_fingerprint',
              'artifact_map_fingerprint', 'shared_writing_contract_fingerprint', 'deterministic_audit_fingerprint',
              'route_audit_fingerprint', 'artifact_fingerprint', 'evaluation_profile_fingerprint', 'judgment_fingerprint'}
    assert fields <= saved['judgment'].keys()
    assert {key: value for key, value in saved.items() if key != 'judgment'} == {key: value for key, value in before.items() if key != 'judgment'}
    stamped = path.read_bytes()
    assert _stamp(folder, capsys)[0] == 0 and path.read_bytes() == stamped
    for _ in range(2):
        assert run_chain(folder)['exit_code'] == 0
        assert path.read_bytes() == stamped


def test_edited_text_makes_the_stamped_review_stale(tmp_path, capsys):
    folder = _copy(tmp_path)
    assert _stamp(folder, capsys)[0] == 0
    before = (folder / 'closure-input.json').read_bytes()
    piece = folder / 'piece.md'
    piece.write_text(piece.read_text().replace('single-threaded', 'multi-threaded', 1))
    for _ in range(2):
        result = run_chain(folder)
        assert result['exit_code'] == 1
        assert result['first_failure']['message'].startswith('judgment_stale:')
        assert '--stamp-review' in result['first_failure']['message'] and str(folder) in result['first_failure']['message']
        assert (folder / 'closure-input.json').read_bytes() == before


def test_unstamped_review_is_refused_with_the_command(tmp_path, capsys):
    folder = _copy(tmp_path)
    assert _stamp(folder, capsys)[0] == 0
    path = folder / 'closure-input.json'
    request = json.loads(path.read_text())
    request['judgment'] = {key: value for key, value in request['judgment'].items() if not key.endswith('_fingerprint')}
    path.write_text(json.dumps(request))
    before = path.read_bytes()
    result = run_chain(folder)
    assert result['exit_code'] == 1
    assert result['first_failure']['message'].startswith('judgment_unstamped:' + request['judgment']['judgment_id'])
    assert '--stamp-review' in result['first_failure']['message'] and str(folder) in result['first_failure']['message']
    assert path.read_bytes() == before


def test_required_unit_missing_from_the_review_fails(tmp_path, capsys):
    folder = _copy(tmp_path)
    assert _stamp(folder, capsys)[0] == 0
    path = folder / 'closure-input.json'
    request = json.loads(path.read_text())
    for row in request['judgment']['reverse_outline']:
        row['content_unit_ids'] = [identity for identity in row['content_unit_ids'] if identity != 'cu-perf']
    request['judgment'].pop('judgment_fingerprint')
    fill_fingerprint(request['judgment'], 'judgment_fingerprint')
    path.write_text(json.dumps(request))
    result = run_chain(folder)
    assert result['first_failure']['message'] == 'judgment_content_unit_unreviewed:cu-perf'


def test_fingerprints_ignore_time_fields(tmp_path, capsys):
    folder = _copy(tmp_path)
    assert _stamp(folder, capsys)[0] == 0
    request = fill_closure_fingerprints(load_request(folder / 'closure-input.json', defaults=CLOSURE_INPUT_FILES))
    for key, field, time in (('route_decision', 'decision_fingerprint', 'decided_at'),
                            ('deterministic_audit', 'audit_fingerprint', 'audited_at'),
                            ('route_review', 'review_fingerprint', 'reviewed_at'),
                            ('judgment', 'judgment_fingerprint', 'judged_at'),
                            ('revision_provenance', 'provenance_fingerprint', 'recorded_at')):
        record = deepcopy(request[key]);expected = record.pop(field)
        record[time] = '2020-01-01T00:00:00Z';fill_fingerprint(record, field)
        assert record[field] == expected
        require_exact_fingerprint(record, field)
    world = yaml.safe_load((EXAMPLES / 'fiction/world.yaml').read_text())
    changed = deepcopy(world);changed['inputs']['events'][0]['at'] = 't99'
    assert fingerprint(world) != fingerprint(changed)  # Domain event time remains content.


@pytest.mark.parametrize('invalid', ['early', 'bad_evidence', 'forged_passed', 'unknown_evidence_field'])
def test_stamp_failure_keeps_the_review_bytes(tmp_path, capsys, invalid):
    folder = _copy(tmp_path)
    path = folder / 'closure-input.json'
    request = json.loads(path.read_text())
    if invalid == 'early':
        piece = folder / 'piece.md';piece.write_bytes(piece.read_bytes() + b'\nSourceGuard\n')
    elif invalid == 'bad_evidence':
        request['judgment']['reverse_outline'][0]['evidence']['excerpt'] = 'SourceGuard'
    elif invalid == 'unknown_evidence_field':
        request['judgment']['reverse_outline'][0]['evidence']['content_fingerprint'] = 'sha256:' + '0' * 64
    else:
        request['judgment']['scores']['coherence'] = 3
        assert request['judgment']['status'] == 'passed'
    path.write_text(json.dumps(request))
    before = path.read_bytes()
    code, output = _stamp(folder, capsys)
    assert code == 1 and 'stamped: closure-input.json judgment ' not in output
    assert path.read_bytes() == before


def test_moving_a_stamped_fixture_requires_explicit_rebinding(tmp_path, capsys):
    folder = _copy(tmp_path)
    assert _stamp(folder, capsys)[0] == 0
    moved = tmp_path / 'moved';shutil.copytree(folder, moved)
    assert (moved / 'piece.md').read_bytes() == (folder / 'piece.md').read_bytes()
    before = (moved / 'closure-input.json').read_bytes()
    result = run_chain(moved)
    assert result['exit_code'] == 1 and result['first_failure']['code'] == 'judgment_stale'
    assert (moved / 'closure-input.json').read_bytes() == before
    assert _stamp(moved, capsys)[0] == 0
    assert run_chain(moved)['exit_code'] == 0


def test_complete_repair_review_can_be_stamped(tmp_path, capsys):
    folder = _copy(tmp_path)
    path = folder / 'closure-input.json';request = json.loads(path.read_text());judgment = request['judgment']
    evidence = deepcopy(judgment['reverse_outline'][0]['evidence'])
    judgment['scores']['coherence'] = 3;judgment['status'] = 'repair'
    judgment['defects'] = [dict(observation_id='judge:defect', dimension='coherence',
        message='The actual opening does not yet license the conclusion.', severity='repair', evidence=evidence)]
    judgment['required_repairs'] = [dict(repair_id='repair:coherence', defect_ids=['judge:defect'],
        target_unit_ids=[evidence['artifact_unit_id']], required_change='Rebuild the opening-to-conclusion dependency.', repair_owner='investigation')]
    path.write_text(json.dumps(request))
    code, output = _stamp(folder, capsys)
    assert code in (0, 1) and 'stamped: closure-input.json judgment ' in output
    saved = json.loads(path.read_text())['judgment']
    assert saved['status'] == 'repair' and saved['required_repairs'] == judgment['required_repairs']
    assert saved['defects'][0]['message'] == judgment['defects'][0]['message']
    result = run_chain(folder)
    assert result['exit_code'] == 1 and result['results']['closure']['closure']['status'] == 'needs_repair'
