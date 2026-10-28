"""Finite shipped examples exercise orchestration without generating writing."""
import json
from pathlib import Path
import shutil
import pytest
from run_chain import run_chain
from tests.e2e.test_worked_examples import run_chain as single_steps

EXAMPLES=Path(__file__).resolve().parents[2]/'skills/logic-writing/assets/examples'

@pytest.mark.parametrize('route',['academic','fiction','investigation','travel'])
def test_run_chain_matches_the_single_steps(tmp_path,route):
    folder=tmp_path/route
    shutil.copytree(EXAMPLES/route,folder)
    original=(folder/'piece.md').read_bytes()
    code,closed=single_steps(folder,route)
    assert code==0
    expected=closed['closure']
    (folder/'map-request.json').unlink()
    (folder/'audit-request.json').unlink()
    result=run_chain(folder)
    actual=result['results']['closure']['closure']
    assert result['exit_code']==0 and result['first_failure'] is None
    assert actual['status']==expected['status']=='passed'
    assert actual['final_owner']==expected['final_owner']
    assert actual['broad_claim_allowed']==expected['broad_claim_allowed'] is False
    assert actual['provider_checks']==expected['provider_checks']
    assert result['summary'].startswith('units:') and 'closure: passed' in result['summary']
    assert (folder/'piece.md').read_bytes()==original
    assert not (folder/'map-request.json').exists() and not (folder/'audit-request.json').exists()


def test_run_chain_stops_at_first_native_failure(tmp_path):
    folder=tmp_path/'bad'
    shutil.copytree(EXAMPLES/'investigation',folder)
    shutil.copyfile(folder/'known-bad/leak.md',folder/'piece.md')
    result=run_chain(folder)
    assert result['exit_code']==1 and result['first_failure']['step']=='audit'
    assert 'review' not in result['results'] and not (folder/'closure.json').exists()
    assert result['results']['audit']['reader_audit']['status']=='repair'


def test_run_chain_unreadable_input_returns_two(tmp_path):
    assert run_chain(tmp_path/'absent')['exit_code']==2
    folder=tmp_path/'invalid';folder.mkdir()
    (folder/'route-request.json').write_text('{')
    assert run_chain(folder)['exit_code']==2


def test_run_chain_provider_refresh_is_explicit(tmp_path,monkeypatch):
    folder=tmp_path/'research'
    shutil.copytree(EXAMPLES/'investigation',folder)
    def unavailable(provider):
        from _common import ValidationError
        raise ValidationError('Install ResearchGuard >= 0.5.16')
    monkeypatch.setattr('run_chain.provider_command',unavailable)
    assert run_chain(folder,until='brief')['exit_code']==0
    result=run_chain(folder,refresh_providers=True)
    assert result['exit_code']==2 and 'Install ResearchGuard' in result['first_failure']['message']


def test_stale_report_line_names_the_code_once(tmp_path, monkeypatch, capsys):
    import sys
    import run_chain as chain

    folder = tmp_path / "fiction"
    shutil.copytree(EXAMPLES / "fiction", folder)
    world = folder / "world.yaml"
    world.write_text(world.read_text() + "\n# probe\n")
    monkeypatch.setattr(sys, "argv", ["run_chain.py", str(folder)])
    assert chain.main() == 1
    lines = capsys.readouterr().out.splitlines()
    assert (
        lines[1]
        == "first failure: closure: world_report_stale:world.yaml (saved report is from other inputs; run with --refresh-providers)"
    )
    assert lines[1].count("world_report_stale") == 1
    assert ": PASS" not in lines[1]
