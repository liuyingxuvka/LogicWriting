"""A required claim is compared with what its own anchors say; a claim sharing no word with them is warned."""
import json
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

import pytest

from run_chain import _stamp_review, main, run_chain
from reader_plan import claim_anchor_gaps
from tests.unit.test_evidence_rules import MIGRATE, _add_unit

EXAMPLES = Path(__file__).resolve().parents[2] / 'skills/logic-writing/assets/examples'
PARAPHRASE = ("Python's next release is expected to ship the free-threaded interpreter as its standard build, "
              "so plan the migration for it.")


def _example(tmp_path, route='investigation'):
    folder = tmp_path / route
    shutil.copytree(EXAMPLES / route, folder)
    return folder


def _warnings(folder):
    result = run_chain(folder, until='brief')
    assert result['exit_code'] == 0, result['first_failure']
    return result['results']['brief']['warnings']


def test_a_supported_but_optional_anchor_does_not_quietly_carry_move_production_this_year(tmp_path, capsys):
    """Round-12 F4: S1 with anc-314-supported attached as support for migrating production this year."""
    folder = _example(tmp_path)
    _add_unit(folder, MIGRATE, ['anc-314-supported'])
    warnings = _warnings(folder)
    assert len(warnings) == 1 and warnings[0].startswith('claim_outruns_anchor:cu-migrate (')
    assert 'anc-314-supported' in warnings[0]
    with patch.object(sys, 'argv', ['run_chain.py', str(folder), '--until', 'brief']):
        assert main() == 0
    assert 'warning: claim_outruns_anchor:cu-migrate (' in capsys.readouterr().out


def test_a_paraphrased_unsupported_alternative_is_warned(tmp_path):
    """Round-12 F4: S2 reworded without 'default' passes the literal restatement rule; its anchor does not say it."""
    folder = _example(tmp_path)
    _add_unit(folder, PARAPHRASE, ['anc-314-supported'], identity='cu-default-next')
    warnings = _warnings(folder)
    assert [row.split(' ', 1)[0] for row in warnings] == ['claim_outruns_anchor:cu-default-next']


@pytest.mark.parametrize('route', ['investigation', 'academic', 'fiction', 'travel'])
def test_the_shipped_plans_raise_no_claim_warning(tmp_path, route):
    folder = _example(tmp_path, route)
    assert _warnings(folder) == []
    result = run_chain(folder)
    assert result['exit_code'] == 0
    assert not any(row['defect_id'].startswith('claim_outruns_anchor:')
                   for row in result['results']['closure']['closure']['residual_risk'])


def test_the_warning_stays_in_closure_as_a_residual_risk(tmp_path):
    folder = _example(tmp_path)
    _add_unit(folder, MIGRATE, ['anc-314-supported'])
    path = folder / 'closure-input.json'
    saved = json.loads(path.read_text())
    row = next(row for row in saved['judgment']['reverse_outline'] if 'cu-recommend' in row['content_unit_ids'])
    row['content_unit_ids'].append('cu-migrate')
    row['evidence']['excerpt'] = MIGRATE
    path.write_text(json.dumps(saved))
    assert _stamp_review(folder)['exit_code'] == 0
    result = run_chain(folder)
    assert result['exit_code'] == 0, result['first_failure']
    risks = [row for row in result['results']['closure']['closure']['residual_risk']
             if row['defect_id'] == 'claim_outruns_anchor:cu-migrate']
    assert len(risks) == 1 and risks[0]['owner'] == 'investigation'


def _brief(owner='investigation', meaning=MIGRATE, relation='support', summary='Supported, no longer experimental.',
           boundary='Official status only.', research=None):
    brief = {'final_owner': owner, 'content_boundaries': {
        'evidence_anchors': [{'anchor_id': 'a1', 'relation': relation, 'observed_summary': summary, 'boundary': boundary}],
        'content_units': [{'content_unit_id': 'u1', 'required': True, 'safe_meaning': meaning, 'evidence_anchor_ids': ['a1']}]}}
    if research is not None:  # a folder with its saved report, which holds the anchor's own record
        report = research / 'research-status.json'
        report.write_text(json.dumps({'evidence': [{'anchor': 'a1', 'summary': summary, 'boundary': boundary}]}))
        brief.update(research_folder=str(research), research_status=str(report))
    return brief


