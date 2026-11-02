"""A saved WorldGuard report counts only for its own world while its inputs are current; travel reads its status."""
import hashlib
from pathlib import Path
import shutil

from _common import load_request
from reader_fill import fill_closure_fingerprints
from tests.v2_support import closure_input, complete_chain
from tests.v2_support import derive_protocol_closure as derive_closure

EXAMPLES=Path(__file__).resolve().parents[2]/'skills/logic-writing/assets/examples'


def test_stale_world_report_fails_closure(tmp_path):
    folder=tmp_path/'fiction'
    shutil.copytree(EXAMPLES/'fiction',folder)
    from run_chain import run_chain
    assert run_chain(folder, until='review')['exit_code'] == 0  # writes the chain's result files; no stamp
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
