"""One route per function: an error reaches the caller or is reported with its text, never a quiet default or a skip."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / 'skills/logic-writing/assets/examples'


def _copy(tmp_path, route='investigation'):
    folder = tmp_path / route
    shutil.copytree(EXAMPLES / route, folder)
    return folder


def test_a_readback_error_is_named_and_the_chain_state_kept(tmp_path, monkeypatch):
    import run_chain as chain
    folder = _copy(tmp_path)

    def broken(*args, **kwargs):
        raise KeyError('injected readback failure')

    monkeypatch.setattr(chain, 'plan_view', broken)
    result = chain.run_chain(folder)
    assert result['exit_code'] == 0
    assert 'injected readback failure' in result['summary']
    assert result['summary'].endswith('chain: passed')  # not 'not_run' for a chain that ran and passed


def test_an_injected_programming_error_fails_the_run(tmp_path, monkeypatch):
    import run_chain as chain
    folder = _copy(tmp_path)

    def broken(*args, **kwargs):
        raise RuntimeError('injected failure')

    monkeypatch.setattr(chain, 'plan_view', broken)
    with pytest.raises(RuntimeError, match='injected failure'):
        chain.run_chain(folder)
    monkeypatch.undo()
    monkeypatch.setattr(chain, 'derive_closure', broken)
    with pytest.raises(RuntimeError, match='injected failure'):
        chain.run_chain(folder)


def test_an_unreadable_research_report_names_its_read_error(tmp_path):
    from derive_closure import provider_checks
    path = tmp_path / 'research-status.json'
    path.write_text('{"verdict": ', encoding='utf-8')
    rows, risks, passed = provider_checks('investigation', {'research_folder': str(tmp_path)}, {},
                                          [{'provider': 'researchguard', 'path': str(path)}])
    assert not passed and rows[0]['status'] == 'unreadable'
    assert rows[0]['reason'].startswith(f'researchguard report {path} cannot be read: ')
    missing = tmp_path / 'absent.json'
    rows, _, _ = provider_checks('investigation', {'research_folder': str(tmp_path)}, {},
                                 [{'provider': 'researchguard', 'path': str(missing)}])
    assert rows[0]['status'] == 'unreadable' and 'No such file' in rows[0]['reason']


def test_an_unreadable_result_file_reads_back_as_unreadable(tmp_path):
    from run_chain import run_chain
    folder = _copy(tmp_path)
    assert run_chain(folder)['exit_code'] == 0
    (folder / 'audit.json').write_text('{"reader_audit": ', encoding='utf-8')
    run = subprocess.run([sys.executable, str(REPO / 'skills/logic-writing/scripts/show_plan.py'),
                          '--input', str(folder / 'shared-writing-result.json')],
                         capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stdout + run.stderr
    first = run.stdout.splitlines()[0]
    assert 'audit: unreadable' in first and 'audit: not_run' not in first


def test_a_skipped_test_fails_the_run(tmp_path):
    probe = tmp_path / 'test_probe.py'
    probe.write_text('import pytest\n\ndef test_hidden():\n    pytest.skip("a handler swallowed the error")\n',
                     encoding='utf-8')
    run = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '-p', 'tests.no_skips',
                          str(probe)], cwd=REPO, capture_output=True, text=True, timeout=120)
    assert run.returncode == 1, run.stdout + run.stderr
    assert '1 failed' in run.stdout and 'this suite allows no skips' in run.stdout


@pytest.mark.parametrize('body', [
    'import pytest\npytest.importorskip("a_module_that_is_not_installed")\n\ndef test_hidden():\n    pass\n',
    'import pytest\npytest.skip("the whole module is off", allow_module_level=True)\n\ndef test_hidden():\n    pass\n',
])
def test_a_module_skipped_at_collection_fails_the_run(tmp_path, body):
    """Review gap: a module-level skip is a collection report, not a test report; it must fail too."""
    probe = tmp_path / 'test_probe.py'
    probe.write_text(body, encoding='utf-8')
    run = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '-p', 'tests.no_skips',
                          str(probe)], cwd=REPO, capture_output=True, text=True, timeout=120)
    assert run.returncode != 0, run.stdout + run.stderr
    assert 'this suite allows no skips' in run.stdout + run.stderr


def test_a_fresh_example_reads_back_with_the_route_decided_from_its_request(tmp_path):
    """show_plan's view input takes one route per input state; before the route step it decides the route."""
    from show_plan import _read_view_input
    folder = _copy(tmp_path)
    assert not (folder / 'route-decision.json').exists()
    request = _read_view_input(folder / 'brief-request.json')
    assert request['route_decision']['final_owner'] == 'investigation'
    (folder / 'route-request.json').unlink()
    with pytest.raises(FileNotFoundError):  # the chosen route's read error reaches the caller
        _read_view_input(folder / 'brief-request.json')


def test_a_blocked_binding_reads_back_with_its_block_and_other_errors_reach_the_caller(tmp_path):
    from run_chain import run_chain
    from show_plan import _read_view_input
    folder = _copy(tmp_path)
    path = folder / 'shared-writing.json'
    shared = json.loads(path.read_text())
    shared['contract']['unit_bindings'][0]['anchor_excerpts'] = ['A QUOTE THAT IS NOT IN THE TEXT']
    path.write_text(json.dumps(shared))
    assert run_chain(folder)['first_failure']['step'] == 'binding'
    for name in ('route-review.json', 'shared-writing-result.json'):
        assert _read_view_input(folder / name)['_binding_blocked']['status'] == 'blocked'
    (folder / 'route-review.json').write_text('{"review": "missing-file.json"}')
    with pytest.raises(FileNotFoundError):
        _read_view_input(folder / 'route-review.json')
