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
    request=fill_closure_fingerprints(load_request(folder/'closure-input.json', defaults=__import__('derive_closure').CLOSURE_INPUT_FILES))
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


import copy
import hashlib
from pathlib import Path
import pytest
from _common import ValidationError, fingerprint
from tests.v2_support import derive_protocol_closure as derive_closure
from tests.v2_support import closure_input, complete_chain

def _research_document(*, withhold=False):
    from pathlib import Path
    import json
    document = json.loads((Path(__file__).resolve().parents[2] / "skills/logic-writing/assets/examples/investigation/research-status.json").read_text())
    if withhold:
        document["verdict"]["root_claim"] = {"id": "h-main-answer", "wording_license": "withhold", "reason": "Native counterevidence remains."}
        document["verdict"]["live_hypotheses"].append("h-other")
        document["hypotheses"].append({"id": "h-other"})
    return document



@pytest.mark.parametrize('provider,document,status', [
    ('researchguard', _research_document(), 'passed'),
    ('worldguard', {'status': 'FAIL', 'contract_id': 'old-market-day'}, 'FAIL'),
    ('researchguard', _research_document(withhold=True), 'failed'),
    ('researchguard', {}, 'unreadable'),
])
def test_provider_status_is_copied_from_the_report_file(tmp_path, provider, document, status):
    import json
    request = closure_input(complete_chain(tmp_path, 'travel-guide' if provider == 'worldguard' else 'investigation'))
    if provider=='worldguard':
        document=copy.deepcopy(document)
        world=Path(request['route_composition']['world_contract'])
        document['input_digests']=[{'path':world.name,'sha256':hashlib.sha256(world.read_bytes()).hexdigest()}]
    path = tmp_path / 'report.json'
    path.write_text(json.dumps(document))
    request['provider_reports'] = [row for row in request['provider_reports'] if row['provider'] != provider]
    request['provider_reports'].append(dict(provider=provider, path=str(path)))
    result = derive_closure(request)['closure']
    row = result['provider_checks'][-1]
    assert row['status'] == status
    assert result['broad_claim_allowed'] == (status == 'passed')
    assert f'{provider} {status}' in result['safe_claim']
    if status != 'passed':
        risk = next(r for r in result['residual_risk'] if r['defect_id'] == f'provider:{provider}')
        assert risk['reason']
        if document.get('verdict', {}).get('root_claim'):
            assert document['verdict']['root_claim']['reason'] in risk['reason']
    elif provider == 'researchguard':
        assert any(r['defect_id'] == 'research:root_claim_not_run' for r in result['residual_risk'])



def test_failing_world_report_limits_the_travel_closure(tmp_path):
    import json
    import sys
    from pathlib import Path
    route = Path(__file__).resolve().parents[2] / 'skills/logic-writing/routes/travel'
    if str(route / 'scripts') not in sys.path:
        sys.path.insert(0, str(route / 'scripts'))
    from fixture_mutation import apply_mutations
    from travel_contract import review_plan
    failed = tmp_path / 'world-fail.json'
    failed.write_text(json.dumps({'status': 'FAIL', 'contract_id': 'old-market-day'}))
    request = closure_input(complete_chain(tmp_path / 'chain', 'travel-guide'))
    world=Path(request['route_composition']['world_contract'])
    failed.write_text(json.dumps({'status':'FAIL','contract_id':'old-market-day','input_digests':[{'path':world.name,'sha256':hashlib.sha256(world.read_bytes()).hexdigest()}]}))
    request['provider_reports'] = [dict(provider='worldguard', path=str(failed))]
    closure = derive_closure(request)['closure']
    assert closure['provider_checks'][0]['status'] == 'FAIL'
    assert closure['broad_claim_allowed'] is False
    assert any(row['defect_id'] == 'provider:worldguard' for row in closure['residual_risk'])
    plan_path = route / 'examples/good_city_couple_trip/plan.json'
    current = json.loads((route / 'examples/positive_cases/near_future_bookable.json').read_text(encoding='utf-8'))
    plan = apply_mutations(json.loads(plan_path.read_text(encoding='utf-8')), current['mutations'])
    plan['world_feasibility']['checks'][0]['worldguard_report'] = str(failed)
    assert review_plan(plan, plan_path=plan_path)['allowed_claim_level'] == 'initial_plan'



def test_missing_required_provider_report_blocks_the_broad_claim(tmp_path):
    request = closure_input(complete_chain(tmp_path))
    request.pop('provider_reports')
    result = derive_closure(request)['closure']
    assert result['status'] == 'passed'
    assert not result['broad_claim_allowed']
    assert result['provider_checks'] == [dict(provider='researchguard', path=None, status='not_run', passed=False, required=True, reason='researchguard report is missing: not_run')]
    assert result['residual_risk'][0]['defect_id'] == 'provider:researchguard'



@pytest.mark.parametrize('contents', [None, 'not json', '[]'])
def test_unreadable_report_is_not_a_pass(tmp_path, contents):
    from derive_closure import provider_checks
    path = tmp_path / 'missing.json'
    if contents is not None:
        path.write_text(contents)
    rows, risks, passed = provider_checks('investigation', {}, {}, [{'provider': 'researchguard', 'path': str(path)}])
    assert not passed and rows[0]['status'] == 'unreadable' and risks



def test_world_report_for_another_contract_fails_closure(tmp_path):
    import json
    from derive_closure import provider_checks
    request = closure_input(complete_chain(tmp_path / 'chain', 'travel-guide'))
    report = tmp_path / 'worldguard-check.json'
    report.write_text(json.dumps({'status': 'PASS', 'contract_id': 'another-world'}))
    request['provider_reports'] = [dict(provider='worldguard', path=str(report))]
    closure = derive_closure(request)['closure']
    assert closure['status'] == 'needs_repair'
    row = closure['provider_checks'][0]
    assert row['status'] == 'failed' and row['reason'].startswith('world_report_mismatch:contract_id')
    risk = next(r for r in closure['residual_risk'] if r['defect_id'] == 'provider:worldguard')
    assert risk['reason'].startswith('world_report_mismatch:contract_id')
    # Without contract_id the contract is named by claim.claim_id, as in WorldGuard.
    world = tmp_path / 'world.yaml'
    world.write_text('claim: {claim_id: c_only}\ninputs: {events: []}\n')
    report.write_text(json.dumps({'status': 'PASS', 'contract_id': 'c_only', 'input_digests':[{'path':world.name,'sha256':hashlib.sha256(world.read_bytes()).hexdigest()}]}))
    rows, _risks, passed = provider_checks('travel-guide', {}, {'world_contract': str(world)},
                                           [dict(provider='worldguard', path=str(report))])
    assert passed and rows[0]['status'] == 'PASS'
    rows, _risks, passed = provider_checks('travel-guide', {}, {}, [dict(provider='worldguard', path=str(report))])
    assert not passed and rows[0]['reason'].startswith('world_report_unbound:world_contract')

