"""Finite researched-unit evidence and declared-response boundaries."""
import copy
import json
from pathlib import Path
import shutil

import pytest

from _common import ValidationError, load_request
from build_reader_brief import validate_request as build_brief
from derive_closure import derive_closure
from run_chain import run_chain
from tests.v2_support import closure_input, complete_chain

EXAMPLES = Path(__file__).resolve().parents[2] / 'skills/logic-writing/assets/examples'
MIGRATE = 'Teams should move production services to the free-threaded build this year.'
RESTATE = 'Free-threading will become the default build in the next Python release, so plan the migration for it.'


def _example(tmp_path, route='investigation'):
    folder = tmp_path / route
    shutil.copytree(EXAMPLES / route, folder)
    assert run_chain(folder, until='route')['exit_code'] == 0
    return folder


def _save(folder, request):
    (folder / 'brief-request.json').write_text(json.dumps(request))


def _add_unit(folder, meaning=MIGRATE, anchors=(), *, required=True, reason=None,
              alternatives=(), identity='cu-migrate'):
    request = json.loads((folder / 'brief-request.json').read_text())
    unit = dict(content_unit_id=identity, safe_meaning=meaning, required=required,
                evidence_anchor_ids=list(anchors), alternative_ids=list(alternatives),
                limitation_ids=[], model_row_ids=[])
    if reason is not None:
        unit['unsupported_reason'] = reason
    request['content_boundaries']['content_units'].append(unit)
    next(row for row in request['composition_plan']['planned_units']
         if row['planned_unit_id'] == 'u-recommend')['content_unit_ids'].append(identity)
    _save(folder, request)
    path = folder / 'shared-writing.json'
    shared = json.loads(path.read_text())
    next(row for row in shared['contract']['unit_bindings']
         if row['planned_unit_id'] == 'u-recommend')['content_unit_ids'].append(identity)
    path.write_text(json.dumps(shared))
    piece = folder / 'piece.md'
    piece.write_text(piece.read_text().rstrip('\n') + ' ' + meaning + '\n')
    return request, unit


def _build(folder):
    return build_brief(load_request(folder / 'brief-request.json'))['reader_brief']


def test_unit_without_anchor_is_unsupported(tmp_path):
    folder = _example(tmp_path)
    _add_unit(folder)
    with pytest.raises(ValidationError, match=r'^content_unit_unsupported:cu-migrate \('):
        _build(folder)

    request = copy.deepcopy(closure_input(complete_chain(tmp_path / 'closure')))
    request['reader_brief']['content_boundaries']['content_units'][0]['evidence_anchor_ids'] = []
    with pytest.raises(ValidationError, match=r'^content_unit_unsupported:content:answer \('):
        derive_closure(request)


def test_unit_restating_an_unsupported_alternative_fails(tmp_path):
    folder = _example(tmp_path)
    request, unit = _add_unit(folder, RESTATE, ['anc-314-supported'], identity='cu-default-next')
    message = r'^content_unit_restates_unsupported:cu-default-next:alt-default-soon \('
    with pytest.raises(ValidationError, match=message):
        _build(folder)
    unit['unsupported_reason'] = 'An explicit gap does not make this an answer to the alternative.'
    _save(folder, request)
    with pytest.raises(ValidationError, match=message):
        _build(folder)

    closed = copy.deepcopy(closure_input(complete_chain(tmp_path / 'closure')))
    boundaries = closed['reader_brief']['content_boundaries']
    unit = boundaries['content_units'][0]
    unit.update(safe_meaning=RESTATE, alternative_ids=[])
    boundaries['alternatives'].append(dict(
        alternative_id='alt-default-soon', safe_meaning='Free-threading will become the default in the next release.',
        status='unsupported', content_unit_ids=[unit['content_unit_id']]))
    with pytest.raises(ValidationError, match=r'^content_unit_restates_unsupported:content:answer:alt-default-soon \('):
        derive_closure(closed)


def test_unsupported_reason_is_a_residual_risk(tmp_path):
    folder = _example(tmp_path)
    reason = 'The evidence does not support this recommendation; keep the gap visible.'
    _add_unit(folder, reason=reason)
    result = run_chain(folder)
    assert result['exit_code'] == 0, result
    assert {'defect_id': 'unsupported:cu-migrate', 'owner': 'investigation', 'reason': reason} in result['results']['closure']['closure']['residual_risk']


