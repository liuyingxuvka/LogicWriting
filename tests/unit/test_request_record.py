"""The saved request and declared unit sources stay visible through the real chain."""
import json
from pathlib import Path
import shutil

import pytest

from _common import ValidationError, load_request
from build_reader_brief import validate_request
from run_chain import run_chain
from show_plan import plan_view, render_plan

EXAMPLE = Path(__file__).resolve().parents[2] / 'skills/logic-writing/assets/examples/investigation'
REQUEST = ('Is free-threaded Python ready to be the default build? '
           'Tell me its official status as of Python 3.14 and whether we should plan a migration now.')


def _example(tmp_path):
    folder = tmp_path / 'investigation'
    shutil.copytree(EXAMPLE, folder)
    request = json.loads((folder / 'brief-request.json').read_text())
    request['request'] = REQUEST
    for unit in request['content_boundaries']['content_units']:
        unit['source'] = 'research'
        if unit['content_unit_id'] == 'cu-status-314':
            unit.update(source='request', quote='official status as of Python 3.14')
        elif unit['content_unit_id'] == 'cu-recommend':
            unit['source'] = 'ai'
    assert run_chain(folder, until='route')['exit_code'] == 0
    return folder, request


def _save(folder, request):
    (folder / 'brief-request.json').write_text(json.dumps(request))


@pytest.mark.parametrize('quote, required', [
    ('is it the default in 3.14', True),
    ('Official status as of Python 3.14', False),
    ('\tofficial status as of Python 3.14', True),
])
def test_quote_not_in_request_fails(tmp_path, quote, required):
    folder, request = _example(tmp_path)
    unit = request['content_boundaries']['content_units'][0]
    unit.update(quote=quote, required=required)
    _save(folder, request)
    with pytest.raises(ValidationError, match=r'^quote_not_in_request:cu-status-314 \('):
        validate_request(load_request(folder / 'brief-request.json'))


@pytest.mark.parametrize('multiple', [False, True])
def test_ai_unit_is_listed_as_added_by_the_writer(tmp_path, multiple):
    folder, request = _example(tmp_path)
    raw = ' \n' + REQUEST + '\n '
    request['request'] = raw
    units = {unit['content_unit_id']: unit for unit in request['content_boundaries']['content_units']}
    expected = ['cu-recommend']
    if multiple:
        for identity in ('cu-not-default', 'cu-perf'):
            units[identity]['source'] = 'ai'
        units['cu-recommend']['required'] = False
        expected = ['cu-perf', 'cu-not-default', 'cu-recommend']
    _save(folder, request)
    result = run_chain(folder)
    assert result['exit_code'] == 0, result
    assert result['results']['brief']['reader_brief']['request'] == raw
    assert result['results']['closure']['closure']['added_by_writer'] == expected
    view = plan_view(load_request(folder / 'reader-brief.json'), input_path=folder / 'reader-brief.json')
    lines = render_plan(view).splitlines()
    wanted = ['added by the writer: ' + identity + ': ' + units[identity]['safe_meaning'] for identity in expected]
    assert lines[1:1 + len(wanted)] == wanted
    assert all(lines.count(line) == 1 for line in wanted)


def test_brief_without_request_is_refused_with_the_fix(tmp_path):
    folder, request = _example(tmp_path)
    request.pop('request')
    _save(folder, request)
    with pytest.raises(ValidationError, match=r"^brief_request_missing \(store the user's request, as received, in request\)$"):
        validate_request(load_request(folder / 'brief-request.json'))
