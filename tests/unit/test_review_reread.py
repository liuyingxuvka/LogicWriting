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
from review_snapshot import changed_spans, reread_problems

EXAMPLES = Path(__file__).resolve().parents[2] / 'skills/logic-writing/assets/examples'
COST_UNIT = 'artifact:paragraph:0006'


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
    _requote(folder, COST_UNIT, 'the slowdown for multi-threaded code')
    result = _stamp_review(folder)
    assert result['exit_code'] == 0, result['first_failure']
    saved = json.loads((folder / 'closure-input.json').read_text())
    assert saved['reviewed_text']['text'] == (folder / 'piece.md').read_text(encoding='utf-8')
    assert saved['reviewed_text']['artifact_fingerprint'] == saved['judgment']['artifact_fingerprint']
    assert run_chain(folder)['exit_code'] == 0


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
    assert _stamp_review(folder)['exit_code'] == 0  # unchanged text: the stamp starts the record
    assert 'reviewed_text' in json.loads(path.read_text())
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
    _requote(folder, COST_UNIT, 'roughly 5-10% [What')
    assert _stamp_review(folder)['exit_code'] == 0


def test_reread_problems_need_no_reread_for_unchanged_text(tmp_path):
    folder = _copy(tmp_path)
    assert run_chain(folder, until='review')['exit_code'] == 0
    from _common import load_request
    request = load_request(folder / 'closure-input.json', defaults=CLOSURE_INPUT_FILES)
    assert reread_problems(request['reviewed_text'], request['judgment'], request['artifact_map'], stamped=True) == []