def test_claim_anchor_gaps_are_computed_from_the_anchor_text(tmp_path):
    assert [row['defect_id'] for row in claim_anchor_gaps(_brief())] == ['claim_outruns_anchor:u1']
    # One shared content word (here a stem: services/service) is enough; this is a lexical signal, not entailment.
    assert claim_anchor_gaps(_brief(summary='Each service was supported.')) == []
    assert claim_anchor_gaps(_brief(boundary='Applies to production services only.')) == []
    assert claim_anchor_gaps(_brief(relation='counter')) == []  # a counter anchor is the unsupported rule's job
    assert claim_anchor_gaps(_brief(owner='fiction-writing')) == []
    assert [row['defect_id'] for row in claim_anchor_gaps(_brief(owner='travel-guide', research=tmp_path))] == ['claim_outruns_anchor:u1']
    # Text without spaces is compared by adjacent character pairs, not as one long word.
    assert claim_anchor_gaps(_brief(meaning='合成材料支持结构性论证。', summary='材料支持论证。', boundary='')) == []
    assert len(claim_anchor_gaps(_brief(meaning='成品写成连续正文。', summary='合成测试材料。', boundary=''))) == 1


# Round-1 review gaps: an extra anchor lent its words to another, and the check read the brief's own copy.

def test_each_cited_anchor_is_compared_on_its_own(tmp_path):
    """A second support anchor sharing 'thread' no longer clears the claim for anc-314-supported."""
    folder = _example(tmp_path)
    _add_unit(folder, MIGRATE, ['anc-314-supported', 'anc-314-perf'])
    warnings = _warnings(folder)
    assert [row.split(' ', 1)[0] for row in warnings] == ['claim_outruns_anchor:cu-migrate']
    assert 'anc-314-supported' in warnings[0] and 'anc-314-perf' not in warnings[0]


def test_the_claim_is_compared_with_the_research_report_not_the_brief_copy(tmp_path):
    """Words added to the brief's copy of an anchor summary do not count; the edited copy is itself reported."""
    folder = _example(tmp_path)
    _add_unit(folder, MIGRATE, ['anc-314-supported'])
    path = folder / 'brief-request.json'
    request = json.loads(path.read_text())
    anchor = next(row for row in request['content_boundaries']['evidence_anchors'] if row['anchor_id'] == 'anc-314-supported')
    anchor['observed_summary'] += ' Production services can move this year.'
    path.write_text(json.dumps(request))
    warnings = _warnings(folder)
    assert sorted(row.split(' ', 1)[0] for row in warnings) == ['anchor_summary_not_report:anc-314-supported',
                                                                 'claim_outruns_anchor:cu-migrate']
    claim = next(row for row in warnings if row.startswith('claim_outruns_anchor:'))
    assert 'the saved research report' in claim


def test_claim_anchor_gaps_compare_each_anchor():
    brief = _brief()
    brief['content_boundaries']['evidence_anchors'].append(
        {'anchor_id': 'a2', 'relation': 'support', 'observed_summary': 'Production services moved this year.', 'boundary': ''})
    brief['content_boundaries']['content_units'][0]['evidence_anchor_ids'].append('a2')
    [gap] = claim_anchor_gaps(brief)
    assert gap['defect_id'] == 'claim_outruns_anchor:u1' and 'a1' in gap['reason'] and 'a2' not in gap['reason']


def test_the_argument_picture_marks_an_edited_anchor_copy(tmp_path):
    from show_argument import picture_for
    folder = _example(tmp_path)
    path = folder / 'brief-request.json'
    request = json.loads(path.read_text())
    anchor = next(row for row in request['content_boundaries']['evidence_anchors'] if row['anchor_id'] == 'anc-314-perf')
    anchor['observed_summary'] = 'No single-thread penalty at all.'
    path.write_text(json.dumps(request))
    assert run_chain(folder, until='brief')['exit_code'] == 0
    picture = picture_for(folder)
    [problem] = [row for row in picture['problems'] if row['code'] == 'anchor_summary_not_report:anc-314-perf']
    assert problem['unit'] == 'u-cost'
