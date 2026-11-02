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

from flowguard import (FunctionResult, Invariant, InvariantResult, ReplayObservation,
                       Workflow, replay_trace, select_covering_traces)
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFacts

from _provider_closure_fixture import (EXAMPLES, PASSING, REPORT_CASES, ROOT, Event, NativeClosure, close_label,
                                       close_output, expected_status, plain_json, provider)

MODEL_ID = 'world_report_model'
PARENT = 'reader-closure'
COMPONENTS = ['reader-closure', 'shared-contracts', 'travel-model']
IMPLEMENTED_BY = {
    "WorldIdentity": "skills/logic-writing/scripts/_common.py:worldguard_report_identity_problems",
}
TESTED_BY = {
    "travel_world_failure_limits_claim": [
        "tests/unit/test_world_report_model.py:test_failing_world_report_limits_the_travel_closure"
    ],
    "world_report_belongs_to_the_contract": [
        "tests/unit/test_world_report_model.py:test_world_report_for_another_contract_fails_closure",
        "tests/unit/test_world_mesh.py:test_tree_report_binds_like_a_contract",
        "tests/unit/test_world_mesh.py:test_old_tree_report_is_refused_with_the_regenerate_command",
    ],
    "world_report_is_current": [
        "tests/unit/test_world_report_model.py:test_stale_world_report_fails_closure",
        "tests/unit/test_world_mesh.py:test_changed_node_file_makes_the_tree_report_stale",
        "tests/unit/test_world_mesh.py:test_embedded_node_bytes_make_the_tree_report_stale",
        "tests/unit/test_world_mesh.py:test_missing_node_digest_is_stale",
    ],
    "world_scope_limits_are_preserved": [
        "tests/unit/test_world_mesh.py:test_world_scope_limits_remain_nonblocking_and_visible"],
}
WORLD_EXPECTED = {'mesh_bound': 'passed', 'contract_scope': 'passed',
                  'mesh_foreign': 'world_report_mismatch:mesh_id',
                  'mesh_old': 'world_report_unbound:world_mesh+regenerate',
                  'mesh_node_stale': 'world_report_stale:ch2_fixed.yaml',
                  'mesh_embedded_stale': 'world_report_stale:mesh_fixed.yaml',
                  'mesh_digest_omitted': 'world_report_stale:ch2_fixed.yaml'}


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
    # The trip validator reads the saved provider status; closure separately rejects stale inputs.
    return 'PASS' if state.report=='world_stale' else expected_status(state)


class Step:
    name = 'Step'
    reads = ('owner', 'independent', 'report')
    writes = ('report', 'closed', 'copied', 'broad', 'named', 'travel_claim_level', 'world_case', 'world_result', 'world_scope_preserved')

    def apply(self, event, state):
        if event.kind == 'world':
            result = WORLD_EXPECTED[event.status]
            return (FunctionResult(result, replace(state, world_case=event.status, world_result=result,
                                                   world_scope_preserved=event.status in {'mesh_bound', 'contract_scope'}),
                                   label='world_' + event.status),)
        if event.kind == 'report':
            return (FunctionResult('saved', replace(state, report=event.status, closed=False,
                                                   copied='', broad=False, named=False, travel_claim_level='initial_plan'), label='saved'),)
        current_status = expected_status(state)
        passing = current_status == PASSING[provider(state)]
        result = replace(state, closed=True, copied=current_status,
                         broad=state.independent and passing,
                         named=not passing,
                         travel_claim_level='bookable' if state.owner == 'travel-guide' and trip_report_status(state)=='PASS' else 'initial_plan')
        return (FunctionResult(close_output(state), result, label=close_label(state)),)


class TravelReadsHandwrittenWorldStatus(Step):
    """Known bad: a travel declaration overwrites a failing saved report."""
    def apply(self, event, state):
        results = super().apply(event, state)
        if event.kind == 'close' and state.owner == 'travel-guide':
            return tuple(replace(result, new_state=replace(result.new_state,
                copied='PASS', travel_claim_level='bookable', broad=state.independent)) for result in results)
        return results


def travel_world_failure_limits_claim(state, trace):
    if state.owner == 'travel-guide' and state.closed and trip_report_status(state) != 'PASS' and state.travel_claim_level != 'initial_plan':
        return InvariantResult.fail('a non-pass saved world report permits only initial planning')
    return InvariantResult.pass_()


