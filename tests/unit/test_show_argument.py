"""The argument picture is computed from the checked plan: only the part under discussion, with what it left out."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

from run_chain import run_chain
from tests.unit.test_evidence_rules import MIGRATE, _add_unit

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / 'skills/logic-writing/assets/examples'
SCRIPT = REPO / 'skills/logic-writing/scripts/show_argument.py'
COMPUTED = re.compile(r'<!-- BEGIN COMPUTED PICTURE: (.+?) -->\n(.*?)\n<!-- END COMPUTED PICTURE -->', re.S)


def _example(tmp_path, route='investigation', until=None):
    folder = tmp_path / route
    shutil.copytree(EXAMPLES / route, folder)
    result = run_chain(folder, until=until) if until else run_chain(folder)
    assert result['exit_code'] == 0, result['first_failure']
    return folder


def _draw(folder, *options):
    run = subprocess.run([sys.executable, str(SCRIPT), str(folder), *options],
                         capture_output=True, text=True, timeout=120)
    return run


def _picture(folder, *options):
    run = _draw(folder, '--json', *options)
    assert run.returncode == 0, run.stdout + run.stderr
    return json.loads(run.stdout)


def _edit_request(folder, change):
    path = folder / 'brief-request.json'
    request = json.loads(path.read_text())
    change(request)
    path.write_text(json.dumps(request))
    assert run_chain(folder, until='brief')['exit_code'] == 0


def _units(request):
    return {row['planned_unit_id']: row for row in request['composition_plan']['planned_units']}


@pytest.mark.parametrize('readme', ['README.md', 'README.zh-CN.md'])
def test_the_readme_discussion_picture_is_the_command_output(tmp_path, readme):
    blocks = COMPUTED.findall((REPO / readme).read_text(encoding='utf-8'))
    assert len(blocks) == 1, 'one computed picture per README'
    command, block = blocks[0]
    assert command == 'show_argument.py ../ft-argument --focus u-recommend'
    folder = _example(tmp_path)
    run = _draw(folder, '--focus', 'u-recommend')
    assert run.returncode == 0, run.stdout + run.stderr
    assert block == run.stdout.rstrip('\n')


def test_a_focus_draws_the_unit_its_neighbours_and_what_it_rests_on(tmp_path):
    folder = _example(tmp_path)
    picture = _picture(folder, '--focus', 'u-recommend')
    assert picture['drawn_units'] == ['u-cost', 'u-next', 'u-recommend']
    assert picture['drawn_anchors'] == ['anc-314-supported', 'anc-314-phase3-undecided']
    assert picture['drawn_limitations'] == ['lim-scope']
    assert picture['problems'] == []
    text = '\n'.join(picture['not_drawn'])
    for name in ('u-answer', 'u-history', 'anc-314-perf', 'anc-313-experimental', 'anc-779-phase3-different',
                 'alt-default-soon (answered in u-next)', 'lim-perf (u-cost)'):
        assert name in text
    mermaid = picture['mermaid']
    assert '-->|"turns status into action"|' in mermaid  # u-next is both the previous unit and a step it builds on
    assert '-.->|"limit"|' in mermaid and '-->|"support"|' in mermaid
    assert picture['boxes'] == 6 and picture['boxes'] <= 12


def test_the_overview_follows_reading_order_and_declared_dependencies(tmp_path):
    folder = _example(tmp_path)
    picture = _picture(folder)
    assert picture['drawn_units'] == ['u-answer', 'u-history', 'u-cost', 'u-next', 'u-recommend']
    assert picture['drawn_alternatives'] == ['alt-default-soon']
    edges = picture['edges']
    assert dict(source='u-cost', target='u-next', kind='order', label='answers the obvious follow-up') in edges
    assert dict(source='u-answer', target='u-next', kind='builds_on', label='') in edges
    assert dict(source='u-answer', target='u-history', kind='builds_on', label='evidence for the answer') in edges
    assert dict(source='alt-default-soon', target='u-next', kind='answers', label='answered in') in edges
    assert any('5 evidence anchors' in row for row in picture['not_drawn'])


@pytest.mark.parametrize('route', ['investigation', 'academic', 'fiction', 'travel'])
def test_the_shipped_plans_draw_without_a_problem(tmp_path, route):
    folder = _example(tmp_path, route)
    picture = _picture(folder)
    assert picture['problems'] == []
    assert picture['boxes'] <= 12
    assert '```mermaid\nflowchart TD\n' in _draw(folder).stdout


def test_a_plan_without_dependencies_says_reachability_was_not_computed(tmp_path):
    folder = _example(tmp_path, 'fiction')
    picture = _picture(folder)
    assert {row['kind'] for row in picture['edges']} == {'order'}
    assert any('declares no downstream_unit_ids' in row for row in picture['not_computed'])
    assert any('fiction-writing' in row for row in picture['not_computed'])


def test_a_conclusion_the_plan_never_reaches_is_marked(tmp_path):
    folder = _example(tmp_path, until='brief')

    def cut(request):
        units = _units(request)
        units['u-cost']['downstream_unit_ids'] = []
        units['u-next']['downstream_unit_ids'] = []
    _edit_request(folder, cut)
    picture = _picture(folder)
    codes = [(row['code'], row['unit']) for row in picture['problems']]
    assert codes == [('leads_nowhere:u-cost', 'u-cost'), ('leads_nowhere:u-next', 'u-next'),
                     ('builds_on_nothing:u-recommend', 'u-recommend'),
                     ('conclusion_not_reached:u-recommend', 'u-recommend')]
    assert re.search(r'class (n\d+,)*n\d+ problem', picture['mermaid'])
    shown = _draw(folder).stdout
    assert '- conclusion_not_reached:u-recommend (no chain of downstream_unit_ids leads from 1. Short answer to 5. What to do)' in shown


def test_a_live_alternative_no_unit_answers_is_marked(tmp_path):
    folder = _example(tmp_path, until='brief')

    def add(request):
        request['content_boundaries']['alternatives'].append(
            dict(alternative_id='alt-wait', safe_meaning='Teams could wait for phase III before testing.',
                 status='live', content_unit_ids=[]))
    _edit_request(folder, add)
    picture = _picture(folder)
    assert [row['code'] for row in picture['problems']] == ['alternative_unanswered:alt-wait']
    assert 'alt-wait' in picture['drawn_alternatives']
    assert not [row for row in picture['edges'] if row['source'] == 'alt-wait']


def test_a_claim_that_outruns_its_anchor_is_marked_on_its_unit(tmp_path):
    """Round-12 F4 S1, drawn: the unit that says 'move production this year' on a 'supported but optional' anchor."""
    folder = tmp_path / 'investigation'
    shutil.copytree(EXAMPLES / 'investigation', folder)
    _add_unit(folder, MIGRATE, ['anc-314-supported'])
    assert run_chain(folder, until='brief')['exit_code'] == 0
    picture = _picture(folder, '--focus', 'u-recommend')
    assert [(row['code'], row['unit']) for row in picture['problems']] == [('claim_outruns_anchor:cu-migrate', 'u-recommend')]
    assert re.search(r'class n\d+ problem', picture['mermaid'])
    assert '-->|"support · cu-migrate"|' in picture['mermaid']


def test_a_claim_with_only_a_stated_gap_is_marked(tmp_path):
    folder = tmp_path / 'investigation'
    shutil.copytree(EXAMPLES / 'investigation', folder)
    _add_unit(folder, MIGRATE, reason='no source covers production readiness')
    assert run_chain(folder, until='brief')['exit_code'] == 0
    problems = _picture(folder)['problems']
    assert [(row['code'], row['unit']) for row in problems] == [('unsupported:cu-migrate', 'u-recommend')]
    assert problems[0]['message'] == 'no anchor supports this claim: no source covers production readiness'


def test_an_audit_finding_is_marked_on_its_unit_and_a_whole_piece_finding_is_listed(tmp_path):
    folder = _example(tmp_path)
    shutil.copyfile(EXAMPLES / 'investigation/known-bad/leak.md', folder / 'piece.md')
    assert run_chain(folder)['exit_code'] == 1
    picture = _picture(folder)
    leaks = [row for row in picture['problems'] if row['code'] == 'audit:workflow_leak']
    assert len(leaks) == 1 and leaks[0]['unit'] in picture['drawn_units'] and leaks[0]['drawn']
    assert 'audit: repair' in picture['summary']
    other = _example(tmp_path / 'cite')
    piece = other / 'piece.md'
    piece.write_text(piece.read_text(encoding='utf-8').replace('[PEP 779]', ''), encoding='utf-8')
    assert run_chain(other)['exit_code'] == 1
    picture = _picture(other)
    assert [(row['code'], row['unit']) for row in picture['problems']] == [('audit:citation_missing', None)]
    assert '- audit:citation_missing (required citation marker is missing: [PEP 779]) [the whole piece]' in _draw(other).stdout


def _large_brief(sections, per_section):
    units, content = [], []
    for s in range(sections):
        units.append(dict(planned_unit_id=f's{s}', parent_unit_id=None, order=s + 1, title=f'Part {s}',
                          unit_kind='section', downstream_unit_ids=[], relation_to_previous='continues',
                          content_unit_ids=[], limitation_ids=[]))
        for p in range(per_section):
            identity = f's{s}p{p}'
            units.append(dict(planned_unit_id=identity, parent_unit_id=f's{s}', order=p + 1, title=f'Step {identity}',
                              unit_kind='paragraph', downstream_unit_ids=[], relation_to_previous='continues',
                              content_unit_ids=['c-' + identity], limitation_ids=[]))
            content.append(dict(content_unit_id='c-' + identity, safe_meaning=f'Claim {identity}.', required=True,
                                evidence_anchor_ids=[], alternative_ids=[], limitation_ids=[]))
    return dict(final_owner='fiction-writing', composition_plan=dict(plan_id='large', central_question='Does a large plan fold?', planned_units=units,
                                                                    content_dispositions=[]),
                content_boundaries=dict(content_units=content, evidence_anchors=[], alternatives=[], limitations=[]))


def test_a_large_plan_is_folded_to_its_parts_and_a_too_large_one_lists_the_views():
    from show_argument import draw
    folded = draw(_large_brief(3, 5))
    assert folded['drawn_units'] == ['s0', 's1', 's2'] and folded['level'] == 'parts'
    assert any('15 units folded into their 3 parts' in row for row in folded['not_drawn'])
    flat = draw(_large_brief(14, 1))
    assert flat['mermaid'] == '' and flat['level'] == 'too_large'
    assert flat['views'][:2] == ['--focus s0 (Part 0, 1 unit)', '--focus s1 (Part 1, 1 unit)']


def test_unreadable_input_is_reported_with_its_reason(tmp_path):
    folder = tmp_path / 'investigation'
    shutil.copytree(EXAMPLES / 'investigation', folder)
    run = _draw(folder)
    assert run.returncode == 2
    assert 'no reader-brief.json' in run.stdout and 'run_chain.py' in run.stdout
    done = _example(tmp_path / 'done')
    run = _draw(done, '--focus', 'u-missing')
    assert run.returncode == 2 and 'unknown planned unit u-missing' in run.stdout
