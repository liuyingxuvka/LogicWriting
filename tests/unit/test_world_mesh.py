"""Read the shared native tree report; unit checks never invoke WorldGuard."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from _common import ValidationError, load_request, worldguard_report_identity_problems
from derive_closure import provider_checks
from reader_plan import build_reader_brief, validate_route_composition
from route_inputs import route_extension_fingerprint
from run_chain import _refresh, run_chain
from show_plan import _summary
from tests.v2_support import make_reader_chain
from world_refs import validate_world_refs

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'tests/fixtures/consumers/worldguard_tree'
EXAMPLES = ROOT / 'skills/logic-writing/assets/examples'


def _tree_provider_row(report, mesh):
    return provider_checks('fiction-writing', {}, {'world_mesh': str(mesh), 'world_check_required': True},
                           [{'provider': 'worldguard', 'path': str(report)}])[0][0]


def test_tree_report_binds_like_a_contract():
    report = json.loads((FIXTURE / 'mesh-report.json').read_text())
    # WorldGuard tests/test_consumer_contract.py asserts the same summary (WG1).
    assert set(report) == {'checked', 'gaps', 'input_digests', 'mesh_id', 'output', 'scope_limits', 'status', 'tree'}
    assert report['mesh_id'] == 'lighthouse'
    assert report['input_digests'] == [dict(path=name, sha256=hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest())
                                      for name in ('ch1_fixed.yaml', 'ch2_fixed.yaml', 'mesh_fixed.yaml')]
    assert worldguard_report_identity_problems(FIXTURE / 'mesh-report.json', world_mesh=FIXTURE / 'mesh_fixed.yaml') == []
    assert _tree_provider_row(FIXTURE / 'mesh-report.json', FIXTURE / 'mesh_fixed.yaml')['passed']


@pytest.mark.parametrize('name', ['ch1_fixed.yaml', 'ch2_fixed.yaml'])
def test_changed_node_file_makes_the_tree_report_stale(tmp_path, name):
    folder = tmp_path / 'tree'
    shutil.copytree(FIXTURE, folder)
    path = folder / name
    path.write_bytes(path.read_bytes() + b'\n')
    assert worldguard_report_identity_problems(folder / 'mesh-report.json', world_mesh=folder / 'mesh_fixed.yaml') == ['world_report_stale:' + name]
    row = _tree_provider_row(folder / 'mesh-report.json', folder / 'mesh_fixed.yaml')
    assert not row['passed'] and row['reason'] == 'world_report_stale:' + name


def test_embedded_node_bytes_make_the_tree_report_stale(tmp_path):
    folder = tmp_path / 'tree'
    shutil.copytree(FIXTURE, folder)
    path = folder / 'mesh_fixed.yaml'
    path.write_bytes(path.read_bytes().replace(b'door_unlocked', b'door_locked', 1))
    assert worldguard_report_identity_problems(folder / 'mesh-report.json', world_mesh=path) == ['world_report_stale:mesh_fixed.yaml']
    row = _tree_provider_row(folder / 'mesh-report.json', path)
    assert not row['passed'] and row['reason'] == 'world_report_stale:mesh_fixed.yaml'


@pytest.mark.parametrize('name', ['ch1_fixed.yaml', 'ch2_fixed.yaml', 'mesh_fixed.yaml'])
def test_missing_node_digest_is_stale(tmp_path, name):
    report = json.loads((FIXTURE / 'mesh-report.json').read_text())
    report['input_digests'] = [row for row in report['input_digests'] if row['path'] != name]
    path = tmp_path / 'report.json'
    path.write_text(json.dumps(report))
    assert worldguard_report_identity_problems(path, world_mesh=FIXTURE / 'mesh_fixed.yaml') == ['world_report_stale:' + name]
    row = _tree_provider_row(path, FIXTURE / 'mesh_fixed.yaml')
    assert not row['passed'] and row['reason'] == 'world_report_stale:' + name


def test_old_tree_report_is_refused_with_the_regenerate_command(tmp_path):
    report = json.loads((FIXTURE / 'mesh-report.json').read_text())
    report.pop('mesh_id')
    path = tmp_path / 'report.json'
    path.write_text(json.dumps(report))
    problem, = worldguard_report_identity_problems(path, world_mesh=FIXTURE / 'mesh_fixed.yaml')
    assert problem.startswith('world_report_unbound:world_mesh (')
    assert 'worldguard mesh-check --mesh' in problem and '--refresh-providers' in problem
    row = _tree_provider_row(path, FIXTURE / 'mesh_fixed.yaml')
    assert not row['passed'] and row['reason'] == problem


def test_foreign_tree_id_is_refused(tmp_path):
    report = json.loads((FIXTURE / 'mesh-report.json').read_text())
    report['mesh_id'] = 'another-tree'
    path = tmp_path / 'report.json'
    path.write_text(json.dumps(report))
    assert worldguard_report_identity_problems(path, world_mesh=FIXTURE / 'mesh_fixed.yaml') == ['world_report_mismatch:mesh_id']


def test_fiction_closure_binds_a_world_mesh():
    rows, _, passed = provider_checks('fiction-writing', {},
        {'world_mesh': str(FIXTURE / 'mesh_fixed.yaml'), 'world_check_required': True},
        [{'provider': 'worldguard', 'path': str(FIXTURE / 'mesh-report.json')}])
    assert passed and rows[0]['passed'] and rows[0]['status'] == 'PASS'


def test_world_refs_resolve_in_mesh_nodes():
    composition = {'world_mesh': 'worldguard_tree/mesh_fixed.yaml'}
    plan = {'planned_units': [{'planned_unit_id': 'scene', 'world_refs': ['e_unlock', 'door_opened_after_handover']}]}
    assert validate_world_refs(plan, composition, FIXTURE.parent) == {'scene': ('e_unlock', 'door_opened_after_handover')}
    plan['planned_units'][0]['world_refs'] = ['never_declared']
    with pytest.raises(ValidationError, match='unknown_world_ref:scene:never_declared'):
        validate_world_refs(plan, composition, FIXTURE.parent)


@pytest.mark.parametrize('owner', ['fiction-writing', 'travel-guide'])
def test_world_contract_and_mesh_are_exclusive(tmp_path, owner):
    chain = make_reader_chain(tmp_path, owner)
    route = deepcopy(chain['route_composition'])
    route.pop('world_contract', None)
    route['world_mesh'] = str(FIXTURE / 'mesh_fixed.yaml')
    route['extension_fingerprint'] = route_extension_fingerprint(route)
    args = dict(owner=owner, reader_intent_fingerprint=route['reader_intent_fingerprint'],
                composition_plan_fingerprint=route['composition_plan_fingerprint'], composition_plan=chain['plan'])
    assert validate_route_composition(route, **args)['world_mesh'] == route['world_mesh']
    route['world_contract'] = str(FIXTURE / 'ch2_fixed.yaml')
    route['extension_fingerprint'] = route_extension_fingerprint(route)
    with pytest.raises(ValidationError):
        validate_route_composition(route, **args)
    with pytest.raises(ValidationError):
        validate_world_refs({'planned_units': [{'planned_unit_id': 'scene', 'world_refs': ['e_unlock']}]}, route)


@pytest.mark.parametrize('nested', [False, True])
def test_world_mesh_loads_relative_to_the_composition_file(tmp_path, nested):
    folder = tmp_path / 'composition'
    folder.mkdir()
    route = {'world_mesh': 'mesh_fixed.yaml'}
    if nested:
        (folder / 'route.json').write_text(json.dumps(route))
        request = {'route_composition': 'composition/route.json'}
    else:
        request = {'route_composition': route}
    path = (tmp_path if nested else folder) / 'request.json'
    path.write_text(json.dumps(request))
    assert load_request(path)['route_composition']['world_mesh'] == str(folder / 'mesh_fixed.yaml')


@pytest.mark.parametrize('kind', ['contract', 'mesh'])
def test_world_scope_limits_remain_nonblocking_and_visible(tmp_path, kind):
    folder = FIXTURE if kind == 'mesh' else EXAMPLES / 'fiction'
    path = folder / ('mesh-report.json' if kind == 'mesh' else 'worldguard-check.json')
    route = {'world_' + kind: str(folder / ('mesh_fixed.yaml' if kind == 'mesh' else 'world.yaml')), 'world_check_required': True}
    rows, risks, passed = provider_checks('fiction-writing', {}, route, [{'provider': 'worldguard', 'path': str(path)}])
    limits = json.loads(path.read_text())['scope_limits']
    assert passed and rows[0]['status'] == 'PASS' and rows[0]['passed']
    scope = [row for row in risks if row['defect_id'].startswith('world:scope_limit:')]
    assert [row['reason'] for row in scope] == [f'WorldGuard report {path}: {limit}' for limit in limits]
    assert all(row['owner'] == 'fiction-writing' for row in scope)
    summary = _summary({'planned_units': []}, {'audit': {'status': 'passed'}, 'review': {'status': 'passed'},
                       'closure': {'status': 'passed', 'residual_risk': risks}})
    assert f'WorldGuard scope limits: {len(limits)}' in summary
    assert all(limit not in summary for limit in limits)
    if kind == 'contract':
        work = tmp_path / 'fiction'
        shutil.copytree(folder, work)
        result = run_chain(work)
        assert result['exit_code'] == 0 and result['results']['closure']['closure']['status'] == 'passed'
        assert any(row['defect_id'].startswith('world:scope_limit:') for row in result['results']['closure']['closure']['residual_risk'])
        assert f'WorldGuard scope limits: {len(limits)}' in result['summary']


def test_travel_brief_binds_its_saved_tree_report(tmp_path):
    chain = make_reader_chain(tmp_path / 'base', 'travel-guide')
    route = deepcopy(chain['route_composition'])
    trip = json.loads(Path(route['trip_plan']).read_text())
    trip['world_feasibility']['checks'][0]['worldguard_report'] = str(FIXTURE / 'mesh-report.json')
    trip_path = tmp_path / 'trip.json'
    trip_path.write_text(json.dumps(trip))
    route['trip_plan'] = str(trip_path)
    route.pop('world_contract')
    route['world_mesh'] = str(FIXTURE / 'mesh_fixed.yaml')
    route['extension_fingerprint'] = route_extension_fingerprint(route)
    args = dict(brief_id='brief:mesh-trip', route_decision=chain['route_decision'],
        content_boundaries=chain['reader_brief']['content_boundaries'], composition_plan=chain['plan'],
        route_composition=route, request=chain['reader_brief']['request'])
    assert build_reader_brief(**args)['route_extension']['extension_fingerprint'] == route['extension_fingerprint']
    report = json.loads((FIXTURE / 'mesh-report.json').read_text())
    report['mesh_id'] = 'another-tree'
    report_path = tmp_path / 'foreign-report.json'
    report_path.write_text(json.dumps(report))
    trip['world_feasibility']['checks'][0]['worldguard_report'] = str(report_path)
    trip_path.write_text(json.dumps(trip))
    with pytest.raises(ValidationError, match='world_report_mismatch:mesh_id'):
        build_reader_brief(**args)


@pytest.mark.parametrize('missing', [None, 'mesh_id', 'input_digests'])
def test_refresh_uses_the_native_mesh_command_and_requires_its_identity(tmp_path, monkeypatch, missing):
    document = json.loads((FIXTURE / 'mesh-report.json').read_text())
    if missing:
        document.pop(missing)
    calls = []
    def saved_response(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, json.dumps(document), '')
    monkeypatch.setattr('run_chain.provider_command', lambda provider: ['native-worldguard'])
    monkeypatch.setattr('run_chain.subprocess.run', saved_response)
    _request = {'route_composition': {'world_mesh': str(FIXTURE / 'mesh_fixed.yaml')}}
    if missing:
        with pytest.raises(ValidationError, match='Install WorldGuard >= 0.8.0 beside Logic Writing to refresh tree reports'):
            _refresh(_request, tmp_path)
        assert not (tmp_path / 'worldguard-check.json').exists()
    else:
        _refresh(_request, tmp_path)
        assert json.loads((tmp_path / 'worldguard-check.json').read_text()) == document
    assert calls == [['native-worldguard', 'mesh-check', '--mesh', str(FIXTURE / 'mesh_fixed.yaml')]]