class ForeignWorldReportPasses(Step):
    """Known bad: a passing report of another world passes closure."""
    def apply(self, event, state):
        results = super().apply(event, state)
        if event.kind == 'close' and provider(state) == 'worldguard' and state.report == 'world_foreign':
            return tuple(replace(result, new_state=replace(result.new_state, copied='PASS',
                broad=state.independent, named=False, travel_claim_level='bookable')) for result in results)
        return results


def world_report_belongs_to_the_contract(state, trace):
    if state.world_case in {'mesh_bound', 'contract_scope', 'mesh_foreign', 'mesh_old'} and state.world_result != WORLD_EXPECTED[state.world_case]:
        return InvariantResult.fail('a tree report must bind by mesh_id; an old report needs the native regeneration command')
    if state.closed and provider(state) == 'worldguard' and state.report == 'world_foreign' and (state.copied != 'failed' or not state.named):
        return InvariantResult.fail('a world report of another contract was counted for this world')
    return InvariantResult.pass_()


def world_report_is_current(state,trace):
    if state.world_case in {'mesh_node_stale', 'mesh_embedded_stale', 'mesh_digest_omitted'} and state.world_result != WORLD_EXPECTED[state.world_case]:
        return InvariantResult.fail('tree bytes and every file node must be covered by current raw input digests')
    if state.closed and provider(state)=='worldguard' and state.report=='world_stale' and (state.copied!='failed' or state.broad or not state.named):
        return InvariantResult.fail('stale world report licensed closure')
    return InvariantResult.pass_()


class StaleWorldReportPasses(Step):
    def apply(self,event,state):
        rows=super().apply(event,state)
        if event.kind=='close' and provider(state)=='worldguard' and state.report=='world_stale':
            return tuple(replace(row,output='passed',new_state=replace(row.new_state,copied='PASS',broad=state.independent,named=False)) for row in rows)
        return rows


def world_scope_limits_are_preserved(state, trace):
    if state.world_case in {'mesh_bound', 'contract_scope'} and not state.world_scope_preserved:
        return InvariantResult.fail('actual WorldGuard scope limits must remain visible, with owner and report path, without blocking PASS')
    return InvariantResult.pass_()


class DropsWorldScope(Step):
    def apply(self, event, state):
        rows = super().apply(event, state)
        if event.kind == 'world':
            return tuple(replace(row, new_state=replace(row.new_state, world_scope_preserved=False)) for row in rows)
        return rows


INVARIANTS = (
    Invariant('world_scope_limits_are_preserved', 'actual provider scope limits remain nonblocking, attributed risks and a summary count', world_scope_limits_are_preserved),
    Invariant('world_report_is_current','world inputs match the saved report',world_report_is_current),
    Invariant('world_report_belongs_to_the_contract', 'a world report counts only for its own world contract', world_report_belongs_to_the_contract),
    Invariant("travel_world_failure_limits_claim", "travel reads saved world status", travel_world_failure_limits_claim),
)
EVENTS = (tuple(Event('report', status) for status in REPORT_CASES) + (Event('close'),)
          + tuple(Event('world', case) for case in WORLD_EXPECTED))


def terminal(event, state, trace):
    # A tree or contract-scope probe stands alone: it runs once, from a fresh self-reviewed travel closure.
    if state.world_case:
        return True
    return event.kind == 'world' and (state.independent or state.report != 'not_run' or state.closed)


def explorer(step):
    return Explorer(workflow=Workflow((step,)),
                    initial_states=tuple(State('travel-guide', independent) for independent in (True, False)),
                    external_inputs=EVENTS, invariants=INVARIANTS, max_sequence_length=2,
                    terminal_predicate=terminal, progress_steps=0)


def build_explorer():
    return explorer(Step())


def broken_variants():
    return {'world_scope_limits_disappear': explorer(DropsWorldScope()),
            'stale_world_report_passes':explorer(StaleWorldReportPasses()),
            'travel_reads_handwritten_world_status': explorer(TravelReadsHandwrittenWorldStatus()),
            'foreign_world_report_passes': explorer(ForeignWorldReportPasses())}


