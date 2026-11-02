"""A new stamp on edited text needs the review to quote the changed passages again; the tool finds them."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

import pytest

from derive_closure import CLOSURE_INPUT_FILES
from run_chain import _stamp_review, main, run_chain
from review_snapshot import changed_spans, review_record, snapshot_problems

EXAMPLES = Path(__file__).resolve().parents[2] / 'skills/logic-writing/assets/examples'
COST_UNIT = 'artifact:paragraph:0006'
# The whole sentence of the cost paragraph that holds the edited word, as it reads after _edit_one_word.
EDITED_SENTENCE = ("The 3.14 release notes put the slowdown for multi-threaded code at roughly 5-10%, "
                   "depending on the platform and C compiler [What's New 3.14]")


def _copy(tmp_path, route='investigation'):
    folder = tmp_path / route
    shutil.copytree(EXAMPLES / route, folder)
    return folder


def _edit_one_word(folder):
    piece = folder / 'piece.md'
    text = piece.read_text(encoding='utf-8')
    assert 'single-threaded' in text
    piece.write_text(text.replace('single-threaded', 'multi-threaded', 1), encoding='utf-8')


def _requote(folder, unit_id, excerpt):
    path = folder / 'closure-input.json'
    saved = json.loads(path.read_text())
    row = next(row for row in saved['judgment']['reverse_outline'] if row['artifact_unit_id'] == unit_id)
    row['evidence']['excerpt'] = excerpt
    path.write_text(json.dumps(saved))


@pytest.mark.parametrize('route', ['investigation', 'academic', 'fiction', 'travel'])
def test_shipped_examples_keep_the_text_their_review_read(route):
    saved = json.loads((EXAMPLES / route / 'closure-input.json').read_text())
    piece = (EXAMPLES / route / 'piece.md').read_bytes()
    record = saved['reviewed_text']
    assert record['text'].encode('utf-8') == piece
    assert record['artifact_fingerprint'] == 'sha256:' + hashlib.sha256(piece).hexdigest() == saved['judgment']['artifact_fingerprint']
    assert record['basis'] == 'first_review' and record['changed_units'] == []
    assert snapshot_problems(record, saved['judgment']) == []


def test_restamping_an_edit_without_rereading_it_is_refused(tmp_path, capsys):
    """The round-12 F4 row: edit one reviewed word, then run the printed --stamp-review unchanged."""
    folder = _copy(tmp_path)
    _edit_one_word(folder)
    stale = run_chain(folder)
    assert stale['exit_code'] == 1 and stale['first_failure']['code'] == 'judgment_stale'
    before = (folder / 'closure-input.json').read_bytes()
    with patch.object(sys, 'argv', ['run_chain.py', str(folder), '--stamp-review']):
        code = main()
    output = capsys.readouterr().out
    assert code == 1
    assert f'first failure: review: review_not_reread:{COST_UNIT} (' in output
    assert 'where it read "single"' in output and 'stamped: ' not in output
    assert (folder / 'closure-input.json').read_bytes() == before
    assert run_chain(folder)['first_failure']['code'] == 'judgment_stale'


def test_quoting_the_new_wording_lets_the_review_be_stamped_again(tmp_path):
    folder = _copy(tmp_path)
    _edit_one_word(folder)
    _requote(folder, COST_UNIT, 'roughly 5-10%')  # an unchanged part of the unit is not a reread
    assert _stamp_review(folder)['first_failure']['code'] == 'review_not_reread'
    _requote(folder, COST_UNIT, EDITED_SENTENCE)
    result = _stamp_review(folder)
    assert result['exit_code'] == 0, result['first_failure']
    assert result['review_basis'] == {'basis': 'compared', 'changed_units': [COST_UNIT]}
    saved = json.loads((folder / 'closure-input.json').read_text())
    assert saved['reviewed_text']['text'] == (folder / 'piece.md').read_text(encoding='utf-8')
    assert saved['reviewed_text']['artifact_fingerprint'] == saved['judgment']['artifact_fingerprint']
    closed = run_chain(folder)
    assert closed['exit_code'] == 0
    assert closed['results']['closure']['closure']['review_basis'] == {'basis': 'compared', 'changed_units': [COST_UNIT]}


def test_removing_the_stamp_does_not_skip_the_reread(tmp_path):
    folder = _copy(tmp_path)
    _edit_one_word(folder)
    path = folder / 'closure-input.json'
    saved = json.loads(path.read_text())
    saved['judgment'] = {key: value for key, value in saved['judgment'].items() if not key.endswith('_fingerprint')}
    path.write_text(json.dumps(saved))
    result = _stamp_review(folder)
    assert result['exit_code'] == 1 and result['first_failure']['code'] == 'review_not_reread'


def test_a_stamp_without_a_saved_text_cannot_certify_changed_text(tmp_path):
    folder = _copy(tmp_path)
    path = folder / 'closure-input.json'
    saved = json.loads(path.read_text())
    saved.pop('reviewed_text')
    path.write_text(json.dumps(saved))
    # On unchanged text the sealed stamp names exactly these bytes, so the copy is saved again; it is not a first review.
    assert _stamp_review(folder, first_review=True)['first_failure']['code'] == 'review_not_first'
    assert _stamp_review(folder)['exit_code'] == 0
    assert json.loads(path.read_text())['reviewed_text']['basis'] == 'restored'
    saved = json.loads(path.read_text());saved.pop('reviewed_text');path.write_text(json.dumps(saved))
    _edit_one_word(folder)
    result = _stamp_review(folder)
    assert result['exit_code'] == 1 and result['first_failure']['code'] == 'review_text_unknown'


def test_closure_refuses_a_saved_text_that_is_not_what_was_stamped(tmp_path):
    folder = _copy(tmp_path)
    path = folder / 'closure-input.json'
    saved = json.loads(path.read_text())
    saved['reviewed_text']['text'] += 'An extra sentence nobody reviewed.\n'
    path.write_text(json.dumps(saved))
    result = run_chain(folder)
    assert result['exit_code'] == 1 and result['first_failure']['message'].startswith('reviewed_text_invalid')


def test_changed_spans_name_word_changes_and_deletions():
    old = 'One two three.\n\nFour five six.'
    assert changed_spans(old, old.replace('two', 'TWO')) == [(4, 7, 'two')]
    deleted = old.replace(' five', '')
    [(start, end, before)] = changed_spans(old, deleted)
    assert start == end and before.strip() == 'five' and deleted[start - 1:start + 1] in (' s', 'r ')
    assert changed_spans(old, old.replace('two three', 'two  three')) == []  # whitespace only: nothing to reread


def test_a_deletion_needs_a_quote_reaching_the_place(tmp_path):
    folder = _copy(tmp_path)
    piece = folder / 'piece.md'
    text = piece.read_text(encoding='utf-8')
    removed = ', depending on the platform and C compiler'
    assert removed in text
    piece.write_text(text.replace(removed, '', 1), encoding='utf-8')
    assert _stamp_review(folder)['first_failure']['code'] == 'review_not_reread'
    _requote(folder, COST_UNIT, 'roughly 5-10% [What')  # the place, but not the sentence it now reads as
    assert _stamp_review(folder)['first_failure']['code'] == 'review_not_reread'
    _requote(folder, COST_UNIT, "The 3.14 release notes put the slowdown for single-threaded code at roughly 5-10% [What's New 3.14]")
    assert _stamp_review(folder)['exit_code'] == 0


def test_unchanged_text_keeps_the_record_of_how_it_was_reviewed(tmp_path):
    folder = _copy(tmp_path)
    assert run_chain(folder, until='review')['exit_code'] == 0
    from _common import load_request
    request = load_request(folder / 'closure-input.json', defaults=CLOSURE_INPUT_FILES)
    record = review_record(request['reviewed_text'], request['judgment'], request['artifact_map'], first_review=False)
    assert record == request['reviewed_text']


# Round-1 review gaps: headings and the title, edits across units, a removed or rewritten saved copy.

def _edit(folder, old, new):
    piece = folder / 'piece.md'
    text = piece.read_text(encoding='utf-8')
    assert old in text
    piece.write_text(text.replace(old, new, 1), encoding='utf-8')


def _unit_id(folder, text):
    result = run_chain(folder, until='map')
    return next(row['artifact_unit_id'] for row in result['results']['map']['artifact_map']['units']
                if row['unit_kind'] != 'document' and row['text'] == text)


def _outline_heading(folder, unit_id, excerpt):
    """The reviewer rereads a heading and gives it its own reverse-outline row quoting the new wording."""
    path = folder / 'closure-input.json'
    saved = json.loads(path.read_text())
    saved['judgment']['reverse_outline'].append(dict(
        artifact_unit_id=unit_id, parent_unit_id=None, observed_job='heading', main_point='names the section',
        support_or_action='frames what follows', content_unit_ids=[], carries_from_unit_ids=[],
        relation_to_previous='opens a section', downstream_effect='sets what the section promises',
        orphaned=False, overloaded=False,
        evidence=dict(artifact_unit_id=unit_id, locator='char:0-0', excerpt=excerpt, excerpt_fingerprint='sha256:' + '0' * 64)))
    path.write_text(json.dumps(saved))


@pytest.mark.parametrize('old,new', [
    ('## What it costs', '## Why it costs nothing'),
    ('# Free-threaded Python: supported, not the default', '# Free-threaded Python: production-ready for every service'),
])
def test_a_changed_heading_or_title_must_be_quoted_again(tmp_path, old, new):
    folder = _copy(tmp_path)
    _edit(folder, old, new)
    result = _stamp_review(folder)
    assert result['exit_code'] == 1
    assert result['first_failure']['code'] == 'review_not_reread'
    unit_id = _unit_id(folder, new)
    assert result['first_failure']['message'].startswith(f'review_not_reread:{unit_id} (')
    assert run_chain(folder)['first_failure']['code'] == 'judgment_stale'
    _outline_heading(folder, unit_id, new.lstrip('# '))
    result = _stamp_review(folder)
    assert result['exit_code'] == 0, result['first_failure']
    assert run_chain(folder)['exit_code'] == 0


def test_an_edit_that_crosses_two_units_needs_both_quoted_again():
    from artifact_map import build_artifact_map_from_text
    from review_snapshot import review_record, snapshot
    old = '# T\n\nAlpha beta gamma.\n\nDelta epsilon.\n'
    new = '# T\n\nAlpha beta omega.\n\n\nZeta epsilon.\n'
    before = build_artifact_map_from_text(old, artifact_path='piece.md', map_id='map:x', language='en', artifact_format='markdown')
    after = build_artifact_map_from_text(new, artifact_path='piece.md', map_id='map:x', language='en', artifact_format='markdown')
    saved = snapshot(before, basis='first_review', changed_units=[])

    def judgment(*quotes):
        rows = [dict(evidence=dict(artifact_unit_id=unit, excerpt=excerpt)) for unit, excerpt in quotes]
        return dict(judgment_id='j', artifact_fingerprint=before['artifact_fingerprint'], reverse_outline=rows,
                    defects=[], strengths=[])

    with pytest.raises(ValueError) as refused:
        review_record(saved, judgment(('artifact:paragraph:0002', 'Alpha beta omega')), after, first_review=False)
    assert 'review_not_reread:artifact:paragraph:0003 (' in str(refused.value)
    record = review_record(saved, judgment(('artifact:paragraph:0002', 'Alpha beta omega'),
                                           ('artifact:paragraph:0003', 'Zeta epsilon')), after, first_review=False)
    assert record['basis'] == 'compared' and record['changed_units'] == ['artifact:paragraph:0002', 'artifact:paragraph:0003']


def _strip(folder, record=True, stamp=True):
    path = folder / 'closure-input.json'
    saved = json.loads(path.read_text())
    if record:
        saved.pop('reviewed_text')
    if stamp:
        saved['judgment'] = {key: value for key, value in saved['judgment'].items() if not key.endswith('_fingerprint')}
    path.write_text(json.dumps(saved))


def test_removing_the_saved_copy_and_the_stamp_needs_a_declared_first_review(tmp_path, capsys):
    """Review gap (a): drop reviewed_text and every judgment fingerprint, then stamp without rereading."""
    folder = _copy(tmp_path)
    _edit_one_word(folder)
    _strip(folder)
    before = (folder / 'closure-input.json').read_bytes()
    result = _stamp_review(folder)
    assert result['exit_code'] == 1 and result['first_failure']['code'] == 'review_first_undeclared'
    assert '--first-review' in result['first_failure']['message']
    assert (folder / 'closure-input.json').read_bytes() == before
    with patch.object(sys, 'argv', ['run_chain.py', str(folder), '--stamp-review', '--first-review']):
        assert main() == 0
    assert 'stamped: closure-input.json judgment j-ft-1 as a first review' in capsys.readouterr().out
    closed = run_chain(folder)
    assert closed['exit_code'] == 0
    closure = closed['results']['closure']['closure']
    assert closure['review_basis'] == {'basis': 'first_review', 'changed_units': []}
    assert 'stamped as a first review' in closure['safe_claim']


def test_a_review_stamped_without_a_saved_copy_is_not_told_to_remove_its_stamp(tmp_path):
    folder = _copy(tmp_path)
    _edit_one_word(folder)
    _strip(folder, stamp=False)
    result = _stamp_review(folder)
    assert result['exit_code'] == 1 and result['first_failure']['code'] == 'review_text_unknown'
    message = result['first_failure']['message']
    # Neither removing the stamp nor declaring a first review is offered: only bringing back what the stamp read.
    assert '_fingerprint' not in message and 'remove' not in message and '--first-review' not in message
    assert 'reviewed_text' in message and 'put back the text' in message


def test_a_saved_copy_rewritten_to_the_new_text_is_refused(tmp_path):
    """Review gap (b): set reviewed_text to the edited text with its sha256 and the judgment's fingerprint to match."""
    folder = _copy(tmp_path)
    _edit_one_word(folder)
    path = folder / 'closure-input.json'
    saved = json.loads(path.read_text())
    text = (folder / 'piece.md').read_text(encoding='utf-8')
    forged = 'sha256:' + hashlib.sha256(text.encode('utf-8')).hexdigest()
    saved['reviewed_text'].update(text=text, artifact_fingerprint=forged)
    saved['judgment']['artifact_fingerprint'] = forged
    path.write_text(json.dumps(saved))
    result = _stamp_review(folder)
    assert result['exit_code'] == 1 and result['first_failure']['code'] == 'reviewed_text_invalid'


