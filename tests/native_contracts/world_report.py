"""A saved WorldGuard report counts only for its own world while its raw inputs remain current.

Closure copies the saved status: a report of another contract, or one whose inputs changed, fails and needs
repair. A tree report binds by mesh_id and covers the mesh and every file node by raw digest; an old one
names the native regeneration command. Actual scope limits stay visible, attributed and nonblocking. The
independent trip validator reads the raw saved status: a non-pass report permits only initial planning.
Closure never runs a provider.
"""
from dataclasses import dataclass, replace
from pathlib import Path
import json
import shutil
import sys
import tempfile
from .provider_cases import EXAMPLES, PASSING, REPORT_CASES, ROOT, Event, NativeClosure, close_label, close_output, expected_status, plain_json, provider
WORLD_EXPECTED = {'mesh_bound': 'passed', 'contract_scope': 'passed', 'mesh_foreign': 'world_report_mismatch:mesh_id', 'mesh_old': 'world_report_unbound:world_mesh+regenerate', 'mesh_node_stale': 'world_report_stale:ch2_fixed.yaml', 'mesh_embedded_stale': 'world_report_stale:mesh_fixed.yaml', 'mesh_digest_omitted': 'world_report_stale:ch2_fixed.yaml'}

@dataclass(frozen=True)
class State:
    owner: str
    independent: bool = True
    report: str = 'not_run'
    closed: bool = False
    copied: str = ''
    broad: bool = False
    named: bool = False
    travel_claim_level: str = 'initial_plan'
    world_case: str = ''
    world_result: str = ''
    world_scope_preserved: bool = False

def trip_report_status(state):
    return 'PASS' if state.report == 'world_stale' else expected_status(state)

class Step:

    def expected(self, event, state):
        if event.kind == 'world':
            result = WORLD_EXPECTED[event.status]
            return (result, replace(state, world_case=event.status, world_result=result, world_scope_preserved=event.status in {'mesh_bound', 'contract_scope'}))
        if event.kind == 'report':
            return ('saved', replace(state, report=event.status, closed=False, copied='', broad=False, named=False, travel_claim_level='initial_plan'))
        current_status = expected_status(state)
        passing = current_status == PASSING[provider(state)]
        result = replace(state, closed=True, copied=current_status, broad=state.independent and passing, named=not passing, travel_claim_level='bookable' if state.owner == 'travel-guide' and trip_report_status(state) == 'PASS' else 'initial_plan')
        return (close_output(state), result)

class TravelReadsHandwrittenWorldStatus(Step):
    """Known bad: a travel declaration overwrites a failing saved report."""

    def expected(self, event, state):
        results = super().expected(event, state)
        if event.kind == 'close' and state.owner == 'travel-guide':
            return (results[0], replace(results[1], copied='PASS', travel_claim_level='bookable', broad=state.independent))
        return results

def travel_world_failure_limits_claim(state):
    if state.owner == 'travel-guide' and state.closed and (trip_report_status(state) != 'PASS') and (state.travel_claim_level != 'initial_plan'):
        return False
    return True

class ForeignWorldReportPasses(Step):
    """Known bad: a passing report of another world passes closure."""

    def expected(self, event, state):
        results = super().expected(event, state)
        if event.kind == 'close' and provider(state) == 'worldguard' and (state.report == 'world_foreign'):
            return (results[0], replace(results[1], copied='PASS', broad=state.independent, named=False, travel_claim_level='bookable'))
        return results

def world_report_belongs_to_the_contract(state):
    if state.world_case in {'mesh_bound', 'contract_scope', 'mesh_foreign', 'mesh_old'} and state.world_result != WORLD_EXPECTED[state.world_case]:
        return False
    if state.closed and provider(state) == 'worldguard' and (state.report == 'world_foreign') and (state.copied != 'failed' or not state.named):
        return False
    return True

def world_report_is_current(state):
    if state.world_case in {'mesh_node_stale', 'mesh_embedded_stale', 'mesh_digest_omitted'} and state.world_result != WORLD_EXPECTED[state.world_case]:
        return False
    if state.closed and provider(state) == 'worldguard' and (state.report == 'world_stale') and (state.copied != 'failed' or state.broad or (not state.named)):
        return False
    return True

class StaleWorldReportPasses(Step):

    def expected(self, event, state):
        rows = super().expected(event, state)
        if event.kind == 'close' and provider(state) == 'worldguard' and (state.report == 'world_stale'):
            return ('passed', replace(rows[1], copied='PASS', broad=state.independent, named=False))
        return rows

def world_scope_limits_are_preserved(state):
    if state.world_case in {'mesh_bound', 'contract_scope'} and (not state.world_scope_preserved):
        return False
    return True

class DropsWorldScope(Step):

    def expected(self, event, state):
        rows = super().expected(event, state)
        if event.kind == 'world':
            return (rows[0], replace(rows[1], world_scope_preserved=False))
        return rows
EVENTS = tuple((Event('report', status) for status in REPORT_CASES)) + (Event('close'),) + tuple((Event('world', case) for case in WORLD_EXPECTED))