@pytest.mark.parametrize('route', ['investigation', 'academic', 'fiction', 'travel'])
def test_shipped_examples_meet_the_evidence_rules(tmp_path, route):
    assert _build(_example(tmp_path, route))['final_owner']


@pytest.mark.parametrize('case', ['counter_only', 'optional', 'nonresearch', 'research_folder',
                                  'academic_missing', 'blank_reason'])
def test_evidence_scope_boundaries(tmp_path, case):
    route = 'fiction' if case in ('nonresearch', 'research_folder') else 'academic' if case == 'academic_missing' else 'investigation'
    folder = _example(tmp_path, route)
    request = json.loads((folder / 'brief-request.json').read_text())
    if case == 'research_folder':
        request.update(research_folder=str(EXAMPLES / 'investigation/research'),
                       research_status=str(EXAMPLES / 'investigation/research-status.json'))
    elif case == 'academic_missing':
        request['content_boundaries']['content_units'][0]['evidence_anchor_ids'] = []
    elif case in ('counter_only', 'optional', 'blank_reason'):
        request, unit = _add_unit(folder, required=case != 'optional', reason='  ' if case == 'blank_reason' else None)
        if case == 'counter_only':
            request['content_boundaries']['evidence_anchors'].append(
                dict(request['content_boundaries']['evidence_anchors'][0], anchor_id='anc-counter', relation='counter',
                     outside_research='Synthetic counter-only probe, not a result of the research folder.'))
            unit['evidence_anchor_ids'] = ['anc-counter']
    _save(folder, request)
    if case in ('optional', 'nonresearch'):
        assert _build(folder)['final_owner']
    else:
        with pytest.raises(ValidationError, match=r'^content_unit_unsupported:'):
            _build(folder)


@pytest.mark.parametrize('meaning', [
    'It is not established that free-threading will become the default in the next release.',
    'The claim "Free-threading will become the default in the next release." is unsupported.',
    'We reject the claim that free-threading will become the default in the next release.',
])
def test_answered_unsupported_alternative_is_allowed(tmp_path, meaning):
    folder = _example(tmp_path)
    _add_unit(folder, meaning, ['anc-314-supported'], alternatives=['alt-default-soon'], identity='cu-default-next')
    assert _build(folder)['final_owner'] == 'investigation'


@pytest.mark.parametrize('alternative, meaning, rejected', [
    ('研究 42', '42 is a separate tally.', False),
    ('研究 42', '研究 42 is claimed.', True),
    ('the and or it', 'A supported bounded statement.', False),
])
def test_unicode_words_and_empty_filtered_alternative(tmp_path, alternative, meaning, rejected):
    folder = _example(tmp_path)
    request, _ = _add_unit(folder, meaning, ['anc-314-supported'], identity='cu-default-next')
    request['content_boundaries']['alternatives'][0]['safe_meaning'] = alternative
    _save(folder, request)
    if rejected:
        with pytest.raises(ValidationError, match=r'^content_unit_restates_unsupported:cu-default-next:alt-default-soon \('):
            _build(folder)
    else:
        assert _build(folder)['final_owner'] == 'investigation'


def _invented_anchor(folder, reason=None):
    request = json.loads((folder / 'brief-request.json').read_text())
    anchor = dict(anchor_id='anc-invented', source_id='src-blog', locator='a blog post, 2025',
                  relation='support', observed_summary='Free-threading is production ready.',
                  boundary="One author's opinion.")
    if reason is not None:
        anchor['outside_research'] = reason
    request['content_boundaries']['evidence_anchors'].append(anchor)
    next(row for row in request['content_boundaries']['content_units']
         if row['content_unit_id'] == 'cu-recommend')['evidence_anchor_ids'].append('anc-invented')
    _save(folder, request)


@pytest.mark.parametrize('reason', [None, '  '])
def test_anchor_outside_the_research_report_fails(tmp_path, reason):
    folder = _example(tmp_path)
    _invented_anchor(folder, reason)
    with pytest.raises(ValidationError, match=r'^anchor_not_in_research:anc-invented \('):
        _build(folder)


def test_outside_research_reason_is_a_residual_risk(tmp_path):
    folder = _example(tmp_path)
    reason = 'This anchor is an outside opinion; it is not a result of the research folder.'
    _invented_anchor(folder, reason)
    result = run_chain(folder)
    assert result['exit_code'] == 0, result
    assert {'defect_id': 'outside_research:anc-invented', 'owner': 'investigation',
            'reason': reason} in result['results']['closure']['closure']['residual_risk']