def test_a_first_review_is_refused_while_a_saved_copy_exists(tmp_path):
    folder = _copy(tmp_path)
    _edit_one_word(folder)
    result = _stamp_review(folder, first_review=True)
    assert result['exit_code'] == 1 and result['first_failure']['code'] == 'review_copy_exists'


def test_closure_needs_the_saved_copy_of_a_stamped_review(tmp_path):
    folder = _copy(tmp_path)
    _strip(folder, stamp=False)
    result = run_chain(folder)
    assert result['exit_code'] == 1 and result['first_failure']['code'] == 'reviewed_text_missing'
    # Closure reaches this check only when the stamp is current for this text, so the plain stamp restores the copy.
    message = result['first_failure']['message']
    assert '--stamp-review' in message and '--first-review' not in message
    assert _stamp_review(folder)['review_basis'] == {'basis': 'restored', 'changed_units': []}
    assert run_chain(folder)['exit_code'] == 0


# Round-2 review gaps: a stamped review re-declared as a first review, a one-word quote taken as a reread,
# and a closure line that does not say how the review was stamped.

def test_a_review_stamped_before_cannot_be_declared_a_first_review(tmp_path, capsys):
    """Gap (1): drop reviewed_text (one field) and stamp edited text with --stamp-review --first-review (one flag)."""
    folder = _copy(tmp_path)
    _edit_one_word(folder)
    _strip(folder, stamp=False)
    before = (folder / 'closure-input.json').read_bytes()
    with patch.object(sys, 'argv', ['run_chain.py', str(folder), '--stamp-review', '--first-review']):
        code = main()
    output = capsys.readouterr().out
    assert code == 1 and 'first failure: review: review_not_first:j-ft-1 (' in output and 'stamped: ' not in output
    assert '--first-review' not in output.split('review_not_first:', 1)[1]
    assert (folder / 'closure-input.json').read_bytes() == before
    assert run_chain(folder)['first_failure']['code'] == 'judgment_stale'