class Native:
    """Replay current closure, tree probes and the trip validator; reuse immutable protocol fixtures."""

    def __init__(self):
        self.closure = NativeClosure()
        self.trip_text = None

    def _world_probe(self, case):
        from derive_closure import provider_checks
        from show_plan import _summary
        with tempfile.TemporaryDirectory(prefix='lw-world-mesh-contract-') as temporary:
            folder = Path(temporary)
            if case == 'contract_scope':
                path = EXAMPLES / 'fiction/worldguard-check.json'
                route = {'world_contract': str(EXAMPLES / 'fiction/world.yaml'), 'world_check_required': True}
                document = json.loads(path.read_text())
            else:
                source = ROOT / 'tests/fixtures/consumers/worldguard_tree'
                for name in ('mesh_fixed.yaml', 'ch1_fixed.yaml', 'ch2_fixed.yaml'):
                    shutil.copyfile(source / name, folder / name)
                path = folder / 'mesh-report.json'
                document = json.loads((source / 'mesh-report.json').read_text())
                route = {'world_mesh': str(folder / 'mesh_fixed.yaml'), 'world_check_required': True}
                if case == 'mesh_foreign':
                    document['mesh_id'] = 'another-tree'
                elif case == 'mesh_old':
                    document.pop('mesh_id')
                elif case == 'mesh_digest_omitted':
                    document['input_digests'] = [row for row in document['input_digests'] if row['path'] != 'ch2_fixed.yaml']
                elif case in {'mesh_node_stale', 'mesh_embedded_stale'}:
                    changed = folder / ('ch2_fixed.yaml' if case == 'mesh_node_stale' else 'mesh_fixed.yaml')
                    raw = changed.read_bytes()
                    changed.write_bytes(raw + b'\n' if case == 'mesh_node_stale' else raw.replace(b'door_unlocked', b'door_locked', 1))
                path.write_text(json.dumps(document))
            rows, risks, passed = provider_checks('fiction-writing', {}, route, [{'provider': 'worldguard', 'path': str(path)}])
            reason = rows[0]['reason']
            result = 'passed' if passed and rows[0]['passed'] and (rows[0]['status'] == 'PASS') else reason.split(' (', 1)[0]
            if case == 'mesh_old' and result == 'world_report_unbound:world_mesh' and ('worldguard mesh-check --mesh' in reason):
                result += '+regenerate'
            scope_rows = [row for row in risks if row['defect_id'].startswith('world:scope_limit:')]
            scopes = document.get('scope_limits', [])
            preserved = passed and len(scope_rows) == len(scopes) and bool(scopes) and all((row['owner'] == 'fiction-writing' and row['reason'] == f'WorldGuard report {path}: {scope}' for row, scope in zip(scope_rows, scopes)))
            summary = _summary({'planned_units': []}, {'audit': {'status': 'passed'}, 'review': {'status': 'passed'}, 'closure': {'status': 'passed', 'residual_risk': risks}})
            return (result, preserved and f'WorldGuard scope limits: {len(scopes)}' in summary)

    def reset(self, state):
        self.state = state
        self.root, self.request = self.closure.request(state.owner, state.independent, [])
        self._trip()

    def _trip(self):
        """A fresh copy of the bookable example trip, citing no saved report yet."""
        if self.trip_text is None:
            travel = ROOT / 'skills/logic-writing/routes/travel'
            if str(travel / 'scripts') not in sys.path:
                sys.path.insert(0, str(travel / 'scripts'))
            from fixture_mutation import apply_mutations
            from travel_contract import review_plan
            self.trip_path = travel / 'examples/good_city_couple_trip/plan.json'
            base = json.loads(self.trip_path.read_text(encoding='utf-8'))
            current = json.loads((travel / 'examples/positive_cases/near_future_bookable.json').read_text(encoding='utf-8'))
            self.trip_text = plain_json(apply_mutations(base, current['mutations']))
            self.review_trip = review_plan
        self.trip = json.loads(self.trip_text)
        self.trip['world_feasibility']['checks'][0]['worldguard_report'] = str(self.root / 'unavailable-world.json')

    def observe(self, event):
        event, state = (event, self.state)
        if event.kind == 'world':
            result, preserved = self._world_probe(event.status)
            self.state = replace(state, world_case=event.status, world_result=result, world_scope_preserved=preserved if event.status in {'mesh_bound', 'contract_scope'} else False)
            return (result, self.state)
        if event.kind == 'report':
            self.root, self.request, path = self.closure.save(state, event.status)
            self._trip()
            if event.status != 'world_foreign':
                self.trip['world_feasibility']['checks'][0]['worldguard_report'] = str(path)
            state = replace(state, report=event.status, closed=False, copied='', broad=False, named=False, travel_claim_level='initial_plan')
            output = 'saved'
        else:
            closure = self.closure.derive(self.request)
            row = closure['provider_checks'][0]
            state = replace(state, closed=True, copied=row['status'], broad=closure['broad_claim_allowed'], named=any((r['defect_id'] == f'provider:{provider(state)}' for r in closure['residual_risk'])), travel_claim_level=self.review_trip(self.trip, plan_path=self.trip_path)['allowed_claim_level'])
            output = closure['status']
        self.state = state
        return (output, state)

    def close(self):
        self.closure.close()
RULES = {'world_scope_limits_are_preserved': world_scope_limits_are_preserved, 'world_report_is_current': world_report_is_current, 'world_report_belongs_to_the_contract': world_report_belongs_to_the_contract, 'travel_world_failure_limits_claim': travel_world_failure_limits_claim}
INITIAL_CASES = tuple((State('travel-guide', independent) for independent in (True, False)))
INPUT_CASES = EVENTS
CALCULATE = Step().expected
BAD_EXPECTATIONS = {'world_scope_limits_disappear': DropsWorldScope().expected, 'stale_world_report_passes': StaleWorldReportPasses().expected, 'travel_reads_handwritten_world_status': TravelReadsHandwrittenWorldStatus().expected, 'foreign_world_report_passes': ForeignWorldReportPasses().expected}
