"""Input freshness is independent of a saved report's passing status."""
import copy
import hashlib
import json
from pathlib import Path
import shutil

from _common import input_digest_problems, load_request
from derive_closure import derive_closure, provider_checks
from reader_fill import fill_closure_fingerprints
from tests.v2_support import run_example_steps

EXAMPLES=Path(__file__).resolve().parents[2]/'skills/logic-writing/assets/examples'


def test_stale_research_report_fails_the_provider_check(tmp_path):
    source=EXAMPLES/'investigation'
    folder=tmp_path/'research'
    shutil.copytree(source/'research',folder)
    report=source/'research-status.json'
    args=('investigation',{'research_folder':str(folder)},{},[{'provider':'researchguard','path':str(report)}])
    assert provider_checks(*args)[2] is True
    with (folder/'source.yaml').open('a') as stream:
        stream.write('\ngaps:\n- gap_id: gap-libs\n  description: Missing independent support.\n  blocking: true\n')
    rows,risks,passed=provider_checks(*args)
    assert not passed and rows[0]['status']=='failed'
    assert rows[0]['reason'].startswith('research_report_stale:source.yaml')
    assert risks


def test_stale_world_report_fails_closure(tmp_path):
    folder=tmp_path/'fiction'
    shutil.copytree(EXAMPLES/'fiction',folder)
    run_example_steps(folder,until='review')
    request=fill_closure_fingerprints(load_request(folder/'closure-input.json'))
    assert derive_closure(request)['closure']['status']=='passed'
    world=folder/'world.yaml'
    original=world.read_text()
    assert original.count('event_id: e_deliver, at: t6')==1
    world.write_text(original.replace('event_id: e_deliver, at: t6','event_id: e_deliver, at: t8'))
    result=derive_closure(request)['closure']
    assert result['status']=='needs_repair' and not result['broad_claim_allowed']
    row=next(row for row in result['provider_checks'] if row['provider']=='worldguard')
    assert row['status']=='failed' and row['reason'].startswith('world_report_stale:world.yaml')


def test_report_without_input_digests_is_stale(tmp_path):
    assert input_digest_problems({},tmp_path,'research.yaml','research_report_stale')==['research_report_stale:input_digests']
    source=tmp_path/'research.yaml'
    source.write_bytes(b'question: current\n')
    row={'path':source.name,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
    assert input_digest_problems({'input_digests':[row]},tmp_path,source.name,'stale')==[]
    absolute=dict(row,path=str(source))
    assert input_digest_problems({'input_digests':[absolute]},tmp_path,source.name,'stale')
    malformed=dict(row,sha256='invalid')
    assert input_digest_problems({'input_digests':[malformed]},tmp_path,source.name,'stale')==['stale:input_digests']
    source.unlink()
    assert input_digest_problems({'input_digests':[row]},tmp_path,source.name,'stale')==['stale:research.yaml']