def test_a_lost_copy_is_saved_again_only_on_the_text_its_sealed_stamp_names(tmp_path, capsys):
    """The way back for a lost copy: put back the stamped text, stamp it, then edit and reread as usual."""
    folder = _copy(tmp_path)
    piece = folder / 'piece.md'
    stamped_text = piece.read_text(encoding='utf-8')
    _edit_one_word(folder)
    _strip(folder, stamp=False)
    assert _stamp_review(folder)['first_failure']['code'] == 'review_text_unknown'
    piece.write_text(stamped_text, encoding='utf-8')
    with patch.object(sys, 'argv', ['run_chain.py', str(folder), '--stamp-review']):
        assert main() == 0
    assert 'on the text its earlier stamp named' in capsys.readouterr().out
    saved = json.loads((folder / 'closure-input.json').read_text())
    assert saved['reviewed_text']['basis'] == 'restored' and saved['reviewed_text']['text'] == stamped_text
    closed = run_chain(folder)
    assert closed['exit_code'] == 0
    assert closed['results']['closure']['closure']['review_basis'] == {'basis': 'restored', 'changed_units': []}
    assert 'closure: passed (review re-stamped on the text its earlier stamp named)' in closed['summary']
    _edit_one_word(folder)
    assert _stamp_review(folder)['first_failure']['code'] == 'review_not_reread'
    _requote(folder, COST_UNIT, EDITED_SENTENCE)
    assert _stamp_review(folder)['review_basis'] == {'basis': 'compared', 'changed_units': [COST_UNIT]}