class Native:
    """Replay current closure, tree probes and the trip validator; reuse immutable protocol fixtures."""
    def __init__(self):
        self.closure = NativeClosure()
        self.trip_text = None

    def _world_probe(self, case):
        from derive_closure import provider_checks
        from show_plan import _summary
        with tempfile.TemporaryDirectory(prefix='lw-world-mesh-model-') as temporary:
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
            result = 'passed' if passed and rows[0]['passed'] and rows[0]['status'] == 'PASS' else reason.split(' (', 1)[0]
            if case == 'mesh_old' and result == 'world_report_unbound:world_mesh' and 'worldguard mesh-check --mesh' in reason:
                result += '+regenerate'
            scope_rows = [row for row in risks if row['defect_id'].startswith('world:scope_limit:')]
            scopes = document.get('scope_limits', [])
            preserved = (passed and len(scope_rows) == len(scopes) and bool(scopes)
                         and all(row['owner'] == 'fiction-writing' and row['reason'] == f'WorldGuard report {path}: {scope}'
                                 for row, scope in zip(scope_rows, scopes)))
            summary = _summary({'planned_units': []}, {'audit': {'status': 'passed'}, 'review': {'status': 'passed'},
                                                     'closure': {'status': 'passed', 'residual_risk': risks}})
            return result, preserved and f'WorldGuard scope limits: {len(scopes)}' in summary

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
            base = json.loads(self.trip_path.read_text(encoding="utf-8"))
            current = json.loads((travel / 'examples/positive_cases/near_future_bookable.json').read_text(encoding="utf-8"))
            self.trip_text = plain_json(apply_mutations(base, current['mutations']))
            self.review_trip = review_plan
        self.trip = json.loads(self.trip_text)
        self.trip['world_feasibility']['checks'][0]['worldguard_report'] = str(self.root / 'unavailable-world.json')

    def apply_step(self, step):
        event, state = step.function_input, self.state
        if event.kind == 'world':
            result, preserved = self._world_probe(event.status)
            self.state = replace(state, world_case=event.status, world_result=result,
                                 world_scope_preserved=preserved if event.status in {'mesh_bound', 'contract_scope'} else False)
            return ReplayObservation(function_name=step.function_name, observed_output=result, observed_state=self.state)
        if event.kind == 'report':
            self.root, self.request, path = self.closure.save(state, event.status)
            self._trip()
            if event.status != 'world_foreign':
                # A trip plan citing another world's report is rejected when the brief is built.
                self.trip['world_feasibility']['checks'][0]['worldguard_report'] = str(path)
            state = replace(state, report=event.status, closed=False, copied='', broad=False,
                            named=False, travel_claim_level='initial_plan')
            output = 'saved'
        else:
            closure = self.closure.derive(self.request)
            row = closure['provider_checks'][0]
            state = replace(state, closed=True, copied=row['status'], broad=closure['broad_claim_allowed'],
                named=any(r['defect_id'] == f'provider:{provider(state)}' for r in closure['residual_risk']),
                travel_claim_level=self.review_trip(self.trip, plan_path=self.trip_path)['allowed_claim_level'])
            output = closure['status']
        self.state = state
        return ReplayObservation(function_name=step.function_name, observed_output=output, observed_state=state)

    def observe_state(self):
        return self.state

    def observe_output(self):
        return None

    def close(self):
        self.closure.close()


def conformance():
    result, adapter = None, Native()
    try:
        traces = build_explorer().explore().traces
        closures = [trace for trace in traces if not any(event.kind == 'world' for event in trace.external_inputs)]
        probes = [trace for trace in traces if len(trace.external_inputs) == len(trace.steps) == 1
                  and trace.steps[0].function_input.kind == 'world']
        for trace in (*select_covering_traces(closures), *probes):
            result = replay_trace(trace=trace, adapter=adapter, invariants=INVARIANTS,
                                  rules=(projected_state_matches(), projected_output_matches()))
            if not result.ok:
                return result
        facts = CodeFacts(ROOT)
        facts.check("native world report replay conforms", result.ok, result.format_text())
        return facts.report()
    finally:
        adapter.close()

USES = {
    'Reports': 'skills/logic-writing/scripts/derive_closure.py:provider_checks',
    'Close': 'skills/logic-writing/scripts/derive_closure.py:derive_closure',
    'WorldScopeSummary': 'skills/logic-writing/scripts/show_plan.py:_summary',
    'InputDigests': 'skills/logic-writing/scripts/_common.py:input_digest_problems',
    'TravelClaims': 'skills/logic-writing/routes/travel/scripts/travel_contract.py:review_plan',
    'ApplyMutations': 'skills/logic-writing/routes/travel/scripts/fixture_mutation.py:apply_mutations',
}