def test_a_lost_copy_is_not_saved_again_from_an_edited_stamp(tmp_path):
    """Pointing the stamp at the edited text by hand breaks the review's own seal, so the copy is not rebuilt from it."""
    folder = _copy(tmp_path)
    _edit_one_word(folder)
    _strip(folder, stamp=False)
    path = folder / 'closure-input.json'
    saved = json.loads(path.read_text())
    text = (folder / 'piece.md').read_bytes()
    saved['judgment']['artifact_fingerprint'] = 'sha256:' + hashlib.sha256(text).hexdigest()
    path.write_text(json.dumps(saved))
    before = path.read_bytes()
    for first_review, code in ((False, 'review_text_unknown'), (True, 'review_not_first')):
        result = _stamp_review(folder, first_review=first_review)
        assert result['exit_code'] == 1 and result['first_failure']['code'] == code
        assert 'changed after that stamp' in result['first_failure']['message']
    assert path.read_bytes() == before


@pytest.mark.parametrize('excerpt', ['multi', 'the slowdown for multi-threaded code'])
def test_a_quote_of_the_changed_word_alone_is_not_a_reread(tmp_path, excerpt):
    """Gap (3): a one-token excerpt such as 'multi' was accepted; the whole sentence that changed must be quoted."""
    folder = _copy(tmp_path)
    _edit_one_word(folder)
    _requote(folder, COST_UNIT, excerpt)
    result = _stamp_review(folder)
    assert result['exit_code'] == 1 and result['first_failure']['code'] == 'review_not_reread'
    text = (folder / 'piece.md').read_text(encoding='utf-8')
    start = text.index(EDITED_SENTENCE)
    words_end = start + len(EDITED_SENTENCE.rstrip(']'))  # from its first word to its last; the closing bracket is not a word
    assert f'quote the whole sentence that holds the change (char:{start}-{words_end})' in result['first_failure']['message']
    _requote(folder, COST_UNIT, EDITED_SENTENCE + '.')
    assert _stamp_review(folder)['exit_code'] == 0


def test_the_closure_line_says_how_the_review_was_stamped(tmp_path, capsys):
    """Gap (4): run_chain's closure line names the review basis, not only closure.json's safe_claim."""
    folder = _copy(tmp_path)
    with patch.object(sys, 'argv', ['run_chain.py', str(folder)]):
        assert main() == 0
    assert 'closure: passed (review stamped as a first review); known-bad: 0 uncaught' in capsys.readouterr().out
    _edit_one_word(folder)
    _requote(folder, COST_UNIT, EDITED_SENTENCE)
    assert _stamp_review(folder)['exit_code'] == 0
    with patch.object(sys, 'argv', ['run_chain.py', str(folder)]):
        assert main() == 0
    assert f'closure: passed (review re-stamped after quoting each changed unit again: {COST_UNIT})' in capsys.readouterr().out
